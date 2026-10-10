#!/usr/bin/env python3
"""Offline tests of the ChatGPT-prepared editorial handoff, no Buffer/network."""
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import prepared_brief_preflight as gate
import social_orchestrator as orchestrator

CID = "2026-10-10-editorial-test-009"


class PreparedHandoffTests(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.root = Path(t.name)
        image = self.root / "media/source-images/prepared-test.png"
        image.parent.mkdir(parents=True)
        Image.new("RGB", (1080, 1350), (12, 24, 36)).save(image)
        review_dir = self.root / "visual-reviews"
        review_dir.mkdir()
        (review_dir / f"{CID}.json").write_text(json.dumps({
            "format_version": 1, "brand": "ai-agent-builder",
            "source": "media/source-images/prepared-test.png",
            "source_sha256": hashlib.sha256(image.read_bytes()).hexdigest(),
            "layout": "logo_only", "heading": None,
            "visual_review": {name: True for name in (
                "no_people", "no_robot", "no_foreign_logo", "no_generated_text",
                "plausible_details", "matches_topic", "heading_and_logo_space")},
            "review_evidence": "Synthetic offline image for automated unit testing only."
        }))
        brief_dir = self.root / "orchestration/briefs"
        brief_dir.mkdir(parents=True)
        self.path = brief_dir / f"{CID}.json"
        self.relpath = f"orchestration/briefs/{CID}.json"
        self.brief = {
            "format_version": 1, "brand": "ai-agent-builder",
            "campaign_id": CID,
            "topic": "Eine nachvollziehbare technische Arbeitsfolge bei KI-Agenten für den Mittelstand",
            "sources": [
                {"url": "https://www.nist.gov/itl/ai-risk-management-framework",
                 "published_at": "2023-01-26"},
                {"url": "https://learn.microsoft.com/en-us/azure/",
                 "published_at": "2025-07-01"}
            ],
            "posting_sources": [
                "https://buffer.com/resources/best-time-to-post-on-linkedin/",
                "https://blog.hootsuite.com/best-time-to-post-on-linkedin/"
            ],
            "execution_mode": "drafts",
            "image_review": f"visual-reviews/{CID}.json",
            "prepared_content": {
                "posts": {t: "Dies ist ein synthetischer und nie zu versendender Test. " * 9
                          for t in orchestrator.TARGETS},
                "visual": None,
                "six_hats": {hat: "Nur Testdaten und kein tatsächlicher redaktioneller Befund."
                             for hat in ("white", "red", "black", "yellow", "green", "blue")},
                "risks": ["Nur simulierte Testinhalte"]
            },
        }
        self.write()
        patcher = patch.object(orchestrator, "ROOT", self.root)
        patcher.start()
        self.addCleanup(patcher.stop)

    def write(self):
        self.path.write_text(json.dumps(self.brief), encoding="utf-8")

    def test_prepared_handoff_validates_without_network_or_buffer(self):
        with patch.object(orchestrator, "fetch_evidence",
                          side_effect=AssertionError("No external source fetch")), \
             patch.object(orchestrator, "call_model",
                          side_effect=AssertionError("No model contact")):
            report = gate.check_prepared(self.relpath)
        self.assertEqual(report["mode"], "chatgpt_prepared_content")
        self.assertEqual(report["post_channels"], list(orchestrator.TARGETS))
        self.assertEqual(report["model_requests"], 0)
        self.assertEqual(report["buffer_requests"], 0)

    def test_unprepared_brief_is_rejected(self):
        del self.brief["prepared_content"]
        self.write()
        with self.assertRaisesRegex(orchestrator.Blocked, "prepared_content"):
            gate.check_prepared(self.relpath)

    def test_changed_source_rejected(self):
        review = self.root / f"visual-reviews/{CID}.json"
        data = json.loads(review.read_text())
        data["source_sha256"] = "0" * 64
        review.write_text(json.dumps(data))
        with self.assertRaises(ValueError):
            gate.check_prepared(self.relpath)

    def test_short_text_rejected(self):
        self.brief["prepared_content"]["posts"]["facebook"] = "Zu kurz"
        self.write()
        with self.assertRaisesRegex(orchestrator.Blocked, "facebook"):
            gate.check_prepared(self.relpath)

    def test_unreviewed_image_rejected(self):
        review = self.root / f"visual-reviews/{CID}.json"
        data = json.loads(review.read_text())
        data["visual_review"]["no_foreign_logo"] = False
        review.write_text(json.dumps(data))
        with self.assertRaises(ValueError):
            gate.check_prepared(self.relpath)

    def test_reused_campaign_rejected(self):
        (self.root / "campaign-manifests").mkdir()
        (self.root / f"campaign-manifests/{CID}.json").write_text("{}")
        with self.assertRaisesRegex(orchestrator.Blocked, "Kampagnen-ID existiert"):
            gate.check_prepared(self.relpath)

    def test_wrong_mode_rejected(self):
        self.brief["execution_mode"] = "smoke"
        self.write()
        with self.assertRaisesRegex(orchestrator.Blocked, "execution_mode"):
            gate.check_prepared(self.relpath)

    def test_no_heading_allowed_but_no_fake_heading(self):
        self.brief["prepared_content"]["visual"] = {"headline": "Dummy"}
        self.write()
        with self.assertRaisesRegex(orchestrator.Blocked, "Grafikentwurf"):
            gate.check_prepared(self.relpath)


if __name__ == "__main__":
    unittest.main()
