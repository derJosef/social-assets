"""Synthetic offline tests for two legacy artwork replacements; no Buffer writes."""
from __future__ import annotations

import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from PIL import Image

from scripts import legacy_six_draft_image_prepare as m


def png_bytes():
    output = io.BytesIO()
    Image.new("RGB", m.SIZE, "#091527").save(output, "PNG")
    return output.getvalue()


class LegacyImagePrepareTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        raw = png_bytes()
        self.raw = raw
        self.sha = m.sha256(raw)
        self.legacy = tuple(
            dict(x, sha256=self.sha, adobe_url=f"https://at.adobe.com/AbC123xyz{i}")
            for i, x in enumerate(m.LEGACY)
        )
        self.built = []

        def build(spec, root, base, final, font, logo):
            j = json.loads(spec.read_text())
            self.built.append(j)
            base.write_bytes(self.raw)
            final.write_bytes(self.raw)
            return {"status": "verified_image_only",
                    "source_sha256": self.sha,
                    "layout": "logo_only", "size": list(m.SIZE),
                    "logo_qa": {"logo_verified": True},
                    "sha256": self.sha}
        self.fake_build = build

    def run_stage(self, fetch=None, builder=None):
        with mock.patch.object(m, "LEGACY", self.legacy):
            return m.stage(self.root, fetch=fetch or (lambda _: self.raw),
                           builder=builder or self.fake_build)

    def test_two_topics_prepare_only_ten_new_files_and_no_buffer(self):
        result = self.run_stage()
        self.assertEqual(len(result), 2)
        self.assertEqual(len(self.built), 2)
        for item in self.legacy:
            outputs = m.paths(self.root, item["key"])
            self.assertTrue(all(p.is_file() for p in outputs.values()))
            self.assertEqual(self.sha, m.sha256(outputs["final"].read_bytes()))
            self.assertEqual(item["ids"], json.loads(outputs["receipt"].read_text())["old_draft_ids"])
        self.assertTrue(all(x["buffer_mutations"] == 0 for x in result))
        self.assertTrue(all(x["publication_authorized"] is False for x in result))
        self.assertTrue(all(x["chatgpt_review"]["kind"] == "chatgpt_visual_inspection_draft_only"
                            for x in self.built))

    def test_bad_sha_rejected_before_scene_build(self):
        with self.assertRaisesRegex(ValueError, "do not match"):
            self.run_stage(fetch=lambda _: self.raw + b"replaced")
        self.assertEqual(self.built, [])

    def test_sha_mismatch_includes_safe_digest_length_and_type(self):
        altered = b"\x89PNG\r\n\x1a\n" + b"private_data_not_for_logs"
        with self.assertRaises(ValueError) as ctx:
            self.run_stage(fetch=lambda _: altered)
        message = str(ctx.exception)
        self.assertIn("received_sha256=" + m.sha256(altered), message)
        self.assertIn("bytes=" + str(len(altered)), message)
        self.assertIn("signature=png", message)
        self.assertIn("topic=" + self.legacy[0]["key"], message)
        self.assertNotIn("private_data_not_for_logs", message)
        self.assertNotIn("AbC123xyz", message)
        self.assertEqual(self.built, [])

    def test_jpeg_shortlink_rendition_is_rejected_with_safe_type(self):
        altered = b"\xff\xd8\xff" + b"do_not_log_me"
        with self.assertRaisesRegex(ValueError, "signature=jpeg"):
            self.run_stage(fetch=lambda _: altered)
        self.assertEqual(self.built, [])

    def test_owner_issue_comment_gate_is_strict(self):
        # This is not a permission to process arbitrary issue comments.
        workflow = (Path(__file__).resolve().parents[1] /
                    ".github/workflows/legacy-six-draft-images-only.yml").read_text()
        self.assertIn("issue_comment:", workflow)
        self.assertIn("github.event.issue.number == 19", workflow)
        self.assertIn("github.event.comment.user.login == 'derJosef'", workflow)
        self.assertIn("github.actor == 'derJosef'", workflow)
        self.assertIn("github.run_attempt == 1", workflow)
        self.assertIn("LEGACY_IMAGE_BUILD_ONCE_20261016", workflow)
        self.assertIn("git ls-remote --heads", workflow)
        self.assertNotIn("BUFFER_API_KEY", workflow)
        self.assertNotIn("  push:", workflow)

    def test_fresh_owner_links_parse_and_reach_image_builder(self):
        body = "\n".join((
            m.FRESH_CONFIRM,
            "wer_liest_mit=https://at.adobe.com/CorrectLink12345",
            "ein_agent_drei_tests=https://at.adobe.com/CorrectLink67890",
        ))
        event = self.root / "github-event.json"
        event.write_text(json.dumps({
            "action": "created",
            "issue": {"number": 19, "user": {"login": "derJosef"}},
            "comment": {"user": {"login": "derJosef"}, "body": body},
        }))
        links = m.parse_owner_image_event(event)
        called = []
        def fetch(url):
            called.append(url)
            return self.raw
        result = self.run_stage_with_links(links, fetch=fetch)
        self.assertEqual(len(result), 2)
        self.assertEqual(called, list(links.values()))
        self.assertTrue(all(item["source_adobe_url"] in called for item in result))
        self.assertTrue(all(item["buffer_mutations"] == 0 for item in result))

    def run_stage_with_links(self, urls, fetch):
        with mock.patch.object(m, "LEGACY", self.legacy):
            return m.stage(self.root, fetch=fetch, builder=self.fake_build, fresh_urls=urls)

    def test_fresh_comment_rejects_other_user_bad_url_or_extra_commands(self):
        good = "\\n".join((
            m.FRESH_CONFIRM,
            "wer_liest_mit=https://at.adobe.com/CorrectLink12345",
            "ein_agent_drei_tests=https://at.adobe.com/CorrectLink67890",
        ))
        path = self.root / "github-event.json"
        event = {
            "action": "created",
            "issue": {"number": 19, "user": {"login": "derJosef"}},
            "comment": {"user": {"login": "derJosef"}, "body": good},
        }
        for bad in (
            {"comment": {"user": {"login": "stranger"}, "body": good}},
            {"issue": {"number": 23, "user": {"login": "derJosef"}}},
            {"comment": {"user": {"login": "derJosef"}, "body": good + "\\nrun=publish"}},
            {"comment": {"user": {"login": "derJosef"}, "body": good.replace("https://at.adobe.com/", "https://other.example/")}},
            {"comment": {"user": {"login": "derJosef"}, "body": good.replace("CorrectLink67890", "CorrectLink12345")}},
        ):
            value = {**event, **bad}
            path.write_text(json.dumps(value))
            with self.assertRaises(ValueError):
                m.parse_owner_image_event(path)

    def test_cannot_overwrite_any_existing_artwork(self):
        p = m.paths(self.root, self.legacy[0]["key"])["source"]
        p.parent.mkdir(parents=True)
        p.write_bytes(b"keep-original")
        with self.assertRaisesRegex(ValueError, "already prepared"):
            self.run_stage()
        self.assertEqual(p.read_bytes(), b"keep-original")
        self.assertEqual(self.built, [])

    def test_mocked_logo_verification_fails_closed(self):
        def bad(spec, root, base, final, font, logo):
            base.write_bytes(self.raw)
            final.write_bytes(self.raw)
            return {"status": "verified_image_only", "source_sha256": self.sha,
                    "layout": "logo_only", "size": list(m.SIZE),
                    "logo_qa": {"logo_verified": False}, "sha256": self.sha}
        with self.assertRaisesRegex(ValueError, "QA did not pass"):
            self.run_stage(builder=bad)
        # This is a local workspace, not a published asset branch. Failed QA
        # prevents a signed report, and the workflow's set -e prevents git push.
        self.assertFalse(m.paths(self.root, self.legacy[0]["key"])["receipt"].exists())

    def test_unexpected_image_geometry_fails(self):
        bad = io.BytesIO()
        Image.new("RGB", (1080, 1080)).save(bad, "PNG")
        raw = bad.getvalue()
        wrong = tuple(dict(x, sha256=m.sha256(raw)) for x in self.legacy)
        with mock.patch.object(m, "LEGACY", wrong):
            with self.assertRaisesRegex(ValueError, "1080x1350"):
                m.stage(self.root, fetch=lambda _: raw, builder=self.fake_build)

    def test_fixed_id_lists_have_no_overlap(self):
        ids = [pid for x in m.LEGACY for pid in x["ids"].values()]
        self.assertEqual(len(ids), 6)
        self.assertEqual(len(set(ids)), 6)
        self.assertEqual({i for x in m.LEGACY for i in x["ids"]},
                         {"linkedin", "facebook", "instagram"})

    def test_draft_repair_script_cannot_mutate_buffer(self):
        import inspect
        code = inspect.getsource(m)
        for dangerous in ("buffer_graphql(", "editPost(", "createPost(", "deletePost(", "shareNow"):
            self.assertNotIn(dangerous, code)


if __name__ == "__main__":
    unittest.main()
