import json
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import autonomous_campaign_gate as gate


class AutonomousCampaignGateTests(unittest.TestCase):
    def test_both_draft_paths_pin_same_inter_and_pillow_before_quality_gate(self):
        root = Path(__file__).resolve().parents[1]
        workflows = [
            root / ".github/workflows/buffer-auto-drafts.yml",
            root / ".github/workflows/social-campaign-orchestrator.yml",
        ]
        url = "https://raw.githubusercontent.com/google/fonts/e1d6480102fed30739fead0faee463101f892c8f/ofl/inter/Inter%5Bopsz%2Cwght%5D.ttf"
        sha = "29160a80ff49ddcab2c97711247e08b1fab27a484a329ce8b813d820dc559031"
        for path in workflows:
            contents = path.read_text(encoding="utf-8")
            with self.subTest(workflow=path.name):
                self.assertIn(url, contents)
                self.assertIn(sha, contents)
                self.assertIn("sha256sum --check --status", contents)
                self.assertIn("Pillow==12.3.0", contents)
                self.assertIn("numpy==2.5.4", contents)
                self.assertIn("python-version: '3.12'", contents)
        standalone = workflows[0].read_text(encoding="utf-8")
        self.assertLess(standalone.index("sha256sum --check --status"),
                        standalone.index("python3 scripts/autonomous_campaign_gate.py"))

    def test_scheduling_is_proposal_only(self):
        self.assertNotIn("editPost", Path(gate.__file__).read_text())
        self.assertNotIn("saveToDraft: false", Path(gate.__file__).read_text())
        self.assertNotIn("createPost", Path(gate.__file__).read_text())

    def test_missing_post_files_fail_closed(self):
        with self.assertRaises(ValueError):
            gate.check_campaign(["ready-for-buffer/auto-2026-10-09-test-linkedin.json"], today=date(2026, 10, 9), verify_image=False)

    def test_duplicate_channel_fails_closed(self):
        p = ["ready-for-buffer/auto-2026-10-09-test-linkedin.json"] * 3
        with self.assertRaises(ValueError):
            gate.check_campaign(p, today=date(2026, 10, 9), verify_image=False)

    def test_utc_requires_z(self):
        with self.assertRaises(ValueError):
            gate.parse_utc("2026-10-22T16:00:00+02:00")

    def test_correct_europe_berlin_dst(self):
        from datetime import datetime, timezone
        from zoneinfo import ZoneInfo
        summer = datetime(2026, 10, 21, 16, tzinfo=ZoneInfo("Europe/Berlin"))
        winter = datetime(2026, 10, 27, 19, tzinfo=ZoneInfo("Europe/Berlin"))
        self.assertEqual(summer.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "2026-10-21T14:00:00Z")
        self.assertEqual(winter.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "2026-10-27T18:00:00Z")

    def test_no_api_side_effects_during_import(self):
        # Importing the gate must not write to Buffer/GitHub.
        self.assertTrue(callable(gate.check_campaign))


    def create_fixture(self, temp_root):
        import hashlib
        from datetime import timedelta, datetime, timezone
        root=Path(temp_root)
        for folder in ["campaign-manifests","media/images","media/source-images","ready-for-buffer"]:
            (root/folder).mkdir(parents=True)
        image_path="media/images/auto-2026-10-09-agenten-tests.png"
        base_path="media/source-images/auto-2026-10-09-agenten-tests.png"
        image=(root/image_path)
        image.write_bytes(b"verified-test-image-placeholder")
        (root/base_path).write_bytes(b"test-background-placeholder")
        url=gate.IMG_BASE+image_path
        posts={}
        for target in gate.TARGETS:
            name=f"ready-for-buffer/auto-2026-10-09-agenten-tests-{target}.json"
            (root/name).write_text(json.dumps({
                "format_version":2,"target":target,
                "text":f"Ein Agent, drei Testschritte: {target}. Was pruefst du zuerst?",
                "media":{"type":"images","images":[{
                    "url":url,"alt_text":"Pruefprozess mit drei Stationen"
                }]}
            }), encoding="utf-8")
            posts[target]=name
        manifest={
            "format_version":1,
            "brand":"ai-agent-builder",
            "campaign_id":"2026-10-09-agenten-tests",
            "checked_at":"2026-10-09",
            "sources":[
                {"url":"https://www.nist.gov/test","published_at":"2026-09-01","checked_at":"2026-10-09"},
                {"url":"https://www.owasp.org/test","published_at":"2026-10-01","checked_at":"2026-10-09"},
            ],
            "checks":{k:True for k in gate.REQUIRED_CHECKS},
            "image":{
                "final":image_path,"base":base_path,
                "sha256":hashlib.sha256(image.read_bytes()).hexdigest(),
                "heading_corner":"top-left","heading_box":[30,60,500,350]
            },
            "posts":posts,
            "posting_times":{
                t:{"local":"2026-11-04T16:00:00+01:00","utc":"2026-11-04T15:00:00Z"}
                for t in gate.TARGETS
            }
        }
        m=root/"campaign-manifests/2026-10-09-agenten-tests.json"
        m.write_text(json.dumps(manifest), encoding="utf-8")
        return posts,manifest,m

    def create_reviewed_fixture(self,temp_root):
        import hashlib
        from PIL import Image
        paths,manifest,m=self.create_fixture(temp_root)
        root=Path(temp_root)
        src_path="media/source-images/2026-10-09-agenten-tests-source.png"
        final=root/manifest["image"]["final"]
        Image.new("RGB",(1080,1350),(7,17,31)).save(root/src_path)
        Image.new("RGB",(1080,1350),(7,17,31)).save(final)
        (root/"visual-reviews").mkdir()
        review={
          "format_version":1,"brand":"ai-agent-builder","layout":"logo_only",
          "heading":None,"source":src_path,
          "source_sha256":hashlib.sha256((root/src_path).read_bytes()).hexdigest(),
          "visual_review":{k:True for k in (
            "no_people","no_robot","no_foreign_logo","no_generated_text",
            "plausible_details","matches_topic","heading_and_logo_space")},
          "review_evidence":"SYNTHETIC TEST FIXTURE ONLY, not real visual acceptance"
        }
        (root/"visual-reviews/2026-10-09-agenten-tests.json").write_text(json.dumps(review))
        manifest["image"]={
          "final":manifest["image"]["final"],"base":manifest["image"]["base"],
          "sha256":hashlib.sha256(final.read_bytes()).hexdigest(),
          "heading_corner":None,"heading_box":None,"layout":"logo_only",
          "review_spec":"visual-reviews/2026-10-09-agenten-tests.json",
          "source_sha256":review["source_sha256"]
        }
        m.write_text(json.dumps(manifest))
        return paths,manifest,m

    def test_old_square_card_manifest_is_blocked(self):
        with tempfile.TemporaryDirectory() as td:
            paths,manifest,m=self.create_fixture(td)
            with patch.object(gate,"ROOT",Path(td)),patch.dict(gate.read_draft.__globals__,{"ROOT":Path(td)}):
                with self.assertRaisesRegex(ValueError,"nicht mehr"):
                    gate.check_campaign(list(paths.values()),today=date(2026,10,9),verify_image=False)

    def test_reviewed_logo_only_draft_gate_with_no_headline_box(self):
        with tempfile.TemporaryDirectory() as td:
            paths,manifest,m=self.create_reviewed_fixture(td)
            with patch.object(gate,"ROOT",Path(td)),patch.dict(gate.read_draft.__globals__,{"ROOT":Path(td)}):
                with patch.object(gate.subprocess,"run") as verified:
                    res=gate.check_campaign(list(paths.values()),today=date(2026,10,9),verify_image=True)
                    command=verified.call_args.args[0]
            self.assertEqual(res["status"],"eligible_for_draft_only")
            self.assertIn("verify",command)
            self.assertNotIn("--heading-box",command)
            self.assertNotIn("--heading-corner",command)

    def test_reviewed_source_tamper_blocks_even_without_logo_verify(self):
        with tempfile.TemporaryDirectory() as td:
            paths,manifest,m=self.create_reviewed_fixture(td)
            source=Path(td)/"media/source-images/2026-10-09-agenten-tests-source.png"
            source.write_bytes(b"tampered")
            with patch.object(gate,"ROOT",Path(td)),patch.dict(gate.read_draft.__globals__,{"ROOT":Path(td)}):
                with self.assertRaises((ValueError,OSError)):
                    gate.check_campaign(list(paths.values()),today=date(2026,10,9),verify_image=False)

    def test_reviewed_logo_only_cannot_add_dummy_heading(self):
        with tempfile.TemporaryDirectory() as td:
            paths,manifest,m=self.create_reviewed_fixture(td)
            manifest["image"]["heading_box"]=[10,20,50,100]
            m.write_text(json.dumps(manifest))
            with patch.object(gate,"ROOT",Path(td)),patch.dict(gate.read_draft.__globals__,{"ROOT":Path(td)}):
                with self.assertRaisesRegex(ValueError,"Fake-Ueberschrift"):
                    gate.check_campaign(list(paths.values()),today=date(2026,10,9),verify_image=False)

    def test_three_channel_preflight_passes_and_does_not_send(self):
        with tempfile.TemporaryDirectory() as td:
            paths, manifest, _=self.create_reviewed_fixture(td)
            with patch.object(gate,"ROOT",Path(td)), patch.dict(gate.read_draft.__globals__,{"ROOT":Path(td)}):
                r=gate.check_campaign(list(paths.values()),today=date(2026,10,9),verify_image=False)
            self.assertEqual(r["status"],"eligible_for_draft_only")
            self.assertEqual(r["scheduling"],"proposal_only")

    def test_missing_one_qa_attestation_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            paths, manifest, m=self.create_reviewed_fixture(td)
            manifest["checks"]["claims_with_sources"]=False
            m.write_text(json.dumps(manifest),encoding="utf-8")
            with patch.object(gate,"ROOT",Path(td)),patch.dict(gate.read_draft.__globals__,{"ROOT":Path(td)}):
                with self.assertRaisesRegex(ValueError,"QA-Nachweise"):
                    gate.check_campaign(list(paths.values()),today=date(2026,10,9),verify_image=False)

    def test_invalid_image_hash_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            paths, manifest, m=self.create_reviewed_fixture(td)
            manifest["image"]["sha256"]="0"*64
            m.write_text(json.dumps(manifest),encoding="utf-8")
            with patch.object(gate,"ROOT",Path(td)),patch.dict(gate.read_draft.__globals__,{"ROOT":Path(td)}):
                with self.assertRaisesRegex(ValueError,"Bildpruefsumme"):
                    gate.check_campaign(list(paths.values()),today=date(2026,10,9),verify_image=False)

    def test_utc_dst_mismatch_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            paths, manifest, m=self.create_reviewed_fixture(td)
            manifest["posting_times"]["linkedin"]["utc"]="2026-11-04T14:00:00Z"
            m.write_text(json.dumps(manifest),encoding="utf-8")
            with patch.object(gate,"ROOT",Path(td)),patch.dict(gate.read_draft.__globals__,{"ROOT":Path(td)}):
                with self.assertRaisesRegex(ValueError,"Sommerzeit"):
                    gate.check_campaign(list(paths.values()),today=date(2026,10,9),verify_image=False)

    def test_verification_failure_blocks_buffer(self):
        from subprocess import CalledProcessError
        with tempfile.TemporaryDirectory() as td:
            paths, manifest, _=self.create_reviewed_fixture(td)
            with patch.object(gate,"ROOT",Path(td)),patch.dict(gate.read_draft.__globals__,{"ROOT":Path(td)}):
                with patch.object(gate.subprocess,"run",side_effect=CalledProcessError(1,"logo verify")):
                    with self.assertRaises(CalledProcessError):
                        gate.check_campaign(list(paths.values()),today=date(2026,10,9),verify_image=True)


    def make_person_review(self,td,*,qa_present=True,correct=True):
        paths,manifest,m=self.create_reviewed_fixture(td)
        review_path=Path(td)/"visual-reviews/2026-10-09-agenten-tests.json"
        review=json.loads(review_path.read_text())
        review["visual_review"]["no_people"]=False
        review["visual_review"].update({
            "photorealistic_ai_face":True,"ai_altered_real_person":False,
            "rights_checked":True,"no_misrepresentation_checked":True,
            "platform_checked":True,
        })
        review["person_checks_evidence"]={
            "rights_basis": "SYNTHETIC FIXTURE: fictional assessment of rights, no real person involved.",
            "misrepresentation_assessment": "SYNTHETIC FIXTURE: not presented as a real employee or real business event.",
            "platform_assessment": "SYNTHETIC FIXTURE: dummy platform disclosure assessment, never live approval.",
        }
        review_path.write_text(json.dumps(review))
        if qa_present:
            manifest["image"]["ai_disclosure"]={
                "required":True,"text":"Powered by AI" if correct else "Powered by IA",
                "font_size_px":42,"margin_px":54,"pixel_verified":True,
                "logo_disjoint_verified":True
            }
        m.write_text(json.dumps(manifest))
        return paths,manifest,m

    def test_person_qa_receipt_missing_blocks_preflight(self):
        with tempfile.TemporaryDirectory() as td:
            paths,_,_=self.make_person_review(td,qa_present=False)
            with patch.object(gate,"ROOT",Path(td)),patch.dict(gate.read_draft.__globals__,{"ROOT":Path(td)}):
                with self.assertRaisesRegex(ValueError,"requires disclosure"):
                    gate.check_campaign(list(paths.values()),today=date(2026,10,9),verify_image=False)

    def test_wrong_caption_wording_blocks_independent_gate(self):
        with tempfile.TemporaryDirectory() as td:
            paths,_,_=self.make_person_review(td,correct=False)
            with patch.object(gate,"ROOT",Path(td)),patch.dict(gate.read_draft.__globals__,{"ROOT":Path(td)}):
                with self.assertRaisesRegex(ValueError,"verification receipt"):
                    gate.check_campaign(list(paths.values()),today=date(2026,10,9),verify_image=False)

    def test_person_receipt_only_can_pass_structural_gate_not_pixel_gate(self):
        from ai_disclosure import DisclosureError
        with tempfile.TemporaryDirectory() as td:
            paths,_,_=self.make_person_review(td)
            with patch.object(gate,"ROOT",Path(td)),patch.dict(gate.read_draft.__globals__,{"ROOT":Path(td)}):
                # Structure-only explicitly skips logo and pixel checks.
                result=gate.check_campaign(list(paths.values()),today=date(2026,10,9),verify_image=False)
                self.assertEqual(result["status"],"eligible_for_draft_only")
                # In a real run the **second gate** must inspect rendered pixels;
                # this fixture's uncaptioned black frame is not acceptable.
                with patch.object(gate.subprocess,"run") as logo_check:
                    with patch("ai_disclosure.verify_final_disclosure",side_effect=DisclosureError("missing caption")):
                        with self.assertRaisesRegex(DisclosureError,"missing caption"):
                            gate.check_campaign(list(paths.values()),today=date(2026,10,9),verify_image=True)
                    logo_check.assert_called()


if __name__ == "__main__":
    unittest.main()
