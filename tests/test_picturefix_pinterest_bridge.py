"""Fail-closed PictureFix PF-01 Pinterest tests; no real HTTP or Buffer mutations."""
import hashlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import buffer_draft as buffer

COMMIT = "a" * 40
PIN_URL = (
    f"https://raw.githubusercontent.com/derJosef/social-assets/{COMMIT}/media/images/"
    + buffer.PICTUREFIX_PINTEREST_IMAGE_NAME
)


def record(**changes):
    result = {
        "format_version": 3,
        "brand": "picturefix",
        "target": "pinterest",
        "text": "Kleine Fotos. Große Erinnerungen. KI-generierte Werbeillustration.",
        "media": {
            "type": "images",
            "images": [{"url": PIN_URL, "alt_text": "KI-generierte Werbeillustration."}],
        },
        "image_sha256": "b" * 64,
        "logo_git_blob_sha1": buffer.PICTUREFIX_LOGO_BLOB,
        "pinterest_title": "Kleine Fotos, große Erinnerungen",
        "pinterest_url": "https://picturefix.de",
    }
    result.update(changes)
    return result


class MockImageResponse(io.BytesIO):
    def __init__(self, body):
        super().__init__(body)
        self.status = 200

    def geturl(self):
        return PIN_URL


class PictureFixPinterestDraftTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        (root / "drafts").mkdir()
        patcher = mock.patch.object(buffer, "ROOT", root)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.root = root

    def read(self, entry=None, path="drafts/picturefix-pf01-pinterest.json"):
        entry = record() if entry is None else entry
        (self.root / path).write_text(json.dumps(entry), encoding="utf-8")
        return buffer.read_draft(path)

    def test_only_pinned_pinterest_original_is_accepted(self):
        draft_path, text, raw = self.read()
        self.assertEqual(draft_path, buffer.PICTUREFIX_DRAFT_NAMES["pinterest"])
        self.assertEqual(text, record()["text"])
        self.assertEqual(len(buffer.parse_assets(raw)), 1)

    def test_legacy_pinterest_never_inherits_aab_authority(self):
        with self.assertRaises(ValueError):
            self.read({"format_version": 2, "target": "pinterest",
                       "text": "Forbidden AAB Pinterest", "media": record()["media"]})

    def test_wrong_filename_is_rejected(self):
        with self.assertRaises(ValueError):
            self.read(path="drafts/other-picturefix-pin.json")

    def test_pinterest_title_destination_and_schema_are_fixed(self):
        for changes in (
            {"pinterest_title": ""},
            {"pinterest_url": "https://example.org"},
            {"pinterest_title": "x" * 101},
            {"published": True},
            {"dueAt": "2026-11-09T12:00:00Z"},
        ):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.read(record(**changes))

    def test_pinterest_illustration_has_dedicated_filename(self):
        media = {"type": "images", "images": [{
            "url": PIN_URL.replace(buffer.PICTUREFIX_PINTEREST_IMAGE_NAME,
                                   buffer.PICTUREFIX_IMAGE_NAME),
            "alt_text": "KI-generierte Illustration."
        }]}
        with self.assertRaises(ValueError):
            self.read(record(media=media))

    def test_explicit_board_from_pinterest_channel_required(self):
        with mock.patch.object(buffer, "buffer_graphql", return_value={
            "channel": {"id": "pf-pin-channel", "metadata": {
                "boards": [{"serviceId": "pf-board-one"}, {"serviceId": "pf-board-two"}]
            }}
        }) as graphql:
            buffer.verify_picturefix_board("pf-key", "pf-pin-channel", "pf-board-one")
            graphql.assert_called_once_with(
                "pf-key", buffer.GET_PICTUREFIX_PINTEREST_BOARDS, {"id": "pf-pin-channel"}
            )
            with self.assertRaises(RuntimeError):
                buffer.verify_picturefix_board("pf-key", "pf-pin-channel", "other-board")

    def test_board_missing_invalid_or_wrong_channel_rejected(self):
        with self.assertRaises(RuntimeError):
            buffer.verify_picturefix_board("k", "c", "")
        for response in (
            {"channel": None},
            {"channel": {"id": "other-channel", "metadata": {"boards": []}}},
            {"channel": {"id": "c", "metadata": {"boards": []}}},
            {"channel": {"id": "c", "metadata": {"boards": "not-a-list"}}},
        ):
            with mock.patch.object(buffer, "buffer_graphql", return_value=response):
                with self.assertRaises(RuntimeError):
                    buffer.verify_picturefix_board("k", "c", "expected")

    def test_pinterest_create_metadata_cannot_schedule(self):
        value = buffer.platform_metadata("pinterest",
            pinterest_board_id="pf-board-one",
            pinterest_title="Kleine Fotos, große Erinnerungen",
            pinterest_url="https://picturefix.de")
        self.assertEqual(value, {"pinterest": {
            "boardServiceId": "pf-board-one",
            "title": "Kleine Fotos, große Erinnerungen",
            "url": "https://picturefix.de"
        }})
        with self.assertRaises(ValueError):
            buffer.platform_metadata("pinterest", pinterest_title="Title", pinterest_url="https://picturefix.de")

    def test_image_validation_uses_real_pinterest_dimensions(self):
        img = Image.new("RGB", (1000, 1500), (135, 110, 84))
        stream = io.BytesIO()
        img.save(stream, "PNG")
        body = stream.getvalue()
        payload = record(image_sha256=hashlib.sha256(body).hexdigest())
        assets = buffer.parse_assets(json.dumps(payload).encode())
        with mock.patch.object(buffer.urllib.request, "urlopen",
                               return_value=MockImageResponse(body)):
            buffer.verify_picturefix_image_bytes(payload, assets)

    def test_wrong_dimensions_are_blocked_before_buffer(self):
        img = Image.new("RGB", (1080, 1350), (135, 110, 84))
        stream = io.BytesIO()
        img.save(stream, "PNG")
        body = stream.getvalue()
        payload = record(image_sha256=hashlib.sha256(body).hexdigest())
        assets = buffer.parse_assets(json.dumps(payload).encode())
        with mock.patch.object(buffer.urllib.request, "urlopen",
                               return_value=MockImageResponse(body)):
            with self.assertRaises(RuntimeError):
                buffer.verify_picturefix_image_bytes(payload, assets)


if __name__ == "__main__":
    unittest.main()
