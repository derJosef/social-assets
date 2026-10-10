#!/usr/bin/env python3
"""Offline unit tests: no model network, Buffer calls, or publication."""
from __future__ import annotations
import json
import hashlib
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch
from PIL import Image

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import social_orchestrator as m

def brief(execution_mode="smoke"):
    return {
        "format_version":1,"brand":"ai-agent-builder",
        "campaign_id":"2026-10-09-datenschutz-forschung",
        "execution_mode":execution_mode,
        "image_review":"visual-reviews/2026-10-09-datenschutz-forschung.json",
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
        source=self.root/"media/source-images/test-orchestrator-source.png"
        source.parent.mkdir(parents=True)
        Image.new("RGB",(1080,1350),(7,17,31)).save(source)
        evidence={
          "format_version":1, "brand":"ai-agent-builder",
          "source":"media/source-images/test-orchestrator-source.png",
          "source_sha256":hashlib.sha256(source.read_bytes()).hexdigest(),
          "layout":"logo_only","heading":None,
          "visual_review":{key:True for key in (
            "no_people","no_robot","no_foreign_logo","no_generated_text",
            "plausible_details","matches_topic","heading_and_logo_space")},
          "review_evidence":"Unit fixture only, not an actual human visual approval"}
        rev=self.root/"visual-reviews/2026-10-09-datenschutz-forschung.json"
        rev.parent.mkdir(parents=True)
        rev.write_text(json.dumps(evidence),encoding="utf-8")
        patcher=patch.object(m,"ROOT",self.root)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_retired_github_models_never_calls_network(self):
        # A GITHUB_TOKEN is NOT an inference-provider token anymore.
        with patch.dict(m.os.environ,{"OPENAI_API_KEY":"","GITHUB_TOKEN":"test-only"},clear=False), \
             patch.object(m.urllib.request,"urlopen",side_effect=AssertionError("no model API allowed")):
            with self.assertRaisesRegex(m.Blocked,"GitHub Models"):
                m.call_model([{"role":"user","content":"Return a word"}])

    def test_unconfigured_auto_copy_stops_before_source_fetch(self):
        obj=brief("drafts")
        self.path.write_text(json.dumps(obj),encoding="utf-8")
        with patch.dict(m.os.environ,{"OPENAI_API_KEY":"","GITHUB_TOKEN":"test-only"},clear=False), \
             patch.object(m,"fetch_evidence",side_effect=AssertionError("do not fetch sources")):
            with self.assertRaisesRegex(m.Blocked,"GitHub Models"):
                m.prepare(self.name,"drafts",str(self.root/"no-model-report.json"))
        report=json.loads((self.root/"no-model-report.json").read_text())
        self.assertEqual(report["state"],"blocked")

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

    def test_missing_review_blocks_even_in_smoke(self):
        data=brief()
        data.pop("image_review")
        self.path.write_text(json.dumps(data),encoding="utf-8")
        with self.assertRaises(m.Blocked):
            m.load_brief(self.name)

    def test_tampered_source_blocks_before_model_calls(self):
        rev=self.root/"visual-reviews/2026-10-09-datenschutz-forschung.json"
        data=json.loads(rev.read_text())
        data["source_sha256"]="0"*64
        rev.write_text(json.dumps(data))
        with self.assertRaises(ValueError):
            m.load_brief(self.name)

    def test_square_image_blocks(self):
        source=self.root/"media/source-images/test-orchestrator-source.png"
        Image.new("RGB",(1080,1080),(7,17,31)).save(source)
        rev=self.root/"visual-reviews/2026-10-09-datenschutz-forschung.json"
        data=json.loads(rev.read_text())
        data["source_sha256"]=hashlib.sha256(source.read_bytes()).hexdigest()
        rev.write_text(json.dumps(data))
        with self.assertRaises(ValueError):
            m.load_brief(self.name)

    def test_generated_cards_cannot_override_reviewed_scene(self):
        g={"posts":{target:"M"*300 for target in m.TARGETS},
           "visual":{"badge":"WRONG"},
           "six_hats":{k:"Documented specific finding by a reviewer" for k in (
             "white","red","black","yellow","green","blue")},
           "risks":[]}
        with self.assertRaises(m.Blocked):
            m.assess_generated(g)
        g["visual"]=None
        m.assess_generated(g)

    def test_no_square_renderer_in_new_pipeline(self):
        source=Path(m.__file__).read_text(encoding="utf-8")
        self.assertNotIn("render_background(",source)
        self.assertIn("social_portfolio_scene",source)

    def test_offline_end_to_end_produces_three_drafts_and_verified_4x5_image(self):
        import shutil
        import autonomous_campaign_gate as gate
        import buffer_draft
        original=Path(m.__file__).resolve().parents[1]/"media/brand/logo-pauderer-original.png"
        destination=self.root/"media/brand/logo-pauderer-original.png"
        destination.parent.mkdir(parents=True)
        shutil.copy2(original,destination)
        scripts=self.root/"scripts"
        scripts.mkdir()
        shutil.copy2(Path(m.__file__).resolve().parent/"logo_composite.py",
                     scripts/"logo_composite.py")
        br=brief("drafts")
        posts={k:("Dieses ist ein rein synthetischer Testbeitrag. " * 10)
               for k in m.TARGETS}
        content={"posts":posts,"visual":None,
                 "six_hats":{k:"A documented synthetic offline test finding of adequate length"
                            for k in ("white","red","black","yellow","green","blue")},
                 "risks":[]}
        m.assess_generated(content)
        sources={s["url"]:"Synthetic evidence fixture" for s in br["sources"]}
        # The shared suite can import the same module under two names.
        # Bind precisely the function object called by the gate.
        with patch.object(gate,"ROOT",self.root), patch.dict(gate.read_draft.__globals__,{"ROOT":self.root}):
            p=m.create_packages(br,sources,content)
        from PIL import Image
        with Image.open(self.root/p["final"]) as rendered:
            self.assertEqual(rendered.size,(1080,1350))
        manifest=json.loads((self.root/p["manifest"]).read_text())
        self.assertEqual(manifest["image"]["layout"],"logo_only")
        self.assertIsNone(manifest["image"]["heading_box"])
        self.assertNotIn("render_background",Path(m.__file__).read_text())
        self.assertFalse((self.root/f"artwork-requests/{br['campaign_id']}.json").exists())
        for target in m.TARGETS:
            item=json.loads((self.root/manifest["posts"][target]).read_text())
            self.assertEqual(item["text"],posts[target])
            self.assertTrue(item["media"]["images"][0]["url"].endswith(p["final"]))

    def test_no_publish_or_schedule_mutation(self):
        text=Path(m.__file__).read_text(encoding="utf-8")
        self.assertNotIn("saveToDraft: false",text)
        self.assertNotIn("ready-to-schedule/",text)
        self.assertNotIn("editPost(",text)

if __name__=="__main__":
    unittest.main()
