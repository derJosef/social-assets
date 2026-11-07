"""Sticken & Lasern dedicated Buffer secret check: read-only, never share credentials."""
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import buffer_draft as buffer


def environment():
    return {
        "GITHUB_REPOSITORY": buffer.REPOSITORY,
        "GITHUB_REF": "refs/heads/main",
        "GITHUB_EVENT_NAME": "issue_comment",
        "GITHUB_ACTOR": "derJosef-agents",
        "BUFFER_BRAND": "sticken-lasern",
        "BUFFER_API_KEY": "  sticken-only-token\r\n",
    }


class StickenLasernBufferReadOnlyTests(unittest.TestCase):
    def test_only_separate_business_organization_is_accepted(self):
        response = {"account": {"organizations": [
            {"name": "Sticken & Lasern", "id": "sticken-org", "channelCount": 2}
        ]}}
        with (mock.patch.dict(os.environ, environment(), clear=True),
              mock.patch.object(buffer, "buffer_graphql", return_value=response) as query,
              mock.patch.object(buffer, "put_receipt", side_effect=AssertionError("receipt write")),
              mock.patch.object(buffer, "fetch_receipt", side_effect=AssertionError("receipt access")),
              mock.patch.object(buffer, "send_draft", side_effect=AssertionError("post write"))):
            buffer.check_sticken_lasern_connection()
            query.assert_called_once_with(
                "sticken-only-token", buffer.GET_PICTUREFIX_ORGANIZATIONS, {}
            )

    def test_aliases_are_only_known_business_names(self):
        for name in ("Sticken & Lasern", "Sticken-Lasern", "Veredelt! by Claudia"):
            with self.subTest(name=name), mock.patch.dict(os.environ, environment(), clear=True):
                with mock.patch.object(buffer, "buffer_graphql", return_value={
                    "account": {"organizations": [{"name": name, "id": "sl-org", "channelCount": 0}]}
                }):
                    buffer.check_sticken_lasern_connection()

    def test_other_buffer_accounts_and_ambiguous_orgs_are_blocked(self):
        for organizations in (
            [{"name": "PictureFix", "id": "pf", "channelCount": 3}],
            [{"name": "AI Agent Builder", "id": "aab", "channelCount": 3}],
            [{"name": "Sticken & Lasern", "id": "sl", "channelCount": 2},
             {"name": "PictureFix", "id": "pf", "channelCount": 3}],
            [{"name": "Sticken & Lasern", "id": "", "channelCount": 2}],
            [],
        ):
            with self.subTest(orgs=organizations), mock.patch.dict(os.environ, environment(), clear=True):
                with mock.patch.object(buffer, "buffer_graphql", return_value={
                    "account": {"organizations": organizations}
                }):
                    with self.assertRaisesRegex(RuntimeError, "no uniquely verified"):
                        buffer.check_sticken_lasern_connection()

    def test_key_never_falls_back_to_picturefix_or_aab(self):
        env = environment()
        del env["BUFFER_API_KEY"]
        env["BUFFER_PICTUREFIX_API_KEY"] = "wrong-tenant"
        env["BUFFER_AAB_API_KEY"] = "wrong-tenant"
        with mock.patch.dict(os.environ, env, clear=True):
            with mock.patch.object(buffer, "buffer_graphql", side_effect=AssertionError("No API")):
                with self.assertRaisesRegex(RuntimeError, "Missing dedicated Sticken-Lasern"):
                    buffer.check_sticken_lasern_connection()

    def test_wrong_identity_event_brand_or_ref_fail_before_api(self):
        for key, value in (
            ("GITHUB_REPOSITORY", "other/repo"),
            ("GITHUB_REF", "refs/heads/other"),
            ("GITHUB_ACTOR", "Sticken-Lasern"),
            ("GITHUB_EVENT_NAME", "workflow_dispatch"),
            ("BUFFER_BRAND", "picturefix"),
        ):
            env = environment()
            env[key] = value
            with self.subTest(key=key), mock.patch.dict(os.environ, env, clear=True):
                with mock.patch.object(buffer, "buffer_graphql", side_effect=AssertionError("No API")):
                    with self.assertRaisesRegex(RuntimeError, "control issue"):
                        buffer.check_sticken_lasern_connection()

    def test_invalid_paste_is_rejected_without_leaking_token(self):
        for raw in ("Bearer invalid", "bad key", "bad\nkey", ""):
            env = environment()
            env["BUFFER_API_KEY"] = raw
            with self.subTest(kind=repr(raw[:4])), mock.patch.dict(os.environ, env, clear=True):
                with mock.patch.object(buffer, "buffer_graphql", side_effect=AssertionError("No API")):
                    with self.assertRaises(RuntimeError) as ctx:
                        buffer.check_sticken_lasern_connection()
                    self.assertNotIn(raw or "secret-string", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
