#!/usr/bin/env python3
"""Offline full-size, real-original-logo checks for draft-only logo-only scenes."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageDraw
from PIL.PngImagePlugin import PngInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from logo_composite import PNG_KEY, compose_file
from logo_only_gate import LogoOnlyError, verify_logo_only, SIZE


class RealLogoOnlyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name)
        self.original = ROOT / "media/brand/logo-pauderer-original.png"
        self.base = self.path / "source.png"
        self.final = self.path / "with-original-logo.png"
        Image.new("RGB", SIZE, (7, 17, 31)).save(self.base)
        compose_file(self.base, self.final, "top-left", self.original,
                     frame="on", margin_ratio=0.05, stroke_ratio=0.03)

    def test_real_logo_no_heading_is_accepted_in_separate_strict_gate(self):
        result = verify_logo_only(self.final, self.base, self.original)
        self.assertEqual(result["profile"], "logo_only")
        self.assertEqual(result["logo_corner"], "bottom-right")
        self.assertEqual(result["canonical_checks_passed"], 9)
        self.assertEqual(result["size"], [1080, 1350])
        self.assertEqual(len(result["not_applicable"]), 1)

    def test_tampered_source_area_fails_logo_only_verification(self):
        with Image.open(self.final) as image:
            original_meta = image.text[PNG_KEY]
            edited = image.copy().convert("RGBA")
        ImageDraw.Draw(edited).rectangle((2, 2, 15, 15), fill="#ff00ff")
        pinfo = PngInfo()
        pinfo.add_text(PNG_KEY, original_meta)
        edited.save(self.final, format="PNG", pnginfo=pinfo)
        with self.assertRaises(LogoOnlyError):
            verify_logo_only(self.final, self.base, self.original)

    def test_forged_logo_position_metadata_fails(self):
        with Image.open(self.final) as image:
            original_meta = json.loads(image.text[PNG_KEY])
            edited = image.copy()
        original_meta["heading_corner"] = "bottom-right"
        pinfo = PngInfo()
        pinfo.add_text(PNG_KEY, json.dumps(original_meta))
        edited.save(self.final, format="PNG", pnginfo=pinfo)
        with self.assertRaises(LogoOnlyError):
            verify_logo_only(self.final, self.base, self.original)

    def test_heading_metadata_removed_fails(self):
        with Image.open(self.final) as image:
            image.save(self.final, format="PNG")
        with self.assertRaises(LogoOnlyError):
            verify_logo_only(self.final, self.base, self.original)


if __name__ == "__main__":
    unittest.main()
