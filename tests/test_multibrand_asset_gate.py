#!/usr/bin/env python3
"""Tests with real generated image bytes, no GitHub or Buffer access."""
import hashlib
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from multibrand_contract import ConfigurationBlocked, plan_job
from multibrand_asset_gate import validate_assets

RUN = "2026-10-20-image-test"

class MultiBrandImageGateTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)

    def build(self, kind, duplicate=False):
        plan = plan_job("ai-agent-builder", kind, RUN)
        assets = []
        for index, item in enumerate(plan["outputs"]):
            path = self.root / item["path"]
            path.parent.mkdir(parents=True, exist_ok=True)
            # Identical desktop frames for index 0 and 2 emulate accidental reuse.
            color_index = 0 if duplicate and index == 2 else index
            color = ((color_index * 47) % 256, (color_index * 83) % 256,
                     (color_index * 119) % 256)
            image = Image.new("RGB", tuple(item["dimensions"]), color)
            image.save(path, format=item["format"].upper())
            assets.append({"path": item["path"],
                           "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
        return {"brand_id": "ai-agent-builder", "kind": kind,
                "run_id": RUN, "assets": assets}

    def test_news_three_formats_pass_with_actual_webp(self):
        manifest = self.build("news")
        result = validate_assets(manifest, self.root)
        self.assertEqual(result["checked_count"], 3)
        self.assertEqual(result["status"], "technical-image-qa-pass")
        self.assertEqual(result["visual_review"], "still-required")
        self.assertEqual(result["publishing"], "not-authorized")

    def test_seven_desktop_mobile_pairs_pass(self):
        manifest = self.build("rotation")
        self.assertEqual(validate_assets(manifest, self.root)["checked_count"], 14)

    def test_reused_menu_motif_files_are_rejected(self):
        manifest = self.build("rotation", duplicate=True)
        with self.assertRaisesRegex(ConfigurationBlocked, "Repeated identical"):
            validate_assets(manifest, self.root)

    def test_modified_bytes_blocked(self):
        manifest = self.build("news")
        path = self.root / manifest["assets"][0]["path"]
        path.write_bytes(path.read_bytes() + b"bad")
        with self.assertRaisesRegex(ConfigurationBlocked, "hash"):
            validate_assets(manifest, self.root)

    def test_brand_context_swap_blocked(self):
        manifest = self.build("news")
        manifest["brand_id"] = "picturefix"
        with self.assertRaises(ConfigurationBlocked):
            validate_assets(manifest, self.root)

    def test_missing_asset_blocked(self):
        manifest = self.build("news")
        manifest["assets"].pop()
        with self.assertRaises(ConfigurationBlocked):
            validate_assets(manifest, self.root)

    def test_wrong_real_file_format_blocked(self):
        manifest = self.build("news")
        first = manifest["assets"][0]
        path = self.root / first["path"]
        Image.new("RGB", (1672, 941), (10, 20, 30)).save(path, format="PNG")
        first["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        with self.assertRaisesRegex(ConfigurationBlocked, "internal"):
            validate_assets(manifest, self.root)

if __name__ == "__main__":
    unittest.main()
