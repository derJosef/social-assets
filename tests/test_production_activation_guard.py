"""Offline security regression for production draft guard: no network permitted."""
import io
import json
import unittest
from unittest import mock
import urllib.error

from scripts import production_activation_guard as guard

MAIN = "a5cd8b2f78ea214789517f96259f01cb58e2e68e"
LEDGER = "1" * 40


def metadata(branch, *, protected=True, sha=None):
    return {"name": branch, "protected": protected,
            "commit": {"sha": sha or (MAIN if branch == "main" else LEDGER)}}


class ActivationGateTests(unittest.TestCase):
    def mock_access(self, *, main_protected=True, ledger_protected=True,
                    main_sha=MAIN, ledger_sha=LEDGER):
        seen = []
        def fake(branch, token):
            self.assertEqual(token, "test-token")
            seen.append(branch)
            return metadata(branch,
                            protected=main_protected if branch == "main" else ledger_protected,
                            sha=main_sha if branch == "main" else ledger_sha)
        return seen, mock.patch.object(guard, "branch_metadata", side_effect=fake)

    def test_requires_both_verified_protected_branches(self):
        seen, patch = self.mock_access()
        with patch:
            evidence = guard.check(guard.REPOSITORY, guard.REF, MAIN, "test-token")
        self.assertEqual(seen, ["main", "automation-receipts"])
        self.assertTrue(evidence["main_protected"])
        self.assertTrue(evidence["receipt_branch_protected"])
        self.assertEqual(evidence["buffer_mutations"], 0)
        self.assertEqual(evidence["image_provider_calls"], 0)

    def test_unprotected_main_blocks_any_draft(self):
        _, patch = self.mock_access(main_protected=False)
        with patch, self.assertRaisesRegex(guard.ActivationBlocked, "main is not protected"):
            guard.check(guard.REPOSITORY, guard.REF, MAIN, "test-token")

    def test_unprotected_receipt_ledger_blocks_any_draft(self):
        _, patch = self.mock_access(ledger_protected=False)
        with patch, self.assertRaisesRegex(guard.ActivationBlocked, "automation-receipts is not protected"):
            guard.check(guard.REPOSITORY, guard.REF, MAIN, "test-token")

    def test_ref_sha_repo_invalid_stops_before_git_provider(self):
        with mock.patch.object(guard, "branch_metadata", side_effect=AssertionError("No external request")):
            for repo, ref, sha in (
                ("somebody/other", guard.REF, MAIN),
                (guard.REPOSITORY, "refs/heads/feature", MAIN),
                (guard.REPOSITORY, guard.REF, "wrong"),
            ):
                with self.subTest(repo=repo, ref=ref, sha=sha):
                    with self.assertRaisesRegex(guard.ActivationBlocked, "exact main"):
                        guard.check(repo, ref, sha, "test-token")

    def test_no_credentials_blocks_before_network(self):
        with mock.patch.object(guard, "branch_metadata", side_effect=AssertionError("No external request")):
            with self.assertRaisesRegex(guard.ActivationBlocked, "credential"):
                guard.check(guard.REPOSITORY, guard.REF, MAIN, "")

    def test_moved_main_head_stops_before_image_and_buffer(self):
        _, patch = self.mock_access(main_sha="f" * 40)
        with patch, self.assertRaisesRegex(guard.ActivationBlocked, "main moved"):
            guard.check(guard.REPOSITORY, guard.REF, MAIN, "test-token")

    def test_invalid_ledger_head_stops(self):
        _, patch = self.mock_access(ledger_sha="unknown")
        with patch, self.assertRaisesRegex(guard.ActivationBlocked, "identifiable Git commit"):
            guard.check(guard.REPOSITORY, guard.REF, MAIN, "test-token")

    def test_api_error_never_assumed_protection(self):
        with mock.patch.object(guard.urllib.request, "urlopen",
                               side_effect=urllib.error.HTTPError("https://api.github.com", 403,
                                                                    "Forbidden", None, None)):
            with self.assertRaisesRegex(guard.ActivationBlocked, "unavailable"):
                guard.branch_metadata("main", "synthetic")
        with mock.patch.object(guard.urllib.request, "urlopen", return_value=mock.MagicMock()) as response:
            response.return_value.__enter__.return_value.read.return_value = b'{"name":"main","protected":false}'
            item = guard.branch_metadata("main", "synthetic")
            self.assertIs(item["protected"], False)

    def test_workflow_runs_security_gate_before_expensive_image(self):
        from pathlib import Path
        file = Path(__file__).resolve().parents[1] / ".github/workflows/social-campaign-orchestrator.yml"
        workflow = file.read_text(encoding="utf-8")
        self.assertIn("python3 scripts/production_activation_guard.py", workflow)
        self.assertLess(workflow.index("scripts/production_activation_guard.py"),
                        workflow.index("scripts/chatgpt_image_import.py"))
        self.assertLess(workflow.index("scripts/production_activation_guard.py"),
                        workflow.index("scripts/buffer_draft.py --draft"))
        self.assertNotIn("saveToDraft: false", workflow)


if __name__ == "__main__":
    unittest.main()
