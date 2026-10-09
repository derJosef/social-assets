#!/usr/bin/env python3
"""Offline unit tests: no model network, Buffer calls, or publication."""
from __future__ import annotations
import json
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import social_orchestrator as m

def brief(execution_mode="smoke"):
    return {
        "format_version":1,"brand":"ai-agent-builder",
        "campaign_id":"2026-10-09-datenschutz-forschung",
        "execution_mode":execution_mode,
        "topic":"Wie Datenflüsse von Verbraucher-KI-Anwendungen Unternehmen zu einer Prüfung der Anbieter motivieren.",
        "sources":[
            {"url":"https://www.basicthinking.de/blog/test","published_at":"2026-10-08"},
            {"url":"https://networks.imdea.org/test","published_at":"2026-09-22"},
        ],
        "posting_sources":[
            "https://buffer.com/resources/best-time-to-post-on-linkedin/",
            "https://sproutsocial.com/insights/best-times-to-post-on-linkedin/"
        ]
    }

class OrchestratorTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        (self.root/"orchestration/briefs").mkdir(parents=True)
        self.name="orchestration/briefs/2026-10-09-datenschutz-forschung.json"
        self.path=self.root/self.name
        self.path.write_text(json.dumps(brief()),encoding="utf-8")
        patcher=patch.object(m,"ROOT",self.root)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_smoke_has_no_external_side_effects(self):
        with patch.object(m,"fetch_evidence",side_effect=AssertionError("unexpected network")), \
             patch.object(m,"call_model",side_effect=AssertionError("unexpected inference")):
            report=m.prepare(self.name,"smoke",str(self.root/"report.json"))
        self.assertEqual(report["state"],"smoke_pass")

    def test_unknown_brand_blocks(self):
        obj=brief();obj["brand"]="different-brand"
        self.path.write_text(json.dumps(obj),encoding="utf-8")
        with self.assertRaises(m.Blocked):
            m.load_brief(self.name)

    def test_urls_cannot_reference_private_host(self):
        for url in ["http://site.com/test","https://127.0.0.1/","https://localhost/test",
                    "https://u:pass@example.com/test"]:
            with self.subTest(url=url), self.assertRaises(m.Blocked):
                m.valid_url(url)

    def test_at_least_two_distinct_source_domains(self):
        obj=brief();obj["sources"][1]["url"]="https://www.basicthinking.de/another"
        self.path.write_text(json.dumps(obj),encoding="utf-8")
        with self.assertRaises(m.Blocked):
            m.load_brief(self.name)

    def test_sommerzeit_and_winterzeit(self):
        a=m.select_times(date(2026,10,9))
        self.assertTrue(all("+01:00" in v["local"] for v in a.values()))
        self.assertTrue(all(v["utc"].endswith("Z") for v in a.values()))

    def test_no_reusing_existing_campaign(self):
        (self.root/"campaign-manifests").mkdir()
        (self.root/"campaign-manifests/2026-10-09-datenschutz-forschung.json").write_text("{}")
        with self.assertRaises(m.Blocked):
            m.available("2026-10-09-datenschutz-forschung")

    def test_invalid_post_text_fails(self):
        g={"posts":{k:"short" for k in m.TARGETS},"visual":{},
           "six_hats":{},"risks":[]}
        with self.assertRaises(m.Blocked):
            m.assess_generated(g)

    def test_no_publish_or_schedule_mutation(self):
        text=Path(m.__file__).read_text(encoding="utf-8")
        self.assertNotIn("saveToDraft: false",text)
        self.assertNotIn("ready-to-schedule/",text)
        self.assertNotIn("editPost(",text)

if __name__=="__main__":
    unittest.main()
