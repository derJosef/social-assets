"""Action outcomes must survive failures before/after the Python orchestrator."""
from __future__ import annotations
import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import action_phase_ledger as ledger


class PhaseLedgerTests(unittest.TestCase):
    def test_failed_tool_reported_with_log_link_and_without_raw_stderr(self):
        report=ledger.build_report({"steps":{},"state":"started"},
            {"checkout":"success", "offline":"failure", "send":"skipped"},
            repo="derJosef/social-assets", run_id="44712345678", job_status="failure")
        self.assertEqual(report["state"],"blocked")
        self.assertEqual(report["action_steps"]["offline"]["status"],"FAIL")
        self.assertEqual(report["action_steps"]["send"]["status"],"NOT_RUN")
        self.assertEqual(report["action_errors"][0]["tool"],"python3 -m unittest")
        self.assertEqual(report["action_errors"][0]["log_url"],
                         "https://github.com/derJosef/social-assets/actions/runs/44712345678")
        self.assertNotIn("stderr",str(report))

    def test_post_send_readback_failure_never_says_three_drafts_verified(self):
        report=ledger.build_report({"steps":{},"state":"ready_for_draft_commit"},
            {"send":"success", "readback":"failure"},
            repo="derJosef/social-assets", run_id="44712345678", job_status="failure")
        self.assertEqual(report["state"],"blocked")
        self.assertEqual(report["resume_safety"],"RECONCILE_BUFFER")
        self.assertEqual(report["buffer_verification"]["status"],"UNVERIFIED")

    def test_ambiguous_send_failure_requires_live_reconciliation(self):
        report=ledger.build_report({}, {"send":"failure"},
            repo="derJosef/social-assets", run_id="44712345678", job_status="failure")
        self.assertEqual(report["resume_safety"],"RECONCILE_BUFFER")

    def test_successful_readback_preserves_verified_receipt(self):
        report=ledger.build_report({"state":"buffer_drafts_verified", "buffer_verification": {"status":"PASS"}},
            {"send":"success", "readback":"success"},
            repo="derJosef/social-assets", run_id="44712345678", job_status="success")
        self.assertEqual(report["state"],"buffer_drafts_verified")
        self.assertEqual(report["buffer_verification"]["status"],"PASS")
        self.assertEqual(report["receipt_state"],"WRITE_PENDING")
        self.assertEqual(report["job_status"],"success")

    def test_existing_weekly_review_keeps_job_status_compatible(self):
        import social_weekly_review
        report=ledger.build_report({"campaign":"2026-11-20-logging-smoke",
                                    "state":"smoke_pass"},
            {"offline":"success", "build":"success"},
            repo="derJosef/social-assets", run_id="44712345678", job_status="success")
        text=social_weekly_review.render(report)
        self.assertIn("Jobstatus: success", text)

    def test_bad_outcome_cannot_forge_success(self):
        with self.assertRaises(ValueError):
            ledger.build_report({}, {"send":"unknown status"},
                repo="derJosef/social-assets", run_id="44712345678", job_status="success")


if __name__=="__main__":
    unittest.main()
