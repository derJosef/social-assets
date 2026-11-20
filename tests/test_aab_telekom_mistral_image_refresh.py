"""Offline guards: exactly 3 existing dated Buffer drafts, image-only edits."""

from __future__ import annotations

import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

from scripts import aab_telekom_mistral_image_refresh as m


def post(channel: str) -> dict:
    fixed = m.POSTS[channel]
    metadata = {
        "linkedin": None,
        "facebook": {"__typename": "FacebookPostMetadata", "type": "post",
                     "firstComment": None, "linkAttachment": None},
        "instagram": {"__typename": "InstagramPostMetadata", "type": "post",
                      "firstComment": None, "link": None, "geolocation": None,
                      "shouldShareToFeed": True, "isAiGenerated": False},
    }[channel]
    return {
        "id": fixed["id"], "channelId": fixed["channel_id"],
        "channelService": channel, "status": "draft", "dueAt": fixed["due_at"],
        "text": "A live Buffer text, potentially manually revised by Josef. " * 5,
        "shareMode": "customScheduled", "schedulingType": "automatic",
        "tags": [{"id": "tag-current"}],
        "assets": [{"type": "image", "source": m.OLD_IMAGE_URL,
                    "mimeType": "image/png"}], "metadata": metadata,
    }


class TestMistralImageRefresh(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.event = Path(self.tmp.name) / "event.json"
        self.event.write_text(json.dumps({
            "action": "created",
            "issue": {"number": 77, "pull_request": {"url": "test"},
                      "user": {"id": m.AGENT_ID}},
            "comment": {"body": m.TRIGGER, "user": {"id": m.AGENT_ID}},
        }), encoding="utf-8")
        self.env = {
            "GITHUB_REPOSITORY": "derJosef/social-assets",
            "GITHUB_REF": "refs/heads/main",
            "GITHUB_EVENT_NAME": "issue_comment",
            "GITHUB_RUN_ATTEMPT": "1",
            "GITHUB_ACTOR": "derJosef-agents",
            "GITHUB_ACTOR_ID": str(m.AGENT_ID),
            "GITHUB_EVENT_PATH": str(self.event),
            "GITHUB_RUN_ID": "999999",
            "BUFFER_API_KEY": "synthetic-not-real",
            "GITHUB_TOKEN": "synthetic-not-real",
        }
        self.posts = {c: post(c) for c in m.POSTS}
        self.receipts = {}
        self.writes = []
        self.edit_calls = []

    def get(self, _token, query, vars):
        name = next(k for k, v in m.POSTS.items() if v["id"] == vars["id"])
        if "editPost(" in query:
            self.edit_calls.append((name, deepcopy(vars)))
            self.posts[name]["assets"][0]["source"] = vars["assets"][0]["image"]["url"]
            return {"editPost": {"__typename": "PostActionSuccess",
                                 "post": {"id": vars["id"]}}}
        return {"post": deepcopy(self.posts[name])}

    def get_receipt(self, _token, name):
        return self.receipts.get(name)

    def write_receipt(self, _token, name, record, _message, sha=None):
        self.writes.append((name, record["state"], sha))
        self.receipts[name] = deepcopy(record)
        return "sha-for-" + name

    def run_edit(self):
        with patch.object(m, "verify_image"):
            m.live_edit(get=self.get, get_receipt=self.get_receipt,
                        write_receipt=self.write_receipt, env=self.env)

    def test_exactly_three_image_edits_preserve_all_other_fields(self):
        before = deepcopy(self.posts)
        self.run_edit()
        self.assertEqual(set(c for c, _ in self.edit_calls), set(m.POSTS))
        for channel, vars in self.edit_calls:
            self.assertEqual(vars["text"], before[channel]["text"])
            self.assertEqual(vars["dueAt"], before[channel]["dueAt"])
            self.assertEqual(vars["tagIds"], ["tag-current"])
            self.assertEqual(vars["assets"][0]["image"]["url"], m.NEW_IMAGE_URL)
            updated = self.posts[channel]
            old = before[channel]
            updated["assets"] = old["assets"]
            self.assertEqual(updated, old)
            self.assertEqual(self.receipts[m.receipt_path(channel)]["state"],
                             "verified_existing_draft_image_only")
        self.assertEqual(self.receipts[m.BATCH_RECEIPT]["state"],
                         "verified_three_existing_drafts_image_only")

    def test_buffer_millisecond_timestamp_is_same_instant_and_preserved(self):
        for channel in m.POSTS:
            self.posts[channel]["dueAt"] = m.POSTS[channel]["due_at"].replace(
                "Z", ".000Z")
        before = deepcopy(self.posts)
        self.run_edit()
        self.assertEqual(len(self.edit_calls), 3)
        for channel, vars in self.edit_calls:
            self.assertEqual(vars["dueAt"], before[channel]["dueAt"])
            self.assertEqual(self.posts[channel]["dueAt"], before[channel]["dueAt"])

    def test_time_change_or_missing_zone_is_still_rejected(self):
        self.assertFalse(m.same_instant("2026-12-09T16:00:00.000Z",
                                        "2026-12-09T15:00:00Z"))
        self.assertFalse(m.same_instant("2026-12-09T15:00:00",
                                        "2026-12-09T15:00:00Z"))

    def test_no_schedule_publish_or_create_mutation(self):
        self.assertIn("editPost(", m.EDIT)
        self.assertNotIn("createPost", m.EDIT)
        self.assertNotIn("shareNow", m.EDIT)
        self.assertNotIn("saveToDraft: false", m.EDIT)
        self.assertIn("saveToDraft: true", m.EDIT)
        self.assertIn("mode: customScheduled", m.EDIT)
        self.assertIn("dueAt: $dueAt", m.EDIT)
        self.assertEqual(len(m.POSTS), 3)
        self.assertTrue(m.NEW_IMAGE_URL.startswith(
            "https://raw.githubusercontent.com/derJosef/social-assets/" + m.IMAGE_COMMIT))

    def test_drift_blocks_before_any_mutation(self):
        for label, key, changed in (
            ("published", "status", "scheduled"),
            ("new time", "dueAt", "2026-12-10T15:00:00Z"),
            ("wrong image", "assets", [{"type": "image", "source": "changed"}]),
            ("wrong account", "channelId", "another-channel"),
            ("missing tags", "tags", None),
            ("short text", "text", "hello"),
            ("wrong mode", "shareMode", "addToQueue"),
        ):
            with self.subTest(label=label):
                changed_post = self.posts["linkedin"]
                original = deepcopy(changed_post)
                changed_post[key] = changed
                with self.assertRaises(m.DraftImageBlocked):
                    self.run_edit()
                self.assertFalse(self.edit_calls)
                self.assertFalse(self.writes)
                self.posts["linkedin"] = original

    def test_wrong_event_blocks_before_buffer_access(self):
        self.env["GITHUB_ACTOR"] = "derJosef"
        with self.assertRaises(m.DraftImageBlocked):
            self.run_edit()
        self.assertFalse(self.edit_calls)
        self.assertFalse(self.writes)

    def test_duplicate_receipt_prevents_second_run(self):
        self.receipts[m.BATCH_RECEIPT] = {"state": "already_reserved"}
        with self.assertRaises(m.DraftImageBlocked):
            self.run_edit()
        self.assertFalse(self.edit_calls)
        self.assertFalse(self.writes)

    def test_user_changed_text_is_preserved_not_reverted(self):
        self.posts["facebook"]["text"] = "Josefs own improved live Buffer copy. " * 6
        self.run_edit()
        facebook = next(x[1] for x in self.edit_calls if x[0] == "facebook")
        self.assertEqual(facebook["text"], "Josefs own improved live Buffer copy. " * 6)


if __name__ == "__main__":
    unittest.main()
