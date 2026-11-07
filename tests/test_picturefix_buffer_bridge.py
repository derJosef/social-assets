"""Offline proof for the existing shared Buffer adapter's PictureFix preview mode.

Never uses Buffer tokens, external HTTP, repository receipt writes, or GitHub APIs.
"""
import hashlib
import io
import json
import os
import struct
import sys
import tempfile
from PIL import Image
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import buffer_draft as buffer


COMMIT = "a" * 40
URL = ("https://raw.githubusercontent.com/derJosef/social-assets/" + COMMIT
       + "/media/images/" + buffer.PICTUREFIX_IMAGE_NAME)


def draft(target="facebook", *, url=URL, image_sha256="b" * 64):
    return {
        "format_version": 3,
        "brand": "picturefix",
        "target": target,
        "text": "Kleine Fotos. Große Erinnerungen. KI-generierte Werbeillustration.",
        "media": {"type": "images", "images": [{
            "url": url, "alt_text": "KI-generierte Werbeillustration; keine echte Restaurierung."
        }]},
        "image_sha256": image_sha256,
        "logo_git_blob_sha1": buffer.PICTUREFIX_LOGO_BLOB,
    }


class MockImageResponse(io.BytesIO):
    def __init__(self, content):
        super().__init__(content)
        self.status = 200

    def geturl(self):
        return URL


class PictureFixBufferBridgeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "drafts").mkdir()
        patcher = mock.patch.object(buffer, "ROOT", self.root)
        patcher.start()
        self.addCleanup(patcher.stop)

    def save_and_read(self, payload, filename="picturefix-pf01-facebook.json"):
        path = self.root / "drafts" / filename
        path.write_text(json.dumps(payload), encoding="utf-8")
        return buffer.read_draft("drafts/" + filename)

    def test_exact_picturefix_draft_with_image_passes_offline(self):
        path, text, raw = self.save_and_read(draft())
        self.assertEqual(path, buffer.PICTUREFIX_DRAFT_NAMES["facebook"])
        assets = buffer.parse_assets(raw)
        self.assertEqual(len(assets), 1)
        self.assertEqual(assets[0]["image"]["url"], URL)
        self.assertTrue(text.startswith("Kleine Fotos."))

    def test_exact_instagram_draft_with_image_passes(self):
        path, _, raw = self.save_and_read(draft("instagram"),
                                          "picturefix-pf01-instagram.json")
        self.assertEqual(path, buffer.PICTUREFIX_DRAFT_NAMES["instagram"])
        self.assertEqual(len(buffer.parse_assets(raw)), 1)

    def test_wrong_brand_extra_scheduling_fields_and_missing_logo_are_blocked(self):
        variants = []
        other = draft(); other["brand"] = "ai-agent-builder"; variants.append(other)
        scheduled = draft(); scheduled["dueAt"] = "2027-01-01T00:00:00Z"; variants.append(scheduled)
        missing_logo = draft(); missing_logo.pop("logo_git_blob_sha1"); variants.append(missing_logo)
        wrong_logo = draft(); wrong_logo["logo_git_blob_sha1"] = "0" * 40; variants.append(wrong_logo)
        for variant in variants:
            with self.subTest(keys=sorted(variant), brand=variant.get("brand")):
                with self.assertRaises(ValueError):
                    self.save_and_read(variant)

    def test_unsafe_media_and_guessable_ref_are_blocked(self):
        inputs = [
            URL.replace(COMMIT, "main"),
            URL.replace("raw.githubusercontent.com", "example.com"),
            URL.replace(buffer.PICTUREFIX_IMAGE_NAME, "unverified.png"),
            URL + "?token=secret",
        ]
        for url in inputs:
            with self.subTest(url=url):
                with self.assertRaises(ValueError):
                    self.save_and_read(draft(url=url))

    def test_no_pinterest_or_arbitrary_filenames(self):
        with self.assertRaises(ValueError):
            self.save_and_read(draft("pinterest"), "picturefix-pf01-pinterest.json")
        with self.assertRaises(ValueError):
            self.save_and_read(draft(), "arbitrary-pf-social-post.json")

    def test_must_have_valid_64_hex_sha_and_one_image(self):
        bad = draft(image_sha256="bad")
        with self.assertRaises(ValueError):
            self.save_and_read(bad)
        bad = draft()
        bad["media"]["images"] = []
        with self.assertRaises(ValueError):
            self.save_and_read(bad)

    def test_pixel_and_sha_verification_requires_actual_png_bytes(self):
        # Synthetic fixture: immutable URL + exact byte hash + PNG IHDR.
        image_bytes = io.BytesIO()
        Image.new("RGB", (1080, 1350), (216, 198, 173)).save(image_bytes, format="PNG")
        raw_png = image_bytes.getvalue()
        obj = draft(image_sha256=hashlib.sha256(raw_png).hexdigest())
        assets = buffer.parse_assets(json.dumps(obj).encode())
        with mock.patch.object(buffer.urllib.request, "urlopen",
                               return_value=MockImageResponse(raw_png)):
            buffer.verify_picturefix_image_bytes(obj, assets)
        with mock.patch.object(buffer.urllib.request, "urlopen",
                               return_value=MockImageResponse(raw_png + b"x")):
            with self.assertRaisesRegex(RuntimeError, "SHA-256"):
                buffer.verify_picturefix_image_bytes(obj, assets)

    def test_reject_wrong_png_dimensions_even_when_sha_matches(self):
        image_bytes = io.BytesIO()
        Image.new("RGB", (1000, 1500), (216, 198, 173)).save(image_bytes, format="PNG")
        data = image_bytes.getvalue()
        obj = draft(image_sha256=hashlib.sha256(data).hexdigest())
        assets = buffer.parse_assets(json.dumps(obj).encode())
        with mock.patch.object(buffer.urllib.request, "urlopen",
                               return_value=MockImageResponse(data)):
            with self.assertRaisesRegex(RuntimeError, "dimensions"):
                buffer.verify_picturefix_image_bytes(obj, assets)

    def test_reject_truncated_png_even_if_sha_and_ihdr_match(self):
        image_bytes = io.BytesIO()
        Image.new("RGB", (1080, 1350), (216, 198, 173)).save(image_bytes, format="PNG")
        cropped = image_bytes.getvalue()[:56]
        obj = draft(image_sha256=hashlib.sha256(cropped).hexdigest())
        assets = buffer.parse_assets(json.dumps(obj).encode())
        with mock.patch.object(buffer.urllib.request, "urlopen",
                               return_value=MockImageResponse(cropped)):
            with self.assertRaisesRegex(RuntimeError, "integrity"):
                buffer.verify_picturefix_image_bytes(obj, assets)

    def test_independent_readback_requires_draft_no_due_at_and_attached_image(self):
        valid = {
            "id": "pf-post-123", "channelId": "pf-fb-456",
            "channelService": "facebook", "status": "draft",
            "dueAt": None, "text": "PF text",
            "assets": [{"type": "image", "source": "https://example.com/verified.png"}],
        }
        def inspect(data):
            return buffer.verified_picturefix_post(
                data, post_id="pf-post-123", channel_id="pf-fb-456",
                target="facebook", original_text="PF text",
            )
        self.assertEqual(inspect(valid), "https://example.com/verified.png")
        for changes in (
            {"id": "wrong"}, {"channelId": "wrong"}, {"channelService": "linkedin"},
            {"status": "scheduled"}, {"dueAt": "2027-01-01T00:00:00Z"},
            {"text": "changed"}, {"assets": []},
            {"assets": [{"type": "video", "source": "https://example.com/movie.mp4"}]},
            {"assets": [{"type": "image", "source": "http://example.com/img.png"}]},
        ):
            with self.subTest(changes=changes):
                self.assertIsNone(inspect({**valid, **changes}))

    def test_no_cross_brand_credential_fallback_before_any_api(self):
        raw = json.dumps(draft()).encode()
        env = {
            "GITHUB_REPOSITORY": buffer.REPOSITORY, "GITHUB_REF": "refs/heads/main",
            "GITHUB_TOKEN": "dummy", "BUFFER_API_KEY": "dummy",
            "GITHUB_ACTOR": "derJosef-agents",
            "GITHUB_EVENT_NAME": "workflow_dispatch",
            "BUFFER_BRAND": "picturefix",
        }
        with mock.patch.dict(os.environ, env, clear=True), mock.patch.object(
            buffer, "resolve_channel", side_effect=AssertionError("API must not be reached")
        ):
            with self.assertRaisesRegex(RuntimeError, "authorized brand"):
                buffer.send_draft("drafts/picturefix-pf01-facebook.json",
                                  draft()["text"], raw)
        env["GITHUB_EVENT_NAME"] = "issue_comment"
        env["BUFFER_BRAND"] = "ai-agent-builder"
        with mock.patch.dict(os.environ, env, clear=True):
            with self.assertRaisesRegex(RuntimeError, "authorized brand"):
                buffer.send_draft("drafts/picturefix-pf01-facebook.json",
                                  draft()["text"], raw)
        env["BUFFER_BRAND"] = "picturefix"
        with (mock.patch.dict(os.environ, env, clear=True),
              mock.patch.object(buffer, "discover_picturefix_channels",
                                side_effect=RuntimeError("PictureFix organization mismatch"))):
            with self.assertRaisesRegex(RuntimeError, "organization mismatch"):
                buffer.send_draft("drafts/picturefix-pf01-facebook.json",
                                  draft()["text"], raw)

    def test_legacy_ai_agent_builder_media_still_supported(self):
        old = {
            "format_version": 2, "target": "facebook", "text": "Existing campaign",
            "media": {"type": "images", "images": [
                {"url": URL, "alt_text": "Existing picture"}
            ]},
        }
        raw = json.dumps(old).encode()
        self.assertEqual(len(buffer.parse_assets(raw)), 1)


if __name__ == "__main__":
    unittest.main()
