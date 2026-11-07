"""Only explicitly read-only Buffer control comments may bypass write serialization."""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = (ROOT / ".github/workflows/buffer-draft.yml").read_text(encoding="utf-8")


class BufferReadOnlyConcurrencyTests(unittest.TestCase):
    def test_exact_three_readonly_comments_have_an_isolated_concurrency_group(self):
        control = WORKFLOW.split("\nconcurrency:\n", 1)[1].split("\njobs:\n", 1)[0]
        for name in ("PF01_PREFLIGHT_ONLY", "PF01_FB_IG_PREFLIGHT_ONLY", "SL_PREFLIGHT_ONLY"):
            self.assertIn(f"'{name}'", control)
        self.assertIn("github.event.issue.number == 64", control)
        self.assertIn("github.event.issue.number == 69", control)
        self.assertIn("github.event.comment.id", control)
        self.assertIn("format('buffer-readonly-{0}'", control)

    def test_buffer_mutations_keep_shared_single_flight_and_never_force_cancel(self):
        control = WORKFLOW.split("\nconcurrency:\n", 1)[1].split("\njobs:\n", 1)[0]
        self.assertIn("|| 'buffer-drafts-single-flight'", control)
        self.assertIn("cancel-in-progress: false", control)
        for write_trigger in (
            "PF01_FACEBOOK_DRAFT_ONLY",
            "PF01_INSTAGRAM_DRAFT_ONLY",
            "PF01_PINTEREST_DRAFT_ONLY",
        ):
            self.assertNotIn(f"'{write_trigger}'", control)
            self.assertIn(f"'{write_trigger}'", WORKFLOW)
        self.assertNotIn("SL_DRAFT_ONLY", control)

    def test_readonly_jobs_have_no_write_permission(self):
        for start, end in [
            ("  picturefix-preflight:", "  sticken-lasern-preflight:"),
            ("  sticken-lasern-preflight:", "  picturefix-fb-ig-preflight:"),
        ]:
            section = WORKFLOW.split(start, 1)[1].split(end, 1)[0]
            self.assertIn("contents: read", section)
            self.assertIn("persist-credentials: false", section)
            self.assertNotIn("GITHUB_TOKEN", section)
            self.assertNotIn("--send", section)
        fb_ig = WORKFLOW.split("  picturefix-fb-ig-preflight:", 1)[1]
        self.assertIn("contents: read", fb_ig)
        self.assertIn("--check-picturefix-social-connection", fb_ig)
        self.assertNotIn("--send", fb_ig)


if __name__ == "__main__":
    unittest.main()
