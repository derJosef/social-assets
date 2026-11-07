"""PictureFix Facebook/Instagram diagnostic stays usable when Pinterest boards are empty."""
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import buffer_draft as buffer


def safe_env():
    return {
        "GITHUB_REPOSITORY": buffer.REPOSITORY,
        "GITHUB_REF": "refs/heads/main",
        "GITHUB_EVENT_NAME": "issue_comment",
        "GITHUB_ACTOR": "derJosef-agents",
        "BUFFER_BRAND": "picturefix",
        "BUFFER_API_KEY": "dedicated-pf-key",
    }


class IndependentPictureFixSocialPreflight(unittest.TestCase):
    def test_facebook_instagram_are_verified_without_board_api(self):
        channels = {"facebook": "pf-fb", "instagram": "pf-ig", "pinterest": "pf-pin"}
        with (mock.patch.dict(os.environ, safe_env(), clear=True),
              mock.patch.object(buffer, "discover_picturefix_channels",
                                return_value=channels) as get_channels,
              mock.patch.object(buffer, "discover_picturefix_board",
                                side_effect=AssertionError("Pinterest must not be requested")) as board,
              mock.patch.object(buffer, "send_draft", side_effect=AssertionError("No Buffer posts")),
              mock.patch.object(buffer, "put_receipt", side_effect=AssertionError("No GitHub writes")),
              mock.patch.object(buffer, "fetch_receipt", side_effect=AssertionError("No receipts"))):
            buffer.check_picturefix_connection(require_pinterest_board=False)
            get_channels.assert_called_once_with("dedicated-pf-key")
            board.assert_not_called()

    def test_original_full_preflight_still_enforces_pinterest_board(self):
        channels = {"facebook": "pf-fb", "instagram": "pf-ig", "pinterest": "pf-pin"}
        with (mock.patch.dict(os.environ, safe_env(), clear=True),
              mock.patch.object(buffer, "discover_picturefix_channels",
                                return_value=channels),
              mock.patch.object(buffer, "discover_picturefix_board",
                                side_effect=RuntimeError("Pinterest board missing")) as board):
            with self.assertRaisesRegex(RuntimeError, "Pinterest board missing"):
                buffer.check_picturefix_connection()
            board.assert_called_once_with("dedicated-pf-key", "pf-pin")

    def test_wrong_brand_and_wrong_actor_rejected_without_api(self):
        for key, value in (
            ("GITHUB_ACTOR", "derJosef"),
            ("BUFFER_BRAND", "ai-agent-builder"),
            ("GITHUB_REF", "refs/heads/feature"),
        ):
            env = safe_env()
            env[key] = value
            with (self.subTest(key=key),
                  mock.patch.dict(os.environ, env, clear=True),
                  mock.patch.object(buffer, "discover_picturefix_channels",
                                    side_effect=AssertionError("No Buffer requests"))):
                with self.assertRaises(RuntimeError):
                    buffer.check_picturefix_connection(require_pinterest_board=False)


if __name__ == "__main__":
    unittest.main()
