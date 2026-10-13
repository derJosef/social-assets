"""Offline tests for GitHub Contents API receipt decoding, never Buffer calls."""
import base64
import json
import textwrap
import unittest

from scripts.orchestrator_verify_buffer import decode_receipt


class GitHubReceiptDecodeTests(unittest.TestCase):
    def test_accepts_github_line_wrapped_base64_without_changing_payload(self):
        record = {
            "draft_file": "ready-for-buffer/auto-2026-10-13-lieferanten-pdf-prueftor-e2e-003-linkedin.json",
            "target": "linkedin",
            "buffer_post_id": "6acdefc5ca68ebbd369b79a7",
            "state": "verified_prescheduled_draft_not_queued",
            "due_at_utc": "2026-10-28T15:00:00Z",
        }
        encoded = base64.b64encode(json.dumps(record).encode("utf-8")).decode("ascii")
        github_content = "\n".join(textwrap.wrap(encoded, 60)) + "\n"
        self.assertIn("\n", github_content)
        actual = decode_receipt({"content": github_content}, "linkedin")
        self.assertEqual(actual, record)

    def test_preserves_base64_integrity_check_against_invalid_character(self):
        with self.assertRaisesRegex(RuntimeError, "Corrupt delivery receipt"):
            decode_receipt({"content": "eyJ4IjoxfQ==\n!not-base64"}, "facebook")

    def test_rejects_non_json_and_missing_api_wrapper(self):
        with self.assertRaisesRegex(RuntimeError, "Missing GitHub receipt"):
            decode_receipt({"not_content": "abc"}, "instagram")
        raw = base64.b64encode(b"not-json").decode("ascii")
        with self.assertRaisesRegex(RuntimeError, "Corrupt delivery receipt"):
            decode_receipt({"content": raw}, "linkedin")


if __name__ == "__main__":
    unittest.main()
