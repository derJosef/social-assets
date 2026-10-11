#!/usr/bin/env python3
"""Offline negative/positive tests: synthetic pixels only, no external image or Buffer."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, PngImagePlugin

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import ai_disclosure as m


class DisclosureTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        font = ImageFont.load_default(size=42)
        source = getattr(font, "path", None)
        if not hasattr(source, "getvalue"):
            self.skipTest("Pillow wheel does not expose a bundled test TTF")
        self.font = self.root / "synthetic-test.ttf"
        self.font.write_bytes(source.getvalue())
        self.base = self.root / "base.png"
        Image.new("RGB", m.SIZE, (24, 47, 64)).save(self.base)

    def test_exact_copy_and_high_contrast(self):
        report = m.apply_to_base(self.base, self.font)
        self.assertEqual(report["text"], "Powered by AI")
        self.assertEqual(report["font_size_px"], 42)
        self.assertEqual(report["margin_px"], 54)
        self.assertGreater(report["contrast_ratio"], 4.5)
        self.assertTrue(report["pixel_verified"])
        self.assertEqual(tuple(report["box"]), m.verify_label_region(self.base, self.font))

    def test_caption_cannot_be_absent(self):
        with self.assertRaises(m.DisclosureError):
            m.verify_label_region(self.base, self.font)

    def test_caption_cannot_be_edited_after_verification(self):
        m.apply_to_base(self.base, self.font)
        with Image.open(self.base) as img:
            altered = img.convert("RGB")
        box = m.verify_label_region(self.base, self.font)
        ImageDraw.Draw(altered).rectangle((box[0]+7, box[1]+7, box[0]+17, box[1]+17), fill="red")
        altered.save(self.base)
        with self.assertRaises(m.DisclosureError):
            m.verify_label_region(self.base, self.font)

    def test_caption_cannot_be_repositioned(self):
        m.apply_to_base(self.base, self.font)
        with Image.open(self.base) as img:
            altered = img.convert("RGB")
        box = m.verify_label_region(self.base, self.font)
        altered.paste((24,47,64),box)
        altered.save(self.base)
        with self.assertRaises(m.DisclosureError):
            m.verify_label_region(self.base, self.font)

    def test_font_must_exist(self):
        with self.assertRaises(m.DisclosureError):
            m.apply_to_base(self.base, self.root/"missing-inter.ttf")

    def test_full_canvas_must_be_four_by_five(self):
        Image.new("RGB", (1080, 1080)).save(self.base)
        with self.assertRaises(m.DisclosureError):
            m.apply_to_base(self.base, self.font)

    def make_fake_compositor_png(self, *, logo_corner="bottom-right"):
        final = self.root / "final.png"
        placement = {
            "heading_corner": None, "logo_only": True, "logo_only_corner": logo_corner,
            "logo_width": 173, "logo_height": 118,
            "margin": 54, "frame": True, "stroke": 5, "gap": 0,
        }
        info = PngImagePlugin.PngInfo()
        info.add_text("logo_placement",json.dumps(placement))
        Image.new("RGB", m.SIZE).save(final,pnginfo=info)
        return final

    def test_original_logo_right_disjoint(self):
        report = m.apply_to_base(self.base,self.font)
        m.verify_no_logo_overlap(self.make_fake_compositor_png(),
                                 tuple(report["box"]))

    def test_original_logo_left_rejected(self):
        report = m.apply_to_base(self.base,self.font)
        # Bottom-left original logo would collide with the approved text label.
        with self.assertRaises(m.DisclosureError):
            m.verify_no_logo_overlap(self.make_fake_compositor_png(logo_corner="bottom-left"),
                                     tuple(report["box"]))

    def test_missing_canonical_logo_placement_rejected(self):
        report = m.apply_to_base(self.base,self.font)
        final=self.root/"no-placement.png"
        Image.new("RGB",m.SIZE).save(final)
        with self.assertRaises(m.DisclosureError):
            m.verify_no_logo_overlap(final,tuple(report["box"]))

    def test_no_unmarked_pixels_outside_caption_changed(self):
        untouched = Image.open(self.base).convert("RGB")
        r = m.apply_to_base(self.base, self.font)
        with Image.open(self.base) as labeled:
            altered = labeled.convert("RGB")
        altered.paste(untouched.crop(tuple(r["box"])), tuple(r["box"]))
        self.assertEqual(untouched.tobytes(), altered.tobytes())


if __name__ == "__main__":
    unittest.main()
