"""Offline regression: no actual OpenAI, GitHub or Buffer requests."""
import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from PIL import Image, ImageDraw

from scripts import automatic_image_source as automatic
from scripts import social_portfolio_scene as scene

CID = "2026-10-19-kontrollierter-workflow"
BRIEF = f"orchestration/briefs/{CID}.json"
REVIEW = f"visual-reviews/{CID}.json"
SOURCE = f"media/source-images/{CID}-source.png"


def generated_png():
    im = Image.new("RGB", (1024, 1536), (7, 17, 31))
    pen = ImageDraw.Draw(im)
    pen.rectangle((165, 250, 820, 1050), outline=(23, 170, 177), width=20)
    pen.ellipse((350, 430, 680, 760), fill=(50, 80, 133))
    out = io.BytesIO()
    im.save(out, format="PNG")
    return out.getvalue()


class AutomaticDraftImageTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        (self.root / "orchestration/briefs").mkdir(parents=True)
        self.data = {
            "format_version": 1, "brand": "ai-agent-builder",
            "campaign_id": CID, "execution_mode": "drafts",
            "image_review": REVIEW,
            "topic": "Kontrollierte Freigaben und nachvollziehbare Prüfungen bei technischen KI-Abläufen.",
        }
        (self.root / BRIEF).write_text(json.dumps(self.data), encoding="utf-8")
        self.original = generated_png()

    def test_generates_only_machine_reviewed_person_free_source_and_spec(self):
        with mock.patch.object(automatic, "generate_image", return_value=self.original) as gen, \
             mock.patch.object(automatic, "audit_image",
                               return_value={name: True for name in automatic.FIELDS}) as audit, \
             mock.patch.object(automatic.urllib.request, "urlopen",
                               side_effect=AssertionError("No real network")):
            result = automatic.create_source(BRIEF, self.root, api_key="synthetic-key")
        self.assertEqual(result["review_method"], "machine_draft_only")
        self.assertEqual(result["human_review"], "pending_after_buffer_draft")
        self.assertEqual(gen.call_count, 1)
        self.assertEqual(audit.call_count, 2)
        src = self.root / SOURCE
        spec = json.loads((self.root / REVIEW).read_text(encoding="utf-8"))
        self.assertEqual(spec["source_sha256"], hashlib.sha256(src.read_bytes()).hexdigest())
        self.assertEqual(scene.validate_spec(spec, self.root), src)
        self.assertEqual(spec["layout"], "logo_only")
        self.assertIn("NOT a human", spec["review_evidence"])
        self.assertNotIn("person_approval_evidence", spec)
        with Image.open(src) as im:
            self.assertEqual(im.size, (1080, 1350))

    def test_no_crop_output_preserves_all_central_frame(self):
        out = automatic.portrait_without_cropping(self.original)
        with Image.open(io.BytesIO(out)) as im:
            self.assertEqual(im.size, (1080, 1350))
            self.assertEqual(im.format, "PNG")
            self.assertNotEqual(im.getpixel((540, 550)), (7, 17, 31))

    def test_missing_api_credential_blocks_before_image_call(self):
        with mock.patch.object(automatic, "generate_image", side_effect=AssertionError("No network")):
            with self.assertRaisesRegex(automatic.ImageSourceBlocked, "API_KEY"):
                automatic.create_source(BRIEF, self.root, api_key="")

    def test_second_visual_review_failure_never_writes_source(self):
        valid = {name: True for name in automatic.FIELDS}
        with mock.patch.object(automatic, "generate_image", return_value=self.original), \
             mock.patch.object(automatic, "audit_image",
                               side_effect=[valid, automatic.ImageSourceBlocked("Face detected")]):
            with self.assertRaisesRegex(automatic.ImageSourceBlocked, "Face"):
                automatic.create_source(BRIEF, self.root, api_key="synthetic")
        self.assertFalse((self.root / SOURCE).exists())
        self.assertFalse((self.root / REVIEW).exists())

    def test_missing_review_fields_never_writes_source(self):
        with mock.patch.object(automatic, "generate_image", return_value=self.original), \
             mock.patch.object(automatic, "audit_image", return_value={"no_people": True}):
            with self.assertRaisesRegex(automatic.ImageSourceBlocked, "unvollständig"):
                automatic.create_source(BRIEF, self.root, api_key="synthetic")
        self.assertFalse((self.root / SOURCE).exists())

    def test_existing_source_or_review_blocks_retry_before_model_call(self):
        (self.root / SOURCE).parent.mkdir(parents=True)
        (self.root / SOURCE).write_bytes(self.original)
        with mock.patch.object(automatic, "generate_image", side_effect=AssertionError("No duplicate")):
            with self.assertRaisesRegex(automatic.ImageSourceBlocked, "überschreiben"):
                automatic.create_source(BRIEF, self.root, api_key="synthetic")

    def test_manual_review_path_is_not_generated_over_existing(self):
        (self.root / REVIEW).parent.mkdir(parents=True)
        (self.root / REVIEW).write_text("{}")
        with self.assertRaisesRegex(automatic.ImageSourceBlocked, "existiert"):
            automatic.load_request(BRIEF, self.root)

    def test_invalid_campaign_or_brand_rejected(self):
        self.data["brand"] = "picturefix"
        (self.root / BRIEF).write_text(json.dumps(self.data))
        with self.assertRaisesRegex(automatic.ImageSourceBlocked, "eindeutigen Draft-Brief"):
            automatic.load_request(BRIEF, self.root)
        self.data["brand"] = "ai-agent-builder"
        self.data["execution_mode"] = "smoke"
        (self.root / BRIEF).write_text(json.dumps(self.data))
        with self.assertRaises(automatic.ImageSourceBlocked):
            automatic.load_request(BRIEF, self.root)

    def test_model_output_cannot_be_square_or_corrupt(self):
        im = Image.new("RGB", (1024, 1024), (13, 19, 27))
        buf = io.BytesIO()
        im.save(buf, format="PNG")
        with self.assertRaisesRegex(automatic.ImageSourceBlocked, "1024x1536"):
            automatic.portrait_without_cropping(buf.getvalue())
        with self.assertRaises(automatic.ImageSourceBlocked):
            automatic.portrait_without_cropping(b"not png")

    def test_machine_review_cannot_claim_fake_manual_or_person_approval(self):
        # This test is about spec validators, not network-produced evidence.
        self.test_generates_only_machine_reviewed_person_free_source_and_spec()
        spec = json.loads((self.root / REVIEW).read_text())
        spec["review_evidence"] = "Josef saw and approved this image"
        with self.assertRaisesRegex(scene.InvalidScene, "invented manual"):
            scene.validate_spec(spec, self.root)
        spec["review_evidence"] = "AUTO-DRAFT-ONLY: NOT a human approval"
        spec["visual_review"]["no_people"] = False
        with self.assertRaises(scene.InvalidScene):
            scene.validate_spec(spec, self.root)
        spec["visual_review"]["no_people"] = True
        spec["automated_review"]["checks"][1]["no_robot"] = False
        with self.assertRaisesRegex(scene.InvalidScene, "inconsistent"):
            scene.validate_spec(spec, self.root)

    def test_generator_never_holds_original_logo_or_buffer_mutations(self):
        script = Path(automatic.__file__).read_text(encoding="utf-8")
        self.assertNotIn("createPost(", script)
        self.assertNotIn("saveToDraft: false", script)
        self.assertNotIn("media/brand/logo-pauderer-original.png", script)
        self.assertNotIn("ready-to-schedule/", script)


if __name__ == "__main__":
    unittest.main()
