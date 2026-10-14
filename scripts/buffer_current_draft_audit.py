#!/usr/bin/env python3
"""Read Buffer AI Agent Builder channel posts without ANY mutation.

Print only truncated previews and metadata in public logs. Store complete texts
in a short-lived GitHub Actions artifact for editorial review.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

if __package__:
    from .buffer_draft import buffer_graphql, GET_ORGANIZATIONS
else:
    from buffer_draft import buffer_graphql, GET_ORGANIZATIONS

CHANNELS = {
    "linkedin": "6aac167eea19ca0bde6ada5b",
    "facebook": "6ac781e46a5c39ccb64fe01c",
    "instagram": "6ac79a686a5c39ccb650f94b",
}
POSTS_QUERY = """
query AuditCurrentPosts($organizationId: OrganizationId!, $channelIds: [ChannelId!], $after: String) {
  posts(first: 100, after: $after, input: {
    organizationId: $organizationId,
    filter: {channelIds: $channelIds},
    sort: [{field: createdAt, direction: desc}]
  }) {
    edges {
      node { id channelId channelService status text dueAt createdAt
             assets { type source } }
    }
    pageInfo { hasNextPage endCursor }
    totalCount
  }
}
"""


class AuditBlocked(RuntimeError):
    pass


def collect(*, get=buffer_graphql, key: str | None = None) -> dict:
    key = key or os.environ.get("BUFFER_API_KEY")
    if not key:
        raise AuditBlocked("Buffer read-only API secret missing")
    acc = get(key, GET_ORGANIZATIONS, {}).get("account")
    orgs = acc.get("organizations") if isinstance(acc, dict) else None
    if not isinstance(orgs, list):
        raise AuditBlocked("Buffer account organizations unavailable")
    all_posts = {}
    scanned = []
    for org in orgs:
        org_id = org.get("id") if isinstance(org, dict) else None
        if not isinstance(org_id, str) or not org_id:
            continue
        scanned.append(org_id)
        after = None
        for page in range(5):
            rows = get(key, POSTS_QUERY, {
                "organizationId": org_id,
                "channelIds": list(CHANNELS.values()),
                "after": after,
            }).get("posts")
            if not isinstance(rows, dict) or not isinstance(rows.get("edges"), list):
                raise AuditBlocked("Buffer posts query returned an invalid page")
            for edge in rows["edges"]:
                post = edge.get("node") if isinstance(edge, dict) else None
                if not isinstance(post, dict):
                    raise AuditBlocked("Bad post record")
                post_id = post.get("id")
                if not isinstance(post_id, str) or post.get("channelId") not in CHANNELS.values():
                    raise AuditBlocked("Unexpected post ID or channel")
                assets = post.get("assets")
                if not isinstance(assets, list):
                    raise AuditBlocked("Buffer post assets malformed")
                channel = next(c for c, ident in CHANNELS.items() if ident == post["channelId"])
                all_posts[post_id] = {
                    "id": post_id, "channel": channel, "status": post.get("status"),
                    "text": post.get("text") or "", "created_at": post.get("createdAt"),
                    "due_at": post.get("dueAt"), "asset_count": len(assets),
                    "asset_types": [a.get("type") for a in assets if isinstance(a, dict)],
                    "asset_urls": [a.get("source") for a in assets if isinstance(a, dict)],
                }
            info = rows.get("pageInfo") or {}
            if not info.get("hasNextPage"):
                break
            after = info.get("endCursor")
            if not isinstance(after, str) or not after:
                raise AuditBlocked("Buffer pagination cursor missing")
        else:
            raise AuditBlocked("More than 500 posts: audit range must be narrowed")
    records = sorted(all_posts.values(), key=lambda p: str(p.get("created_at") or ""), reverse=True)
    return {
        "checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "kind": "read_only_ai_agent_builder_draft_audit",
        "channels": CHANNELS, "organization_count": len(scanned),
        "count": len(records), "posts": records,
        "no_buffer_mutations": True,
    }


def main() -> int:
    if os.environ.get("GITHUB_EVENT_NAME") != "issue_comment":
        print("Only restricted comment-based owner audit is authorized.", file=sys.stderr)
        return 1
    try:
        data = collect()
        dest = Path(os.environ.get("RUNNER_TEMP", "/tmp")) / "current-buffer-posts.json"
        dest.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        print("BUFFER_READ_ONLY_AUDIT", data["count"], "current posts, no mutation")
        for post in data["posts"]:
            preview = " ".join(post["text"].split())[:210]
            print("BUFFER_AUDIT_POST", json.dumps({
                "id":post["id"],"channel":post["channel"],"status":post["status"],
                "due_at":post["due_at"], "asset_count":post["asset_count"],
                "created_at":post["created_at"],"preview":preview
            },ensure_ascii=False))
        return 0
    except (AuditBlocked, ValueError, OSError, RuntimeError) as exc:
        print("BUFFER_AUDIT_BLOCKED", type(exc).__name__, str(exc)[:220], file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
