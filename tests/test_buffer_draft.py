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



class MediaAssetTests(unittest.TestCase):
    IMAGE = "https://raw.githubusercontent.com/derJosef/social-assets/main/media/images/probe.png"
    IMAGE_2 = "https://raw.githubusercontent.com/derJosef/social-assets/main/media/images/probe2.jpg"
    PDF = "https://raw.githubusercontent.com/derJosef/social-assets/main/media/documents/probe.pdf"

    def decode(self, media):
        obj = {"format_version": 2, "target": "linkedin", "text": "Probetext", "media": media}
        return integration.parse_assets(json.dumps(obj).encode("utf-8"))

    def test_image_assets_include_alt_text(self):
        assets = self.decode({"type": "images", "images": [
            {"url": self.IMAGE, "alt_text": "Bild mit einem Prozessdiagramm"},
            {"url": self.IMAGE_2, "alt_text": "Vergrößerung"}
        ]})
        self.assertEqual(2, len(assets))
        self.assertEqual("Bild mit einem Prozessdiagramm", assets[0]["image"]["metadata"]["altText"])

    def test_document_requires_title_and_thumbnail(self):
        assets = self.decode({
            "type": "document", "url": self.PDF, "thumbnail_url": self.IMAGE, "title": "Testkarussell"
        })
        self.assertEqual([{"document": {
            "url": self.PDF, "thumbnailUrl": self.IMAGE, "title": "Testkarussell"
        }}], assets)

    def test_document_missing_thumbnail_fails(self):
        with self.assertRaises(ValueError):
            self.decode({"type": "document", "url": self.PDF, "title": "No image"})

    def test_external_host_rejected(self):
        with self.assertRaises(ValueError):
            self.decode({"type": "images", "images": [
                {"url": "https://example.com/random.png", "alt_text": "Extern"}
            ]})

    def test_query_in_media_url_rejected(self):
        with self.assertRaises(ValueError):
            self.decode({"type": "images", "images": [
                {"url": self.IMAGE + "?token=secret", "alt_text": "Gefährlich"}
            ]})

    def test_duplicate_media_rejected(self):
        with self.assertRaises(ValueError):
            self.decode({"type": "images", "images": [
                {"url": self.IMAGE, "alt_text": "Erstes Bild"},
                {"url": self.IMAGE, "alt_text": "Zweites Bild"}
            ]})

    def test_more_than_twenty_images_rejected(self):
        with self.assertRaises(ValueError):
            self.decode({"type": "images", "images": [
                {"url": self.IMAGE, "alt_text": "Test"} for _ in range(21)
            ]})

    def test_media_must_be_declared_on_v2(self):
        with self.assertRaises(ValueError):
            integration.parse_assets(b'{"format_version":2,"target":"linkedin","text":"Hallo"}')

    def test_only_one_media_type(self):
        with self.assertRaises(ValueError):
            self.decode({"type":"video", "url":"https://example.com/file.mp4"})

    def test_mutation_must_always_save_as_draft(self):
        query = integration.CREATE_DRAFT
        self.assertIn("saveToDraft: true", query)
        self.assertIn("assets: $assets", query)
        self.assertNotIn("shareNow", query)

    def test_public_media_preflight_head_check(self):
        asset = {"image": {"url": self.IMAGE}}
        headers = {"Content-Type": "image/png", "Content-Length": "25430"}
        class Response:
            def __enter__(self): return self
            def __exit__(self, *a): return False
            self_headers = headers
            @property
            def headers(self): return self.self_headers
        with mock.patch.object(integration.urllib.request, "urlopen", return_value=Response()) as call:
            integration.verify_media_access([asset])
        self.assertEqual("HEAD", call.call_args.args[0].get_method())

    def test_media_url_404_stops_preflight(self):
        import urllib.error
        asset = {"image": {"url": self.IMAGE}}
        with mock.patch.object(
            integration.urllib.request, "urlopen",
            side_effect=urllib.error.HTTPError(self.IMAGE, 404, "not found", {}, None),
        ):
            with self.assertRaises(RuntimeError):
                integration.verify_media_access([asset])


if __name__ == "__main__":
    unittest.main()
