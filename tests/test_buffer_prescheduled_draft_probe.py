"""Never access Buffer or GitHub; mock the one-time scheduled-draft probe."""

import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import buffer_prescheduled_draft_probe as probe


def valid_environment():
    return {
        "GITHUB_REPOSITORY": "derJosef/social-assets",
        "GITHUB_REF": "refs/heads/main",
        "GITHUB_EVENT_NAME": "workflow_dispatch",
        "GITHUB_ACTOR": "derJosef",
        "GITHUB_RUN_ATTEMPT": "1",
        "PROBE_CONFIRMATION": probe.CONFIRMATION,
        "GITHUB_RUN_ID": "12345",
        "GITHUB_TOKEN": "test-github-token",
        "BUFFER_API_KEY": "test-buffer-token",
    }


class PrescheduledDraftProbeTests(unittest.TestCase):
    def setUp(self):
        self.env = valid_environment()
        self.now = datetime(2026, 10, 11, 21, 0, tzinfo=timezone.utc)

    def test_guard_allows_only_owner_single_manual_main_run(self):
        probe.check_execution_guard(self.env)
        substitutions = {
            "GITHUB_REPOSITORY": "other/other",
            "GITHUB_REF": "refs/heads/feature/unsafe",
            "GITHUB_EVENT_NAME": "push",
            "GITHUB_ACTOR": "not-josef",
            "GITHUB_RUN_ATTEMPT": "2",
            "PROBE_CONFIRMATION": "yes",
            "GITHUB_RUN_ID": "bad",
            "GITHUB_TOKEN": "",
            "BUFFER_API_KEY": "",
        }
        for name, bad in substitutions.items():
            with self.subTest(field=name):
                env = {**self.env, name: bad}
                with self.assertRaisesRegex(RuntimeError, "Sicherheitssperre|fehlt"):
                    probe.check_execution_guard(env)

    def test_future_due_time_is_120_days_away(self):
        self.assertEqual(probe.future_time(self.now), "2027-02-08T12:00:00Z")
        with self.assertRaises(ValueError):
            probe.future_time(datetime(2026, 10, 11))

    def test_accepts_equivalent_iso_date_and_no_queue_state(self):
        expected = probe.future_time(self.now)
        record = {"id": "a", "channelId": "linkedin-channel", "status": "draft",
                  "dueAt": "2027-02-08T12:00:00.000+00:00"}
        self.assertTrue(probe.verified_post(record, post_id="a", channel_id="linkedin-channel", due_at=expected))
        for changed in (
            {"status": "scheduled"}, {"status": "buffer"}, {"dueAt": None},
            {"dueAt": "2027-02-09T12:00:00Z"}, {"dueAt": "not-a-date"},
            {"channelId": "wrong"}, {"id": "wrong"},
        ):
            with self.subTest(changed=changed):
                self.assertFalse(probe.verified_post({**record, **changed}, post_id="a",
                                                     channel_id="linkedin-channel", due_at=expected))

    def test_dangerous_operations_are_not_present(self):
        source = Path(probe.__file__).read_text(encoding="utf-8")
        self.assertEqual(source.count("  createPost(input:"), 1)
        self.assertIn("    saveToDraft: true", probe.CREATE_PRESET_DRAFT)
        self.assertIn("    mode: customScheduled", probe.CREATE_PRESET_DRAFT)
        self.assertIn("    dueAt: $dueAt", probe.CREATE_PRESET_DRAFT)
        for forbidden in ("editPost(", "deletePost(", "shareNow", "saveToDraft: false"):
            self.assertNotIn(forbidden, probe.CREATE_PRESET_DRAFT + probe.READ_POST)

    def test_live_workflow_is_manual_owner_only_and_offline_ci_is_readonly(self):
        root = Path(__file__).resolve().parents[1]
        live = (root / ".github/workflows/buffer-prescheduled-draft-probe.yml").read_text()
        ci = (root / ".github/workflows/buffer-prescheduled-draft-probe-offline-pr.yml").read_text()
        self.assertIn("  workflow_dispatch:", live)
        self.assertIn("github.actor == 'derJosef'", live)
        self.assertIn("github.ref == 'refs/heads/main'", live)
        self.assertIn("github.run_attempt == 1", live)
        self.assertIn("buffer-drafts-single-flight", live)
        self.assertIn("contents: write", live)
        self.assertIn("python3 -B scripts/buffer_prescheduled_draft_probe.py --live", live)
        for trigger in ("  push:", "  pull_request:", "  schedule:", "  workflow_run:"):
            self.assertNotIn(trigger, live)
        self.assertIn("  pull_request:", ci)
        self.assertIn("contents: read", ci)
        self.assertNotIn("secrets.BUFFER_API_KEY", ci)
        self.assertNotIn("--live", ci)

    def test_without_live_flag_is_noop(self):
        with patch.object(sys, "argv", ["buffer_prescheduled_draft_probe.py"]), \
             patch.object(probe, "live_probe") as live:
            self.assertEqual(probe.main(), 0)
            live.assert_not_called()

    def test_duplicate_receipt_blocks_before_any_buffer_call(self):
        with patch.object(probe, "fetch_receipt", return_value={"state": "pending"}), \
             patch.object(probe, "resolve_channel") as channels, \
             patch.object(probe, "buffer_graphql") as buffer, \
             patch.object(probe, "put_receipt") as receipt:
            with self.assertRaisesRegex(RuntimeError, "bereits reserviert"):
                probe.live_probe(self.env, now=self.now)
        channels.assert_not_called()
        buffer.assert_not_called()
        receipt.assert_not_called()

    def run_mock_probe(self, *, create_status="draft", create_due=None, read_status="draft", read_due=None):
        events = []
        due = probe.future_time(self.now)
        created = {"id": "probe-post-123", "channelId": "linkedin-channel", "status": create_status,
                   "dueAt": create_due if create_due is not None else due}
        read = {"id": "probe-post-123", "channelId": "linkedin-channel", "status": read_status,
                "dueAt": read_due if read_due is not None else due}

        def fake_receipt(token, path, data, message, sha=None):
            events.append(("receipt", data["state"], data.get("buffer_post_id"), sha))
            return f"sha-{len(events)}"

        def fake_buffer(token, query, variables):
            if "createPost(input:" in query:
                events.append(("create", variables.copy()))
                return {"createPost": {"post": created}}
            events.append(("read", variables.copy()))
            return {"post": read}

        with patch.object(probe, "fetch_receipt", return_value=None), \
             patch.object(probe, "resolve_channel", return_value="linkedin-channel") as channel, \
             patch.object(probe, "put_receipt", side_effect=fake_receipt), \
             patch.object(probe, "buffer_graphql", side_effect=fake_buffer):
            failure = None
            try:
                probe.live_probe(self.env, now=self.now)
            except RuntimeError as exc:
                failure = str(exc)
        channel.assert_called_once_with("test-buffer-token", "linkedin", "")
        return events, failure

    def test_success_creates_exactly_one_dated_draft_and_reads_it_back(self):
        events, failure = self.run_mock_probe()
        self.assertIsNone(failure)
        self.assertEqual([kind for kind, *_ in events],
                         ["receipt", "create", "receipt", "read", "receipt"])
        self.assertEqual(events[0][1], "pending_manual_reconciliation_on_failure")
        self.assertEqual(events[2][1:3], ("created_requires_independent_check", "probe-post-123"))
        self.assertEqual(events[4][1], "verified_prescheduled_draft_not_queued")
        self.assertEqual(events[1][1]["channelId"], "linkedin-channel")
        self.assertEqual(events[1][1]["dueAt"], "2027-02-08T12:00:00Z")
        self.assertIn("NICHT VERÖFFENTLICHEN", events[1][1]["text"])

    def test_scheduled_response_is_alarm_and_stops_without_second_mutation(self):
        events, failure = self.run_mock_probe(create_status="scheduled")
        self.assertIn("ALARM", failure)
        self.assertEqual([kind for kind, *_ in events], ["receipt", "create", "receipt"])
        self.assertEqual(events[-1][2], "probe-post-123")

    def test_wrong_date_response_is_alarm(self):
        events, failure = self.run_mock_probe(create_due="2027-02-09T12:00:00Z")
        self.assertIn("ALARM", failure)
        self.assertEqual([kind for kind, *_ in events], ["receipt", "create", "receipt"])

    def test_disagreement_in_independent_readback_is_alarm(self):
        events, failure = self.run_mock_probe(read_status="scheduled")
        self.assertIn("ALARM", failure)
        self.assertEqual([kind for kind, *_ in events], ["receipt", "create", "receipt", "read"])

    def test_failed_or_ambiguous_creation_stays_pending_for_manual_reconciliation(self):
        with patch.object(probe, "fetch_receipt", return_value=None), \
             patch.object(probe, "resolve_channel", return_value="linkedin-channel"), \
             patch.object(probe, "put_receipt", return_value="reserved") as put, \
             patch.object(probe, "buffer_graphql", return_value={"createPost": {"__typename": "MutationError"}}) as buf:
            with self.assertRaisesRegex(RuntimeError, "nicht eindeutig"):
                probe.live_probe(self.env, now=self.now)
        self.assertEqual(put.call_count, 1)
        self.assertEqual(buf.call_count, 1)


if __name__ == "__main__":
    unittest.main()
