"""PictureFix read-only tenant preflight; no mutation or AAB credential fallback."""
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import buffer_draft as buffer


def safe_env():
    return {
        "GITHUB_REPOSITORY": "derJosef/social-assets",
        "GITHUB_REF": "refs/heads/main",
        "GITHUB_EVENT_NAME": "issue_comment",
        "GITHUB_ACTOR": "derJosef-agents",
        "BUFFER_BRAND": "picturefix",
        "BUFFER_API_KEY": "dedicated-pf-key",
    }


class PictureFixReadOnlyPreflightTests(unittest.TestCase):
    def test_three_exact_profiles_and_board_checked_without_mutation(self):
        ids = {"facebook": "pf-fb", "instagram": "pf-ig", "pinterest": "pf-pin"}
        with (mock.patch.dict(os.environ, safe_env(), clear=True),
              mock.patch.object(buffer, "discover_picturefix_channels",
                                return_value=ids) as channels,
              mock.patch.object(buffer, "discover_picturefix_board",
                                return_value="pf-board") as board,
              mock.patch.object(buffer, "put_receipt", side_effect=AssertionError("no writes")),
              mock.patch.object(buffer, "fetch_receipt", side_effect=AssertionError("no receipts"))):
            buffer.check_picturefix_connection()
            channels.assert_called_once_with("dedicated-pf-key")
            board.assert_called_once_with("dedicated-pf-key", "pf-pin")

    def test_missing_dedicated_token_rejected_without_aab_fallback(self):
        env = safe_env()
        del env["BUFFER_API_KEY"]
        env["BUFFER_AAB_API_KEY"] = "not-a-pf-token"
        with mock.patch.dict(os.environ, env, clear=True):
            with self.assertRaises(RuntimeError):
                buffer.check_picturefix_connection()

    def test_wrong_event_identity_and_brand_denied(self):
        for key, val in (("GITHUB_REF", "refs/heads/other"),
                         ("GITHUB_ACTOR", "derJosef"),
                         ("GITHUB_EVENT_NAME", "workflow_dispatch"),
                         ("BUFFER_BRAND", "ai-agent-builder"),
                         ("GITHUB_REPOSITORY", "other/repo")):
            env = safe_env()
            env[key] = val
            with self.subTest(key=key), mock.patch.dict(os.environ, env, clear=True):
                with self.assertRaises(RuntimeError):
                    buffer.check_picturefix_connection()

    def test_board_is_checked_only_after_all_channels_are_verified(self):
        with (mock.patch.dict(os.environ, safe_env(), clear=True),
              mock.patch.object(buffer, "discover_picturefix_channels",
                                side_effect=RuntimeError("wrong channel")),
              mock.patch.object(buffer, "discover_picturefix_board") as board):
            with self.assertRaises(RuntimeError):
                buffer.check_picturefix_connection()
            board.assert_not_called()


if __name__ == "__main__":
    unittest.main()
