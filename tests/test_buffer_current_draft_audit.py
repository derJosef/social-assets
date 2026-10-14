"""Offline safety tests for Buffer editorial inventory: no mutation or scheduling."""
import json
import unittest
from pathlib import Path
from scripts import buffer_current_draft_audit as mod

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/buffer-current-editorial-audit.yml"

class AuditTests(unittest.TestCase):
    def test_fetch_draft_and_scheduled_posts_without_write(self):
        calls = []
        def get(key, query, vars):
            calls.append((query, vars))
            if "organizations" in query:
                return {"account":{"organizations":[{"id":"org1"}]}}
            self.assertEqual(vars["channelIds"],list(mod.CHANNELS.values()))
            self.assertIn("posts(", query)
            return {"posts":{"edges":[
                {"node":{"id":"a1","channelId":mod.CHANNELS["linkedin"],
                 "status":"scheduled","text":"Already approved","createdAt":"2026-10-10T10:00:00Z",
                 "dueAt":"2026-10-20T16:00:00Z","assets":[{"type":"image","source":"https://example.test/i.png"}]}},
                {"node":{"id":"a2","channelId":mod.CHANNELS["facebook"],
                 "status":"draft","text":"Needs illustration","createdAt":"2026-10-11T10:00:00Z",
                 "dueAt":None,"assets":[]}},
            ],"pageInfo":{"hasNextPage":False},"totalCount":2}}
        got=mod.collect(get=get,key="test-only")
        self.assertEqual(got["count"],2)
        self.assertEqual(got["posts"][0]["asset_count"],0)
        self.assertTrue(got["no_buffer_mutations"])
        self.assertEqual(len(calls),2)

    def test_postsresults_query_uses_only_documented_fields(self):
        # Buffer GraphQL schema: PostsResults exposes edges and pageInfo ONLY.
        # The original audit failed with a GraphQL error because totalCount
        # exists on other connections but not on PostsResults.
        q = mod.POSTS_QUERY
        self.assertIn("edges {", q)
        self.assertIn("pageInfo {", q)
        self.assertNotIn("totalCount", q)
        self.assertIn("createdAt", q)
        self.assertIn("assets { type source }", q)

    def test_rejects_unknown_channel_and_pagination_failure(self):
        def get(key, query, variables):
            if "organizations" in query:
                return {"account":{"organizations":[{"id":"org1"}]}}
            return {"posts":{"edges":[{"node":{"id":"x","channelId":"wrong","assets":[]}}],"pageInfo":{}}}
        with self.assertRaises(mod.AuditBlocked):
            mod.collect(get=get,key="test")

    def test_workflow_guarded_and_query_is_read_only(self):
        w=WORKFLOW.read_text()
        for item in ("issue_comment:","github.actor == 'derJosef'","github.event.issue.number == 19",
                     "AUDIT_AI_AGENT_BUFFER_DRAFTS_20261013","contents: read",
                     "persist-credentials: false","retention-days: 1"):
            self.assertIn(item,w)
        for danger in ("createPost(","editPost(","git push","contents: write",
                       "workflow_dispatch:","schedule:"):
            self.assertNotIn(danger,w)
        for danger in ("mutation ","createPost(","editPost("):
            self.assertNotIn(danger,mod.POSTS_QUERY)


if __name__ == "__main__":
    unittest.main()
