"""Keep all Buffer writer workflows on the same non-dropping serial queue.

When an issue_comment triggers many workflows, GitHub normally replaces the
single pending member of a concurrency group.  queue: max changes only this
pending policy; at most one Buffer writer in the group can still execute.
"""
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
WRITER_WORKFLOWS = {
    "buffer-auto-drafts.yml": "buffer-drafts-single-flight",
    "buffer-auto-schedule.yml": "buffer-schedule-single-flight",
    "buffer-draft.yml": "buffer-drafts-single-flight",
    "buffer-prescheduled-draft-probe.yml": "buffer-drafts-single-flight",
    "paf-tv-cover-video-media-update.yml": "buffer-schedule-single-flight",
    "paf-tv-facebook-instagram-drafts.yml": "buffer-drafts-single-flight",
    "paf-tv-move-recovery.yml": "buffer-schedule-single-flight",
    "paf-tv-move-two-scheduled-posts.yml": "buffer-schedule-single-flight",
    "paf-tv-schedule-german-clip01.yml": "buffer-schedule-single-flight",
    "paf-tv-video-draft-probe.yml": "buffer-drafts-single-flight",
    "picturefix-pf01-preschedule.yml": "buffer-drafts-single-flight",
}


class BufferQueueSafetyTests(unittest.TestCase):
    def test_all_shared_writer_groups_keep_fifo_and_no_pending_replacement(self):
        self.assertEqual(len(WRITER_WORKFLOWS), 11)
        for name, group in WRITER_WORKFLOWS.items():
            with self.subTest(workflow=name):
                source = (ROOT / ".github" / "workflows" / name).read_text(encoding="utf-8")
                section = source.split("\nconcurrency:\n", 1)[1].split("\njobs:\n", 1)[0]
                self.assertIn(group, section)
                self.assertIn("\n  cancel-in-progress: false\n", section)
                self.assertEqual(section.count("\n  queue: max\n"), 1)
                self.assertNotIn("queue: single", section)

    def test_picturefix_draft_change_still_requires_manual_approval(self):
        source = (ROOT / ".github" / "workflows" /
                  "picturefix-pf01-preschedule.yml").read_text(encoding="utf-8")
        self.assertIn("PF01_FACEBOOK_PRESCHEDULE_DRAFT_ONLY", source)
        self.assertIn("PF01_INSTAGRAM_PRESCHEDULE_DRAFT_ONLY", source)
        self.assertIn("PF01_PINTEREST_PRESCHEDULE_DRAFT_ONLY", source)
        self.assertIn("--send", source)
        self.assertIn("BUFFER_BRAND: picturefix", source)
        self.assertNotIn("createPost", source)
        self.assertNotIn("shareNow", source)


if __name__ == "__main__":
    unittest.main()
