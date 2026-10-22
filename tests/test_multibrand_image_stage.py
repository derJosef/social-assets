"""Real-byte staging tests: no external API, website, Adobe or Buffer mutation."""
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from multibrand_contract import ConfigurationBlocked, plan_job
from multibrand_image_stage import stage_images

RUN = "2026-10-20-staging-test"


class ResponsiveStageTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)

    def spec(self, kind: str, override_size: dict | None = None):
        plan = plan_job("ai-agent-builder", kind, RUN)
        entries = []
        for number, output in enumerate(plan["outputs"]):
            label = f"motif-{number:02d}"
            input_path = f"inputs/ai-agent-builder/{kind}/{RUN}/{label}.png"
            source_path = self.root / input_path
            source_path.parent.mkdir(parents=True, exist_ok=True)
            dimensions = tuple(output["dimensions"])
            if override_size and number in override_size:
                dimensions = override_size[number]
            image = Image.new("RGB", dimensions,
                              (number * 13 % 256, number * 47 % 256, number * 81 % 256))
            image.save(source_path, "PNG")
            entries.append({"input_path": input_path, "output_path": output["path"],
                            "sha256": hashlib.sha256(source_path.read_bytes()).hexdigest()})
        return {"brand_id": "ai-agent-builder", "kind": kind,
                "run_id": RUN, "sources": entries}

    def test_news_three_variants_are_staged_with_verified_image_bytes(self):
        data = self.spec("news")
        result = stage_images(data, self.root, self.root)
        self.assertEqual(result["status"], "technical-image-qa-pass")
        self.assertEqual(result["checked_count"], 3)
        self.assertEqual(result["visual_review"], "still-required")
        self.assertEqual(result["publishing"], "not-authorized")
        manifest = (self.root / f"generated/ai-agent-builder/news/{RUN}/asset-manifest.json")
        self.assertTrue(manifest.is_file())
        self.assertEqual(len(json.loads(manifest.read_text())["assets"]), 3)

    def test_menu_rotation_stages_all_seven_regions_without_posting(self):
        result = stage_images(self.spec("rotation"), self.root, self.root)
        self.assertEqual(result["checked_count"], 14)
        self.assertFalse(result["publishing"] == "authorized")
        self.assertEqual(len(set(a["sha256"] for a in result["assets"])), 14)

    def test_no_upsample(self):
        wrong = self.spec("news", override_size={0: (836, 470)})
        with self.assertRaisesRegex(ConfigurationBlocked, "upscale"):
            stage_images(wrong, self.root, self.root)
        self.assertFalse((self.root / f"generated/ai-agent-builder/news/{RUN}").exists())

    def test_no_cropping_or_stretching(self):
        wrong = self.spec("news", override_size={0: (1672, 1200)})
        with self.assertRaisesRegex(ConfigurationBlocked, "aspect"):
            stage_images(wrong, self.root, self.root)

    def test_preflight_does_not_leave_partial_files_after_hash_error(self):
        wrong = self.spec("news")
        wrong["sources"][-1]["sha256"] = "0" * 64
        with self.assertRaisesRegex(ConfigurationBlocked, "SHA mismatch"):
            stage_images(wrong, self.root, self.root)
        self.assertFalse((self.root / f"generated/ai-agent-builder/news/{RUN}").exists())

    def test_no_reusing_generated_campaign(self):
        spec = self.spec("news")
        stage_images(spec, self.root, self.root)
        with self.assertRaisesRegex(ConfigurationBlocked, "overwrite"):
            stage_images(spec, self.root, self.root)

    def test_brand_swap_cannot_take_other_brand_assets(self):
        wrong = self.spec("news")
        wrong["brand_id"] = "picturefix"
        with self.assertRaises(ConfigurationBlocked):
            stage_images(wrong, self.root, self.root)

    def test_wrong_job_source_namespace_rejected(self):
        wrong = self.spec("news")
        wrong["sources"][0]["input_path"] = wrong["sources"][0]["input_path"].replace(
            "inputs/ai-agent-builder/news/", "inputs/ai-agent-builder/rotation/"
        )
        with self.assertRaisesRegex(ConfigurationBlocked, "Source outside"):
            stage_images(wrong, self.root, self.root)


if __name__ == "__main__":
    unittest.main()
