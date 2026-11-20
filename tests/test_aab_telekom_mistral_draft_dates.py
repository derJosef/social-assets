"""Offline proof that today's News correction touches three draft times only."""

from __future__ import annotations

import json
import tempfile
import unittest
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

from scripts import aab_telekom_mistral_draft_dates as m


def sample(channel: str) -> dict:
    p = m.POSTS[channel]
    return {
        "id": p["id"], "channelId": p["channel_id"],
        "channelService": channel, "status": "draft",
        "dueAt": p["old"].replace("Z", ".000Z"),
        "shareMode": "customScheduled", "schedulingType": "automatic",
        "text": f"Josefs redaktioneller bestehender Text für {channel}. " * 6,
        "tags": [{"id": "existing-tag"}],
        "assets": [{"type": "image", "source": m.NEW_IMAGE_URL,
                    "mimeType": "image/png"}],
        "metadata": {"__typename": "InstagramPostMetadata", "type": "post"}
        if channel == "instagram" else None,
    }


class DraftDatesTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        event = Path(self.tmp.name) / "event.json"
        event.write_text(json.dumps({
            "action": "created",
            "issue": {"number": m.TRIGGER_PR,
                      "pull_request": {"url": "https://github.com/example/pr"},
                      "user": {"id": m.AGENT_ID}},
            "comment": {"body": m.TRIGGER, "user": {"id": m.AGENT_ID}},
        }), encoding="utf-8")
        self.env = {
            "GITHUB_REPOSITORY": "derJosef/social-assets",
            "GITHUB_REF": "refs/heads/main", "GITHUB_EVENT_NAME": "issue_comment",
            "GITHUB_RUN_ATTEMPT": "1", "GITHUB_ACTOR": "derJosef-agents",
            "GITHUB_ACTOR_ID": str(m.AGENT_ID),
            "GITHUB_EVENT_PATH": str(event), "GITHUB_RUN_ID": "synthetic-run",
            "BUFFER_API_KEY": "synthetic", "GITHUB_TOKEN": "synthetic",
        }
        self.posts = {c: sample(c) for c in m.POSTS}
        self.receipts = {}
        self.edits = []
        self.writes = []

    def get(self, _token, query, variables):
        channel = next(c for c, p in m.POSTS.items() if p["id"] == variables["id"])
        if "editPost(" in query:
            self.edits.append(deepcopy(variables))
            self.posts[channel]["dueAt"] = variables["dueAt"].replace("Z", ".000Z")
            return {"editPost": {"__typename": "PostActionSuccess", "post": {
                "id": variables["id"], "channelId": m.POSTS[channel]["channel_id"],
                "status": "draft", "dueAt": self.posts[channel]["dueAt"]}}}
        return {"post": deepcopy(self.posts[channel])}

    def fetch_receipt(self, _token, path):
        return self.receipts.get(path)

    def put_receipt(self, _token, path, record, _message, sha=None):
        self.writes.append((path, record["state"], sha))
        self.receipts[path] = deepcopy(record)
        return f"fake-sha-{len(self.writes)}"

    def run_move(self):
        m.live_move(get=self.get, get_receipt=self.fetch_receipt,
                    write_receipt=self.put_receipt, env=self.env,
                    now=datetime(2026, 11, 20, 9, 30, tzinfo=timezone.utc))

    def test_all_three_existing_drafts_moved_and_everything_else_intact(self):
        original = deepcopy(self.posts)
        self.run_move()
        self.assertEqual(len(self.edits), 3)
        self.assertEqual(set(edit["id"] for edit in self.edits),
                         {p["id"] for p in m.POSTS.values()})
        for channel, p in m.POSTS.items():
            after = self.posts[channel]
            self.assertTrue(m.same_instant(after["dueAt"], p["new"]))
            after["dueAt"] = original[channel]["dueAt"]
            self.assertEqual(after, original[channel])
            self.assertEqual(self.receipts[m.receipt_path(channel)]["state"],
                             "verified_existing_draft_due_at_only")
        self.assertEqual(self.receipts[m.BATCH]["state"],
                         "verified_three_draft_dates_only_no_publish")

    def test_no_publish_create_or_content_variables(self):
        m.contract(now=datetime(2026, 11, 20, 9, 30, tzinfo=timezone.utc))
        self.assertIn("saveToDraft: true", m.EDIT)
        self.assertNotIn("createPost", m.EDIT)
        self.assertNotIn("shareNow", m.EDIT)
        self.assertNotIn("text:", m.EDIT)
        self.assertNotIn("assets:", m.EDIT)
        self.run_move()
        for variables in self.edits:
            self.assertEqual(set(variables), {"id", "dueAt"})

    def test_wrong_actor_rejected_before_any_buffer_mutation(self):
        self.env["GITHUB_ACTOR"] = "derJosef"
        with self.assertRaises(m.Blocked):
            self.run_move()
        self.assertEqual(self.edits, [])
        self.assertEqual(self.writes, [])

    def test_changed_status_media_time_or_channel_rejected(self):
        for key, value in [
            ("status", "scheduled"),
            ("dueAt", "2026-12-02T17:00:00Z"),
            ("channelId", "unknown"),
            ("shareMode", "addToQueue"),
            ("assets", [{"type": "image", "source": "unapproved"}]),
            ("text", "short"),
        ]:
            with self.subTest(key=key):
                old = deepcopy(self.posts["facebook"])
                self.posts["facebook"][key] = value
                with self.assertRaises(m.Blocked):
                    self.run_move()
                self.assertFalse(self.edits)
                self.assertFalse(self.writes)
                self.posts["facebook"] = old

    def test_receipt_prevents_repeated_mutation(self):
        self.receipts[m.BATCH] = {"state": "already_reserved"}
        with self.assertRaises(m.Blocked):
            self.run_move()
        self.assertEqual(self.edits, [])

    def test_time_too_close_rejected(self):
        with self.assertRaises(m.Blocked):
            m.contract(now=datetime(2026, 11, 20, 11, 41, tzinfo=timezone.utc))

    def test_content_drift_after_reservation_stops_next_edit(self):
        original_get = self.get
        reads = {c: 0 for c in m.POSTS}

        def drifting_get(token, query, variables):
            channel = next(c for c, p in m.POSTS.items() if p["id"] == variables["id"])
            if "editPost(" not in query:
                reads[channel] += 1
                if channel == "facebook" and reads[channel] == 2:
                    self.posts[channel]["text"] += "Extern geändert"
            return original_get(token, query, variables)

        with self.assertRaises(m.Blocked):
            m.live_move(get=drifting_get, get_receipt=self.fetch_receipt,
                        write_receipt=self.put_receipt, env=self.env,
                        now=datetime(2026, 11, 20, 9, 30, tzinfo=timezone.utc))
        self.assertEqual(self.edits, [])
        self.assertEqual(self.receipts[m.BATCH]["state"],
                         "pending_manual_reconciliation_on_failure")


if __name__ == "__main__":
    unittest.main()
