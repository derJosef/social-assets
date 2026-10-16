"""End-to-end *offline*: native PNG -> normalized PNG -> Adobe handoff.

No Adobe upload, Buffer call, GitHub write, model or logo compositor
is invoked by this fixture; all links are synthetic.
"""
import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from scripts.normalize_chatgpt_raw_png import normalize
from scripts.prepare_normalized_adobe_handoff import prepare, AdobeHandoffBlocked
from scripts.chatgpt_image_import import inspect_brief


CID = "2026-10-15-raw-image-handoff-probe"
ADOBE_URL = "https://at.adobe.com/AbC01234xYz"


class HandoffTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        d = Path(self.temp.name)
        self.native, self.normalized, self.receipt = (
            d / "native.png", d / "normalized.png", d / "normalization.json"
        )
        self.review, self.output = d / "review.json", d / "handoff.json"
        Image.new("RGB", (1122, 1402), "#07111f").save(self.native)
        normalize(self.native, self.normalized, self.receipt)
        self.data = {
            "visual_review": {
                "no_people": False,
                "no_robot": True, "no_foreign_logo": True,
                "no_generated_text": True, "plausible_details": True,
                "matches_topic": True, "heading_and_logo_space": True,
            },
            "figure_review": {
                "kind": "stylized_hologram",
                "photorealistic_ai_face": False,
                "ai_altered_real_person": False,
            },
            "review_evidence": (
                "ChatGPT inspected actual synthetic test artwork: a blue "
                "wireframe hologram, clearly non-photorealistic. "
                "NOT a human inspection or publication approval."
            ),
        }
        self.review.write_text(json.dumps(self.data), encoding="utf-8")

    def run_handoff(self, **overrides):
        options = dict(normalized=self.normalized, receipt=self.receipt,
                       visual_review=self.review, adobe_url=ADOBE_URL,
                       campaign_id=CID, output=self.output)
        return prepare(**(options | overrides))

    def test_output_is_exact_existing_import_schema_with_post_resize_hash(self):
        result = self.run_handoff()
        payload = json.loads(self.output.read_text())["chatgpt_image"]
        norm = json.loads(self.receipt.read_text())
        self.assertEqual(payload["sha256"], norm["output_sha256"])
        self.assertNotEqual(payload["sha256"], norm["source_sha256"])
        self.assertEqual(payload["url"], ADOBE_URL)
        self.assertEqual(payload["figure_review"], self.data["figure_review"])
        campaign, checked = inspect_brief({
            "campaign_id": CID, "brand": "ai-agent-builder",
            "execution_mode": "drafts",
            "image_review": f"visual-reviews/{CID}.json",
            "chatgpt_image": payload,
        })
        self.assertEqual(campaign, CID)
        self.assertEqual(checked, payload)
        self.assertEqual(result["buffer_requests"], 0)
        self.assertFalse(result["image_generator_context_verified"])

    def test_stale_hash_or_replaced_png_is_rejected(self):
        with Image.open(self.normalized) as im:
            im.convert("RGB").save(self.normalized)
        # Changing bytes to something else with the same valid PNG geometry.
        img = Image.new("RGB", (1080, 1350), "#0a2035")
        img.save(self.normalized)
        with self.assertRaisesRegex(AdobeHandoffBlocked, "bytes differ"):
            self.run_handoff()
        self.assertFalse(self.output.exists())

    def test_source_hash_cannot_be_mistaken_for_output_hash(self):
        j = json.loads(self.receipt.read_text())
        j["output_sha256"] = j["source_sha256"]
        self.receipt.write_text(json.dumps(j), encoding="utf-8")
        with self.assertRaises(AdobeHandoffBlocked):
            self.run_handoff()

    def test_bad_url_cannot_enter_transfer_handoff(self):
        for url in ("https://evil.test/not-adobe.png", "http://at.adobe.com/AbC01234xYz",
                    "https://at.adobe.com.evil.test/AbC01234xYz"):
            with self.subTest(url=url):
                with self.assertRaises(AdobeHandoffBlocked):
                    self.run_handoff(adobe_url=url)

    def test_visual_review_cannot_be_invented_or_missing(self):
        self.data["review_evidence"] = "approved"
        self.review.write_text(json.dumps(self.data))
        with self.assertRaises(AdobeHandoffBlocked):
            self.run_handoff()
        self.assertFalse(self.output.exists())

    def test_hologram_figure_review_requires_nonrealistic_face(self):
        self.data["figure_review"]["photorealistic_ai_face"] = True
        self.review.write_text(json.dumps(self.data))
        with self.assertRaises(AdobeHandoffBlocked):
            self.run_handoff()

    def test_output_must_not_be_overwritten(self):
        self.output.write_text('{"prior":"keep"}')
        with self.assertRaises(AdobeHandoffBlocked):
            self.run_handoff()
        self.assertEqual(self.output.read_text(), '{"prior":"keep"}')

    def test_fail_closed_receipt_unsafe_claims(self):
        for key in ("image_visual_qa_passed", "model_context_verified",
                    "rights_and_platform_checks_verified", "buffer_or_publication_permitted"):
            j = json.loads(self.receipt.read_text())
            j[key] = True
            self.receipt.write_text(json.dumps(j))
            with self.subTest(flag=key):
                with self.assertRaises(AdobeHandoffBlocked):
                    self.run_handoff()
            j[key] = False
            self.receipt.write_text(json.dumps(j))

    def test_missing_or_bad_normalized_image_rejected(self):
        self.normalized.unlink()
        with self.assertRaises(AdobeHandoffBlocked):
            self.run_handoff()


if __name__ == "__main__":
    unittest.main()
