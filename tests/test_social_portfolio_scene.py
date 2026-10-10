#!/usr/bin/env python3
"""Offline, synthetic tests. Never contact Buffer or an image model."""
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import social_portfolio_scene as m


class SceneTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root / "media/source-images/test-scene.png"
        self.source.parent.mkdir(parents=True)
        Image.new("RGB", (1122, 1402), (7, 17, 31)).save(self.source)
        self.spec = {
            "format_version": 1, "brand": "ai-agent-builder",
            "source": "media/source-images/test-scene.png",
            "source_sha256": hashlib.sha256(self.source.read_bytes()).hexdigest(),
            "heading": "WER GIBT DEN BEFEHL?",
            "visual_review": {key: True for key in m.REVIEW_KEYS},
            "review_evidence": "TEST ONLY: synthetic fixture, not an approval",
        }

    def test_fingerprint_changed_fails_closed(self):
        self.spec["source_sha256"] = "0" * 64
        with self.assertRaises(m.InvalidScene):
            m.validate_spec(self.spec, self.root)

    def test_no_visual_review_fails_closed(self):
        self.spec["visual_review"]["no_people"] = False
        with self.assertRaises(m.InvalidScene):
            m.validate_spec(self.spec, self.root)

    def test_no_human_evidence_fails_closed(self):
        self.spec["review_evidence"] = ""
        with self.assertRaises(m.InvalidScene):
            m.validate_spec(self.spec, self.root)

    def test_refuses_bad_paths(self):
        self.spec["source"] = "../../personal-data.png"
        with self.assertRaises(m.InvalidScene):
            m.validate_spec(self.spec, self.root)

    def test_refuses_square_without_cropping(self):
        Image.new("RGB", (1400, 1400)).save(self.source)
        self.spec["source_sha256"] = hashlib.sha256(self.source.read_bytes()).hexdigest()
        with self.assertRaises(m.InvalidScene):
            m.validate_spec(self.spec, self.root)

    def test_accepts_genuine_4x5_dimensions(self):
        self.assertEqual(m.validate_spec(self.spec, self.root), self.source)

    def test_heading_wrap_is_limited(self):
        # PIL's builtin font keeps the offline test independent from font downloads.
        from PIL import ImageDraw, ImageFont
        canvas = Image.new("RGB", m.SIZE)
        lines = m.layout_heading(ImageDraw.Draw(canvas),
                                 "WER GIBT DEN BEFEHL?",
                                 ImageFont.load_default(size=67))
        self.assertGreaterEqual(len(lines), 1)
        self.assertLessEqual(len(lines), 3)

    def test_no_buffer_or_publishing_operations(self):
        source = Path(m.__file__).read_text(encoding="utf-8")
        self.assertNotIn("deletePost(", source)
        self.assertNotIn("editPost(", source)
        self.assertNotIn("createPost(", source)
        self.assertNotIn("saveToDraft: false", source)


if __name__ == "__main__":
    unittest.main()
