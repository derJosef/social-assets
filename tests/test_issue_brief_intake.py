"""No-network tests for guarded GitHub-Issues weekly campaign intake."""
import json
import tempfile
import unittest
from pathlib import Path

from scripts import issue_brief_intake as intake

CID = "2026-10-19-kontrollierte-agenten"


def event():
    body = {
        "format_version": 1, "brand": "ai-agent-builder",
        "campaign_id": CID, "execution_mode": "drafts",
        "image_review": f"visual-reviews/{CID}.json",
        "topic": "Ein deutscher B2B-Mittelstand nutzt kontrollierte KI-Agenten für Dokumentenprüfungen.",
        "sources": [
            {"url": "https://www.nist.gov/ai", "published_at": "2026-06-01"},
            {"url": "https://owasp.org/", "published_at": "2026-05-10"},
        ],
        "posting_sources": [
            "https://buffer.com/resources/best-time-to-post-on-linkedin/",
            "https://sproutsocial.com/insights/best-times-to-post-on-linkedin/",
            "https://buffer.com/resources/best-time-to-post-on-facebook/",
            "https://sproutsocial.com/insights/best-times-to-post-on-facebook/",
            "https://buffer.com/resources/when-is-the-best-time-to-post-on-instagram/",
            "https://sproutsocial.com/insights/best-times-to-post-on-instagram/",
        ],
        "chatgpt_image": {
            "transport": "adobe_transfer",
            "url": "https://at.adobe.com/AbC01234xYz",
            "sha256": "a" * 64,
            "visual_review": {k: True for k in (
                "no_people", "no_robot", "no_foreign_logo",
                "no_generated_text", "plausible_details", "matches_topic",
                "heading_and_logo_space"
            )},
            "review_evidence": "ChatGPT visual inspection of the actual image; NOT a human review. Synthetic fixture only."
        },
        "prepared_content": {
            "posts": {
                "linkedin": "Synthetischer LinkedIn-Beitrag mit vielen technischen Details. " * 6,
                "facebook": "Synthetischer Facebook-Beitrag mit verständlichem Praxisbeispiel. " * 6,
                "instagram": "Synthetischer Instagram-Beitrag zu kontrollierten Arbeitsabläufen. " * 6,
            },
            "visual": None,
            "six_hats": {
                color: f"Konkrete und längere synthetische Erläuterung aus Sicht {color}."
                for color in ("white", "red", "black", "yellow", "green", "blue")
            },
            "risks": ["Synthetic only"],
        }
    }
    return {
        "action": "opened", "repository": {"full_name": "derJosef/social-assets"},
        "issue": {
            "number": 31, "title": f"AIAGENT_BRIEF:{CID}",
            "user": {"login": "derJosef"},
            "author_association": "OWNER", "body": json.dumps(body),
        },
    }


