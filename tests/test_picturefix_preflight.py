"""PictureFix read-only preflight: explicitly no Buffer mutation and no AAB fallback."""
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
        "BUFFER_FACEBOOK_CHANNEL_ID": "pf-fb",
        "BUFFER_INSTAGRAM_CHANNEL_ID": "pf-ig",
        "BUFFER_PINTEREST_CHANNEL_ID": "pf-pin",
        "BUFFER_PICTUREFIX_PINTEREST_BOARD_SERVICE_ID": "pf-pin-board",
    }


class PictureFixReadOnlyPreflightTests(unittest.TestCase):
    def test_three_channels_and_board_checked_without_mutation(self):
        with (mock.patch.dict(os.environ, safe_env(), clear=True),
              mock.patch.object(buffer, "resolve_channel",
                                side_effect=lambda token, target, preferred_id,
                                channel_cache=None: preferred_id) as resolve,
              mock.patch.object(buffer, "verify_picturefix_board") as board,
              mock.patch.object(buffer, "put_receipt", side_effect=AssertionError("no writes")),
              mock.patch.object(buffer, "fetch_receipt", side_effect=AssertionError("no receipts"))):
            buffer.check_picturefix_connection()
            self.assertEqual(resolve.call_count, 3)
            self.assertEqual([call.args[1] for call in resolve.call_args_list],
                             ["facebook", "instagram", "pinterest"])
            self.assertTrue(all(c.args[0] == "dedicated-pf-key"
                                for c in resolve.call_args_list))
            board.assert_called_once_with("dedicated-pf-key", "pf-pin", "pf-pin-board")

    def test_missing_credentials_rejected_no_aab_fallback(self):
        for key in ("BUFFER_API_KEY", "BUFFER_FACEBOOK_CHANNEL_ID",
                    "BUFFER_INSTAGRAM_CHANNEL_ID", "BUFFER_PINTEREST_CHANNEL_ID",
                    "BUFFER_PICTUREFIX_PINTEREST_BOARD_SERVICE_ID"):
            env = safe_env()
            del env[key]
            env["BUFFER_AAB_API_KEY"] = "must-not-fallback"
            with self.subTest(key=key), mock.patch.dict(os.environ, env, clear=True):
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
              mock.patch.object(buffer, "resolve_channel",
                                side_effect=RuntimeError("wrong channel")),
              mock.patch.object(buffer, "verify_picturefix_board") as board):
            with self.assertRaises(RuntimeError):
                buffer.check_picturefix_connection()
            board.assert_not_called()


if __name__ == "__main__":
    unittest.main()
