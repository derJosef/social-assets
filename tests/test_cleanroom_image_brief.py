"""Offline tests: no model, Adobe, GitHub or Buffer activity."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import cleanroom_image_brief as cleanroom


VALID = {
    "version": 1,
    "scene": "document-review",
    "steps": ["receive", "inspect", "release"],
    "composition": "connected-three",
    "figure": "none",
}


class CleanRoomBriefTests(unittest.TestCase):
    def test_output_contains_only_compiled_allowlist_words(self):
        job = cleanroom.compiled_job(VALID)
        content = json.dumps(job, ensure_ascii=False).lower()
        for forbidden in ("pauderer", "agent builder", "personalos", "github.com", "http://",
                          "https://", "logo", "buffer", "claudia", "brand"):
            self.assertNotIn(forbidden, content)
        self.assertEqual(job["reference_images"], [])
        self.assertIs(job["isolation_verified"], False)
        self.assertEqual(job["purpose"], "raw_image_only")
        self.assertEqual(job["generator_prompt_sha256"],
                         hashlib.sha256(job["generator_prompt"].encode()).hexdigest())

    def test_repeatable_and_no_uncontrolled_input(self):
        self.assertEqual(cleanroom.compiled_job(VALID), cleanroom.compiled_job(dict(VALID)))
        for field, value in (("brand", "pauderer"), ("reference_image", "file.png"),
                             ("topic", "Write company signage"), ("notes", "PersonalOS")):
            with self.subTest(field=field):
                with self.assertRaises(cleanroom.InvalidCleanRoomSpec):
                    cleanroom.compile_prompt({**VALID, field: value})

    def test_approved_hologram_uses_synthetic_not_real_person_prompt(self):
        prompt = cleanroom.compile_prompt({**VALID, "figure": "hologram"})
        self.assertIn("wireframe hologram", prompt)
        self.assertIn("No realistic faces", prompt)
        self.assertIn("No letters", prompt)
        self.assertNotIn("No people, silhouettes, hands or robots.", prompt)
        self.assertEqual(cleanroom.compiled_job({**VALID, "figure": "hologram"})["reference_images"], [])

    def test_photorealistic_figure_is_not_a_hologram(self):
        for candidate in ("photorealistic", "real-person", "robot", "digital-human-photo", ""):
            with self.subTest(figure=candidate):
                with self.assertRaises(cleanroom.InvalidCleanRoomSpec):
                    cleanroom.compile_prompt({**VALID, "figure": candidate})

    def test_rejects_unknown_steps_and_duplicate_stages(self):
        for steps in (["receive", "inspect", "untrusted"],
                      ["receive", "receive", "release"], ["receive"],
                      ["receive", "inspect", "release", "archive"]):
            with self.subTest(steps=steps):
                with self.assertRaises(cleanroom.InvalidCleanRoomSpec):
                    cleanroom.compile_prompt({**VALID, "steps": steps})

    def test_rejects_other_types_versions_and_compositions(self):
        for patch in ({"version": True}, {"version": 2}, {"scene": ["document-review"]},
                      {"composition": "logo-poster"}, {"figure": True}):
            with self.subTest(patch=patch):
                with self.assertRaises(cleanroom.InvalidCleanRoomSpec):
                    cleanroom.compile_prompt({**VALID, **patch})

    def test_all_presets_compile_without_brand_contamination(self):
        for scene in cleanroom.SCENES:
            for composition in cleanroom.COMPOSITIONS:
                job = cleanroom.compiled_job({**VALID, "scene": scene,
                                              "composition": composition})
                self.assertTrue(job["generator_prompt"].startswith("Create a single"))
                self.assertEqual(job["reference_images"], [])

    def test_cli_rejects_duplicate_json_fields(self):
        with self.assertRaisesRegex(cleanroom.InvalidCleanRoomSpec, "Duplicate"):
            json.loads('{"version":1,"version":2}',
                       object_pairs_hook=cleanroom._reject_duplicate_keys)

    def test_only_new_files_can_be_written(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "spec.json"
            output = Path(directory) / "job.json"
            source.write_text(json.dumps(VALID), encoding="utf-8")
            job = cleanroom.compiled_job(json.loads(source.read_text()))
            with output.open("x", encoding="utf-8") as handle:
                json.dump(job, handle)
            with self.assertRaises(FileExistsError):
                with output.open("x", encoding="utf-8"):
                    pass


if __name__ == "__main__":
    unittest.main()
