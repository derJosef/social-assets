"""Untrusted copy/paste Buffer API token handling; no Buffer network requests."""
import json
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import buffer_draft as buffer


class PictureFixApiTokenTests(unittest.TestCase):
    def test_outer_whitespace_is_removed(self):
        self.assertEqual(buffer.normalize_picturefix_api_key("  \r\nraw-buffer-key\n  "),
                         "raw-buffer-key")

    def test_internal_control_chars_and_bearer_prefix_are_rejected(self):
        for token in ("abc\ndef", "abc\rdef", "abc def", "abc\tdef",
                      "Bearer abc", "bearer abc", "abc\x00def",
                      "abc\u00fcdef", "\r\n  ", ""):
            with self.subTest(token_type=repr(token[:3])), self.assertRaises(RuntimeError):
                buffer.normalize_picturefix_api_key(token)

    def test_live_readonly_discovery_receives_only_normalized_key(self):
        env = {
            "GITHUB_REPOSITORY": "derJosef/social-assets",
            "GITHUB_REF": "refs/heads/main",
            "GITHUB_EVENT_NAME": "issue_comment",
            "GITHUB_ACTOR": "derJosef-agents",
            "BUFFER_BRAND": "picturefix",
            "BUFFER_API_KEY": " raw-buffer-key\r\n",
        }
        ids = {"facebook": "pf-fb", "instagram": "pf-ig", "pinterest": "pf-pin"}
        with (mock.patch.dict(os.environ, env, clear=True),
              mock.patch.object(buffer, "discover_picturefix_channels", return_value=ids) as lookup,
              mock.patch.object(buffer, "discover_picturefix_board",
                                return_value="pf-board") as boards,
              mock.patch.object(buffer, "put_receipt", side_effect=AssertionError("write")),
              mock.patch.object(buffer, "buffer_graphql", side_effect=AssertionError("network"))):
            buffer.check_picturefix_connection()
            lookup.assert_called_once_with("raw-buffer-key")
            boards.assert_called_once_with("raw-buffer-key", "pf-pin")

    def test_picturefix_send_uses_normalized_token_before_channel_discovery(self):
        env = {
            "GITHUB_REPOSITORY": buffer.REPOSITORY,
            "GITHUB_REF": "refs/heads/main",
            "GITHUB_EVENT_NAME": "issue_comment",
            "GITHUB_ACTOR": "derJosef-agents",
            "BUFFER_BRAND": "picturefix",
            "BUFFER_API_KEY": " \nraw-buffer-key\n",
            "GITHUB_TOKEN": "dummy-github-token",
        }
        raw = json.dumps({"format_version": 3, "target": "facebook"}).encode()
        with (mock.patch.dict(os.environ, env, clear=True),
              mock.patch.object(buffer, "discover_picturefix_channels",
                                side_effect=RuntimeError("blocked for test")) as lookup,
              mock.patch.object(buffer, "put_receipt", side_effect=AssertionError("write"))):
            with self.assertRaisesRegex(RuntimeError, "blocked for test"):
                buffer.send_draft("drafts/picturefix-pf01-facebook.json", "text", raw)
            lookup.assert_called_once_with("raw-buffer-key", channel_cache=None)


if __name__ == "__main__":
    unittest.main()
