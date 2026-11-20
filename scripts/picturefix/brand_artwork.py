#!/usr/bin/env python3
"""Put the *actual* PictureFix logo on AI artwork and verify its image pixels.

Only campaign illustrations, never the PictureFix restoration service, are touched.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageOps


CANONICAL_BLOB = "0cd926e6631209dd4e5c8029dfb72c29bbf89ea8"
BACKGROUND = (255, 253, 248, 255)
LOGO_LAYOUT = {
    "facebook_instagram": {"canvas": (1080, 1350), "size": (350, 84), "xy": (42, 42)},
    "pinterest": {"canvas": (1000, 1500), "size": (325, 78), "xy": (38, 55)},
}


def load_canonical_logo(path: Path) -> Image.Image:
    # Text-only GitHub connectors cannot always transfer a PNG directly into
    # a background agent's editor.  The .b64 sibling is a byte-for-byte lossless
    # transport, not a generated logo.  Both paths must match the same Git blob.
    if path.suffix == ".b64":
        raw = base64.b64decode("".join(path.read_text(encoding="ascii").split()), validate=True)
    else:
        raw = path.read_bytes()
    blob_sha = hashlib.sha1(f"blob {len(raw)}\0".encode("ascii") + raw).hexdigest()
    if blob_sha != CANONICAL_BLOB:
        raise ValueError("PictureFix brand image differs from the true approved logo")
    with Image.open(BytesIO(raw)) as img:
        if img.format != "PNG" or img.size != (445, 107):
            raise ValueError("Canonical PictureFix logo format/dimensions changed")
        return img.convert("RGBA")


def logo_for_target(original: Image.Image, target: str) -> Image.Image:
    layout = LOGO_LAYOUT[target]
    return original.resize(layout["size"], Image.Resampling.LANCZOS)


def compose(source: Path, dest: Path, target: str, *, logo: Path) -> str:
    """Generate deterministic final artwork from one already-reviewed AI scene."""
    if target not in LOGO_LAYOUT:
        raise ValueError("Unknown PictureFix image variant")
    layout = LOGO_LAYOUT[target]
    real_logo = logo_for_target(load_canonical_logo(logo), target)
    with Image.open(source) as art:
        if art.format != "PNG":
            raise ValueError("AI scene must be a PNG")
        image = ImageOps.fit(art.convert("RGBA"), layout["canvas"], Image.Resampling.LANCZOS)
    x, y = layout["xy"]
    w, h = real_logo.size
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((x - 18, y - 16, x + w + 18, y + h + 16),
                           radius=14, fill=BACKGROUND)
    image.alpha_composite(real_logo, (x, y))
    dest.parent.mkdir(parents=True, exist_ok=True)
    image.save(dest, format="PNG", optimize=True)
    verify_imprint(dest, target, logo=logo)
    return hashlib.sha256(dest.read_bytes()).hexdigest()


def verify_imprint(file: Path, target: str, *, logo: Path) -> None:
    """Exact logo pixels on stable light badge; avoids trusting a QA checkbox."""
    if target not in LOGO_LAYOUT:
        raise ValueError("Unknown PictureFix image variant")
    layout = LOGO_LAYOUT[target]
    original = logo_for_target(load_canonical_logo(logo), target)
    expected = Image.new("RGBA", original.size, BACKGROUND)
    expected.alpha_composite(original)
    with Image.open(file) as saved:
        if saved.format != "PNG" or saved.size != layout["canvas"]:
            raise ValueError("PictureFix image dimensions are wrong")
        saved.load()
        x, y = layout["xy"]
        actual = saved.convert("RGBA").crop((x, y, x + original.width, y + original.height))
        if actual.tobytes() != expected.tobytes():
            raise ValueError("Final PictureFix PNG does not contain the verified real logo imprint")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--variant", choices=tuple(LOGO_LAYOUT), required=True)
    parser.add_argument("--logo", type=Path, default=Path("media/brand/PictureFixLogo_Web.png"),
                        help="Original PNG or byte-identical text-only .b64 transport")
    args = parser.parse_args()
    print(compose(args.source, args.out, args.variant, logo=args.logo))


if __name__ == "__main__":
    main()
