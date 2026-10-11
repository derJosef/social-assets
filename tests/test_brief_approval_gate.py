"""Synthetic offline checks for the proposed, non-deployed brief approval gate."""

import base64
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import brief_approval_gate as gate


CAMPAIGN = "2026-10-11-offline-probe"
BRIEF = f"orchestration/briefs/{CAMPAIGN}.json"
REVIEW = f"visual-reviews/{CAMPAIGN}.json"
SOURCE = f"media/source-images/{CAMPAIGN}.png"
APPROVAL = f"orchestration/approvals/{CAMPAIGN}.json"
POST = f"ready-for-buffer/auto-{CAMPAIGN}-linkedin.json"


class FakeGithub:
    def __init__(self, approval: bytes):
        self.approval = approval
        self.protected = True
        self.merged_by = "derJosef"
        self.changed_files = [{"filename": APPROVAL, "status": "added"}]
        self.commits = [{"sha": "a" * 40}]
        self.calls = []

    def __call__(self, path):
        self.calls.append(path)
        if path == "branches/main":
            return {"protected": self.protected}
        if path == f"contents/{APPROVAL}?ref=main":
            return {"encoding": "base64", "content": base64.b64encode(self.approval).decode()}
        if path == f"commits?path={APPROVAL}&sha=main&per_page=1":
            return self.commits
        if path == f"commits/{'a' * 40}/pulls":
            return [{"number": 17}]
        if path == "pulls/17":
            return {
                "number": 17, "merged_at": "2026-10-11T18:00:00Z",
                "merged_by": {"login": self.merged_by},
                "base": {"ref": "main", "repo": {"full_name": gate.REPOSITORY}},
            }
        if path.startswith("commits/") and path.endswith("/pulls"):
            return []
        if path == "pulls/17/files?per_page=100":
            return self.changed_files
        raise AssertionError(f"Unexpected mocked GitHub request: {path}")


class BriefApprovalTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.approval_file = self.root / APPROVAL
        self.brief_file = self.root / BRIEF
        self.review_file = self.root / REVIEW
        self.source_file = self.root / SOURCE
        for file in (self.approval_file, self.brief_file, self.review_file, self.source_file):
            file.parent.mkdir(parents=True, exist_ok=True)
        self.source_file.write_bytes(b"synthetic source image bytes; never send")
        self.brief = {
            "format_version": 1, "brand": "ai-agent-builder",
            "campaign_id": CAMPAIGN, "execution_mode": "drafts",
            "image_review": REVIEW,
            "prepared_content": {"posts": {"linkedin": "synthetic only"}},
        }
        self.review = {"source": SOURCE, "source_sha256": gate.sha256(self.source_file.read_bytes())}
        self.write_json(self.brief_file, self.brief)
        self.write_json(self.review_file, self.review)
        self.approval = {
            "format_version": 1, "campaign_id": CAMPAIGN, "brief_path": BRIEF,
            "brief_sha256": gate.sha256(self.brief_file.read_bytes()),
            "image_review_path": REVIEW,
            "image_review_sha256": gate.sha256(self.review_file.read_bytes()),
            "source_sha256": gate.sha256(self.source_file.read_bytes()),
            "targets": ["linkedin", "facebook", "instagram"],
            "purpose": "unscheduled_buffer_draft_only", "state": "approved",
        }
        self.save()
        self.github = FakeGithub(self.approval_file.read_bytes())
        patcher = mock.patch.dict(os.environ, {
            "GITHUB_REPOSITORY": gate.REPOSITORY, "GITHUB_REF": "refs/heads/main",
        })
        patcher.start()
        self.addCleanup(patcher.stop)
        # Not even a stray real HTTP request is acceptable in these tests.
        network = mock.patch.object(gate.urllib.request, "urlopen",
                                    side_effect=AssertionError("network forbidden"))
        network.start()
        self.addCleanup(network.stop)

    @staticmethod
    def write_json(path, data):
        path.write_text(json.dumps(data, ensure_ascii=False, sort_keys=True), encoding="utf-8")

    def save(self):
        self.write_json(self.approval_file, self.approval)

    def authorize(self, path=POST):
        return gate.authorize_draft(path, root=self.root, api_get=self.github)

    def test_t01_authorized_pr_for_exact_brief_draft_only(self):
        receipt = self.authorize()
        self.assertEqual(receipt["approved_pr"], 17)
        self.assertEqual(receipt["merged_by"], "derJosef")
        self.assertIn("branches/main", self.github.calls)
        self.assertFalse(any("buffer" in path for path in self.github.calls))

    def test_t02_execution_mode_drafts_without_approval_fails_closed(self):
        self.approval_file.unlink()
        with self.assertRaises(OSError):
            self.authorize()
        self.assertEqual(self.github.calls, [])

    def test_t03_spoofed_json_identity_cannot_authorize(self):
        self.approval["approved_by"] = "derJosef"
        self.save()
        with self.assertRaisesRegex(gate.ApprovalBlocked, "Freigabefeld"):
            self.authorize()
        self.assertEqual(self.github.calls, [])
        del self.approval["approved_by"]
        self.save()
        self.github.approval = self.approval_file.read_bytes()
        self.github.merged_by = "github-actions[bot]"
        with self.assertRaisesRegex(gate.ApprovalBlocked, "Josef"):
            self.authorize()

    def test_t04_changed_brief_bytes_even_whitespace_block(self):
        self.brief_file.write_bytes(self.brief_file.read_bytes() + b"\n")
        with self.assertRaisesRegex(gate.ApprovalBlocked, "Brief nach"):
            self.authorize()
        self.assertEqual(self.github.calls, [])

    def test_t05_changed_review_or_image_block(self):
        self.review_file.write_bytes(self.review_file.read_bytes() + b"\n")
        with self.assertRaisesRegex(gate.ApprovalBlocked, "Bildreview nach"):
            self.authorize()
        self.write_json(self.review_file, self.review)
        self.source_file.write_bytes(b"tampered")
        with self.assertRaisesRegex(gate.ApprovalBlocked, "Quellbild"):
            self.authorize()

    def test_t05_campaign_platform_or_scope_mismatch_block(self):
        with self.assertRaisesRegex(gate.ApprovalBlocked, "auto-Kampagnen"):
            self.authorize("ready-for-buffer/auto-other-linkedin.json")
        self.approval["targets"] = ["linkedin"]
        self.save()
        with self.assertRaisesRegex(gate.ApprovalBlocked, "Plattform"):
            self.authorize()

    def test_t06_revocation_and_unknown_state_block(self):
        for state in ("revoked", "maybe"):
            with self.subTest(state=state):
                self.approval["state"] = state
                self.save()
                with self.assertRaisesRegex(gate.ApprovalBlocked, "widerrufen"):
                    self.authorize()
        self.assertEqual(self.github.calls, [])

    def test_t07_wrong_execution_context_blocks_without_api(self):
        for field, value in (("GITHUB_REF", "refs/heads/topic"),
                             ("GITHUB_REPOSITORY", "evil/fork")):
            with self.subTest(field=field), mock.patch.dict(os.environ, {field: value}):
                with self.assertRaisesRegex(gate.ApprovalBlocked, "social-assets/main"):
                    self.authorize()
        self.assertEqual(self.github.calls, [])

    def test_t08_unprepared_brief_blocks(self):
        self.brief.pop("prepared_content")
        self.write_json(self.brief_file, self.brief)
        self.approval["brief_sha256"] = gate.sha256(self.brief_file.read_bytes())
        self.save()
        with self.assertRaisesRegex(gate.ApprovalBlocked, "vorbereitet"):
            self.authorize()
        self.assertEqual(self.github.calls, [])

    def test_t09_main_must_be_protected(self):
        self.github.protected = False
        with self.assertRaisesRegex(gate.ApprovalBlocked, "nicht geschützt"):
            self.authorize()

    def test_t10_remote_main_record_cannot_differ(self):
        self.github.approval = b"{\"state\":\"approved\"}"
        with self.assertRaisesRegex(gate.ApprovalBlocked, "weicht"):
            self.authorize()

    def test_t11_manual_or_legacy_files_are_not_auto_authorized(self):
        for path in ("drafts/probe.json", "ready-for-buffer/2026-10-10-manual.json",
                     f"ready-for-buffer/replace-{CAMPAIGN}-linkedin.json"):
            with self.subTest(path=path):
                with self.assertRaisesRegex(gate.ApprovalBlocked, "auto-Kampagnen"):
                    self.authorize(path)
        self.assertEqual(self.github.calls, [])

    def test_t12_three_platforms_share_one_approval_not_scheduling(self):
        for target in gate.TARGETS:
            evidence = self.authorize(f"ready-for-buffer/auto-{CAMPAIGN}-{target}.json")
            self.assertEqual(evidence["approved_pr"], 17)
        script = Path(gate.__file__).read_text(encoding="utf-8")
        self.assertNotIn("createPost(", script)
        self.assertNotIn("editPost(", script)
        self.assertNotIn("saveToDraft: false", script)

    def test_t13_bundled_brief_change_in_approval_pr_is_rejected(self):
        self.github.changed_files = [
            {"filename": APPROVAL, "status": "added"},
            {"filename": BRIEF, "status": "modified"},
        ]
        with self.assertRaisesRegex(gate.ApprovalBlocked, "eigenständige"):
            self.authorize()

    def test_direct_push_without_pr_cannot_authorize(self):
        self.github.commits = [{"sha": "b" * 40}]
        with self.assertRaisesRegex(gate.ApprovalBlocked, "eigenständige"):
            self.authorize()
        self.github.commits = [{"sha": "a" * 40}]
        self.github.merged_by = "unknown"
        with self.assertRaisesRegex(gate.ApprovalBlocked, "eigenständige"):
            self.authorize()

    def test_broken_source_path_fails_closed(self):
        self.review["source"] = "../../secrets.png"
        self.write_json(self.review_file, self.review)
        self.approval["image_review_sha256"] = gate.sha256(self.review_file.read_bytes())
        self.save()
        with self.assertRaisesRegex(gate.ApprovalBlocked, "Quellbildpfad"):
            self.authorize()

    def test_duplicate_approval_json_keys_fail_closed(self):
        raw = self.approval_file.read_text(encoding="utf-8")
        self.approval_file.write_text(raw.replace('"state": "approved"',
                                                  '"state": "revoked", "state": "approved"'),
                                      encoding="utf-8")
        with self.assertRaisesRegex(gate.ApprovalBlocked, "Doppelter JSON-Schlüssel"):
            self.authorize()
        self.assertEqual(self.github.calls, [])


if __name__ == "__main__":
    unittest.main()
