#!/usr/bin/env python3
"""Deterministisches Logo-Compositing und Pruefung fuer Social-Media-Grafiken.

Gehoert zum Skill `meine-marke`. Die Regeln stehen in SKILL.md (Abschnitt Logo)
und in references/social-media/DESIGN.md; dieses Skript fuehrt sie technisch aus.
Es verwendet ausschliesslich Pillow und NumPy, keine generative KI.

    compose  Original-Logo laden, proportional skalieren, optional weissen
             Aussenrahmen aus der Logomaske erzeugen, in der diagonal gegenueber
             liegenden Ecke zur Hauptueberschrift einsetzen.
    verify   Fertige Grafik gegen die Regeln pruefen. Exit 0 = freigabefaehig,
             1 = nicht freigabefaehig, 2 = Pruefung unvollstaendig.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from PIL.PngImagePlugin import PngInfo

ORIGINAL_SIZE = (1939, 1324)
ORIGINAL_SHA256 = "15dc410d1a05b96c13466ddf3052ba9cc783cdd7252b74f4fb5c3f886510dea0"
DEFAULT_ORIGINAL = Path(r"B:\KI-lian Workspace\work\assets\brand\logo\Logo.png")

CORNERS = ("top-left", "top-right", "bottom-left", "bottom-right")
OPPOSITE = {
    "top-left": "bottom-right",
    "top-right": "bottom-left",
    "bottom-left": "top-right",
    "bottom-right": "top-left",
}

SUPERSAMPLE = 3
PNG_KEY = "logo_placement"


class LogoError(Exception):
    """Die Originaldatei oder ein Parameter verletzt die Logo-Regeln."""


@dataclass(frozen=True)
class Placement:
    """Alle Parameter, die ein Compositing eindeutig und reproduzierbar machen."""

    heading_corner: str
    logo_width: int
    logo_height: int
    margin: int
    frame: bool
    stroke: int
    gap: int
    canvas_width: int
    canvas_height: int

    @property
    def pad(self) -> int:
        return (self.gap + self.stroke) if self.frame else 0

    @property
    def layer_size(self) -> tuple[int, int]:
        return self.logo_width + 2 * self.pad, self.logo_height + 2 * self.pad

    @property
    def logo_corner(self) -> str:
        return OPPOSITE[self.heading_corner]

    def box(self) -> tuple[int, int, int, int]:
        """Aeussere Box der Logoebene einschliesslich Rahmen (x0, y0, x1, y1)."""
        lw, lh = self.layer_size
        corner = self.logo_corner
        x0 = self.margin if corner.endswith("left") else self.canvas_width - self.margin - lw
        y0 = self.margin if corner.startswith("top") else self.canvas_height - self.margin - lh
        return x0, y0, x0 + lw, y0 + lh


# --------------------------------------------------------------------------- Original


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_original(path: Path = DEFAULT_ORIGINAL, check_hash: bool = True) -> Image.Image:
    """Laedt das Original-Logo und kontrolliert Abmessungen und Pruefsumme."""
    path = Path(path)
    if not path.is_file():
        raise LogoError(f"Original-Logo nicht gefunden: {path}")
    if check_hash:
        found = sha256_file(path)
        if found != ORIGINAL_SHA256:
            raise LogoError(
                f"Pruefsumme weicht ab ({found}). Entweder ist die Datei nicht das freigegebene "
                "Original oder das Logo wurde bewusst erneuert; dann ORIGINAL_SHA256 und die "
                "Regel in meine-marke aktualisieren."
            )
    image = Image.open(path)
    if image.size != ORIGINAL_SIZE:
        raise LogoError(f"Abmessungen {image.size} statt {ORIGINAL_SIZE}.")
    return image.convert("RGBA")


# --------------------------------------------------------------------------- Geometrie


def scale_logo(logo: Image.Image, width: int) -> Image.Image:
    """Skaliert proportional auf die Breite `width`; die Hoehe folgt dem Seitenverhaeltnis."""
    if width < 1:
        raise LogoError("Logo-Breite muss positiv sein.")
    height = max(1, round(width * logo.height / logo.width))
    return logo.resize((width, height), Image.LANCZOS)


def fill_holes(mask: np.ndarray) -> np.ndarray:
    """Fuellt vom Rand aus nicht erreichbare Luecken: aeussere Silhouette der Maske."""
    height, width = mask.shape
    probe = Image.new("L", (width + 2, height + 2), 255)
    probe.paste(Image.fromarray((~mask).astype(np.uint8) * 255), (1, 1))
    ImageDraw.floodfill(probe, (0, 0), 128)
    outside = np.asarray(probe)[1:-1, 1:-1] == 128
    return ~outside


def disk_dilate(mask: np.ndarray, radius: int) -> np.ndarray:
    """Dilatation mit exakter Kreisscheibe, daher in jede Richtung gleich weit.

    Die Scheibe wird als Vereinigung horizontaler Sehnen aufgebaut. Ein
    quadratisches Strukturelement wuerde diagonal um den Faktor 1,41 dicker.
    """
    if radius <= 0:
        return mask.copy()
    height, width = mask.shape
    padded = np.zeros((height + 2 * radius, width + 2 * radius), dtype=bool)
    padded[radius:radius + height, radius:radius + width] = mask
    ph, pw = padded.shape
    cumulative = np.zeros((ph, pw + 1), dtype=np.int32)
    np.cumsum(padded, axis=1, out=cumulative[:, 1:])
    columns = np.arange(pw)
    out = np.zeros_like(padded)
    cache: dict[int, np.ndarray] = {}
    for dy in range(-radius, radius + 1):
        half = int(np.floor(np.sqrt(radius * radius - dy * dy)))
        if half not in cache:
            high = np.minimum(columns + half + 1, pw)
            low = np.maximum(columns - half, 0)
            cache[half] = (cumulative[:, high] - cumulative[:, low]) > 0
        row = cache[half]
        if dy >= 0:
            out[dy:, :] |= row[:ph - dy, :]
        else:
            out[:ph + dy, :] |= row[-dy:, :]
    return out[radius:radius + height, radius:radius + width]


def build_logo_layer(
    original: Image.Image, width: int, frame: bool, stroke: int, gap: int = 0
) -> Image.Image:
    """Logoebene (RGBA). Mit `frame` liegt ein weisser Aussenrahmen aus der Logomaske darunter."""
    logo = scale_logo(original, width)
    if not frame:
        return logo
    if stroke < 1 or gap < 0:
        raise LogoError("Rahmen braucht stroke >= 1 und gap >= 0.")
    pad = gap + stroke
    big = scale_logo(original, width * SUPERSAMPLE)
    alpha = np.asarray(big)[:, :, 3] > 0
    pad_big = pad * SUPERSAMPLE
    canvas = np.zeros((alpha.shape[0] + 2 * pad_big, alpha.shape[1] + 2 * pad_big), dtype=bool)
    canvas[pad_big:pad_big + alpha.shape[0], pad_big:pad_big + alpha.shape[1]] = alpha
    silhouette = fill_holes(canvas)
    outer = disk_dilate(silhouette, pad_big)
    inner = disk_dilate(silhouette, gap * SUPERSAMPLE)
    ring = outer & ~inner
    white = ring | (silhouette & ~canvas)
    target = (logo.width + 2 * pad, logo.height + 2 * pad)
    white_small = Image.fromarray(white.astype(np.uint8) * 255).resize(target, Image.LANCZOS)
    layer = Image.new("RGBA", target, (255, 255, 255, 0))
    layer.putalpha(white_small)
    layer.alpha_composite(logo, (pad, pad))
    return layer


# --------------------------------------------------------------------------- Compositing


def luminance(image: Image.Image) -> float:
    grey = np.asarray(image.convert("RGB").convert("L"), dtype=float)
    return float(grey.mean())


def make_placement(
    canvas: tuple[int, int],
    heading_corner: str,
    logo_width_ratio: float = 0.16,
    margin_ratio: float = 0.05,
    frame: bool = True,
    stroke_ratio: float = 0.03,
    gap: int = 0,
) -> Placement:
    if heading_corner not in CORNERS:
        raise LogoError(f"Unbekannte Ecke {heading_corner!r}; erlaubt: {', '.join(CORNERS)}")
    canvas_w, canvas_h = canvas
    logo_w = round(canvas_w * logo_width_ratio)
    logo_h = max(1, round(logo_w * ORIGINAL_SIZE[1] / ORIGINAL_SIZE[0]))
    return Placement(
        heading_corner=heading_corner,
        logo_width=logo_w,
        logo_height=logo_h,
        margin=round(min(canvas_w, canvas_h) * margin_ratio),
        frame=frame,
        stroke=max(1, round(logo_w * stroke_ratio)) if frame else 0,
        gap=gap if frame else 0,
        canvas_width=canvas_w,
        canvas_height=canvas_h,
    )


def composite(base: Image.Image, layer: Image.Image, placement: Placement) -> Image.Image:
    """Setzt die Logoebene deterministisch ein. Pixel ausserhalb der Box bleiben unveraendert."""
    if base.size != (placement.canvas_width, placement.canvas_height):
        raise LogoError("Basisbild passt nicht zur Placement-Groesse.")
    if layer.size != placement.layer_size:
        raise LogoError("Logoebene passt nicht zur Placement-Groesse.")
    x0, y0, _, _ = placement.box()
    result = base.convert("RGBA")
    result.alpha_composite(layer, (x0, y0))
    return result


def compose_file(
    base_path: Path,
    out_path: Path,
    heading_corner: str,
    original_path: Path = DEFAULT_ORIGINAL,
    logo_width_ratio: float = 0.16,
    margin_ratio: float = 0.05,
    frame: str = "auto",
    stroke_ratio: float = 0.03,
    gap: int = 0,
) -> Placement:
    original = load_original(original_path)
    base = Image.open(base_path).convert("RGBA")
    placement = make_placement(base.size, heading_corner, logo_width_ratio, margin_ratio, True, stroke_ratio, gap)
    if frame == "auto":
        x0, y0, x1, y1 = placement.box()
        use_frame = luminance(base.crop((x0, y0, x1, y1))) < 128
        placement = make_placement(base.size, heading_corner, logo_width_ratio, margin_ratio, use_frame, stroke_ratio, gap)
    elif frame == "off":
        placement = make_placement(base.size, heading_corner, logo_width_ratio, margin_ratio, False, stroke_ratio, gap)
    elif frame != "on":
        raise LogoError("frame muss auto, on oder off sein.")
    layer = build_logo_layer(original, placement.logo_width, placement.frame, placement.stroke, placement.gap)
    result = composite(base, layer, placement)
    info = PngInfo()
    info.add_text(PNG_KEY, json.dumps(asdict(placement)))
    result.save(out_path, "PNG", pnginfo=info)
    return placement


# --------------------------------------------------------------------------- Pruefung


@dataclass
class Check:
    name: str
    status: str  # ok | fail | skipped
    detail: str


def _diff(a: Image.Image, b: Image.Image) -> np.ndarray:
    return np.abs(np.asarray(a.convert("RGBA"), dtype=np.int16) - np.asarray(b.convert("RGBA"), dtype=np.int16))


def verify(
    final: Image.Image,
    base: Image.Image,
    placement: Placement,
    original: Image.Image,
    heading_box: tuple[int, int, int, int] | None = None,
    tolerance: int = 3,
    min_margin_ratio: float = 0.03,
) -> list[Check]:
    """Prueft eine fertige Grafik. Die Regeln entsprechen references/social-media/DESIGN.md."""
    checks: list[Check] = []

    def add(name: str, ok: bool, detail: str) -> None:
        checks.append(Check(name, "ok" if ok else "fail", detail))

    # 1. Originalvorlage
    add("Originalvorlage", original.size == ORIGINAL_SIZE, f"Abmessungen {original.size}, erwartet {ORIGINAL_SIZE}")

    # 2. Seitenverhaeltnis
    expected_h = round(placement.logo_width * ORIGINAL_SIZE[1] / ORIGINAL_SIZE[0])
    add(
        "Seitenverhaeltnis",
        abs(placement.logo_height - expected_h) <= 1,
        f"Logo {placement.logo_width}x{placement.logo_height}, proportional waeren {placement.logo_width}x{expected_h}",
    )

    # 3. Bildgroesse
    add("Bildgroesse", final.size == base.size == (placement.canvas_width, placement.canvas_height),
        f"Endbild {final.size}, Basisbild {base.size}")
    if final.size != base.size:
        return checks

    # 4. Logobereich == deterministisch erzeugte Ebene (innere Formen, Farben, Rahmen)
    layer = build_logo_layer(original, placement.logo_width, placement.frame, placement.stroke, placement.gap)
    if layer.size != placement.layer_size:
        add("Logo unveraendert (Innenformen, Farben, Rahmen)", False,
            f"Ebene {layer.size} passt nicht zu den angegebenen Massen {placement.layer_size}")
        return checks
    expected = composite(base, layer, placement)
    x0, y0, x1, y1 = placement.box()
    inside = _diff(final.crop((x0, y0, x1, y1)), expected.crop((x0, y0, x1, y1)))
    worst = int(inside.max()) if inside.size else 0
    add("Logo unveraendert (Innenformen, Farben, Rahmen)", worst <= tolerance,
        f"groesste Pixelabweichung {worst} (erlaubt {tolerance})")

    # 5. Rahmen
    if placement.frame:
        add("Weisser Aussenrahmen gleichmaessig", placement.stroke >= 1 and worst <= tolerance,
            f"Strichstaerke {placement.stroke} px, Abstand {placement.gap} px, aus der Logomaske erzeugt")
    else:
        checks.append(Check("Weisser Aussenrahmen gleichmaessig", "skipped", "kein Rahmen vorgesehen"))

    # 6. Andere Bildinhalte unveraendert
    outside = _diff(final, base)
    outside[y0:y1, x0:x1, :] = 0
    changed = int((outside.max(axis=2) > tolerance).sum())
    add("Uebrige Bildinhalte unveraendert", changed == 0, f"{changed} veraenderte Pixel ausserhalb der Logobox")

    # 7. Vollstaendig sichtbar und Sicherheitsabstand
    in_bounds = x0 >= 0 and y0 >= 0 and x1 <= placement.canvas_width and y1 <= placement.canvas_height
    add("Logo vollstaendig sichtbar", in_bounds, f"Box {placement.box()} in {placement.canvas_width}x{placement.canvas_height}")
    min_margin = round(min(placement.canvas_width, placement.canvas_height) * min_margin_ratio)
    margins = (x0, y0, placement.canvas_width - x1, placement.canvas_height - y1)
    add("Sicherheitsabstand zum Bildrand", min(margins) >= min_margin,
        f"Abstaende links/oben/rechts/unten {margins}, Minimum {min_margin} px")

    # 8. Diagonale Ecke
    corner = placement.logo_corner
    near_x = x0 if corner.endswith("left") else placement.canvas_width - x1
    near_y = y0 if corner.startswith("top") else placement.canvas_height - y1
    far_x = placement.canvas_width - x1 if corner.endswith("left") else x0
    far_y = placement.canvas_height - y1 if corner.startswith("top") else y0
    in_corner = near_x == near_y == placement.margin and near_x < far_x and near_y < far_y
    # Tatsaechliche Lage im fertigen Bild: Begrenzung aller gegenueber dem Basisbild geaenderten Pixel.
    changed_mask = _diff(final, base).max(axis=2) > 0
    if changed_mask.any():
        rows = np.flatnonzero(changed_mask.any(axis=1))
        cols = np.flatnonzero(changed_mask.any(axis=0))
        center_x = (cols[0] + cols[-1]) / 2
        center_y = (rows[0] + rows[-1]) / 2
        actual = (f"{'top' if center_y < placement.canvas_height / 2 else 'bottom'}-"
                  f"{'left' if center_x < placement.canvas_width / 2 else 'right'}")
    else:
        actual = "nicht gefunden"
    add("Logo diagonal gegenueber der Hauptueberschrift",
        in_corner and corner == OPPOSITE[placement.heading_corner] and actual == corner,
        f"Ueberschrift {placement.heading_corner}, erwartet Logo {corner}, gemessen im Bild {actual}, "
        f"Randabstand {near_x}/{near_y} px")

    # 9. Ueberschrift
    if heading_box is None:
        checks.append(Check("Ueberschrift sichtbar, ohne Ueberlagerung, in der Ueberschriftsecke", "skipped",
                            "heading_box fehlt: Pruefung unvollstaendig"))
    else:
        hx0, hy0, hx1, hy1 = heading_box
        visible = hx0 >= 0 and hy0 >= 0 and hx1 <= placement.canvas_width and hy1 <= placement.canvas_height
        overlap = not (hx1 <= x0 or hx0 >= x1 or hy1 <= y0 or hy0 >= y1)
        center_x, center_y = (hx0 + hx1) / 2, (hy0 + hy1) / 2
        left = center_x < placement.canvas_width / 2
        top = center_y < placement.canvas_height / 2
        in_quadrant = placement.heading_corner == f"{'top' if top else 'bottom'}-{'left' if left else 'right'}"
        add("Ueberschrift sichtbar, ohne Ueberlagerung, in der Ueberschriftsecke",
            visible and not overlap and in_quadrant,
            f"sichtbar={visible}, Ueberlagerung={overlap}, Ueberschrift im Quadranten {placement.heading_corner}={in_quadrant}")
    return checks


def verify_files(
    final_path: Path,
    base_path: Path,
    original_path: Path = DEFAULT_ORIGINAL,
    heading_corner: str | None = None,
    heading_box: tuple[int, int, int, int] | None = None,
) -> tuple[int, list[Check]]:
    original = load_original(original_path)
    final = Image.open(final_path)
    raw = final.text.get(PNG_KEY) if hasattr(final, "text") else None
    if raw is None:
        raise LogoError(f"Keine Placement-Angaben im PNG ({PNG_KEY}); Grafik wurde nicht mit compose erzeugt.")
    placement = Placement(**json.loads(raw))
    if heading_corner and heading_corner != placement.heading_corner:
        placement = Placement(**{**asdict(placement), "heading_corner": heading_corner})
    checks = verify(final, Image.open(base_path), placement, original, heading_box)
    if any(c.status == "fail" for c in checks):
        return 1, checks
    if any(c.status == "skipped" and "unvollst" in c.detail for c in checks):
        return 2, checks
    return 0, checks


# --------------------------------------------------------------------------- CLI


def _box(text: str) -> tuple[int, int, int, int]:
    parts = [int(p) for p in text.split(",")]
    if len(parts) != 4:
        raise argparse.ArgumentTypeError("x0,y0,x1,y1 erwartet")
    return parts[0], parts[1], parts[2], parts[3]


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    comp = sub.add_parser("compose", help="Logo in die diagonal gegenueberliegende Ecke einsetzen")
    comp.add_argument("base", type=Path, help="Bild aus der KI-Bildgenerierung (ohne Logo)")
    comp.add_argument("out", type=Path, help="fertiges PNG")
    comp.add_argument("--heading-corner", required=True, choices=CORNERS)
    comp.add_argument("--original", type=Path, default=DEFAULT_ORIGINAL)
    comp.add_argument("--logo-width-ratio", type=float, default=0.16)
    comp.add_argument("--margin-ratio", type=float, default=0.05)
    comp.add_argument("--frame", choices=("auto", "on", "off"), default="auto")
    comp.add_argument("--stroke-ratio", type=float, default=0.03)
    comp.add_argument("--gap", type=int, default=0)

    ver = sub.add_parser("verify", help="fertige Grafik pruefen")
    ver.add_argument("final", type=Path)
    ver.add_argument("base", type=Path, help="dasselbe Basisbild, das compose bekam")
    ver.add_argument("--original", type=Path, default=DEFAULT_ORIGINAL)
    ver.add_argument("--heading-corner", choices=CORNERS)
    ver.add_argument("--heading-box", type=_box, help="x0,y0,x1,y1 der Hauptueberschrift in Pixeln")

    args = parser.parse_args(argv)
    try:
        if args.command == "compose":
            placement = compose_file(args.base, args.out, args.heading_corner, args.original,
                                     args.logo_width_ratio, args.margin_ratio, args.frame,
                                     args.stroke_ratio, args.gap)
            print(json.dumps(asdict(placement), indent=2))
            return 0
        code, checks = verify_files(args.final, args.base, args.original, args.heading_corner, args.heading_box)
    except LogoError as error:
        print(f"FEHLER: {error}")
        return 1
    for check in checks:
        print(f"[{check.status.upper():7}] {check.name}: {check.detail}")
    print({0: "ERGEBNIS: freigabefaehig", 1: "ERGEBNIS: NICHT freigabefaehig, nicht an Buffer uebergeben",
           2: "ERGEBNIS: Pruefung unvollstaendig, nicht freigabefaehig"}[code])
    return code


if __name__ == "__main__":
    raise SystemExit(main())
