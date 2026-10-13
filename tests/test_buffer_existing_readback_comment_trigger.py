"""Offline-only guard for the narrowly scoped issue-comment readback trigger."""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
YML = ROOT / ".github/workflows/buffer-existing-campaign-readback.yml"


class OnlyOneReadbackIssueTriggerTests(unittest.TestCase):
    def test_expected_exact_comment_trigger_and_owner_guards(self):
        content = YML.read_text(encoding="utf-8")
        for phrase in (
            "workflow_dispatch:", "issue_comment:", "types: [created]",
            "github.actor == 'derJosef'",
            "github.ref == 'refs/heads/main'",
            "github.event_name == 'issue_comment'",
            "github.event.action == 'created'",
            "github.event.issue.number == 19",
            "!github.event.issue.pull_request",
            "github.event.issue.user.login == 'derJosef'",
            "github.event.comment.user.login == 'derJosef'",
            "github.event.comment.body == 'RUN_READ_ONLY_DRAFTS_20261013_E2E003'",
            "AIAGENT_BRIEF:2026-10-13-lieferanten-pdf-prueftor-e2e-003",
            "contents: read",
        ):
            self.assertIn(phrase, content)

    def test_data_only_and_read_only_behavior_remains(self):
        content = YML.read_text(encoding="utf-8")
        self.assertIn("git show", content)
        self.assertIn("scripts/orchestrator_verify_buffer.py", content)
        self.assertIn("actions/upload-artifact@v4", content)
        self.assertIn("persist-credentials: false", content)
        for dangerous in ("createPost(", "editPost(", "queuePost(", "publishPost(",
                          "git push", "permissions:\n  contents: write",
                          "scripts/buffer_draft.py --draft"):
            self.assertNotIn(dangerous, content)

    def test_keep_manual_dispatch_compatible(self):
        text = YML.read_text(encoding="utf-8")
        self.assertIn("inputs.campaign", text)
        self.assertIn("github.event_name == 'workflow_dispatch'", text)
        self.assertIn("github.event_name == 'issue_comment' && "
                      "'2026-10-13-lieferanten-pdf-prueftor-e2e-003' || inputs.campaign", text)


if __name__ == "__main__":
    unittest.main()
