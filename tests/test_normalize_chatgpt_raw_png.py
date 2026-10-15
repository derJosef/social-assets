"""Offline tests: normalization only, no visual or legal attestation."""
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from scripts.normalize_chatgpt_raw_png import (
    normalize, ImageNormalizationBlocked, sha256,
)


class NormalizeRawPNGTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name)
        self.input = self.folder / "input.png"
        self.output = self.folder / "output.png"
        self.report = self.folder / "report.json"

    def create(self, size=(1122, 1402)):
        Image.new("RGB", size, "#07111f").save(self.input, format="PNG")

    def test_genuine_near_4by5_image_normalizes_without_crop(self):
        self.create()
        src_hash = sha256(self.input)
        result = normalize(self.input, self.output, self.report)
        with Image.open(self.output) as image:
            self.assertEqual(image.size, (1080, 1350))
            self.assertEqual(image.format, "PNG")
            self.assertEqual(image.getpixel((0, 0)), (7, 17, 31))
            self.assertEqual(image.getpixel((1079, 1349)), (7, 17, 31))
        self.assertEqual(sha256(self.input), src_hash)
        self.assertEqual(result["source_sha256"], src_hash)
        self.assertEqual(result["output_sha256"], sha256(self.output))
        self.assertEqual(result["operation"], "lanczos_scale_no_crop")
        self.assertFalse(result["image_visual_qa_passed"])
        self.assertFalse(result["buffer_or_publication_permitted"])
        self.assertFalse(result["model_context_verified"])

    def test_square_mismatch_fails_without_writing(self):
        self.create((1400, 1400))
        with self.assertRaises(ImageNormalizationBlocked):
            normalize(self.input, self.output, self.report)
        self.assertFalse(self.output.exists())

    def test_insufficient_resolution_fails(self):
        self.create((900, 1125))
        with self.assertRaises(ImageNormalizationBlocked):
            normalize(self.input, self.output, self.report)

    def test_existing_output_not_overwritten(self):
        self.create()
        self.output.write_bytes(b"OLD IMPORTANT IMAGE")
        with self.assertRaises(ImageNormalizationBlocked):
            normalize(self.input, self.output, self.report)
        self.assertEqual(self.output.read_bytes(), b"OLD IMPORTANT IMAGE")

    def test_source_output_alias_cannot_destroy_original(self):
        self.create()
        original_hash = sha256(self.input)
        with self.assertRaises(ImageNormalizationBlocked):
            normalize(self.input, self.input, self.report)
        self.assertEqual(sha256(self.input), original_hash)

    def test_corrupt_input_fails_closed(self):
        self.input.write_bytes(b"fake png")
        with self.assertRaises(ImageNormalizationBlocked):
            normalize(self.input, self.output, self.report)

    def test_wrong_format_with_png_extension_rejected(self):
        Image.new("RGB", (1122, 1402), "blue").save(self.input, format="JPEG")
        with self.assertRaises(ImageNormalizationBlocked):
            normalize(self.input, self.output, self.report)


if __name__ == "__main__":
    unittest.main()
