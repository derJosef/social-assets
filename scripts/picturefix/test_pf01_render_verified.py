"""Isolated, fully offline regression tests for the PF-01 social-image renderer."""
import importlib.util
import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw

MODULE_PATH = Path(__file__).with_name("pf01_render_verified.py")
spec = importlib.util.spec_from_file_location("pf01_renderer", MODULE_PATH)
pf = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pf)

class TestPictureFixPF01(unittest.TestCase):
    def setUp(self):
        self.logo = Image.new("RGBA", (445, 107), (255, 255, 255, 0))
        ImageDraw.Draw(self.logo).rectangle((10, 15, 425, 92), fill=(55, 40, 25, 255))

    def test_git_blob_hash_follows_git_algorithm(self):
        import hashlib
        content = b"PF logo fixture"
        self.assertEqual(pf.git_blob_sha(content), hashlib.sha1(b"blob 15\0PF logo fixture").hexdigest())

    def test_unmodified_draft_outside_logo_panel(self):
        for role, expected in [("facebook_instagram", (1080, 1350)), ("pinterest", (1000, 1500))]:
            with self.subTest(role=role):
                original = Image.new("RGBA", expected, (225, 211, 196, 255))
                result, rect = pf.composite_exact(original, self.logo, role)
                self.assertEqual(result.size, expected)
                self.assertEqual(result.getpixel((1, 1)), original.getpixel((1, 1)))
                masked_result = result.copy()
                masked_original = original.copy()
                ImageDraw.Draw(masked_result).rectangle(rect, fill=(0, 0, 0, 0))
                ImageDraw.Draw(masked_original).rectangle(rect, fill=(0, 0, 0, 0))
                self.assertIsNone(ImageChops.difference(masked_result.convert("RGB"), masked_original.convert("RGB")).getbbox())
                self.assertIsNotNone(ImageChops.difference(result.convert("RGB"), original.convert("RGB")).getbbox())

    def test_reject_unverified_logo_before_creating_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bad = root / "wrong-logo.png"
            self.logo.save(bad)
            out = root / "out"
            with self.assertRaisesRegex(ValueError, "Unverified logo"):
                pf.render(root, bad, out)
            self.assertFalse(out.exists())

    def test_reject_wrong_input_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "not-the-approved-draft.png"
            self.logo.save(p)
            with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
                pf.load_verified(p, expected_sha256="0" * 64)

if __name__ == "__main__":
    unittest.main()
