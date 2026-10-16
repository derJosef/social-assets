"""Synthetic-only proof that one-off image draft cannot publish or retry."""
from __future__ import annotations

import hashlib
import os
import unittest
from datetime import datetime, timezone
from unittest import mock

from scripts import buffer_image_prescheduled_draft_probe as probe
from scripts.buffer_draft import CREATE_DATED_DRAFT


class OneImageProbeTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 10, 16, 8, 32, tzinfo=timezone.utc)
        self.due = probe.future_time(self.now)
        self.env = {
            "GITHUB_REPOSITORY": probe.REPOSITORY,
            "GITHUB_REF": "refs/heads/main",
            "GITHUB_EVENT_NAME": "workflow_dispatch",
            "GITHUB_ACTOR": "derJosef",
            "GITHUB_RUN_ATTEMPT": "1",
            "GITHUB_RUN_ID": "88123456",
            "PROBE_CONFIRMATION": probe.CONFIRMATION,
            "GITHUB_TOKEN": "synthetic-github",
            "BUFFER_API_KEY": "synthetic-buffer",
        }
        self.text = (
            f"{probe.TEXT_PREFIX} Bildvergleich mit dem erfolgreichen Text-Entwurf. "
            f"{probe.PROBE_ID}. GitHub-Lauf {self.env['GITHUB_RUN_ID']}."
        )
        self.post = {
            "id": "synthetic-post-001", "channelId": "linkedin-synthetic",
            "status": "draft", "dueAt": self.due,
        }
        self.readback = {
            **self.post, "text": self.text,
            "assets": [{
                "source": probe.IMAGE_URL, "mimeType": "image/png",
            }],
        }

    def run_mocked(self, first=None, second=None, *, exists=None, preflight_error=None):
        saved = []
        def put(*args, **kwargs):
            saved.append(dict(args[2]))
            return f"synthetic-receipt-sha-{len(saved)}"
        answer = {"createPost": {"post": self.post}} if first is None else first
        confirm = {"post": self.readback} if second is None else second
        graph = mock.Mock(side_effect=[answer, confirm])
        with (
            mock.patch.object(probe, "fetch_receipt", return_value=exists) as get,
            mock.patch.object(probe, "put_receipt", side_effect=put) as put_mock,
            mock.patch.object(probe, "preflight_image", side_effect=preflight_error) as pre,
            mock.patch.object(probe, "resolve_channel", return_value="linkedin-synthetic") as chan,
            mock.patch.object(probe, "buffer_graphql", graph),
        ):
            try:
                probe.run_probe(self.env, now=self.now)
                error = None
            except (RuntimeError, ValueError) as exc:
                error = str(exc)
        return {
            "error": error, "saved": saved, "graph": graph,
            "receipt": put_mock, "preflight": pre, "channel": chan, "lookup": get,
        }

    def test_success_is_one_create_one_read_only_verify_three_receipts(self):
        row = self.run_mocked()
        self.assertIsNone(row["error"])
        self.assertEqual(row["graph"].call_count, 2)
        mutation = row["graph"].call_args_list[0]
        self.assertEqual(mutation.args[1], CREATE_DATED_DRAFT)
        args = mutation.args[2]
        self.assertEqual(args["assets"][0]["image"]["url"], probe.IMAGE_URL)
        self.assertEqual(args["assets"][0]["image"]["metadata"]["altText"], probe.ALT)
        self.assertEqual(args["dueAt"], self.due)
        self.assertIsNone(args["metadata"])
        self.assertIn("saveToDraft: true", mutation.args[1])
        self.assertNotIn("saveToDraft: false", mutation.args[1])
        self.assertNotIn("editPost", mutation.args[1])
        self.assertEqual([x["state"] for x in row["saved"]], [
            "pending_manual_reconciliation_on_failure",
            "created_requires_independent_check",
            "verified_prescheduled_image_draft_not_queued",
        ])
        self.assertEqual(row["graph"].call_args_list[1].args[1], probe.READ_IMAGE_DRAFT)

    def test_explicit_owner_dispatch_is_required(self):
        for k, value in (
            ("GITHUB_ACTOR", "evil-user"),
            ("GITHUB_EVENT_NAME", "push"),
            ("GITHUB_REF", "refs/heads/untrusted"),
            ("GITHUB_RUN_ATTEMPT", "2"),
            ("PROBE_CONFIRMATION", ""),
        ):
            with self.subTest(k=k):
                attempt = {**self.env, k: value}
                with self.assertRaisesRegex(RuntimeError, "gesperrt"):
                    probe.run_probe(attempt, now=self.now, fetch=lambda _: b"")
        self.assertEqual(probe.future_time(self.now)[-1], "Z")

    def test_preexisting_receipt_blocks_all_writes(self):
        row = self.run_mocked(exists={"state": "pending_manual_reconciliation_on_failure"})
        self.assertIn("bereits reserviert", row["error"])
        self.assertEqual(row["graph"].call_count, 0)
        self.assertEqual(len(row["saved"]), 0)
        row["preflight"].assert_not_called()

    def test_bad_media_blocks_before_pending_reservation(self):
        row = self.run_mocked(preflight_error=RuntimeError("image SHA mismatch"))
        self.assertIn("image SHA mismatch", row["error"])
        self.assertEqual(row["graph"].call_count, 0)
        self.assertEqual(len(row["saved"]), 0)

    def test_invalid_input_is_sanitized_and_pending_never_retried(self):
        secret = "DO_NOT_EXPOSE_BUFFER_SECRET_123"
        row = self.run_mocked(first={"createPost": {
            "__typename": "InvalidInputError",
            "message": "Cannot download image https://example.invalid?token=" + secret,
        }})
        self.assertIn("InvalidInputError", row["error"])
        self.assertIn("Diagnosekategorie=media_access", row["error"])
        self.assertNotIn(secret, row["error"])
        self.assertNotIn("example.invalid", row["error"])
        self.assertEqual(row["graph"].call_count, 1)
        self.assertEqual(len(row["saved"]), 1)
        self.assertEqual(row["saved"][0]["state"], "pending_manual_reconciliation_on_failure")

    def test_wrong_created_status_blocks_independent_read(self):
        row = self.run_mocked(first={"createPost": {"post": {**self.post, "status": "scheduled"}}})
        self.assertIn("ALARM", row["error"])
        self.assertEqual(row["graph"].call_count, 1)
        self.assertEqual([x["state"] for x in row["saved"]], [
            "pending_manual_reconciliation_on_failure",
            "created_requires_independent_check",
        ])

    def test_wrong_or_missing_media_in_readback_blocks(self):
        for assets in ([], [{"source": "wrong", "mimeType": "application/pdf"}]):
            with self.subTest(assets=assets):
                row = self.run_mocked(second={"post": {**self.readback, "assets": assets}})
                self.assertIn("ALARM", row["error"])
                self.assertEqual(row["graph"].call_count, 2)
                self.assertEqual(len(row["saved"]), 2)

    def test_wrong_image_source_even_if_png_blocks(self):
        row = self.run_mocked(second={"post": {
            **self.readback,
            "assets": [{"source": "https://not-original.invalid/other.png",
                        "mimeType": "image/png"}],
        }})
        self.assertIn("ALARM", row["error"])
        self.assertEqual(row["graph"].call_count, 2)
        self.assertEqual(len(row["saved"]), 2)

    def test_wrong_post_text_in_readback_blocks(self):
        row = self.run_mocked(second={"post": {**self.readback, "text": "unexpected"}})
        self.assertIn("ALARM", row["error"])
        self.assertEqual(len(row["saved"]), 2)

    def test_preflight_requires_exact_pinned_png_bytes(self):
        raw = b"\x89PNG\r\n\x1a\n" + b"synthetic-test-image-bytes"
        with mock.patch.object(probe, "IMAGE_SHA256", hashlib.sha256(raw).hexdigest()):
            probe.preflight_image(fetch=lambda _: raw)
            with self.assertRaisesRegex(RuntimeError, "SHA-verifiziert"):
                probe.preflight_image(fetch=lambda _: raw + b"changed")

    def test_image_reference_is_original_logo_pinned_commit(self):
        self.assertTrue(probe.IMAGE_URL.startswith(
            "https://raw.githubusercontent.com/derJosef/social-assets/"
            + probe.IMAGE_COMMIT + "/media/images/"
        ))
        self.assertEqual(len(probe.IMAGE_SHA256), 64)
        self.assertEqual(probe.TARGET, "linkedin")
        self.assertNotIn("2026-10-15-drei-kontrollpunkte-e2e-linkedin", probe.RECEIPT)

    def test_only_one_mutating_graphql_query_in_script(self):
        import inspect
        source = inspect.getsource(probe)
        self.assertNotIn("deletePost", source)
        self.assertNotIn("editPost(", source)
        self.assertNotIn("shareNow", source)
        self.assertNotIn("saveToDraft: false", source)
        self.assertIn("CREATE_DATED_DRAFT", source)


if __name__ == "__main__":
    unittest.main()
