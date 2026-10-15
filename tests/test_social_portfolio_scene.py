#!/usr/bin/env python3
"""Offline, synthetic tests. Never contact Buffer or an image model."""
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import social_portfolio_scene as m


class SceneTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root / "media/source-images/test-scene.png"
        self.source.parent.mkdir(parents=True)
        Image.new("RGB", (1122, 1402), (7, 17, 31)).save(self.source)
        self.spec = {
            "format_version": 1, "brand": "ai-agent-builder",
            "layout": "headline",
            "source": "media/source-images/test-scene.png",
            "source_sha256": hashlib.sha256(self.source.read_bytes()).hexdigest(),
            "heading": "WER GIBT DEN BEFEHL?",
            "visual_review": {key: True for key in m.REVIEW_KEYS},
            "review_evidence": "TEST ONLY: synthetic fixture, not an approval",
        }

    def test_fingerprint_changed_fails_closed(self):
        self.spec["source_sha256"] = "0" * 64
        with self.assertRaises(m.InvalidScene):
            m.validate_spec(self.spec, self.root)

    def test_no_visual_review_fails_closed(self):
        self.spec["visual_review"]["no_people"] = False
        with self.assertRaises(m.InvalidScene):
            m.validate_spec(self.spec, self.root)

    def test_ambiguous_logo_or_text_only_chatgpt_draft_and_explicit_record(self):
        self.spec["layout"] = "logo_only"
        self.spec["heading"] = None
        self.spec["chatgpt_review"] = {
            "kind": "chatgpt_visual_inspection_draft_only",
            "source_sha256": self.spec["source_sha256"],
        }
        self.spec["review_evidence"] = (
            "ChatGPT actual source check: unscharf, logo-/textartige "
            "Minimarkierung nicht eindeutig. NOT a human approval."
        )
        self.spec["visual_review"]["no_foreign_logo"] = None
        self.spec["visual_review"]["no_generated_text"] = None
        self.assertEqual(m.validate_spec(self.spec, self.root), self.source)
        # No equivalently relaxed legacy/automatic/personal review.
        self.spec.pop("chatgpt_review")
        with self.assertRaises(m.InvalidScene):
            m.validate_spec(self.spec, self.root)

    def test_clear_logo_rejected_even_with_chatgpt_review(self):
        self.spec["chatgpt_review"] = {
            "kind": "chatgpt_visual_inspection_draft_only",
            "source_sha256": self.spec["source_sha256"],
        }
        self.spec["review_evidence"] = (
            "ChatGPT saw a clearly recognizable foreign brand at the margin. "
            "NOT a human approval."
        )
        self.spec["visual_review"]["no_foreign_logo"] = False
        with self.assertRaises(m.InvalidScene):
            m.validate_spec(self.spec, self.root)

    def test_uncertain_generated_text_requires_documented_evidence(self):
        self.spec["chatgpt_review"] = {
            "kind": "chatgpt_visual_inspection_draft_only",
            "source_sha256": self.spec["source_sha256"],
        }
        self.spec["review_evidence"] = "ChatGPT checked. NOT a human sign-off."
        self.spec["visual_review"]["no_generated_text"] = None
        with self.assertRaisesRegex(m.InvalidScene, "Uncertain mark"):
            m.validate_spec(self.spec, self.root)

    def test_people_still_block_chatgpt_ambiguity(self):
        self.spec["chatgpt_review"] = {
            "kind": "chatgpt_visual_inspection_draft_only",
            "source_sha256": self.spec["source_sha256"],
        }
        self.spec["review_evidence"] = (
            "ChatGPT: unscharf nur die mögliche Marke, NOT a human approval."
        )
        self.spec["visual_review"]["no_people"] = False
        self.spec["visual_review"]["no_foreign_logo"] = None
        with self.assertRaises(m.InvalidScene):
            m.validate_spec(self.spec, self.root)

    def test_classified_stylized_hologram_uses_chatgpt_draft_review(self):
        self.spec["chatgpt_review"] = {
            "kind": "chatgpt_visual_inspection_draft_only",
            "source_sha256": self.spec["source_sha256"],
        }
        self.spec["figure_review"] = {
            "kind": "stylized_hologram",
            "photorealistic_ai_face": False,
            "ai_altered_real_person": False,
        }
        self.spec["review_evidence"] = (
            "ChatGPT checked original technical scene with a clearly artificial "
            "blue holographic wireframe. NOT a human approval."
        )
        self.spec["visual_review"]["no_people"] = False
        self.assertEqual(m.validate_spec(self.spec, self.root), self.source)
        self.assertFalse(m.needs_disclosure(self.spec))

    def test_hologram_cannot_bypass_real_person_review(self):
        self.spec["chatgpt_review"] = {
            "kind": "chatgpt_visual_inspection_draft_only",
            "source_sha256": self.spec["source_sha256"],
        }
        self.spec["figure_review"] = {
            "kind": "stylized_hologram",
            "photorealistic_ai_face": True,
            "ai_altered_real_person": False,
        }
        self.spec["review_evidence"] = (
            "ChatGPT original image with a hologram-like realistic person. "
            "NOT a human approval."
        )
        self.spec["visual_review"]["no_people"] = False
        with self.assertRaises(m.InvalidScene):
            m.validate_spec(self.spec, self.root)

    def test_no_hologram_classification_does_not_bypass_people_gate(self):
        self.spec["chatgpt_review"] = {
            "kind": "chatgpt_visual_inspection_draft_only",
            "source_sha256": self.spec["source_sha256"],
        }
        self.spec["review_evidence"] = (
            "ChatGPT saw an unspecified human-like figure. NOT a human approval."
        )
        self.spec["visual_review"]["no_people"] = False
        with self.assertRaises(m.InvalidScene):
            m.validate_spec(self.spec, self.root)

    def test_no_human_evidence_fails_closed(self):
        self.spec["review_evidence"] = ""
        with self.assertRaises(m.InvalidScene):
            m.validate_spec(self.spec, self.root)

    def test_refuses_bad_paths(self):
        self.spec["source"] = "../../personal-data.png"
        with self.assertRaises(m.InvalidScene):
            m.validate_spec(self.spec, self.root)

    def test_refuses_square_without_cropping(self):
        Image.new("RGB", (1400, 1400)).save(self.source)
        self.spec["source_sha256"] = hashlib.sha256(self.source.read_bytes()).hexdigest()
        with self.assertRaises(m.InvalidScene):
            m.validate_spec(self.spec, self.root)

    def test_accepts_genuine_4x5_dimensions(self):
        self.assertEqual(m.validate_spec(self.spec, self.root), self.source)

    def test_heading_wrap_is_limited(self):
        # PIL's builtin font keeps the offline test independent from font downloads.
        from PIL import ImageDraw, ImageFont
        canvas = Image.new("RGB", m.SIZE)
        lines = m.layout_heading(ImageDraw.Draw(canvas),
                                 "WER GIBT DEN BEFEHL?",
                                 ImageFont.load_default(size=67))
        self.assertGreaterEqual(len(lines), 1)
        self.assertLessEqual(len(lines), 3)

    def test_render_exact_four_by_five_and_never_overwrite(self):
        from PIL import ImageFont
        # Pillow bundles a small readable default font; this test does not
        # inspect or rebrand the verified production Inter font.
        default_font = ImageFont.load_default(size=67)
        if not hasattr(default_font.path, "getvalue"):
            self.skipTest("This Pillow build does not expose its bundled font")
        font_path = self.root / "test-font.ttf"
        font_path.write_bytes(default_font.path.getvalue())
        output = self.root / "base.png"
        heading = m.render_base(self.source, output, self.spec["heading"], font_path)
        with Image.open(output) as image:
            self.assertEqual(image.size, (1080, 1350))
        self.assertGreaterEqual(heading[0], 0)
        self.assertLess(heading[3], 540)
        with self.assertRaises(FileExistsError):
            m.render_base(self.source, output, self.spec["heading"], font_path)

    def test_logo_only_has_null_heading_not_dummy_text(self):
        self.spec["layout"] = "logo_only"
        self.spec["heading"] = None
        self.assertEqual(m.validate_spec(self.spec, self.root), self.source)
        output = self.root / "logo-only-base.png"
        bbox = m.render_base(self.source, output, None, self.root / "nonexistent.ttf")
        self.assertIsNone(bbox)
        with Image.open(output) as image:
            self.assertEqual(image.size, (1080, 1350))
            # Base is uniform dark blue; no rendered headline or overlay.
            self.assertEqual(image.getpixel((100, 100)), (7, 17, 31))
            self.assertEqual(image.getpixel((400, 500)), (7, 17, 31))

    def test_logo_only_refuses_fake_heading(self):
        self.spec["layout"] = "logo_only"
        self.spec["heading"] = "DUMMY"
        with self.assertRaises(m.InvalidScene):
            m.validate_spec(self.spec, self.root)

    def test_headline_rejects_absent_heading(self):
        self.spec["heading"] = None
        with self.assertRaises(m.InvalidScene):
            m.validate_spec(self.spec, self.root)

    def test_end_to_end_logo_only_original_logo_no_font_required(self):
        import shutil
        # The source is synthetic; these true-valued test fixtures do not
        # authorize any production image or any Buffer mutation.
        fixture = dict(self.spec, layout="logo_only", heading=None)
        spec_dir = self.root / "visual-reviews"
        spec_dir.mkdir()
        spec_path = spec_dir / "synthetic-logo-only.json"
        spec_path.write_text(json.dumps(fixture), encoding="utf-8")
        scripts = self.root / "scripts"
        scripts.mkdir()
        source_script = Path(m.__file__).resolve().parents[0] / "logo_composite.py"
        shutil.copy2(source_script, scripts / "logo_composite.py")
        original = Path(m.__file__).resolve().parents[1] / "media/brand/logo-pauderer-original.png"
        base = self.root / "media/source-images/logo-only-render-base.png"
        final = self.root / "media/images/logo-only-render-branded.png"
        result = m.build(spec_path, self.root, base, final,
                         self.root / "deliberately-missing-font.ttf", original)
        self.assertEqual(result["heading_box"], None)
        self.assertEqual(result["layout"], "logo_only")
        self.assertEqual(result["logo_qa"]["validator"], "personalos_canonical")
        self.assertEqual(result["logo_qa"]["profile"], "logo_only")
        self.assertIs(result["logo_qa"]["logo_verified"], True)
        self.assertEqual(result["logo_qa"]["source_visual_review"], "manual")
        self.assertEqual(result["size"], [1080, 1350])
        self.assertTrue(final.is_file())
        with Image.open(base) as raw:
            # No title/dimming veil was put onto the source.
            self.assertEqual(raw.getpixel((100, 100)), (7, 17, 31))
        with self.assertRaises(FileExistsError):
            m.build(spec_path, self.root, base, final,
                    self.root / "deliberately-missing-font.ttf", original)

    def test_no_buffer_or_publishing_operations(self):
        source = Path(m.__file__).read_text(encoding="utf-8")
        self.assertNotIn("deletePost(", source)
        self.assertNotIn("editPost(", source)
        self.assertNotIn("createPost(", source)
        self.assertNotIn("saveToDraft: false", source)


    def use_person_review(self, *, face=False, edited=False):
        # Synthetic evidence exercises schema only; it cannot authorize a real image.
        self.spec["visual_review"]["no_people"] = False
        self.spec["visual_review"].update({
            "photorealistic_ai_face": face,
            "ai_altered_real_person": edited,
            "rights_checked": True,
            "no_misrepresentation_checked": True,
            "platform_checked": True,
        })
        self.spec["person_checks_evidence"] = {
            "rights_basis": (
                "SYNTHETIC FIXTURE: rights assessment of a fictional test image; "
                "this statement does not verify any real-world identity or rights."
            ),
            "misrepresentation_assessment": (
                "SYNTHETIC FIXTURE: the visual is not presented as actual "
                "company staff, customers, customer projects or a real event."
            ),
            "platform_assessment": (
                "SYNTHETIC FIXTURE: review of channel disclosure obligations "
                "was simulated, never an actual platform assessment."
            ),
        }

    def test_ai_generated_photorealistic_face_requires_checks_not_individual_approval(self):
        self.use_person_review(face=True)
        self.assertEqual(m.validate_spec(self.spec, self.root), self.source)
        self.assertTrue(m.needs_disclosure(self.spec))
        self.assertNotIn("person_use_approved", self.spec["visual_review"])
        self.assertNotIn("person_approval_evidence", self.spec)

    def test_ai_modified_real_photo_requires_same_caption(self):
        self.use_person_review(edited=True)
        self.assertEqual(m.validate_spec(self.spec, self.root), self.source)
        self.assertTrue(m.needs_disclosure(self.spec))

    def test_unchanged_real_photo_does_not_trigger_ai_caption(self):
        self.use_person_review()
        self.assertEqual(m.validate_spec(self.spec, self.root), self.source)
        self.assertFalse(m.needs_disclosure(self.spec))

    def test_each_person_check_is_a_hard_gate(self):
        for check in ("rights_checked", "no_misrepresentation_checked", "platform_checked"):
            with self.subTest(check=check):
                self.use_person_review(face=True)
                self.spec["visual_review"][check] = False
                with self.assertRaises(m.InvalidScene):
                    m.validate_spec(self.spec, self.root)

    def test_missing_or_short_check_evidence_rejected(self):
        for field in ("rights_basis", "misrepresentation_assessment", "platform_assessment"):
            with self.subTest(field=field):
                self.use_person_review(face=True)
                self.spec["person_checks_evidence"][field] = "ok"
                with self.assertRaises(m.InvalidScene):
                    m.validate_spec(self.spec, self.root)
        self.use_person_review(edited=True)
        self.spec.pop("person_checks_evidence")
        with self.assertRaises(m.InvalidScene):
            m.validate_spec(self.spec, self.root)

    def test_old_person_approval_fields_do_not_bypass_rights_checks(self):
        self.use_person_review(face=True)
        self.spec["person_approval_evidence"] = "Old Josef individual permission"
        with self.assertRaises(m.InvalidScene):
            m.validate_spec(self.spec, self.root)
        self.spec.pop("person_approval_evidence")
        self.spec["visual_review"]["person_use_approved"] = True
        with self.assertRaises(m.InvalidScene):
            m.validate_spec(self.spec, self.root)

    def test_ai_face_and_no_people_inconsistent(self):
        self.use_person_review(face=True)
        self.spec["visual_review"]["no_people"] = True
        with self.assertRaises(m.InvalidScene):
            m.validate_spec(self.spec, self.root)

    def test_legacy_unclassified_person_rejected(self):
        self.spec["visual_review"]["no_people"] = False
        with self.assertRaises(m.InvalidScene):
            m.validate_spec(self.spec, self.root)

    def test_person_check_cannot_use_string_true(self):
        self.use_person_review(face=True)
        self.spec["visual_review"]["rights_checked"] = "true"
        with self.assertRaises(m.InvalidScene):
            m.validate_spec(self.spec, self.root)

    def test_clean_scene_with_explicit_negative_classification_accepted(self):
        self.spec["visual_review"].update({
            "photorealistic_ai_face": False,
            "ai_altered_real_person": False,
            "rights_checked": False,
            "no_misrepresentation_checked": False,
            "platform_checked": False,
        })
        m.validate_spec(self.spec, self.root)
        self.assertFalse(m.needs_disclosure(self.spec))

    def test_end_to_end_person_capability_uses_two_independent_image_gates(self):
        import shutil
        from PIL import ImageFont
        font_path = self.root/"Inter-for-fixtures.ttf"
        # Prefer the system TTF on GitHub's Ubuntu runner; the synthetic
        # Pillow fallback keeps tests portable without sharing font assets.
        try:
            test_ttf = ImageFont.truetype("DejaVuSans.ttf", 42)
            import shutil as _shutil
            _shutil.copyfile(test_ttf.path, font_path)
        except OSError:
            fallback = ImageFont.load_default(size=42)
            source = getattr(fallback, "path", None)
            if not hasattr(source, "getvalue"):
                self.skipTest("No test TTF available on this runner")
            font_path.write_bytes(source.getvalue())
        self.use_person_review(face=True)
        self.spec["layout"]="logo_only"
        self.spec["heading"]=None
        spec_dir=self.root/"visual-reviews"
        spec_dir.mkdir()
        spec_path=spec_dir/"synthetic-person.json"
        spec_path.write_text(json.dumps(self.spec),encoding="utf-8")
        scripts=self.root/"scripts"
        scripts.mkdir()
        root_scripts=Path(m.__file__).resolve().parent
        shutil.copy2(root_scripts/"logo_composite.py",scripts/"logo_composite.py")
        original=root_scripts.parent/"media/brand/logo-pauderer-original.png"
        base=self.root/"media/source-images/synthetic-disclosure-base.png"
        final=self.root/"media/images/synthetic-disclosure-final.png"
        result=m.build(spec_path,self.root,base,final,font_path,original)
        self.assertTrue(result["ai_disclosure"]["required"])
        self.assertTrue(result["ai_disclosure"]["pixel_verified"])
        self.assertTrue(result["ai_disclosure"]["logo_disjoint_verified"])
        self.assertTrue(result["ai_disclosure"]["final_pixel_verified"])
        self.assertTrue(result["logo_qa"]["logo_verified"])
        from ai_disclosure import verify_label_region, verify_no_logo_overlap
        caption=verify_label_region(base,font_path)
        verify_no_logo_overlap(final,caption)
        self.assertEqual(result["size"],[1080,1350])


if __name__ == "__main__":
    unittest.main()
