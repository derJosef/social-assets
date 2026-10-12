"""Offline reports only: all Buffer API requests mocked; no scheduling or publish."""
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from scripts import social_weekly_review as review

CID = "2026-10-19-kontrollierte-ki"
IMG = (
    "https://raw.githubusercontent.com/derJosef/social-assets/"
    + "a" * 40 + f"/media/images/{CID}-branded.png"
)
IDS = {
    "linkedin": "0123456789abcdef01234567",
    "facebook": "abcdef012345678901234567",
    "instagram": "0123abcdef45678901234567",
}


def example_report():
    outputs = {}
    for i, target in enumerate(review.TARGETS):
        utc = datetime(2026, 10, 21 + i, 13, tzinfo=timezone.utc)
        outputs[target] = {
            "post_id": IDS[target], "service": target,
            "channel_id": f"channel-{target}", "status": "draft",
            "dueAt": utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "scheduled_local": utc.astimezone(ZoneInfo("Europe/Berlin")).isoformat(timespec="seconds"),
            "text": f"Testbeitrag für {target}: Änderungen in Buffer bleiben maßgeblich.",
            "review_image_url": IMG,
            "buffer_asset_url": IMG, "image_attached_in_buffer": True,
            "buffer_dashboard_url": "https://publish.buffer.com",
            "buffer_link_kind": "official_dashboard_not_direct_post",
            "buffer_direct_post_url": None,
            "editorial_approval": "pending_after_draft",
            "published": False,
        }
    return {
        "campaign": CID, "state": "buffer_drafts_verified",
        "job_status": "success",
        "buffer_verification": {
            "status": "PASS", "checked_at": "2026-10-19T07:30:00Z",
            "posts": outputs,
        },
    }


class SocialWeeklyReviewTests(unittest.TestCase):
    def setUp(self):
        self.r = example_report()
        self.posts = self.r["buffer_verification"]["posts"]

    def test_verified_three_drafts_render_with_actual_ids_text_and_dates(self):
        md = review.render(self.r)
        self.assertIn("drei geprüfte, vordatierte Buffer-Drafts", md)
        for target in review.TARGETS:
            self.assertIn(IDS[target], md)
            self.assertIn(f"Testbeitrag für {target}", md)
            self.assertIn(self.posts[target]["scheduled_local"], md)
        self.assertEqual(md.count("(https://publish.buffer.com)"), 3)
        self.assertEqual(md.count(IMG), 3)
        self.assertIn("kein individueller Post-Link", md)
        self.assertIn("keine", md.lower())
        self.assertNotIn("saveToDraft: false", md)

    def test_missing_verified_receipt_cannot_be_offered_as_approved(self):
        self.r["buffer_verification"]["status"] = "BLOCKED"
        md = review.render(self.r)
        self.assertIn("Status: BLOCKED", md)
        self.assertNotIn(IMG, md)
        self.assertNotIn(IDS["facebook"], md)

    def test_partial_three_channel_result_never_claims_three_drafts(self):
        self.posts.pop("instagram")
        self.assertIn("Status: BLOCKED", review.render(self.r))

    def test_scheduled_or_published_post_never_offered_as_draft(self):
        for k, value in (("status", "scheduled"), ("published", True),
                         ("editorial_approval", "approved")):
            with self.subTest(field=k):
                original = self.posts["instagram"][k]
                self.posts["instagram"][k] = value
                self.assertIn("Status: BLOCKED", review.render(self.r))
                self.posts["instagram"][k] = original

    def test_duplicate_post_or_channel_or_wrong_service_blocks(self):
        invalid = [
            ("post_id", self.posts["linkedin"]["post_id"]),
            ("channel_id", self.posts["linkedin"]["channel_id"]),
            ("service", "linkedin"),
        ]
        for key, value in invalid:
            with self.subTest(key=key):
                original = self.posts["facebook"][key]
                self.posts["facebook"][key] = value
                self.assertIn("Status: BLOCKED", review.render(self.r))
                self.posts["facebook"][key] = original

    def test_fake_direct_link_blocks_instead_of_fabricating(self):
        self.posts["facebook"]["buffer_direct_post_url"] = (
            "https://publish.buffer.com/p/guess/edit/abcdef012345678901234567"
        )
        text = review.render(self.r)
        self.assertIn("Status: BLOCKED", text)
        self.assertNotIn("guess", text)

    def test_non_immutable_image_url_blocks(self):
        self.posts["facebook"]["review_image_url"] = (
            "https://raw.githubusercontent.com/derJosef/social-assets/main/media/images/test.png"
        )
        self.assertIn("Status: BLOCKED", review.render(self.r))

    def test_invalid_utc_berlin_conversion_blocks(self):
        self.posts["linkedin"]["scheduled_local"] = "2026-10-21T16:00:00+02:00"
        self.assertIn("Status: BLOCKED", review.render(self.r))

    def test_missing_asset_or_text_blocks(self):
        for k, v in (("text", ""), ("image_attached_in_buffer", False)):
            original = self.posts["instagram"][k]
            self.posts["instagram"][k] = v
            self.assertIn("Status: BLOCKED", review.render(self.r))
            self.posts["instagram"][k] = original

    def test_untrusted_post_cannot_break_text_fence(self):
        self.posts["linkedin"]["text"] = (
            "Sinnvoller Testtext\n~~~~\n# Nicht veröffentlichen"
        )
        text = review.render(self.r)
        self.assertIn("~~~~~text\n", text)
        self.assertIn("~~~~~\n", text)

    def test_cli_creates_snapshot_without_buffer_or_github(self):
        with tempfile.TemporaryDirectory() as td:
            source, destination = Path(td) / "report.json", Path(td) / "review.md"
            source.write_text(json.dumps(self.r), encoding="utf-8")
            # A report is derived only from input data, no external network.
            import sys
            from unittest import mock
            with mock.patch.object(sys, "argv", [
                "social_weekly_review.py", "--report", str(source),
                "--markdown", str(destination),
            ]):
                self.assertEqual(review.main(), 0)
            self.assertEqual(destination.read_text(encoding="utf-8"), review.render(self.r))

    def test_blocked_run_is_reported_even_without_any_posts(self):
        report = {
            "campaign": CID, "state": "blocked_before_preparation",
            "job_status": "failure",
        }
        result = review.render(report)
        self.assertIn("BLOCKED", result)
        self.assertNotIn(IMG, result)
        self.assertNotIn("Buffer-Post-ID:", result)


if __name__ == "__main__":
    unittest.main()
