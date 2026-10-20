"""Regression: discarded main PNGs and unpublished Buffer drafts must not become news."""
import hashlib
import io
import sys
import unittest
from pathlib import Path
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from news_source_provenance_gate import NewsSourceBlocked, verify_published_news_source

COMMIT = "ac03f948b5ed24dd49c3363dfdef7c82de01810b"
FILENAME = "media/images/2026-10-16-legacy-wer-liest-mit-4x5-branded.png"
POST_ID = "6ac8d5ab26e224ee545ee761"
URL = f"https://raw.githubusercontent.com/derJosef/social-assets/{COMMIT}/{FILENAME}"

class NewsSourceGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        img = Image.new("RGB", (1080, 1350), (8, 40, 76))
        stream = io.BytesIO()
        img.save(stream, "PNG", compress_level=0)
        cls.source = stream.getvalue()
        cls.sha = hashlib.sha256(cls.source).hexdigest()

    def input(self):
        return dict(
            brand="ai-agent-builder",
            post={"id": POST_ID, "channelService": "facebook", "status": "sent",
                  "text": "Verifizierter Text in Buffer, nicht alter GitHub-Entwurf.",
                  "assets": [{"type": "image", "source": URL, "mimeType": "image/png"}]},
            expected_post_id=POST_ID, expected_channel="facebook",
            image_commit=COMMIT, image_path=FILENAME,
            expected_image_sha256=self.sha, actual_image_bytes=self.source
        )

    def test_realistic_published_buffer_response_allows_only_news_draft(self):
        result = verify_published_news_source(**self.input())
        self.assertEqual(result["state"], "verified_published_source_for_news_draft")
        self.assertEqual(result["buffer_status"], "sent")
        self.assertFalse(result["website_publication_authorized"])

    def test_old_main_artwork_rejected_even_if_valid_png(self):
        record = self.input()
        record["image_commit"] = "main"
        with self.assertRaisesRegex(NewsSourceBlocked, "immutable"):
            verify_published_news_source(**record)

    def test_discouraged_early_october_image_does_not_match_published_buffer_image(self):
        record = self.input()
        record["image_path"] = "media/images/2026-10-09-ki-chatdaten-drittanbieter-branded.png"
        with self.assertRaisesRegex(NewsSourceBlocked, "differs"):
            verify_published_news_source(**record)

    def test_never_accept_old_unpublished_drafts(self):
        for status in ("draft", "scheduled", "buffer", "pending"):
            record = self.input()
            record["post"]["status"] = status
            with self.subTest(status=status), self.assertRaisesRegex(NewsSourceBlocked, "sent"):
                verify_published_news_source(**record)

    def test_no_media_or_different_channel_blocked(self):
        record = self.input()
        record["post"]["assets"] = []
        with self.assertRaisesRegex(NewsSourceBlocked, "one current image"):
            verify_published_news_source(**record)
        record = self.input()
        record["post"]["channelService"] = "linkedin"
        with self.assertRaisesRegex(NewsSourceBlocked, "channel"):
            verify_published_news_source(**record)

    def test_wrong_image_bytes_or_size_blocked(self):
        record = self.input()
        record["actual_image_bytes"] = self.source + b"x"
        with self.assertRaisesRegex(NewsSourceBlocked, "SHA256"):
            verify_published_news_source(**record)
        record = self.input()
        img = Image.new("RGB", (1080, 1080), (8, 40, 76))
        stream = io.BytesIO()
        img.save(stream, "PNG", compress_level=0)
        record["actual_image_bytes"] = stream.getvalue()
        record["expected_image_sha256"] = hashlib.sha256(stream.getvalue()).hexdigest()
        with self.assertRaisesRegex(NewsSourceBlocked, "1080x1350"):
            verify_published_news_source(**record)

    def test_foreign_brand_consent_not_inherited(self):
        record = self.input()
        record["brand"] = "picturefix"
        with self.assertRaisesRegex(NewsSourceBlocked, "consent"):
            verify_published_news_source(**record)

if __name__ == "__main__":
    unittest.main()
