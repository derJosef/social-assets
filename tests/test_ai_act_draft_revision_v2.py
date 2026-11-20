"""Offline guards for the single-use EU AI Act existing-draft correction."""
from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import ai_act_draft_revision_v2 as revision

ROOT = Path(__file__).resolve().parents[1]


class RevisionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.event = Path(self.tmp.name) / "event.json"
        self.old, self.new = revision.expected_texts(ROOT)
        self.posts = {
            target: {
                "id": record["id"], "channelId": record["channel"],
                "channelService": target, "status": "draft",
                "dueAt": record["due_at"], "text": self.old[target],
                "shareMode": "customScheduled", "schedulingType": "automatic",
                "assets": [{"type": "image", "source": revision.OLD_IMAGE,
                            "mimeType": "image/png"}],
                "tags": [{"id": "tag1"}],
                "metadata": {"__typename": target, "type": "post"},
            } for target, record in revision.TARGETS.items()
        }
        self.receipts = {}
        self.mutations = []

    def env(self, mode="preflight", *, actor="derJosef-agents"):
        self.event.write_text(json.dumps({
            "action": "created",
            "issue": {"number": revision.ISSUE, "title": revision.ISSUE_TITLE,
                      "user": {"login": "derJosef"}},
            "comment": {"body": revision.COMMANDS[mode],
                        "user": {"login": actor,
                                 "id": revision.ACTOR_ID if actor == revision.ACTOR
                                 else 999}},
        }), encoding="utf-8")
        return {"GITHUB_REPOSITORY": "derJosef/social-assets",
                "GITHUB_REF": "refs/heads/main",
                "GITHUB_EVENT_NAME": "issue_comment",
                "GITHUB_RUN_ATTEMPT": "1",
                "GITHUB_ACTOR": actor,
                "GITHUB_ACTOR_ID": str(revision.ACTOR_ID),
                "GITHUB_EVENT_PATH": str(self.event),
                "BUFFER_API_KEY": "fake", "GITHUB_TOKEN": "fake",
                "GITHUB_RUN_ID": "test-123"}

    def query(self, _key, graphql, variables):
        if "mutation" not in graphql:
            pid = variables["id"]
            target = next(t for t, p in self.posts.items() if p["id"] == pid)
            return {"post": copy.deepcopy(self.posts[target])}
        self.mutations.append(copy.deepcopy(variables))
        pid = variables["id"]
        target = next(t for t, p in self.posts.items() if p["id"] == pid)
        self.posts[target]["text"] = variables["text"]
        self.posts[target]["assets"] = [{
            "type": "image", "source": revision.NEW_IMAGE,
            "mimeType": "image/png"
        }]
        return {"editPost": {"post": copy.deepcopy(self.posts[target])}}

    def get_receipt(self, _key, path):
        return copy.deepcopy(self.receipts.get(path))

    def put_receipt(self, _key, path, data, _message, sha=None):
        if path in self.receipts and sha != "sha-placeholder":
            raise AssertionError("Receipt update without lease")
        self.receipts[path] = copy.deepcopy(data)
        return "sha-placeholder"

    def run_revision(self, mode, env=None):
        with mock.patch.object(revision, "verify_image",
                               return_value=revision.NEW_IMAGE):
            return revision.run(mode, root=ROOT, env=env or self.env(mode),
                                query=self.query, get_receipt=self.get_receipt,
                                put_receipt=self.put_receipt)

    def test_exactly_five_instagram_hashtags_only(self):
        self.assertTrue(self.old["instagram"].endswith("#Digitalisierung"))
        self.assertEqual(len(self.new["instagram"].split("#")) - 1, 5)
        self.assertEqual(self.old["facebook"], self.new["facebook"])
        self.assertEqual(self.old["linkedin"], self.new["linkedin"])

    def test_read_only_preflight_never_writes(self):
        result = self.run_revision("preflight")
        self.assertEqual(result["state"], "read_only_preflight_pass")
        self.assertEqual(len(result["existing_ids"]), 3)
        self.assertEqual(self.mutations, [])
        self.assertEqual(self.receipts, {})

    def test_exactly_three_existing_posts_changed_never_created(self):
        result = self.run_revision("apply")
        self.assertEqual(result["state"],
                         "verified_three_existing_drafts_revised_unpublished")
        self.assertEqual(len(self.mutations), 3)
        self.assertTrue(all("dueAt" in mutation for mutation in self.mutations))
        for target, post in self.posts.items():
            self.assertEqual(post["id"], revision.TARGETS[target]["id"])
            self.assertEqual(post["status"], "draft")
            self.assertEqual(post["dueAt"], revision.TARGETS[target]["due_at"])
            self.assertEqual(post["text"], self.new[target])
            self.assertEqual(post["assets"][0]["source"], revision.NEW_IMAGE)
            self.assertEqual(self.receipts[revision.receipt_path(target)]["state"],
                             "verified_existing_draft_revised_unpublished")
        self.assertEqual(self.receipts[revision.BATCH_RECEIPT]["state"],
                         "verified_three_existing_drafts_revised_unpublished")

    def test_scheduled_post_blocks_entire_batch_before_mutation(self):
        self.posts["facebook"]["status"] = "scheduled"
        with self.assertRaisesRegex(revision.RevisionBlocked, "Status"):
            self.run_revision("apply")
        self.assertEqual(self.mutations, [])
        self.assertEqual(self.receipts, {})

    def test_wrong_channel_blocks_before_mutation(self):
        self.posts["instagram"]["channelId"] = "wrong"
        with self.assertRaisesRegex(revision.RevisionBlocked, "Channel-ID"):
            self.run_revision("apply")
        self.assertEqual(self.mutations, [])

    def test_existing_batch_receipt_blocks_replay(self):
        self.receipts[revision.BATCH_RECEIPT] = {"state": "pending"}
        with self.assertRaisesRegex(revision.RevisionBlocked, "bereits reserviert"):
            self.run_revision("apply")
        self.assertEqual(self.mutations, [])

    def test_ambiguous_first_mutation_blocks_replay(self):
        def ambiguous(*args):
            if "mutation" in args[1]:
                self.mutations.append(copy.deepcopy(args[2]))
                raise ConnectionError("indeterminate post-edit outcome")
            return self.query(*args)
        with mock.patch.object(revision, "verify_image",
                               return_value=revision.NEW_IMAGE):
            with self.assertRaises(ConnectionError):
                revision.run("apply", root=ROOT, env=self.env("apply"),
                             query=ambiguous, get_receipt=self.get_receipt,
                             put_receipt=self.put_receipt)
        self.assertEqual(len(self.mutations), 1)
        with self.assertRaisesRegex(revision.RevisionBlocked, "bereits reserviert"):
            self.run_revision("apply")
        self.assertEqual(len(self.mutations), 1)

    def test_wrong_actor_blocks_without_reading_buffer(self):
        with self.assertRaisesRegex(revision.RevisionBlocked, "authentifizierter"):
            self.run_revision("apply", env=self.env("apply", actor="derJosef"))
        self.assertEqual(self.mutations, [])

    def test_wrong_issue_comment_blocks(self):
        env = self.env("apply")
        payload = json.loads(self.event.read_text())
        payload["comment"]["body"] = "AIAGENT_AI_ACT_BAD_COMMAND"
        self.event.write_text(json.dumps(payload))
        with self.assertRaisesRegex(revision.RevisionBlocked, "Exakter"):
            self.run_revision("apply", env=env)
        self.assertEqual(self.mutations, [])


if __name__ == "__main__":
    unittest.main()
