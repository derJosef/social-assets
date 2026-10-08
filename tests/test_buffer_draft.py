#!/usr/bin/env python3
"""Offline regression tests; no Buffer or GitHub API calls."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import buffer_draft as integration


class DraftValidationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "drafts").mkdir()
        (self.root / "ready-for-buffer").mkdir()
        self.root_patch = mock.patch.object(integration, "ROOT", self.root)
        self.root_patch.start()
        self.addCleanup(self.root_patch.stop)

    def write_draft(self, where, name="probe.json"):
        path = self.root / where / name
        path.write_text(
            json.dumps({"format_version": 1, "target": "linkedin", "text": "Prüftext"}, ensure_ascii=False),
            encoding="utf-8",
        )
        return path

    def test_manual_draft_is_valid(self):
        self.write_draft("drafts")
        relative, text, _ = integration.read_draft("drafts/probe.json")
        self.assertEqual("drafts/probe.json", relative)
        self.assertEqual("Prüftext", text)

    def test_approved_draft_is_valid(self):
        self.write_draft("ready-for-buffer")
        relative, text, _ = integration.read_draft("ready-for-buffer/probe.json")
        self.assertEqual("ready-for-buffer/probe.json", relative)
        self.assertEqual("Prüftext", text)

    def test_unapproved_external_file_is_rejected(self):
        self.write_draft("drafts")
        outside = self.root / "other.json"
        outside.write_text('{"format_version":1,"target":"linkedin","text":"secret"}')
        with self.assertRaises(ValueError):
            integration.read_draft("other.json")

    def test_nested_path_is_rejected(self):
        nested = self.root / "ready-for-buffer" / "sub"
        nested.mkdir()
        (nested / "post.json").write_text(
            '{"format_version":1,"target":"linkedin","text":"A"}'
        )
        with self.assertRaises(ValueError):
            integration.read_draft("ready-for-buffer/sub/post.json")

    def test_receipt_name_differs_for_manual_and_approved(self):
        self.assertNotEqual(
            integration.receipt_path("drafts/probe.json"),
            integration.receipt_path("ready-for-buffer/probe.json"),
        )


class ChannelSelectionTests(unittest.TestCase):
    def fake_api(self, token, query, variables):
        if query == integration.GET_ORGANIZATIONS:
            return {"account": {"organizations": [{"id": "o1"}]}}
        if query == integration.GET_CHANNELS:
            return {"channels": [{"id": "linked1", "service": "linkedin"}]}
        raise AssertionError("Unexpected API query")

    def test_automatic_selection_when_one_linkedin_channel(self):
        with mock.patch.object(integration, "buffer_graphql", side_effect=self.fake_api):
            self.assertEqual("linked1", integration.resolve_linkedin_channel("dummy-key"))

    def test_explicit_wrong_channel_is_rejected(self):
        with mock.patch.object(integration, "buffer_graphql", side_effect=self.fake_api):
            with self.assertRaises(RuntimeError):
                integration.resolve_linkedin_channel("dummy-key", "wrong")


if __name__ == "__main__":
    unittest.main()
