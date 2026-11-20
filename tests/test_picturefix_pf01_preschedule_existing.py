"""Offline safety regression tests, picked up by unittest discover."""
import base64
from datetime import datetime, timezone
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.picturefix import pf01_preschedule_existing as p


def sample_record():
    return {
        "brand": "picturefix", "format_version": 3,
        "target": "facebook", "text": "Approved PF01 text",
        "image_sha256": "a" * 64,
        "media": {"images": [{"url": "https://example.test/image.png"}]},
    }


def sample_receipt(record, raw, *, status="draft"):
    return {
        "state": "verified_unpublished_draft_with_image",
        "draft_file": "drafts/picturefix-pf01-facebook.json",
        "target": "facebook",
        "draft_sha256": hashlib.sha256(raw).hexdigest(),
        "original_image_sha256": record["image_sha256"],
        "buffer_asset_url": record["media"]["images"][0]["url"],
        "buffer_status": status, "buffer_due_at": None,
        "buffer_post_id": "a" * 24, "channel_id": "b" * 24,
    }


class PictureFixPF01PrescheduleSafety(unittest.TestCase):
    def test_exact_utc_windows_and_only_existing_edit(self):
        self.assertEqual(p.TIMES, {
            "facebook": "2026-11-20T17:00:00Z",
            "instagram": "2026-11-20T20:00:00Z",
            "pinterest": "2026-11-23T09:00:00Z",
        })
        self.assertIn("editPost(", p.EDIT)
        for excluded in ("createPost(", "shareNow", "assets:", "text:"):
            self.assertNotIn(excluded, p.EDIT)
        self.assertIn("saveToDraft: true", p.EDIT)

    def test_original_receipt_base64_with_github_line_breaks(self):
        record = sample_record()
        raw = (json.dumps(record) + "\n").encode()
        original = sample_receipt(record, raw)
        encoded = base64.b64encode(json.dumps(original).encode()).decode()
        wrapped = "\n".join(encoded[i:i+60] for i in range(0, len(encoded), 60))
        with patch.object(p.bridge, "receipt_path", return_value="receipt.json"):
            actual = p.load_verified_original("secret", "facebook", record, raw,
                                              get_receipt=lambda _k, _f: {"content": wrapped})
        self.assertEqual(actual, original)

    def test_original_receipt_rejects_changed_status(self):
        record = sample_record()
        raw = json.dumps(record).encode()
        bad = sample_receipt(record, raw, status="scheduled")
        encoded = base64.b64encode(json.dumps(bad).encode()).decode()
        with patch.object(p.bridge, "receipt_path", return_value="receipt.json"):
            with self.assertRaises(p.PrescheduleBlocked):
                p.load_verified_original("secret", "facebook", record, raw,
                                         get_receipt=lambda _k, _f: {"content": encoded})

    def test_post_readback_requires_original_image_text_draft_and_time(self):
        record = sample_record()
        receipt = sample_receipt(record, json.dumps(record).encode())
        post = {
            "id": "a" * 24, "channelId": "b" * 24,
            "channelService": "facebook", "status": "draft",
            "text": record["text"], "dueAt": "2026-11-20T17:00:00.000Z",
            "shareMode": "customScheduled", "schedulingType": "automatic",
            "assets": [{"type": "image", "source": record["media"]["images"][0]["url"]}],
        }
        p.verify_post(post, "facebook", record, receipt, due_at=p.TIMES["facebook"])
        for key, wrong in (("status", "buffer"), ("text", "changed"),
                           ("channelId", "wrong"), ("dueAt", "2026-11-21T17:00:00Z")):
            with self.subTest(key=key), self.assertRaises(p.PrescheduleBlocked):
                p.verify_post({**post, key: wrong}, "facebook", record, receipt,
                              due_at=p.TIMES["facebook"])
        with self.assertRaises(p.PrescheduleBlocked):
            p.verify_post({**post, "assets": []}, "facebook", record, receipt,
                          due_at=p.TIMES["facebook"])

    def test_event_requires_exact_actor_issue_body_first_attempt(self):
        event = {"action": "created", "issue": {"number": 81,
                 "title": p.ISSUE_TITLE, "user": {"id": p.AGENT_ID}},
                 "comment": {"user": {"id": p.AGENT_ID},
                             "body": p.COMMANDS["facebook"]}}
        with tempfile.TemporaryDirectory() as tmpdir:
            event_path = Path(tmpdir) / "event.json"
            event_path.write_text(json.dumps(event))
            env = {"GITHUB_REPOSITORY": "derJosef/social-assets",
                   "GITHUB_REF": "refs/heads/main", "GITHUB_EVENT_NAME": "issue_comment",
                   "GITHUB_RUN_ATTEMPT": "1", "GITHUB_ACTOR": p.AGENT_LOGIN,
                   "GITHUB_ACTOR_ID": str(p.AGENT_ID), "GITHUB_EVENT_PATH": str(event_path)}
            p.verify_event("facebook", env)
            for key, wrong in (("GITHUB_ACTOR", "derJosef"),
                               ("GITHUB_RUN_ATTEMPT", "2"),
                               ("GITHUB_REF", "refs/heads/feature")):
                with self.subTest(key=key), self.assertRaises(p.PrescheduleBlocked):
                    p.verify_event("facebook", {**env, key: wrong})
            event["comment"]["body"] = p.COMMANDS["instagram"]
            event_path.write_text(json.dumps(event))
            with self.assertRaises(p.PrescheduleBlocked):
                p.verify_event("facebook", env)

    def test_near_or_past_date_blocks_before_any_mutation(self):
        with patch.object(p, "verify_event") as verified_event, \
             patch.object(p.bridge, "buffer_graphql") as api:
            with self.assertRaises(p.PrescheduleBlocked):
                p.live_preschedule("facebook", env={},
                                   now=datetime(2026, 11, 20, 17, 0, tzinfo=timezone.utc))
            verified_event.assert_called_once()
            api.assert_not_called()


if __name__ == "__main__":
    unittest.main()
