"""PF-02 offline red/green safety checks. No GitHub or Buffer network calls."""

from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from scripts.picturefix import pf02_dated_drafts as p


CLOCK = datetime(2026, 11, 20, 12, tzinfo=timezone.utc)


class PF02Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.event_file = Path(self.temp.name) / "github_event.json"
        self.event = {
            "action": "created",
            "issue": {"number": 64, "title": p.ISSUE_TITLE, "user": {"id": p.AGENT_ID}},
            "comment": {"user": {"id": p.AGENT_ID}, "body": p.COMMANDS["facebook"]},
        }
        self.event_file.write_text(json.dumps(self.event), encoding="utf-8")
        self.env = {
            "GITHUB_REPOSITORY": "derJosef/social-assets",
            "GITHUB_REF": "refs/heads/main",
            "GITHUB_EVENT_NAME": "issue_comment",
            "GITHUB_RUN_ATTEMPT": "1",
            "GITHUB_ACTOR": "derJosef-agents",
            "GITHUB_ACTOR_ID": str(p.AGENT_ID),
            "GITHUB_EVENT_PATH": str(self.event_file),
            "GITHUB_TOKEN": "fake-github-token",
            "BUFFER_API_KEY": "fake-dedicated-picturefix-token",
            "BUFFER_BRAND": "picturefix",
            "GITHUB_RUN_ID": "offline-1",
        }

    def test_all_three_platforms_have_fixed_provenance_and_times(self):
        expected = ["facebook", "instagram", "pinterest"]
        for target in expected:
            with self.subTest(target=target):
                path, record, raw, assets = p.read_pf02(target, now=CLOCK)
                self.assertEqual(record["brand"], "picturefix")
                self.assertEqual(record["campaign_id"], "PF-02")
                self.assertTrue(path.endswith(f"pf02-{target}.json"))
                self.assertEqual(len(assets), 1)
                self.assertTrue(raw)
        self.assertEqual(len(set(p.SPEC[x]["due_at"] for x in expected)), 3)

    def test_wrong_github_identity_or_replayed_job_is_rejected(self):
        for key, value in (("GITHUB_ACTOR", "derJosef"),
                           ("GITHUB_ACTOR_ID", "12345"),
                           ("GITHUB_RUN_ATTEMPT", "2"),
                           ("GITHUB_REF", "refs/heads/branch")):
            with self.subTest(key=key), self.assertRaises(p.PF02Blocked):
                p.verify_event("facebook", {**self.env, key: value})

    def test_bad_issue_or_command_is_rejected(self):
        self.event["comment"]["body"] = "PF01_FACEBOOK_DRAFT_ONLY"
        self.event_file.write_text(json.dumps(self.event), encoding="utf-8")
        with self.assertRaises(p.PF02Blocked):
            p.verify_event("facebook", self.env)

    def test_images_and_copy_are_tamper_checked(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "drafts").mkdir()
            (root / "media/images").mkdir(parents=True)
            original = p.ROOT
            f = original / "drafts/picturefix-pf02-facebook.json"
            img = original / "media/images" / p.SPEC["facebook"]["file"]
            record = json.loads(f.read_text(encoding="utf-8"))
            record["image_sha256"] = "a" * 64
            (root / "drafts/picturefix-pf02-facebook.json").write_text(json.dumps(record), encoding="utf-8")
            import shutil
            shutil.copy2(img, root / "media/images" / img.name)
            with mock.patch.object(p, "ROOT", root), self.assertRaises(p.PF02Blocked):
                p.read_pf02("facebook", now=CLOCK)

    def _simulate(self, bad_due_at: bool = False, existing_receipt: bool = False):
        target = "facebook"
        channel = "picturefix-fb-channel"
        post_id = "a" * 24
        _, record, _, _ = p.read_pf02(target, now=CLOCK)
        sent = []
        receipts = []

        def query(token, operation, vars):
            sent.append(operation)
            if "mutation CreateDatedDraft" in operation:
                return {"createPost": {"post": {
                    "id": post_id, "channelId": channel, "status": "draft",
                    "dueAt": record["due_at_utc"] if not bad_due_at else "2027-01-01T00:00:00Z",
                }}}
            return {"post": {
                "id": post_id, "channelId": channel, "channelService": target,
                "status": "draft", "dueAt": record["due_at_utc"],
                "text": record["text"], "shareMode": "customScheduled",
                "schedulingType": "automatic",
                "assets": [{"type": "image", "source": record["media"]["images"][0]["url"]}],
            }}

        def put(token, receipt, data, message, sha=None):
            receipts.append(dict(data))
            return "receipt-sha" + str(len(receipts))

        with mock.patch.object(p.bridge, "discover_picturefix_channels", return_value={target: channel}), \
             mock.patch.object(p.bridge, "verify_media_access"), \
             mock.patch.object(p.bridge, "verify_picturefix_image_bytes"), \
             mock.patch.object(p.bridge, "normalize_picturefix_api_key", return_value="fake-token"):
            p.send(target, env=self.env, query=query, now=CLOCK,
                   get_receipt=(lambda *a: {} if existing_receipt else None),
                   put_receipt=put)
        return sent, receipts

    def test_live_path_calls_one_create_and_independently_reads_draft(self):
        sent, receipts = self._simulate()
        self.assertEqual(len(sent), 2)
        self.assertIn("saveToDraft: true", sent[0])
        self.assertIn("mode: customScheduled", sent[0])
        self.assertNotIn("saveToDraft: false", sent[0])
        self.assertEqual(receipts[0]["state"], "pending_manual_reconciliation_on_failure")
        self.assertEqual(receipts[-1]["state"], "verified_prescheduled_draft_not_queued_with_image")
        self.assertEqual(receipts[-1]["buffer_status"], "draft")

    def test_existing_receipt_prevents_duplicate_buffer_mutation(self):
        with self.assertRaises(p.PF02Blocked):
            self._simulate(existing_receipt=True)

    def test_mismatched_create_response_stops_with_pending_receipt(self):
        with self.assertRaises(p.PF02Blocked):
            self._simulate(bad_due_at=True)


if __name__ == "__main__":
    unittest.main()
