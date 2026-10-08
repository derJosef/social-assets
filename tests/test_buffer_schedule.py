"""Offline regression tests for the separate Buffer scheduling approval gate."""
import hashlib
import importlib.util
import json
import os
import sys
import tempfile
import types
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch


# The existing buffer_draft.py is imported next to buffer_schedule.py on GitHub.
# For isolated offline tests, substitute only its stable helper API.
helper = types.ModuleType("buffer_draft")
helper.REPOSITORY = "derJosef/social-assets"
helper.receipt_path = lambda p: f"delivery-receipts/{hashlib.sha256(p.encode()).hexdigest()[:24]}.json"
helper.channel_preference = lambda target: ""
helper.resolve_channel = lambda token, target, preferred_id="": "verified-channel"
helper.fetch_receipt = lambda token, path: None
helper.put_receipt = lambda token, path, data, message, sha=None: "receipt-sha"
helper.buffer_graphql = lambda *args: {}
sys.modules["buffer_draft"] = helper
spec = importlib.util.spec_from_file_location("buffer_schedule_under_test", Path(__file__).resolve().parents[1] / "scripts" / "buffer_schedule.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
sys.modules.pop("buffer_draft", None)


class ScheduleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        module.ROOT = self.root
        for d in ("ready-for-buffer", "delivery-receipts", "ready-to-schedule"):
            (self.root / d).mkdir()
        self.draft_file = "ready-for-buffer/test-linkedin.json"
        self.request_file = "ready-to-schedule/test-linkedin.json"
        draft = {"format_version": 1, "target": "linkedin", "text": "Testtext ohne Geheimnisse"}
        raw = (json.dumps(draft) + "\n").encode()
        (self.root / self.draft_file).write_bytes(raw)
        delivery = {
            "state": "draft_created", "draft_file": self.draft_file,
            "target": "linkedin", "draft_sha256": hashlib.sha256(raw).hexdigest(),
            "buffer_post_id": "existing-draft-id",
        }
        (self.root / helper.receipt_path(self.draft_file)).write_text(json.dumps(delivery))
        self.request = {
            "format_version": 1, "target": "linkedin", "draft_file": self.draft_file,
            "publish_at_utc": "2026-10-09T13:00:00Z", "approved_for_scheduling": True,
        }
        self.now = datetime(2026, 10, 8, 16, 0, tzinfo=timezone.utc)
        self.write_request()

    def write_request(self):
        (self.root / self.request_file).write_text(json.dumps(self.request))

    def test_valid_approved_request(self):
        i = module.inspect_request(self.request_file, self.now)
        self.assertEqual(i["post_id"], "existing-draft-id")
        self.assertEqual(i["due_at"], "2026-10-09T13:00:00Z")

    def test_explicit_approval_required(self):
        self.request["approved_for_scheduling"] = False
        self.write_request()
        with self.assertRaisesRegex(ValueError, "freigabe"):
            module.inspect_request(self.request_file, self.now)

    def test_past_time_rejected(self):
        self.request["publish_at_utc"] = "2026-10-08T16:01:00Z"
        self.write_request()
        with self.assertRaisesRegex(ValueError, "Zukunft"):
            module.inspect_request(self.request_file, self.now)

    def test_timestamp_must_be_utc(self):
        self.request["publish_at_utc"] = "2026-10-09T15:00:00+02:00"
        self.write_request()
        with self.assertRaisesRegex(ValueError, "UTC"):
            module.inspect_request(self.request_file, self.now)

    def test_path_escape_rejected(self):
        with self.assertRaises(ValueError):
            module.inspect_request("ready-to-schedule/../ready-for-buffer/test-linkedin.json", self.now)

    def test_draft_change_rejected(self):
        (self.root / self.draft_file).write_text('{"target":"linkedin","text":"geändert"}')
        with self.assertRaisesRegex(ValueError, "bestätigter"):
            module.inspect_request(self.request_file, self.now)

    def test_wrong_channel_rejected(self):
        self.request["target"] = "facebook"
        self.write_request()
        with self.assertRaisesRegex(ValueError, "Kanal"):
            module.inspect_request(self.request_file, self.now)

    def test_existing_schedule_receipt_prevents_replay(self):
        info = module.inspect_request(self.request_file, self.now)
        with patch.dict(os.environ, {"GITHUB_REPOSITORY": helper.REPOSITORY, "GITHUB_REF": "refs/heads/main", "BUFFER_API_KEY": "dummy", "GITHUB_TOKEN": "dummy"}), patch.object(module, "buffer_graphql", return_value={"post": {"id": "existing-draft-id", "channelId": "verified-channel", "status": "draft", "text": "Testtext ohne Geheimnisse"}}), patch.object(module, "fetch_receipt", return_value={"state": "scheduled"}), patch.object(module, "put_receipt") as write:
            with self.assertRaisesRegex(RuntimeError, "existiert"):
                module.schedule(info)
            write.assert_not_called()

    def test_schedule_edits_same_post_without_reupload(self):
        info = module.inspect_request(self.request_file, self.now)
        actions = [
            {"post": {"id": "existing-draft-id", "channelId": "verified-channel", "status": "draft", "text": "Testtext ohne Geheimnisse"}},
            {"editPost": {"post": {"id": "existing-draft-id", "channelId": "verified-channel", "status": "buffer", "dueAt": "2026-10-09T13:00:00Z"}}},
        ]
        with patch.dict(os.environ, {"GITHUB_REPOSITORY": helper.REPOSITORY, "GITHUB_REF": "refs/heads/main", "BUFFER_API_KEY": "dummy", "GITHUB_TOKEN": "dummy"}), patch.object(module, "buffer_graphql", side_effect=actions) as api, patch.object(module, "fetch_receipt", return_value=None), patch.object(module, "put_receipt", return_value="sha") as receipt:
            module.schedule(info)
            self.assertEqual(api.call_count, 2)
            self.assertEqual(api.call_args.args[2], {"id": "existing-draft-id", "dueAt": "2026-10-09T13:00:00Z", "text": "Testtext ohne Geheimnisse"})
            self.assertEqual(receipt.call_count, 2)
            self.assertEqual(receipt.call_args.args[2]["state"], "scheduled")


if __name__ == "__main__":
    unittest.main()
