"""Pure offline checks for the ChatGPT -> GitHub production-run ledger."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import production_run_journal as journal


RUN_ID = "c5238a22-0408-832c-89c2-8d1a2b08bf3d"


def header():
    return journal.new_header(RUN_ID, "6ad9da13ed2481919326ec8e2a42d6d5", "scheduled",
                              started_at="2026-11-20T13:20:00Z")


def event(phase, state="PASS", **kwargs):
    return {"schema_version": 1, "run_id": RUN_ID, "phase": phase,
            "state": state, "recorded_at": "2026-11-20T13:26:00Z", **kwargs}


def receipts():
    return [{"target": target, "post_id": str(i + 1),
             "channel_id": "channel-" + str(i + 1), "status": "draft",
             "due_at": "2026-11-25T10:00:00Z"}
            for i, target in enumerate(("linkedin", "facebook", "instagram"))]


class JournalTests(unittest.TestCase):
    def test_normal_started_then_pass_uses_a_single_issue(self):
        events = [event("start"), event("inventory", "STARTED"),
                  event("inventory", "PASS"), event("research", "STARTED"),
                  event("research", "PASS")]
        result = journal.resume_decision(header(), events)
        self.assertEqual(result["decision"], "NEXT")
        self.assertEqual(result["phase"], "copy")

    def test_failed_phase_needs_explicit_reconciliation_reference(self):
        events = [event("start"), event("inventory", "ERROR", error={
            "tool": "search", "kind": "timeout", "summary": "Timeout"}),
            event("inventory", "PASS")]
        with self.assertRaises(journal.JournalError):
            journal.resume_decision(header(), events)

    def test_failing_run_without_github_transfer_is_resumable_only_after_inspection(self):
        events = [event("start"), event("inventory"), event("research", "STARTED")]
        result = journal.resume_decision(header(), events)
        self.assertEqual(result["decision"], "INSPECT")
        self.assertEqual(result["phase"], "research")

    def test_no_production_without_persisted_start(self):
        self.assertEqual(journal.resume_decision(header(), [])["decision"], "STOP")

    def test_readback_ids_must_be_distinct_and_draft_only(self):
        events = [event("start"), event("inventory")]
        events.extend(event(step) for step in ("research", "copy", "image", "transfer", "github", "actions", "buffer"))
        invalid = receipts()
        invalid[1]["post_id"] = invalid[0]["post_id"]
        with self.assertRaises(journal.JournalError):
            journal.resume_decision(header(), events + [event("readback", receipts=invalid)])
        invalid = receipts()
        invalid[2]["status"] = "scheduled"
        with self.assertRaises(journal.JournalError):
            journal.resume_decision(header(), events + [event("readback", receipts=invalid)])

    def test_complete_verified_workflow_is_not_replayed(self):
        events = [event(phase, receipts=receipts()) if phase == "readback" else event(phase)
                  for phase in journal.PHASES]
        self.assertEqual(journal.resume_decision(header(), events)["decision"], "DONE")

    def test_ambiguous_buffer_write_never_autoretries(self):
        steps = [event(phase) for phase in journal.PHASES[:8]]
        self.assertEqual(journal.resume_decision(header(), steps + [event("buffer", "STARTED")])["decision"], "RECONCILE")
        self.assertEqual(journal.resume_decision(header(), steps + [event("buffer", "ERROR", error={"tool": "Buffer API", "kind": "timeout", "summary": "No response"})])["decision"], "RECONCILE")

    def test_ambiguous_github_commit_never_replays_blindly(self):
        events = [event(phase) for phase in journal.PHASES[:6]]
        self.assertEqual(journal.resume_decision(header(), events + [event("github", "STARTED")])["decision"], "RECONCILE")

    def test_error_event_is_recorded_and_closed_to_automatic_resume(self):
        events = [event("start"), event("inventory"), event("research", "ERROR", error={
            "tool": "web_search", "kind": "timeout", "summary": "Request timed out"})]
        self.assertEqual(journal.resume_decision(header(), events)["decision"], "INSPECT")

    def test_error_and_blocked_cannot_be_written_without_reason(self):
        with self.assertRaises(journal.JournalError):
            journal.validate_event(event("research", "ERROR"), RUN_ID)
        with self.assertRaises(journal.JournalError):
            journal.validate_event(event("research", "BLOCKED"), RUN_ID)
        journal.validate_event(event("research", "BLOCKED", evidence={
            "reason": "Two independent current sources unavailable"}), RUN_ID)

    def test_secrets_and_raw_tool_payloads_are_rejected(self):
        for secret in ("Bearer eyJhbGciOiJIUzI1NiJ9.abcdef", "sk-proj-AbCdEf1234567890123456", "ghp_123456789012345678901234567890123456"):
            with self.subTest(secret=secret[:4]):
                with self.assertRaises(journal.JournalError):
                    journal.validate_event(event("research", "ERROR", error={"tool": "some-tool", "kind": "api", "summary": secret}), RUN_ID)

    def test_incorrect_ids_order_or_duplicate_pass_are_rejected(self):
        with self.assertRaises(journal.JournalError):
            journal.resume_decision(header(), [event("research")])
        with self.assertRaises(journal.JournalError):
            journal.resume_decision(header(), [event("start"), event("start")])
        with self.assertRaises(journal.JournalError):
            journal.resume_decision(header(), [event("start", "PASS", run_id="invalid")])

    def test_new_run_header_rejects_invalid_identity(self):
        with self.assertRaises(journal.JournalError):
            journal.new_header("../../bad", "abc", "scheduled")


if __name__ == "__main__":
    unittest.main()