class OwnerIssueIntakeTests(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.root = Path(t.name)
        (self.root / "orchestration/briefs").mkdir(parents=True)
        self.e = event()
        self.event_file = self.root / "issue.json"

    def save(self):
        self.event_file.write_text(json.dumps(self.e), encoding="utf-8")

    def test_owner_issue_creates_exact_one_ephemeral_brief(self):
        self.save()
        result = intake.stage(self.event_file, self.root)
        self.assertEqual(result["campaign"], CID)
        self.assertEqual(result["issue_number"], 31)
        self.assertFalse(result["main_changed"])
        self.assertEqual(result["buffer_posts_created"], 0)
        path = self.root / result["brief"]
        self.assertEqual(json.loads(path.read_text())["campaign_id"], CID)
        with self.assertRaisesRegex(intake.IssueBriefBlocked, "No overwrite"):
            intake.stage(self.event_file, self.root)

    def test_other_issue_without_exact_title_cannot_execute(self):
        self.e["issue"]["title"] = "README or promotional issue"
        with self.assertRaises(intake.IssueBriefBlocked):
            intake.extract(self.e)

    def test_non_owner_or_wrong_repo_cannot_execute(self):
        for field, value in [
            ("repository.full_name", "attacker/repo"),
            ("issue.user.login", "attacker"),
            ("issue.author_association", "NONE"),
            ("issue.author_association", "COLLABORATOR"),
        ]:
            with self.subTest(field=field):
                obj = json.loads(json.dumps(self.e))
                target = obj
                keys = field.split(".")
                for k in keys[:-1]:
                    target = target[k]
                target[keys[-1]] = value
                with self.assertRaises(intake.IssueBriefBlocked):
                    intake.extract(obj)

    def test_issue_events_other_than_opened_are_never_processed(self):
        self.e["action"] = "edited"
        with self.assertRaisesRegex(intake.IssueBriefBlocked, "newly opened"):
            intake.extract(self.e)

    def test_never_accept_markdown_commands_or_code_blocks(self):
        fence = chr(96) * 3
        self.e["issue"]["body"] = fence + "json\n" + self.e["issue"]["body"] + "\n" + fence
        with self.assertRaisesRegex(intake.IssueBriefBlocked, "not Markdown"):
            intake.extract(self.e)

    def test_mismatch_campaign_brand_and_review_are_rejected(self):
        for key, value in [
            ("campaign_id", "2026-10-19-other"),
            ("brand", "picturefix"),
            ("execution_mode", "smoke"),
            ("image_review", "other.jpg"),
        ]:
            with self.subTest(field=key):
                altered = json.loads(json.dumps(self.e))
                body = json.loads(altered["issue"]["body"])
                body[key] = value
                altered["issue"]["body"] = json.dumps(body)
                with self.assertRaisesRegex(intake.IssueBriefBlocked, "mismatch"):
                    intake.extract(altered)

    def test_missing_platform_never_leaves_staged_file(self):
        b = json.loads(self.e["issue"]["body"])
        b["prepared_content"]["posts"].pop("facebook")
        self.e["issue"]["body"] = json.dumps(b)
        self.save()
        with self.assertRaisesRegex(intake.IssueBriefBlocked, "All three"):
            intake.stage(self.event_file, self.root)
        self.assertFalse((self.root / f"orchestration/briefs/{CID}.json").exists())

    def test_legacy_card_visual_blocks_before_image_provider(self):
        body = json.loads(self.e["issue"]["body"])
        body["prepared_content"]["visual"] = {"cards": [{"title": "old"}]}
        self.e["issue"]["body"] = json.dumps(body)
        with self.assertRaisesRegex(intake.IssueBriefBlocked, "visual must be null"):
            intake.extract(self.e)

    def test_short_platform_post_or_incomplete_six_hats_block(self):
        for change in ("short_post", "missing_hat"):
            with self.subTest(change=change):
                altered = json.loads(json.dumps(self.e))
                body = json.loads(altered["issue"]["body"])
                if change == "short_post":
                    body["prepared_content"]["posts"]["linkedin"] = "Short"
                else:
                    body["prepared_content"]["six_hats"].pop("blue")
                altered["issue"]["body"] = json.dumps(body)
                with self.assertRaises(intake.IssueBriefBlocked):
                    intake.extract(altered)

    def test_extra_unknown_fields_fail_closed(self):
        b = json.loads(self.e["issue"]["body"])
        b["run_shell"] = "echo unsafe"
        self.e["issue"]["body"] = json.dumps(b)
        with self.assertRaisesRegex(intake.IssueBriefBlocked, "Unexpected brief fields"):
            intake.extract(self.e)

    def test_invalid_slug_blocks_before_file_write(self):
        self.e["issue"]["title"] = "AIAGENT_BRIEF:../../main"
        self.save()
        with self.assertRaises(intake.IssueBriefBlocked):
            intake.stage(self.event_file, self.root)
        self.assertEqual(list((self.root / "orchestration/briefs").glob("*")), [])

    def test_trust_boundary_workflow_requires_owner_and_default_branch(self):
        repo = Path(__file__).resolve().parents[1]
        yml = (repo / ".github/workflows/social-campaign-orchestrator.yml").read_text()
        self.assertIn("issues:", yml)
        self.assertIn("author_association == 'OWNER'", yml)
        self.assertIn("scripts/issue_brief_intake.py", yml)
        self.assertIn("scripts/production_activation_guard.py", yml)
        self.assertLess(yml.index("issue_brief_intake.py"),
                        yml.index("python3 scripts/chatgpt_image_import.py --brief"))
        self.assertIn('expected_post_count=6', yml)
        self.assertIn("orchestration/briefs/", yml)

    def test_script_contains_no_mutating_api_calls(self):
        script = Path(intake.__file__).read_text(encoding="utf-8")
        self.assertNotIn("createPost(", script)
        self.assertNotIn("editPost(", script)
        self.assertNotIn("subprocess", script)
        self.assertNotIn("eval(", script)


if __name__ == "__main__":
    unittest.main()
