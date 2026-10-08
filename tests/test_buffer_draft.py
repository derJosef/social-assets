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




class MultiChannelTests(unittest.TestCase):
    IMAGE = "https://raw.githubusercontent.com/derJosef/social-assets/main/media/images/test.png"
    PDF = "https://raw.githubusercontent.com/derJosef/social-assets/main/media/documents/test.pdf"

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "drafts").mkdir()
        (self.root / "ready-for-buffer").mkdir()
        p = mock.patch.object(integration, "ROOT", self.root)
        p.start()
        self.addCleanup(p.stop)

    def validate(self, record):
        path = self.root / "drafts" / "check.json"
        path.write_text(json.dumps(record), encoding="utf-8")
        return integration.read_draft("drafts/check.json")

    def test_facebook_text_is_allowed(self):
        _, text, raw = self.validate({"format_version": 1, "target": "facebook", "text": "Facebook test"})
        self.assertEqual(text, "Facebook test")
        self.assertEqual(integration.parse_assets(raw), [])

    def test_instagram_text_only_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "mindestens ein Bild"):
            self.validate({"format_version": 1, "target": "instagram", "text": "No image"})

    def test_instagram_single_image_is_allowed(self):
        self.validate({"format_version": 2, "target": "instagram", "text": "Caption",
            "media": {"type": "images", "images": [{"url": self.IMAGE, "alt_text": "Ein Testbild"}]}})

    def test_facebook_document_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "ausschließlich für LinkedIn"):
            self.validate({"format_version": 2, "target": "facebook", "text": "PDF",
                "media": {"type": "document", "url": self.PDF, "thumbnail_url": self.IMAGE, "title": "PDF"}})

    def test_instagram_document_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "ausschließlich für LinkedIn"):
            self.validate({"format_version": 2, "target": "instagram", "text": "PDF",
                "media": {"type": "document", "url": self.PDF, "thumbnail_url": self.IMAGE, "title": "PDF"}})

    def test_instagram_over_ten_images_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "maximal 10 Bilder"):
            self.validate({"format_version": 2, "target": "instagram", "text": "Many",
                "media": {"type": "images", "images": [
                    {"url": f"https://raw.githubusercontent.com/derJosef/social-assets/main/media/images/i{i}.png",
                     "alt_text": "Bild"} for i in range(11)]}})

    def test_instagram_caption_limit(self):
        with self.assertRaisesRegex(ValueError, "2200"):
            self.validate({"format_version": 2, "target": "instagram", "text": "x" * 2201,
                "media": {"type": "images", "images": [{"url": self.IMAGE, "alt_text": "Bild"}]}})

    def test_unknown_target_is_rejected(self):
        with self.assertRaises(ValueError):
            self.validate({"format_version": 1, "target": "picturefix", "text": "Wrong brand"})

    def test_channel_selection_never_crosses_services(self):
        def api(token, query, variables):
            if query == integration.GET_ORGANIZATIONS:
                return {"account": {"organizations": [{"id": "o1"}]}}
            return {"channels": [
                {"id": "id_li", "service": "linkedin"},
                {"id": "id_fb", "service": "facebook"},
                {"id": "id_ig", "service": "instagram"}]}
        with mock.patch.object(integration, "buffer_graphql", side_effect=api):
            self.assertEqual(integration.resolve_channel("token", "facebook"), "id_fb")
            self.assertEqual(integration.resolve_channel("token", "instagram"), "id_ig")
            self.assertEqual(integration.resolve_channel("token", "linkedin"), "id_li")
            with self.assertRaises(RuntimeError):
                integration.resolve_channel("token", "facebook", "id_ig")

    def test_ambiguous_facebook_channel_requires_preference(self):
        def api(token, query, variables):
            if query == integration.GET_ORGANIZATIONS:
                return {"account": {"organizations": [{"id": "o1"}]}}
            return {"channels": [
                {"id": "id_fb1", "service": "facebook"},
                {"id": "id_fb2", "service": "facebook"}]}
        with mock.patch.object(integration, "buffer_graphql", side_effect=api):
            with self.assertRaisesRegex(RuntimeError, "Mehrere facebook-Kanäle"):
                integration.resolve_channel("token", "facebook")
            self.assertEqual(integration.resolve_channel("token", "facebook", "id_fb2"), "id_fb2")

    def test_facebook_metadata_has_required_post_type(self):
        self.assertEqual({"facebook": {"type": "post"}}, integration.platform_metadata("facebook"))

    def test_instagram_metadata_has_two_required_fields(self):
        self.assertEqual(
            {"instagram": {"type": "post", "shouldShareToFeed": True}},
            integration.platform_metadata("instagram"),
        )

    def test_linkedin_metadata_unchanged(self):
        self.assertIsNone(integration.platform_metadata("linkedin"))

    def test_graphql_query_passes_metadata_to_create_post(self):
        self.assertIn("$metadata: PostInputMetaData", integration.CREATE_DRAFT)
        self.assertIn("metadata: $metadata", integration.CREATE_DRAFT)
        self.assertIn("saveToDraft: true", integration.CREATE_DRAFT)

    def test_only_drafts_mutation(self):
        self.assertIn("saveToDraft: true", integration.CREATE_DRAFT)
        self.assertNotIn("saveToDraft: false", integration.CREATE_DRAFT)



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
            @property
            def headers(self):
                return {"Content-Type": "image/png", "Content-Length": "25430"}
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
