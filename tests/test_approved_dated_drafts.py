"""Offline tests for the production path enabled ONLY after a protected brief approval.

There are no GitHub or Buffer network calls in this module.
"""
import json
import base64
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock
from zoneinfo import ZoneInfo

from scripts import buffer_draft as sender
from scripts import brief_approval_gate as approvals
from scripts import orchestrator_verify_buffer as reconciliation


CAMPAIGN = "2026-10-12-synthetic-approval"
POST = f"ready-for-buffer/auto-{CAMPAIGN}-linkedin.json"
TARGETS = ("linkedin", "facebook", "instagram")
POST_ID = "0123456789abcdef01234567"


class DatedDraftTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        for folder in ("campaign-manifests", "ready-for-buffer", "drafts", "orchestration/briefs"):
            (self.root / folder).mkdir(parents=True)
        self.now = datetime.now(timezone.utc)
        self.times = {}
        for offset, target in enumerate(TARGETS):
            utc = (self.now + timedelta(days=12 + offset)).replace(hour=12, minute=0, second=0, microsecond=0)
            self.times[target] = {
                "utc": utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "local": utc.astimezone(ZoneInfo("Europe/Berlin")).isoformat(timespec="seconds"),
            }
        self.due = self.times["linkedin"]["utc"]
        self.manifest = {
            "brand": "ai-agent-builder", "campaign_id": CAMPAIGN,
            "posting_times": self.times,
            "posts": {t: f"ready-for-buffer/auto-{CAMPAIGN}-{t}.json" for t in TARGETS},
        }
        self.save_manifest()
        self.post_texts = {t: f"Synthetic approved {t} text" for t in TARGETS}
        for target in TARGETS:
            draft = {"format_version": 1, "target": target, "text": self.post_texts[target]}
            if target != "linkedin":
                draft = {"format_version": 2, "target": target, "text": self.post_texts[target],
                         "media": {"type": "images", "images": [{
                             "url": "https://raw.githubusercontent.com/derJosef/social-assets/main/media/images/probe.png",
                             "alt_text": "Synthetisches Testbild",
                         }]}}
            (self.root / f"ready-for-buffer/auto-{CAMPAIGN}-{target}.json").write_text(
                json.dumps(draft),
                encoding="utf-8",
            )
        (self.root / "orchestration/briefs" / f"{CAMPAIGN}.json").write_text(
            json.dumps({"prepared_content": {"posts": self.post_texts}}), encoding="utf-8",
        )
        root = mock.patch.object(sender, "ROOT", self.root)
        root.start()
        self.addCleanup(root.stop)

    def save_manifest(self):
        (self.root / "campaign-manifests" / f"{CAMPAIGN}.json").write_text(
            json.dumps(self.manifest), encoding="utf-8",
        )

    def test_date_is_read_from_manifest_not_post_text(self):
        self.assertEqual(sender.planned_due_at(POST, "linkedin", now=self.now), self.due)

    def test_manual_drafts_remain_unscheduled(self):
        self.assertIsNone(sender.planned_due_at("drafts/manual.json", "linkedin", now=self.now))

    def test_legacy_ready_path_is_not_automatic_approval_bypass(self):
        with self.assertRaisesRegex(RuntimeError, "Legacy-ready-for-buffer"):
            sender.planned_due_at("ready-for-buffer/legacy.json", "linkedin", now=self.now)

    def test_filename_platform_mismatch_blocked(self):
        with self.assertRaisesRegex(RuntimeError, "Kanal"):
            sender.planned_due_at(POST, "facebook", now=self.now)

    def test_manifest_wrong_campaign_or_brand_blocked(self):
        for field, value in (("campaign_id", "other"), ("brand", "picturefix")):
            with self.subTest(field=field):
                original = self.manifest[field]
                self.manifest[field] = value
                self.save_manifest()
                with self.assertRaisesRegex(RuntimeError, "Kampagnenmanifest"):
                    sender.planned_due_at(POST, "linkedin", now=self.now)
                self.manifest[field] = original
                self.save_manifest()

    def test_wrong_or_missing_local_time_fails_closed(self):
        self.times["linkedin"]["local"] = "2026-06-01T12:00:00+02:00"
        self.save_manifest()
        with self.assertRaisesRegex(RuntimeError, "konvertierter"):
            sender.planned_due_at(POST, "linkedin", now=self.now)

    def test_past_and_near_future_times_are_blocked(self):
        for seconds in (-86400, 300):
            with self.subTest(seconds=seconds):
                utc = (self.now + timedelta(seconds=seconds)).replace(microsecond=0)
                self.times["linkedin"]["utc"] = utc.strftime("%Y-%m-%dT%H:%M:%SZ")
                self.times["linkedin"]["local"] = utc.astimezone(ZoneInfo("Europe/Berlin")).isoformat(timespec="seconds")
                self.save_manifest()
                with self.assertRaisesRegex(RuntimeError, "abgelaufener"):
                    sender.planned_due_at(POST, "linkedin", now=self.now)

    def test_dated_mutation_never_enqueues(self):
        self.assertIn("saveToDraft: true", sender.CREATE_DATED_DRAFT)
        self.assertIn("mode: customScheduled", sender.CREATE_DATED_DRAFT)
        self.assertIn("dueAt: $dueAt", sender.CREATE_DATED_DRAFT)
        for mutation in (sender.CREATE_DATED_DRAFT, sender.CREATE_DRAFT):
            self.assertNotIn("saveToDraft: false", mutation)
            self.assertNotIn("editPost", mutation)
            self.assertNotIn("shareNow", mutation)

    def test_only_exact_independently_read_back_draft_is_accepted(self):
        obj = {"id": POST_ID, "channelId": "li", "status": "draft", "dueAt": self.due}
        self.assertTrue(sender.verified_dated_post(obj, post_id=POST_ID, channel_id="li", due_at=self.due))
        for key, value in (("status", "scheduled"), ("channelId", "other"),
                           ("id", "wrong"), ("dueAt", None), ("dueAt", "2027-01-01T12:00:00Z")):
            with self.subTest(key=key):
                self.assertFalse(sender.verified_dated_post({**obj, key: value},
                    post_id=POST_ID, channel_id="li", due_at=self.due))

    def test_local_output_must_match_approved_editorial_text(self):
        import scripts.autonomous_campaign_gate as qa
        original_read = qa.read_draft
        with mock.patch.object(qa, "check_campaign", return_value={}), \
             mock.patch.object(approvals, "authorize_draft", return_value={"approved_pr": 42}):
            self.assertEqual(sender.authorize_auto_dated_draft(POST), {"approved_pr": 42})
            changed = self.root / POST
            changed.write_text(json.dumps({"format_version":1,"target":"linkedin","text":"Unapproved change"}))
            with self.assertRaisesRegex(RuntimeError, "weicht"):
                sender.authorize_auto_dated_draft(POST)
        self.assertIs(qa.read_draft, original_read)

    def run_send(self, *, response_post=None, read_post=None, exists=None, approval_error=None):
        _, text, raw = sender.read_draft(POST)
        default = {"id": POST_ID, "channelId": "li-channel", "status": "draft", "dueAt": self.due}
        created = response_post if response_post is not None else default
        confirmed = read_post if read_post is not None else default
        graph = mock.Mock(side_effect=[{"createPost": {"post": created}}, {"post": confirmed}])
        saved_records = []
        def save_receipt(token, path, record, message, **kwargs):
            saved_records.append(json.loads(json.dumps(record)))
            return ("sha-one", "sha-two", "sha-three")[len(saved_records) - 1]
        receipt_put = mock.Mock(side_effect=save_receipt)
        receipt_put.saved_records = saved_records
        approved = mock.Mock(return_value={"approved_pr": 42})
        if approval_error is not None:
            approved.side_effect = approval_error
        env = {
            "GITHUB_REPOSITORY": sender.REPOSITORY, "GITHUB_REF": "refs/heads/main",
            "GITHUB_TOKEN": "synthetic-gh", "BUFFER_API_KEY": "synthetic-buffer",
            "GITHUB_RUN_ID": "9999",
        }
        with mock.patch.dict(os.environ, env), \
             mock.patch.object(sender, "authorize_auto_dated_draft", approved), \
             mock.patch.object(sender, "resolve_channel", return_value="li-channel"), \
             mock.patch.object(sender, "fetch_receipt", return_value=exists), \
             mock.patch.object(sender, "put_receipt", receipt_put), \
             mock.patch.object(sender, "buffer_graphql", graph):
            try:
                sender.send_draft(POST, text, raw)
                error = None
            except (RuntimeError, ValueError) as exc:
                error = str(exc)
        return graph, receipt_put, approved, error

    def test_success_uses_one_create_and_readback_after_reservation(self):
        graph, receipts, approval, error = self.run_send()
        self.assertIsNone(error)
        self.assertEqual(graph.call_count, 2)
        self.assertEqual(graph.call_args_list[0].args[1], sender.CREATE_DATED_DRAFT)
        self.assertEqual(graph.call_args_list[0].args[2]["dueAt"], self.due)
        self.assertEqual(graph.call_args_list[1].args[1], sender.READ_DATED_DRAFT)
        self.assertEqual(receipts.call_count, 3)
        self.assertEqual(receipts.saved_records[0]["state"], "pending_manual_reconciliation_on_failure")
        self.assertEqual(receipts.saved_records[1]["state"], "created_requires_independent_check")
        self.assertEqual(receipts.saved_records[2]["state"], "verified_prescheduled_draft_not_queued")
        approval.assert_called_once_with(POST)

    def test_wrong_create_status_raises_alarm_and_never_retries(self):
        scheduled = {"id": POST_ID, "channelId": "li-channel", "status": "scheduled", "dueAt": self.due}
        graph, receipts, _, error = self.run_send(response_post=scheduled)
        self.assertIn("ALARM", error)
        self.assertEqual(graph.call_count, 1)
        self.assertEqual(receipts.call_count, 2)

    def test_wrong_readback_status_raises_alarm_no_retry(self):
        wrong = {"id": POST_ID, "channelId": "li-channel", "status": "scheduled", "dueAt": self.due}
        graph, receipts, _, error = self.run_send(read_post=wrong)
        self.assertIn("ALARM", error)
        self.assertEqual(graph.call_count, 2)
        self.assertEqual(receipts.call_count, 2)

    def test_existing_receipt_blocks_create(self):
        graph, receipts, _, error = self.run_send(exists={"state": "pending"})
        self.assertIn("Kein erneuter API-Aufruf", error)
        self.assertEqual(graph.call_count, 0)
        self.assertEqual(receipts.call_count, 0)

    def test_unapproved_brief_blocks_before_buffer_and_github_receipt(self):
        graph, receipts, _, error = self.run_send(approval_error=ValueError("brief not approved"))
        self.assertIn("brief not approved", error)
        self.assertEqual(graph.call_count, 0)
        self.assertEqual(receipts.call_count, 0)

    def test_all_three_sender_entrypoints_are_gated(self):
        repo = Path(__file__).resolve().parents[1]
        manual = (repo / ".github/workflows/buffer-draft.yml").read_text()
        automatic = (repo / ".github/workflows/buffer-auto-drafts.yml").read_text()
        orchestrator = (repo / ".github/workflows/social-campaign-orchestrator.yml").read_text()
        self.assertIn("scripts/buffer_draft.py --draft", manual)
        self.assertIn("scripts/buffer_draft.py --draft", automatic)
        self.assertIn("scripts/buffer_draft.py --draft", orchestrator)
        self.assertIn("--dated-draft", orchestrator)
        self.assertLess(orchestrator.index("--dated-draft"),
                        orchestrator.index("python3 scripts/social_orchestrator.py --brief"))

    def test_orchestrator_reconciliation_requires_receipt_and_date_per_channel(self):
        channels = {name: f"channel-{name}" for name in TARGETS}
        def receipt(token, path):
            target = next(t for t in TARGETS if path == sender.receipt_path(
                f"ready-for-buffer/auto-{CAMPAIGN}-{t}.json"))
            record = {
                "draft_file": f"ready-for-buffer/auto-{CAMPAIGN}-{target}.json",
                "state": "verified_prescheduled_draft_not_queued",
                "due_at_utc": self.times[target]["utc"],
                "buffer_post_id": POST_ID,
                "channel_id": channels[target],
            }
            return {"content": base64.b64encode(json.dumps(record).encode()).decode()}
        queried = []
        def graphql(token, query, variables):
            target = TARGETS[len(queried)]
            queried.append(target)
            return {"post": {"id": POST_ID, "channelId": channels[target],
                             "status": "draft", "dueAt": self.times[target]["utc"]}}
        env = {"GITHUB_TOKEN": "synthetic", "BUFFER_API_KEY": "synthetic"}
        with mock.patch.dict(os.environ, env), \
             mock.patch.object(reconciliation, "planned_due_at", side_effect=lambda path, t: self.times[t]["utc"]), \
             mock.patch.object(reconciliation, "fetch_receipt", side_effect=receipt), \
             mock.patch.object(reconciliation, "buffer_graphql", side_effect=graphql):
            result = reconciliation.verify(CAMPAIGN)
        self.assertEqual(queried, list(TARGETS))
        self.assertEqual(result["linkedin"]["dueAt"], self.due)

    def test_orchestrator_reconciliation_rejects_undated_old_receipt(self):
        old = {"state": "draft_created", "draft_file": POST,
               "buffer_post_id": POST_ID}
        content = base64.b64encode(json.dumps(old).encode()).decode()
        with mock.patch.dict(os.environ, {"GITHUB_TOKEN": "synthetic", "BUFFER_API_KEY": "synthetic"}), \
             mock.patch.object(reconciliation, "planned_due_at", return_value=self.due), \
             mock.patch.object(reconciliation, "fetch_receipt", return_value={"content": content}), \
             mock.patch.object(reconciliation, "buffer_graphql", side_effect=AssertionError("No Buffer API")):
            with self.assertRaisesRegex(RuntimeError, "independently verified"):
                reconciliation.verify(CAMPAIGN)


if __name__ == "__main__":
    unittest.main()
