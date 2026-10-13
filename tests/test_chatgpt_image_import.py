"""No-network tests for the proven ChatGPT -> Adobe -> GitHub PNG import."""
import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from PIL import Image

from scripts import chatgpt_image_import as tr

CID = "2026-10-20-image-transfer-pilot"
BRIEF = f"orchestration/briefs/{CID}.json"
PNG = f"media/source-images/{CID}-source.png"
REVIEW = f"visual-reviews/{CID}.json"


def fake_png(size=(1080, 1350)):
    image = Image.new("RGB", size, "#07111f")
    blob = io.BytesIO()
    image.save(blob, format="PNG")
    return blob.getvalue()


def make_brief(raw):
    return {
        "campaign_id": CID, "brand": "ai-agent-builder",
        "execution_mode": "drafts",
        "image_review": REVIEW,
        "chatgpt_image": {
            "transport": "adobe_transfer",
            "url": "https://at.adobe.com/AbC01234xYz",
            "sha256": hashlib.sha256(raw).hexdigest(),
            "visual_review": {k: True for k in tr.CHECKS},
            "review_evidence": (
                "ChatGPT visual inspection of original bytes: empty technical "
                "document scene. NOT a human approval; Josef must review Buffer draft."
            ),
        },
    }


class ChatGPTImageImportTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "orchestration/briefs").mkdir(parents=True)
        self.raw = fake_png()
        self.brief = make_brief(self.raw)
        (self.root / BRIEF).write_text(json.dumps(self.brief), encoding="utf-8")

    def update(self):
        (self.root / BRIEF).write_text(json.dumps(self.brief), encoding="utf-8")

    def test_verified_adobe_transfer_stages_exact_png_without_api_or_buffer(self):
        called = []
        result = tr.import_image(BRIEF, self.root, fetch=lambda url: (
            called.append(url) or self.raw
        ))
        self.assertEqual(len(called), 1)
        self.assertEqual((self.root / PNG).read_bytes(), self.raw)
        self.assertEqual(json.loads((self.root / REVIEW).read_text())["source_sha256"],
                         hashlib.sha256(self.raw).hexdigest())
        self.assertEqual(result["model_requests"], 0)
        self.assertEqual(result["buffer_requests"], 0)
        with self.assertRaisesRegex(tr.ChatImageBlocked, "kein Retry"):
            tr.import_image(BRIEF, self.root, fetch=lambda url: self.raw)

    def test_wrong_hash_never_writes_source_or_review(self):
        self.brief["chatgpt_image"]["sha256"] = "0" * 64
        self.update()
        with self.assertRaisesRegex(tr.ChatImageBlocked, "SHA256"):
            tr.import_image(BRIEF, self.root, fetch=lambda url: self.raw)
        self.assertFalse((self.root / PNG).exists())
        self.assertFalse((self.root / REVIEW).exists())

    def test_ambiguous_tiny_mark_keeps_transfer_and_explicit_pending_review(self):
        self.brief["chatgpt_image"]["visual_review"]["no_foreign_logo"] = None
        self.brief["chatgpt_image"]["visual_review"]["no_generated_text"] = None
        self.brief["chatgpt_image"]["review_evidence"] = (
            "ChatGPT inspected the actual original. Tiny blurry marking unklar "
            "am Monitorrahmen, Fremdlogo/Schrift nicht eindeutig; NOT a human review."
        )
        self.update()
        result = tr.import_image(BRIEF, self.root, fetch=lambda url: self.raw)
        self.assertEqual(result["visual_review_pending"],
                         ["no_foreign_logo", "no_generated_text"])
        review = json.loads((self.root / REVIEW).read_text())
        self.assertIsNone(review["visual_review"]["no_foreign_logo"])
        self.assertIsNone(review["visual_review"]["no_generated_text"])
        self.assertEqual(review["source_sha256"], hashlib.sha256(self.raw).hexdigest())

    def test_clear_foreign_logo_blocks_before_any_transfer(self):
        self.brief["chatgpt_image"]["visual_review"]["no_foreign_logo"] = False
        self.update()
        with self.assertRaises(tr.ChatImageBlocked):
            tr.import_image(BRIEF, self.root,
                            fetch=lambda url: self.fail("must not fetch"))

    def test_ambiguous_mark_without_explicit_evidence_fails(self):
        self.brief["chatgpt_image"]["visual_review"]["no_generated_text"] = None
        self.update()
        with self.assertRaisesRegex(tr.ChatImageBlocked, "Unklare Logo"):
            tr.import_image(BRIEF, self.root,
                            fetch=lambda url: self.fail("must not fetch"))

    def test_non_4_by_5_png_blocked(self):
        wrong_size = fake_png((1024, 1536))
        self.brief["chatgpt_image"]["sha256"] = hashlib.sha256(wrong_size).hexdigest()
        self.update()
        with self.assertRaisesRegex(tr.ChatImageBlocked, "1080 x 1350"):
            tr.import_image(BRIEF, self.root, fetch=lambda url: wrong_size)
        self.assertFalse((self.root / PNG).exists())

    def test_missing_transport_blocked_before_fetch(self):
        del self.brief["chatgpt_image"]
        self.update()
        with self.assertRaisesRegex(tr.ChatImageBlocked, "keine automatische"):
            tr.import_image(BRIEF, self.root,
                            fetch=lambda url: self.fail("must not fetch"))
        self.assertFalse((self.root / PNG).exists())

    def test_untrusted_url_and_redirect_blocked(self):
        self.brief["chatgpt_image"]["url"] = "https://localhost/private"
        self.update()
        with self.assertRaisesRegex(tr.ChatImageBlocked, "Adobe-Transfer"):
            tr.import_image(BRIEF, self.root,
                            fetch=lambda url: self.fail("must not fetch"))
        for url in ("http://at.adobe.com/AbC01234xYz",
                    "https://127.0.0.1/png",
                    "https://at.adobe.com.evil.org/AbC01234xYz"):
            with self.subTest(url=url):
                with self.assertRaises(tr.ChatImageBlocked):
                    tr.safe_location(url)

    def test_no_unchecked_people_or_made_up_human_review(self):
        self.brief["chatgpt_image"]["visual_review"]["no_people"] = False
        self.update()
        with self.assertRaisesRegex(tr.ChatImageBlocked, "Bildsichtprüfungen"):
            tr.import_image(BRIEF, self.root,
                            fetch=lambda url: self.fail("must not fetch"))
        self.brief["chatgpt_image"]["visual_review"]["no_people"] = True
        self.brief["chatgpt_image"]["review_evidence"] = "Josef reviewed it"
        self.update()
        with self.assertRaisesRegex(tr.ChatImageBlocked, "menschliche"):
            tr.import_image(BRIEF, self.root,
                            fetch=lambda url: self.fail("must not fetch"))


if __name__ == "__main__":
    unittest.main()
