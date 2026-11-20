"""Regression: Actions logs each step without expanding publish authority."""
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]


class WorkflowLedgerTests(unittest.TestCase):
    def test_action_outcomes_are_collected_in_always_step(self):
        yml=(ROOT/".github/workflows/social-campaign-orchestrator.yml").read_text()
        for step in ("checkout", "deps", "offline", "request", "guard", "collision",
                     "image_import", "preflight", "reservations", "font", "build",
                     "freeze", "send", "readback"):
            self.assertIn("id: "+step, yml)
            self.assertIn("steps."+step+".outcome", yml)
        self.assertIn("scripts/action_phase_ledger.py",yml)
        self.assertIn("if: always()",yml)

    def test_original_trigger_and_review_authority_remain(self):
        yml=(ROOT/".github/workflows/social-campaign-orchestrator.yml").read_text()
        self.assertIn("branches: [main]",yml)
        self.assertIn("cancel-in-progress: false",yml)
        self.assertIn("github.event.issue.user.login == 'derJosef'",yml)
        self.assertNotIn("shareNow",yml)
        self.assertNotIn("schedule:",yml)


if __name__=="__main__":
    unittest.main()
