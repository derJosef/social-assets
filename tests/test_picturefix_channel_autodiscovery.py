"""Fail-closed live PictureFix channel + Pinterest board autodiscovery tests."""
import copy
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import buffer_draft as buffer


def responses():
    return {
        "org": {"account": {"organizations": [{
            "id": "org-pf", "name": "PictureFix", "channelCount": 3
        }]}},
        "channels": {"channels": [
            {"id": "pf-fb", "service": "facebook", "name": "PictureFix Fotorestaurierung",
             "organizationId": "org-pf", "isDisconnected": False, "isLocked": False},
            {"id": "pf-ig", "service": "instagram", "name": "picturefix.de",
             "organizationId": "org-pf", "isDisconnected": False, "isLocked": False},
            {"id": "pf-pin", "service": "pinterest", "name": "picturefixde",
             "organizationId": "org-pf", "isDisconnected": False, "isLocked": False},
        ]},
        "boards": {"channel": {"id": "pf-pin", "metadata": {
            "boards": [{"serviceId": "pf-board"}]
        }}},
    }


def graphql_fixture(data, query, variables):
    if query == buffer.GET_PICTUREFIX_ORGANIZATIONS:
        return data["org"]
    if query == buffer.GET_PICTUREFIX_CHANNELS:
        if variables != {"organizationId": "org-pf"}:
            raise AssertionError("Unexpected organization ID")
        return data["channels"]
    if query == buffer.GET_PICTUREFIX_PINTEREST_BOARDS:
        if variables != {"id": "pf-pin"}:
            raise AssertionError("Unexpected Pinterest channel ID")
        return data["boards"]
    raise AssertionError("No other API query should be made")


class PictureFixAutodiscoveryTests(unittest.TestCase):
    def discover(self, changes=None, environment=None):
        data = responses()
        if changes:
            changes(data)
        with (mock.patch.dict(os.environ, environment or {}, clear=True),
              mock.patch.object(buffer, "buffer_graphql",
                  side_effect=lambda token, query, variables:
                      graphql_fixture(data, query, variables)) as api):
            ids = buffer.discover_picturefix_channels("pf-secret")
            board = buffer.discover_picturefix_board("pf-secret", ids["pinterest"])
        return ids, board, api

    def test_live_three_exact_profiles_single_board(self):
        ids, board, api = self.discover()
        self.assertEqual(ids, {"facebook": "pf-fb", "instagram": "pf-ig", "pinterest": "pf-pin"})
        self.assertEqual(board, "pf-board")
        self.assertEqual(api.call_count, 3)
        self.assertTrue(all(c.args[0] == "pf-secret" for c in api.call_args_list))

    def test_cache_does_not_send_more_queries_or_change_identities(self):
        data = responses()
        cache = {}
        with mock.patch.dict(os.environ, {}, clear=True), mock.patch.object(
            buffer, "buffer_graphql",
            side_effect=lambda token, query, variables: graphql_fixture(data, query, variables)
        ) as api:
            one = buffer.discover_picturefix_channels("pf-secret", channel_cache=cache)
            two = buffer.discover_picturefix_channels("pf-secret", channel_cache=cache)
        self.assertEqual(one, two)
        self.assertEqual(api.call_count, 2)

    def test_wrong_or_extra_organization_fail_closed(self):
        for corrupt in (
            lambda d: d["org"]["account"]["organizations"][0].update(name="AI Agent Builder"),
            lambda d: d["org"]["account"]["organizations"].append(
                {"id": "aab", "name": "AI Agent Builder", "channelCount": 3}),
            lambda d: d["org"]["account"]["organizations"][0].update(channelCount=2),
            lambda d: d["org"].update(account=None),
        ):
            with self.subTest(corrupt=corrupt), self.assertRaises(RuntimeError):
                self.discover(corrupt)

    def test_channel_name_service_ownership_lock_and_uniqueness_fail_closed(self):
        for corrupt in (
            lambda d: d["channels"]["channels"][0].update(name="Not PictureFix"),
            lambda d: d["channels"]["channels"][0].update(service="linkedin"),
            lambda d: d["channels"]["channels"][0].update(isLocked=True),
            lambda d: d["channels"]["channels"][0].update(isDisconnected=True),
            lambda d: d["channels"]["channels"][0].update(organizationId="other-org"),
            lambda d: d["channels"]["channels"][0].update(id="pf-ig"),
            lambda d: d["channels"]["channels"].pop(),
            lambda d: d["channels"]["channels"].append(copy.deepcopy(d["channels"]["channels"][0])),
        ):
            with self.subTest(corrupt=corrupt), self.assertRaises(RuntimeError):
                self.discover(corrupt)

    def test_conflicting_explicit_channel_id_is_rejected(self):
        with self.assertRaises(RuntimeError):
            self.discover(environment={"BUFFER_INSTAGRAM_CHANNEL_ID": "wrong-id"})

    def test_one_explicit_valid_channel_id_is_compatible(self):
        ids, board, _ = self.discover(
            environment={"BUFFER_INSTAGRAM_CHANNEL_ID": "pf-ig"})
        self.assertEqual(ids["instagram"], "pf-ig")

    def test_several_boards_require_an_explicit_choice(self):
        def add_second(d):
            d["boards"]["channel"]["metadata"]["boards"].append({"serviceId": "another-board"})
        with self.assertRaises(RuntimeError):
            self.discover(add_second)
        ids, board, _ = self.discover(add_second,
            environment={"BUFFER_PICTUREFIX_PINTEREST_BOARD_SERVICE_ID": "pf-board"})
        self.assertEqual(ids["pinterest"], "pf-pin")
        self.assertEqual(board, "pf-board")

    def test_wrong_board_choice_is_rejected(self):
        with self.assertRaises(RuntimeError):
            self.discover(environment={
                "BUFFER_PICTUREFIX_PINTEREST_BOARD_SERVICE_ID": "someone-elses-board"
            })

    def test_invalid_boards_are_rejected(self):
        for corrupt in (
            lambda d: d["boards"]["channel"]["metadata"].update(boards=[]),
            lambda d: d["boards"]["channel"]["metadata"].update(boards=[{}]),
            lambda d: d["boards"]["channel"]["metadata"].update(
                boards=[{"serviceId": "pf-board"}, {"serviceId": "pf-board"}]),
            lambda d: d["boards"]["channel"].update(id="wrong-channel"),
        ):
            with self.subTest(corrupt=corrupt), self.assertRaises(RuntimeError):
                self.discover(corrupt)


if __name__ == "__main__":
    unittest.main()
