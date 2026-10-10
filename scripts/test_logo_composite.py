"""Tests fuer logo_composite: Seitenverhaeltnis, Position und gleichmaessiger Rahmen.

Aufruf:  python -m unittest discover -s skills/josefs-marke/scripts -p "test_logo_composite.py"

Die meisten Tests nutzen ein synthetisches Logo und laufen ueberall. Tests mit dem
echten Original werden uebersprungen, wenn die Datei nicht erreichbar ist.
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))
import logo_composite as lc  # noqa: E402


def synthetic_logo() -> Image.Image:
    """Dunkelblaue Schraegform mit weisser Innenflaeche und einem eingeschlossenen Loch."""
    image = Image.new("RGBA", lc.ORIGINAL_SIZE, (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.polygon([(500, 0), (1939, 0), (1939, 900), (1439, 1324), (0, 1324), (350, 250)], fill=(38, 64, 108, 255))
    draw.polygon([(700, 150), (1500, 150), (1500, 500), (700, 500)], fill=(254, 254, 254, 255))
    draw.polygon([(900, 800), (1000, 800), (1000, 900), (900, 900)], fill=(0, 0, 0, 0))  # Loch
    return image


def gradient_base(width: int = 1080, height: int = 1350) -> Image.Image:
    """Dunkles Basisbild mit Verlauf, damit veraenderte Pixel auffallen."""
    x = np.linspace(7, 40, width, dtype=np.uint8)[None, :]
    y = np.linspace(17, 60, height, dtype=np.uint8)[:, None]
    array = np.zeros((height, width, 3), dtype=np.uint8)
    array[:, :, 0] = x
    array[:, :, 1] = y
    array[:, :, 2] = 31
    return Image.fromarray(array, "RGB")


class GeometryTests(unittest.TestCase):
    def test_opposite_table_matches_rule(self):
        self.assertEqual(lc.OPPOSITE, {
            "top-left": "bottom-right", "top-right": "bottom-left",
            "bottom-left": "top-right", "bottom-right": "top-left"})

    def test_scale_keeps_aspect_ratio(self):
        logo = synthetic_logo()
        target = lc.ORIGINAL_SIZE[0] / lc.ORIGINAL_SIZE[1]
        for width in (57, 100, 173, 311, 640, 1939):
            scaled = lc.scale_logo(logo, width)
            self.assertLessEqual(abs(scaled.width / scaled.height - target) * scaled.height, 1.0, width)

    def test_disk_dilate_is_isotropic(self):
        mask = np.zeros((101, 101), dtype=bool)
        mask[50, 50] = True
        radius = 20
        grown = lc.disk_dilate(mask, radius)
        yy, xx = np.mgrid[0:101, 0:101]
        brute_force = (yy - 50) ** 2 + (xx - 50) ** 2 <= radius ** 2
        self.assertTrue(np.array_equal(grown, brute_force), "Dilatation ist keine exakte Kreisscheibe")

    def test_frame_thickness_uniform_around_slanted_shape(self):
        """Jeder Rahmenpixel liegt zwischen gap und gap+stroke vom Logo; kein Pixel in dieser Zone fehlt."""
        stroke, gap = 6, 2
        canvas = np.zeros((90, 130), dtype=bool)
        image = Image.new("L", (130, 90), 0)
        ImageDraw.Draw(image).polygon([(30, 20), (100, 20), (80, 70), (14, 70)], fill=255)
        canvas[:] = np.asarray(image) > 0
        silhouette = lc.fill_holes(canvas)
        ring = lc.disk_dilate(silhouette, gap + stroke) & ~lc.disk_dilate(silhouette, gap)
        ring_points = np.argwhere(ring)
        zone = lc.disk_dilate(silhouette, gap + stroke) & ~silhouette
        zone_points = np.argwhere(zone)
        sil_points = np.argwhere(silhouette)

        def nearest(points: np.ndarray) -> np.ndarray:
            deltas = points[:, None, :] - sil_points[None, :, :]
            return np.sqrt((deltas ** 2).sum(axis=2)).min(axis=1)

        ring_distance = nearest(ring_points)
        self.assertGreaterEqual(ring_distance.min(), gap)
        self.assertLessEqual(ring_distance.max(), gap + stroke + 1e-9)
        zone_distance = nearest(zone_points)
        expected_ring = int((zone_distance > gap).sum())
        self.assertEqual(len(ring_points), expected_ring, "Rahmen hat Luecken oder Ausbuchtungen")

    def test_fill_holes_closes_enclosed_gap_only(self):
        mask = np.zeros((20, 20), dtype=bool)
        mask[2:18, 2:18] = True
        mask[8:12, 8:12] = False
        filled = lc.fill_holes(mask)
        self.assertTrue(filled[9, 9])
        self.assertFalse(filled[0, 0])


class LayerTests(unittest.TestCase):
    def test_layer_keeps_logo_pixels_and_adds_white_frame(self):
        original = synthetic_logo()
        layer = lc.build_logo_layer(original, 300, frame=True, stroke=6, gap=0)
        logo = lc.scale_logo(original, 300)
        self.assertEqual(layer.size, (312, logo.height + 12))
        inner = layer.crop((6, 6, 6 + logo.width, 6 + logo.height))
        mask = np.asarray(logo)[:, :, 3] == 255
        self.assertTrue(np.array_equal(np.asarray(inner)[mask], np.asarray(logo)[mask]))
        self.assertEqual(tuple(layer.getpixel((0, layer.height // 2))), (255, 255, 255, 0))
        corner_alpha = np.asarray(layer)[:, :, 3]
        self.assertEqual(int(corner_alpha[layer.height // 2, 2]), 0)

    def test_enclosed_hole_becomes_opaque_white(self):
        original = synthetic_logo()
        layer = lc.build_logo_layer(original, 600, frame=True, stroke=8, gap=0)
        scale = 600 / lc.ORIGINAL_SIZE[0]
        px, py = int(950 * scale) + 8, int(850 * scale) + 8
        self.assertEqual(tuple(layer.getpixel((px, py))), (255, 255, 255, 255))

    def test_no_frame_returns_scaled_logo(self):
        original = synthetic_logo()
        layer = lc.build_logo_layer(original, 250, frame=False, stroke=0)
        self.assertEqual(list(layer.getdata()), list(lc.scale_logo(original, 250).getdata()))


class PlacementTests(unittest.TestCase):
    def test_logo_sits_in_corner_opposite_to_heading(self):
        for heading in lc.CORNERS:
            placement = lc.make_placement((1080, 1350), heading)
            x0, y0, x1, y1 = placement.box()
            corner = lc.OPPOSITE[heading]
            if corner.endswith("left"):
                self.assertEqual(x0, placement.margin, heading)
            else:
                self.assertEqual(1080 - x1, placement.margin, heading)
            if corner.startswith("top"):
                self.assertEqual(y0, placement.margin, heading)
            else:
                self.assertEqual(1350 - y1, placement.margin, heading)

    def test_current_motif_heading_top_left_gives_logo_bottom_right(self):
        placement = lc.make_placement((1080, 1350), "top-left")
        self.assertEqual(placement.logo_corner, "bottom-right")
        x0, y0, x1, y1 = placement.box()
        self.assertGreater(x0, 540)
        self.assertGreater(y0, 675)

    def test_frame_box_includes_frame_inside_margin(self):
        placement = lc.make_placement((1080, 1350), "top-left", frame=True)
        x0, y0, x1, y1 = placement.box()
        self.assertEqual(1080 - x1, placement.margin)
        self.assertEqual(1350 - y1, placement.margin)
        self.assertEqual((x1 - x0, y1 - y0), placement.layer_size)


class VerifyTests(unittest.TestCase):
    def setUp(self):
        self.original = synthetic_logo()
        self.base = gradient_base()

    def build(self, heading="top-left", frame=True):
        placement = lc.make_placement(self.base.size, heading, frame=frame)
        layer = lc.build_logo_layer(self.original, placement.logo_width, placement.frame, placement.stroke, placement.gap)
        return placement, lc.composite(self.base, layer, placement)

    def statuses(self, final, placement, heading_box=(54, 54, 700, 400)):
        return {c.name: c.status for c in lc.verify(final, self.base, placement, self.original, heading_box)}

    def test_correct_composite_passes_every_check(self):
        placement, final = self.build()
        statuses = self.statuses(final, placement)
        self.assertNotIn("fail", statuses.values(), statuses)
        self.assertNotIn("skipped", {v for k, v in statuses.items() if "Rahmen" not in k}, statuses)

    def test_no_frame_variant_passes(self):
        placement, final = self.build(frame=False)
        statuses = self.statuses(final, placement)
        self.assertNotIn("fail", statuses.values(), statuses)

    def test_stretched_logo_fails(self):
        placement, _ = self.build()
        layer = lc.build_logo_layer(self.original, placement.logo_width, placement.frame, placement.stroke, placement.gap)
        squeezed = layer.resize((layer.width, round(layer.height * 0.8)), Image.LANCZOS)
        final = self.base.convert("RGBA")
        x0, y0, _, _ = placement.box()
        final.alpha_composite(squeezed, (x0, y0))
        self.assertEqual(self.statuses(final, placement)["Logo unveraendert (Innenformen, Farben, Rahmen)"], "fail")

    def test_declared_nonproportional_size_fails(self):
        placement, final = self.build()
        bad = lc.Placement(**{**placement.__dict__, "logo_height": placement.logo_height + 20})
        self.assertEqual(self.statuses(final, bad)["Seitenverhaeltnis"], "fail")

    def test_logo_in_wrong_corner_fails(self):
        placement, final = self.build("top-left")
        wrong = lc.Placement(**{**placement.__dict__, "heading_corner": "bottom-right"})
        self.assertEqual(self.statuses(final, wrong)["Logo diagonal gegenueber der Hauptueberschrift"], "fail")

    def test_altered_background_fails(self):
        placement, final = self.build()
        final.putpixel((10, 10), (255, 0, 0, 255))
        self.assertEqual(self.statuses(final, placement)["Uebrige Bildinhalte unveraendert"], "fail")

    def test_recolored_inner_shape_fails(self):
        placement, final = self.build()
        x0, y0, x1, y1 = placement.box()
        ImageDraw.Draw(final).rectangle([x0 + 40, y0 + 40, x0 + 80, y0 + 60], fill=(200, 0, 0, 255))
        self.assertEqual(self.statuses(final, placement)["Logo unveraendert (Innenformen, Farben, Rahmen)"], "fail")

    def test_cropped_logo_fails(self):
        placement, final = self.build()
        x0, y0, x1, y1 = placement.box()
        ImageDraw.Draw(final).rectangle([x0, y0, x1, y0 + 30], fill=(7, 17, 31, 255))
        self.assertEqual(self.statuses(final, placement)["Logo unveraendert (Innenformen, Farben, Rahmen)"], "fail")

    def test_heading_overlapping_logo_fails(self):
        placement, final = self.build()
        x0, y0, x1, y1 = placement.box()
        name = "Ueberschrift sichtbar, ohne Ueberlagerung, in der Ueberschriftsecke"
        self.assertEqual(self.statuses(final, placement, (x0 - 50, y0 - 50, x1, y1))[name], "fail")

    def test_heading_in_wrong_quadrant_fails(self):
        placement, final = self.build("top-left")
        name = "Ueberschrift sichtbar, ohne Ueberlagerung, in der Ueberschriftsecke"
        self.assertEqual(self.statuses(final, placement, (700, 60, 1000, 300))[name], "fail")

    def test_missing_heading_box_is_incomplete(self):
        placement, final = self.build()
        name = "Ueberschrift sichtbar, ohne Ueberlagerung, in der Ueberschriftsecke"
        self.assertEqual(self.statuses(final, placement, None)[name], "skipped")

    def test_margin_too_small_fails(self):
        base = self.base
        placement = lc.make_placement(base.size, "top-left", margin_ratio=0.005)
        layer = lc.build_logo_layer(self.original, placement.logo_width, placement.frame, placement.stroke, placement.gap)
        final = lc.composite(base, layer, placement)
        self.assertEqual(self.statuses(final, placement)["Sicherheitsabstand zum Bildrand"], "fail")


class FileRoundTripTests(unittest.TestCase):
    def test_compose_and_verify_files_with_synthetic_original(self):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            gradient_base().save(folder / "base.png")
            synthetic_logo().save(folder / "logo.png")
            original = folder / "logo.png"
            original_loader = lc.load_original
            lc.load_original = lambda path=original, check_hash=True: original_loader(path, check_hash=False)
            try:
                placement = lc.compose_file(folder / "base.png", folder / "out.png", "top-left", original, frame="on")
                code, checks = lc.verify_files(folder / "out.png", folder / "base.png", original, heading_box=(54, 54, 700, 400))
            finally:
                lc.load_original = original_loader
            self.assertEqual(placement.logo_corner, "bottom-right")
            self.assertEqual(code, 0, [c for c in checks if c.status != "ok"])
            with self.assertRaises(lc.LogoError):
                lc.load_original(original)  # synthetisches Logo hat falsche Pruefsumme

    def test_auto_frame_only_on_dark_background(self):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            original = folder / "logo.png"
            synthetic_logo().save(original)
            original_loader = lc.load_original
            lc.load_original = lambda path=original, check_hash=True: original_loader(path, check_hash=False)
            try:
                Image.new("RGB", (800, 1000), (7, 17, 31)).save(folder / "dark.png")
                Image.new("RGB", (800, 1000), (247, 244, 238)).save(folder / "light.png")
                dark = lc.compose_file(folder / "dark.png", folder / "d.png", "top-left", original)
                light = lc.compose_file(folder / "light.png", folder / "l.png", "top-left", original)
            finally:
                lc.load_original = original_loader
            self.assertTrue(dark.frame)
            self.assertFalse(light.frame)


class LogoOnlyTests(unittest.TestCase):
    """Bildposts ohne jede Beschriftung: Logo in fester Ecke, keine Platzhalter-Ueberschrift."""

    HEADING_CHECK = "Ueberschrift sichtbar, ohne Ueberlagerung, in der Ueberschriftsecke"
    CORNER_CHECK = "Logo in der festgelegten Ecke (Logo-only)"

    def setUp(self):
        self.original = synthetic_logo()
        self.base = gradient_base()

    def build(self, corner="bottom-right", frame=True):
        placement = lc.make_placement(self.base.size, None, frame=frame, logo_corner=corner)
        layer = lc.build_logo_layer(self.original, placement.logo_width, placement.frame, placement.stroke, placement.gap)
        return placement, lc.composite(self.base, layer, placement)

    def checks(self, final, placement, heading_box=None):
        return {c.name: c for c in lc.verify(final, self.base, placement, self.original, heading_box)}

    def test_placement_has_no_heading_and_uses_chosen_corner(self):
        for corner in lc.CORNERS:
            placement = lc.make_placement((1080, 1350), None, logo_corner=corner)
            self.assertTrue(placement.logo_only)
            self.assertIsNone(placement.heading_corner)
            self.assertEqual(placement.logo_corner, corner)
            x0, y0, x1, y1 = placement.box()
            self.assertEqual(x0 if corner.endswith("left") else 1080 - x1, placement.margin)
            self.assertEqual(y0 if corner.startswith("top") else 1350 - y1, placement.margin)

    def test_exactly_one_corner_argument_is_required(self):
        with self.assertRaises(lc.LogoError):
            lc.make_placement((1080, 1350), None)
        with self.assertRaises(lc.LogoError):
            lc.make_placement((1080, 1350), "top-left", logo_corner="bottom-right")
        with self.assertRaises(lc.LogoError):
            lc.make_placement((1080, 1350), None, logo_corner="middle")

    def test_standard_placement_is_not_logo_only(self):
        placement = lc.make_placement((1080, 1350), "top-left")
        self.assertFalse(placement.logo_only)
        self.assertIsNone(placement.logo_only_corner)
        self.assertEqual(placement.logo_corner, "bottom-right")

    def test_correct_logo_only_composite_has_no_failures_and_no_heading_check(self):
        placement, final = self.build()
        checks = self.checks(final, placement)
        self.assertEqual([n for n, c in checks.items() if c.status == "fail"], [])
        self.assertEqual([n for n, c in checks.items() if c.status == "skipped"], [])
        self.assertNotIn(self.HEADING_CHECK, checks)
        self.assertEqual(checks[self.CORNER_CHECK].status, "ok")
        self.assertEqual(checks["Basisbild ohne Schrift und ohne Fremdlogo"].status, "manual")

    def test_all_logo_checks_still_run(self):
        placement, final = self.build()
        checks = self.checks(final, placement)
        for name in ("Originalvorlage", "Seitenverhaeltnis", "Bildgroesse",
                     "Logo unveraendert (Innenformen, Farben, Rahmen)", "Uebrige Bildinhalte unveraendert",
                     "Logo vollstaendig sichtbar", "Sicherheitsabstand zum Bildrand"):
            self.assertEqual(checks[name].status, "ok", name)

    def test_no_frame_variant_passes(self):
        placement, final = self.build(frame=False)
        checks = self.checks(final, placement)
        self.assertEqual([n for n, c in checks.items() if c.status == "fail"], [])

    def test_logo_in_other_corner_than_declared_fails(self):
        placement, final = self.build("bottom-right")
        wrong = lc.Placement(**{**placement.__dict__, "logo_only_corner": "top-left"})
        self.assertEqual(self.checks(final, wrong)[self.CORNER_CHECK].status, "fail")

    def test_heading_box_is_rejected_in_logo_only(self):
        placement, final = self.build()
        checks = self.checks(final, placement, heading_box=(54, 54, 700, 400))
        self.assertEqual(checks["Logo-only: keine Ueberschrift angegeben"].status, "fail")

    def test_stretched_logo_fails(self):
        placement, _ = self.build()
        layer = lc.build_logo_layer(self.original, placement.logo_width, placement.frame, placement.stroke, placement.gap)
        squeezed = layer.resize((layer.width, round(layer.height * 0.8)), Image.LANCZOS)
        final = self.base.convert("RGBA")
        x0, y0, _, _ = placement.box()
        final.alpha_composite(squeezed, (x0, y0))
        self.assertEqual(self.checks(final, placement)["Logo unveraendert (Innenformen, Farben, Rahmen)"].status, "fail")

    def test_text_or_other_change_outside_logo_fails(self):
        placement, final = self.build()
        ImageDraw.Draw(final).rectangle([100, 100, 400, 160], fill=(245, 247, 250, 255))  # nachtraeglich eingefuegte Zeile
        self.assertEqual(self.checks(final, placement)["Uebrige Bildinhalte unveraendert"].status, "fail")

    def test_margin_too_small_fails(self):
        placement = lc.make_placement(self.base.size, None, margin_ratio=0.005, logo_corner="bottom-right")
        layer = lc.build_logo_layer(self.original, placement.logo_width, placement.frame, placement.stroke, placement.gap)
        final = lc.composite(self.base, layer, placement)
        self.assertEqual(self.checks(final, placement)["Sicherheitsabstand zum Bildrand"].status, "fail")

    def test_old_png_metadata_without_logo_only_fields_still_loads(self):
        import json
        from dataclasses import asdict
        legacy = asdict(lc.make_placement((1080, 1350), "top-left"))
        legacy.pop("logo_only")
        legacy.pop("logo_only_corner")
        placement = lc.Placement(**json.loads(json.dumps(legacy)))
        self.assertFalse(placement.logo_only)
        self.assertEqual(placement.logo_corner, "bottom-right")

    def test_missing_heading_box_in_standard_mode_stays_incomplete(self):
        placement = lc.make_placement(self.base.size, "top-left")
        layer = lc.build_logo_layer(self.original, placement.logo_width, placement.frame, placement.stroke, placement.gap)
        final = lc.composite(self.base, layer, placement)
        checks = self.checks(final, placement)
        self.assertEqual(checks[self.HEADING_CHECK].status, "skipped")
        self.assertNotIn("Basisbild ohne Schrift und ohne Fremdlogo", checks)

    def test_file_round_trip_exit_codes(self):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            gradient_base().save(folder / "base.png")
            synthetic_logo().save(folder / "logo.png")
            original = folder / "logo.png"
            original_loader = lc.load_original
            lc.load_original = lambda path=original, check_hash=True: original_loader(path, check_hash=False)
            try:
                placement = lc.compose_file(folder / "base.png", folder / "out.png", None, original,
                                            frame="on", logo_corner="bottom-right")
                code, checks = lc.verify_files(folder / "out.png", folder / "base.png", original)
                self.assertEqual(code, 0, [c for c in checks if c.status not in ("ok", "manual")])
                code_box, _ = lc.verify_files(folder / "out.png", folder / "base.png", original,
                                              heading_box=(54, 54, 700, 400))
                with self.assertRaises(lc.LogoError):
                    lc.verify_files(folder / "out.png", folder / "base.png", original, heading_corner="top-left")
            finally:
                lc.load_original = original_loader
            self.assertTrue(placement.logo_only)
            self.assertEqual(placement.logo_corner, "bottom-right")
            self.assertEqual(code_box, 1)

    def test_cli_requires_exactly_one_corner_option(self):
        for argv in (["compose", "a.png", "b.png"],
                     ["compose", "a.png", "b.png", "--heading-corner", "top-left", "--logo-corner", "bottom-right"]):
            with self.assertRaises(SystemExit):
                lc.main(argv)


@unittest.skipUnless(lc.DEFAULT_ORIGINAL.is_file(), "Original-Logo nicht erreichbar")
class RealOriginalTests(unittest.TestCase):
    def test_original_matches_pinned_size_and_hash(self):
        image = lc.load_original(lc.DEFAULT_ORIGINAL)
        self.assertEqual(image.size, (1939, 1324))

    def test_real_logo_frame_keeps_inner_whites_opaque_and_aspect(self):
        original = lc.load_original(lc.DEFAULT_ORIGINAL)
        layer = lc.build_logo_layer(original, 400, frame=True, stroke=8, gap=0)
        logo = lc.scale_logo(original, 400)
        self.assertLessEqual(abs(logo.width / logo.height - 1939 / 1324) * logo.height, 1.0)
        scale = 400 / 1939
        for x, y in ((200, 1000), (1000, 150), (800, 1000)):  # weisse Innenflaechen des Originals
            self.assertEqual(layer.getpixel((int(x * scale) + 8, int(y * scale) + 8))[3], 255)

    def test_real_logo_only_end_to_end_passes_and_tampering_fails(self):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            gradient_base().save(folder / "base.png")
            placement = lc.compose_file(folder / "base.png", folder / "out.png", None, frame="on",
                                        logo_corner="bottom-right")
            self.assertTrue(placement.logo_only)
            code, checks = lc.verify_files(folder / "out.png", folder / "base.png")
            self.assertEqual(code, 0, [c for c in checks if c.status not in ("ok", "manual")])
            tampered = Image.open(folder / "out.png")
            info = tampered.text
            tampered = tampered.convert("RGBA")
            tampered.putpixel((5, 5), (255, 0, 0, 255))
            from PIL.PngImagePlugin import PngInfo
            meta = PngInfo()
            meta.add_text(lc.PNG_KEY, info[lc.PNG_KEY])
            tampered.save(folder / "bad.png", pnginfo=meta)
            code, _ = lc.verify_files(folder / "bad.png", folder / "base.png")
            self.assertEqual(code, 1)

    def test_real_logo_end_to_end_passes_and_tampering_fails(self):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            gradient_base().save(folder / "base.png")
            lc.compose_file(folder / "base.png", folder / "out.png", "top-left", frame="on")
            code, checks = lc.verify_files(folder / "out.png", folder / "base.png", heading_box=(54, 54, 700, 400))
            self.assertEqual(code, 0, [c for c in checks if c.status != "ok"])
            tampered = Image.open(folder / "out.png")
            info = tampered.text
            tampered = tampered.convert("RGBA")
            tampered.putpixel((5, 5), (255, 0, 0, 255))
            from PIL.PngImagePlugin import PngInfo
            meta = PngInfo()
            meta.add_text(lc.PNG_KEY, info[lc.PNG_KEY])
            tampered.save(folder / "bad.png", pnginfo=meta)
            code, _ = lc.verify_files(folder / "bad.png", folder / "base.png", heading_box=(54, 54, 700, 400))
            self.assertEqual(code, 1)


if __name__ == "__main__":
    unittest.main()
