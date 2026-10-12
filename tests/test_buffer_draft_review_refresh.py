"""Offline tests for read-only Buffer refresh after Josef edits drafts."""
import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

from scripts import buffer_draft_review_refresh as reader
from test_social_weekly_review import example_report


class BufferLiveReviewRefreshTests(unittest.TestCase):
    def setUp(self):
        self.snapshot = example_report()
        self.items = self.snapshot["buffer_verification"]["posts"]
        self.now = datetime(2026, 10, 19, 8, tzinfo=timezone.utc)

    def query(self, overrides=None):
        overrides = overrides or {}
        n = 0
        calls = []

        def graphql(token, query, variables):
            nonlocal n
            target = reader.TARGETS[n]
            n += 1
            calls.append((token, query, variables))
            old = self.items[target]
            post = {
                "id": old["post_id"], "channelId": old["channel_id"],
                "channelService": target, "status": "draft",
                "dueAt": old["dueAt"], "text": old["text"],
                "assets": [{"type": "image", "source": old["buffer_asset_url"]}],
            }
            post.update(overrides.get(target, {}))
            return {"post": post}
        with mock.patch.dict(os.environ, {"BUFFER_API_KEY": "synthetic-buffer"}), \
             mock.patch.object(reader, "buffer_graphql", side_effect=graphql):
            try:
                result = reader.refresh(self.snapshot, now=self.now)
                error = None
            except (RuntimeError, ValueError) as exc:
                result = None
                error = str(exc)
        return result, error, calls

    def test_identical_live_buffer_copy_never_schedules_anything(self):
        result, error, calls = self.query()
        self.assertIsNone(error)
        self.assertEqual(len(calls), 3)
        self.assertEqual(result["state"], "read_only_drafts_inspected")
        self.assertTrue(result["all_three_future_dated"])
        self.assertFalse(result["any_manual_changes"])
        self.assertTrue(result["editorial_approval_required"])
        self.assertFalse(result["publish_or_schedule_authorized"])
        self.assertTrue(result["no_queue_or_publish"])
        for target, info in result["posts"].items():
            self.assertEqual(info["changes_since_original"], [])
            self.assertEqual(info["current_text"], self.items[target]["text"])
            self.assertEqual(info["current_due_at"], self.items[target]["dueAt"])
            self.assertTrue(info["editable_live_buffer_copy_authoritative"])
            self.assertIsNone(info["buffer_direct_post_url"])
        self.assertTrue(all("InspectOrchestratedPost" in q for _, q, _ in calls))

    def test_modified_text_and_media_are_read_from_buffer_not_old_github(self):
        result, error, _ = self.query({
            "linkedin": {"text": "Josefs neuer Text direkt in Buffer"},
            "facebook": {"assets": [
                {"type": "image", "source": "https://example.com/edited-image.png"}]},
        })
        self.assertIsNone(error)
        self.assertTrue(result["any_manual_changes"])
        self.assertEqual(result["posts"]["linkedin"]["current_text"],
                         "Josefs neuer Text direkt in Buffer")
        self.assertEqual(result["posts"]["linkedin"]["changes_since_original"], ["text"])
        self.assertEqual(result["posts"]["facebook"]["changes_since_original"], ["media"])
        self.assertEqual(result["posts"]["facebook"]["current_image_url"],
                         "https://example.com/edited-image.png")
        self.assertFalse(result["publish_or_schedule_authorized"])

    def test_manual_date_change_preserved_and_visible(self):
        new_time = "2026-10-29T12:00:00Z"
        result, error, _ = self.query({
            "instagram": {"dueAt": new_time},
        })
        self.assertIsNone(error)
        self.assertEqual(result["posts"]["instagram"]["current_due_at"], new_time)
        self.assertEqual(result["posts"]["instagram"]["changes_since_original"], ["time"])
        self.assertTrue(result["all_three_future_dated"])

    def test_manual_due_at_deletion_does_not_schedule(self):
        result, error, _ = self.query({"instagram": {"dueAt": None}})
        self.assertIsNone(error)
        self.assertFalse(result["all_three_future_dated"])
        self.assertFalse(result["posts"]["instagram"]["has_future_date"])
        self.assertIn("time", result["posts"]["instagram"]["changes_since_original"])
        self.assertFalse(result["publish_or_schedule_authorized"])

    def test_expired_date_is_detected(self):
        result, error, _ = self.query({
            "facebook": {"dueAt": "2026-10-18T12:00:00Z"},
        })
        self.assertIsNone(error)
        self.assertFalse(result["all_three_future_dated"])
        self.assertFalse(result["posts"]["facebook"]["has_future_date"])

    def test_queued_or_sent_post_blocks_all_three_review(self):
        for status in ("scheduled", "buffer", "sent", "error"):
            with self.subTest(status=status):
                result, error, calls = self.query({
                    "facebook": {"status": status},
                })
                self.assertIsNone(result)
                self.assertIn("no longer an unpublished", error)
                self.assertLessEqual(len(calls), 2)

    def test_wrong_id_channel_or_network_blocks(self):
        for field, value in (
            ("id", "a" * 24), ("channelId", "unrelated"),
            ("channelService", "instagram"),
        ):
            with self.subTest(field=field):
                result, error, _ = self.query({
                    "linkedin": {field: value},
                })
                self.assertIsNone(result)
                self.assertIn("identity or channel changed", error)

    def test_missing_image_blocks_instead_of_using_stale_github_media(self):
        result, error, _ = self.query({
            "instagram": {"assets": []},
        })
        self.assertIsNone(result)
        self.assertIn("image attachment missing", error)

    def test_missing_credentials_stop_before_api_call(self):
        with mock.patch.dict(os.environ, {"BUFFER_API_KEY": ""}), \
             mock.patch.object(reader, "buffer_graphql",
                               side_effect=AssertionError("No API request")):
            with self.assertRaisesRegex(reader.LiveReviewBlocked, "not configured"):
                reader.refresh(self.snapshot, now=self.now)

    def test_invalid_original_receipt_stops_before_buffer_call(self):
        self.snapshot["buffer_verification"]["status"] = "BLOCKED"
        with mock.patch.dict(os.environ, {"BUFFER_API_KEY": "synthetic"}), \
             mock.patch.object(reader, "buffer_graphql",
                               side_effect=AssertionError("No API request")):
            with self.assertRaisesRegex(ValueError, "no complete Buffer confirmation"):
                reader.refresh(self.snapshot, now=self.now)

    def test_read_only_dispatch_workflow_cannot_write_repo_or_publish(self):
        wf = (Path(__file__).resolve().parents[1]
              / ".github/workflows/buffer-draft-live-review.yml").read_text(encoding="utf-8")
        self.assertIn("workflow_dispatch:", wf)
        self.assertIn("contents: read", wf)
        self.assertNotIn("contents: write", wf)
        self.assertNotIn("pull_request:", wf)
        self.assertNotIn("  push:", wf)
        self.assertNotIn("gh api -X PUT", wf)
        self.assertNotIn("gh api -X POST", wf)
        self.assertIn("scripts/buffer_draft_review_refresh.py", wf)
        self.assertIn("--verified-report", wf)
        self.assertIn("workflow_dispatch", wf)

    def test_module_contains_no_graphql_mutation(self):
        code = Path(reader.__file__).read_text(encoding="utf-8")
        self.assertNotIn("mutation Create", code)
        self.assertNotIn("mutation Edit", code)
        self.assertNotIn("saveToDraft: false", code)
        self.assertNotIn("createPost(", code)
        self.assertNotIn("editPost(", code)


if __name__ == "__main__":
    unittest.main()
