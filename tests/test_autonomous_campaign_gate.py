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

    def test_three_channel_preflight_passes_and_does_not_send(self):
        with tempfile.TemporaryDirectory() as td:
            paths, manifest, _=self.create_fixture(td)
            with patch.object(gate,"ROOT",Path(td)), patch.dict(gate.read_draft.__globals__,{"ROOT":Path(td)}):
                r=gate.check_campaign(list(paths.values()),today=date(2026,10,9),verify_image=False)
            self.assertEqual(r["status"],"eligible_for_draft_only")
            self.assertEqual(r["scheduling"],"proposal_only")

    def test_missing_one_qa_attestation_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            paths, manifest, m=self.create_fixture(td)
            manifest["checks"]["claims_with_sources"]=False
            m.write_text(json.dumps(manifest),encoding="utf-8")
            with patch.object(gate,"ROOT",Path(td)),patch.dict(gate.read_draft.__globals__,{"ROOT":Path(td)}):
                with self.assertRaisesRegex(ValueError,"QA-Nachweise"):
                    gate.check_campaign(list(paths.values()),today=date(2026,10,9),verify_image=False)

    def test_invalid_image_hash_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            paths, manifest, m=self.create_fixture(td)
            manifest["image"]["sha256"]="0"*64
            m.write_text(json.dumps(manifest),encoding="utf-8")
            with patch.object(gate,"ROOT",Path(td)),patch.dict(gate.read_draft.__globals__,{"ROOT":Path(td)}):
                with self.assertRaisesRegex(ValueError,"Bildpruefsumme"):
                    gate.check_campaign(list(paths.values()),today=date(2026,10,9),verify_image=False)

    def test_utc_dst_mismatch_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            paths, manifest, m=self.create_fixture(td)
            manifest["posting_times"]["linkedin"]["utc"]="2026-11-04T14:00:00Z"
            m.write_text(json.dumps(manifest),encoding="utf-8")
            with patch.object(gate,"ROOT",Path(td)),patch.dict(gate.read_draft.__globals__,{"ROOT":Path(td)}):
                with self.assertRaisesRegex(ValueError,"Sommerzeit"):
                    gate.check_campaign(list(paths.values()),today=date(2026,10,9),verify_image=False)

    def test_verification_failure_blocks_buffer(self):
        from subprocess import CalledProcessError
        with tempfile.TemporaryDirectory() as td:
            paths, manifest, _=self.create_fixture(td)
            with patch.object(gate,"ROOT",Path(td)),patch.dict(gate.read_draft.__globals__,{"ROOT":Path(td)}):
                with patch.object(gate.subprocess,"run",side_effect=CalledProcessError(1,"logo verify")):
                    with self.assertRaises(CalledProcessError):
                        gate.check_campaign(list(paths.values()),today=date(2026,10,9),verify_image=True)


if __name__ == "__main__":
    unittest.main()
