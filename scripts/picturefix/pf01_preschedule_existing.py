#!/usr/bin/env python3
"""One-shot, approval-gated pre-scheduling of the three existing PF-01 drafts.

This cannot create, queue or publish a post.  Each target is a fixed existing
Buffer draft and needs its own author-verified GitHub Issue #81 comment.
"""
from __future__ import annotations

import argparse
import base64
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sys

from scripts import buffer_draft as bridge


ISSUE_NUMBER = 81
ISSUE_TITLE = "PICTUREFIX PF01 EXISTING DRAFT PRESCHEDULE CONTROL"
AGENT_LOGIN = "derJosef-agents"
AGENT_ID = 350701981

# Each time is intentionally pinned and separately approved as a *draft*.
# Europe/Berlin in November = UTC+01. No workflow input can override a time.
TIMES = {
    "facebook": "2026-11-20T17:00:00Z",   # Fri 18:00 Berlin
    "instagram": "2026-11-20T20:00:00Z",  # Fri 21:00 Berlin
    "pinterest": "2026-11-23T09:00:00Z",  # Mon 10:00 Berlin
}

COMMANDS = {
    name: f"PF01_{name.upper()}_PRESCHEDULE_DRAFT_ONLY"
    for name in TIMES
}

# Distinct irreversible one-shot receipts for editing existing posts.
RECEIPTS = {
    name: f"delivery-receipts/2026-11-20-picturefix-pf01-preschedule-{name}.json"
    for name in TIMES
}

READ = """
query VerifyPF01Post($id: PostId!) {
  post(input: { id: $id }) {
    id channelId channelService status dueAt text shareMode schedulingType
    assets { type source }
  }
}
"""

EDIT = """
mutation PrescheduleExistingPF01Draft($id: PostId!, $dueAt: DateTime!) {
  editPost(input: {
    id: $id
    mode: customScheduled
    dueAt: $dueAt
    schedulingType: automatic
    saveToDraft: true
  }) {
    __typename
    ... on PostActionSuccess { post { id channelId status dueAt } }
    ... on MutationError { message }
  }
}
"""


class PrescheduleBlocked(RuntimeError):
    """Fail closed without exposing token, customer content or mutation body."""


def require(condition: bool, reason: str) -> None:
    if not condition:
        raise PrescheduleBlocked(reason)


def same_instant(actual: object, expected: str) -> bool:
    if not isinstance(actual, str):
        return False
    try:
        parsed = datetime.fromisoformat(actual.replace("Z", "+00:00"))
        expected_parsed = datetime.fromisoformat(expected.replace("Z", "+00:00"))
        return parsed.tzinfo is not None and parsed == expected_parsed
    except ValueError:
        return False


def verify_event(target: str, env: dict[str, str]) -> None:
    require(env.get("GITHUB_REPOSITORY") == bridge.REPOSITORY and
            env.get("GITHUB_REF") == "refs/heads/main" and
            env.get("GITHUB_EVENT_NAME") == "issue_comment" and
            env.get("GITHUB_RUN_ATTEMPT") == "1" and
            env.get("GITHUB_ACTOR") == AGENT_LOGIN and
            env.get("GITHUB_ACTOR_ID") == str(AGENT_ID),
            "Only an original authorized GitHub Issue comment on main is allowed")
    event_path = Path(env.get("GITHUB_EVENT_PATH", ""))
    require(event_path.is_file() and event_path.stat().st_size < 100_000,
            "Verified GitHub event JSON is required")
    event = json.loads(event_path.read_text(encoding="utf-8"))
    issue, comment = event.get("issue") or {}, event.get("comment") or {}
    require(event.get("action") == "created" and
            issue.get("number") == ISSUE_NUMBER and
            issue.get("title") == ISSUE_TITLE and
            not issue.get("pull_request") and
            (issue.get("user") or {}).get("id") == AGENT_ID and
            (comment.get("user") or {}).get("id") == AGENT_ID and
            comment.get("body") == COMMANDS[target],
            "Exact one-target PictureFix pre-schedule command is required")


def load_verified_original(token: str, target: str, record: dict,
                           draft_raw: bytes, *, get_receipt=None) -> dict:
    get_receipt = get_receipt or bridge.fetch_receipt
    raw_receipt = get_receipt(token, bridge.receipt_path(bridge.PICTUREFIX_DRAFT_NAMES[target]))
    require(isinstance(raw_receipt, dict) and
            isinstance(raw_receipt.get("content"), str),
            "Original PictureFix transfer receipt is missing")
    try:
        decoded = base64.b64decode("".join(raw_receipt["content"].split()), validate=True)
        receipt = json.loads(decoded)
    except (ValueError, TypeError, json.JSONDecodeError) as exc:
        raise PrescheduleBlocked("Original receipt is not valid") from exc
    image = record["media"]["images"][0]["url"]
    require(receipt.get("state") == "verified_unpublished_draft_with_image" and
            receipt.get("draft_file") == bridge.PICTUREFIX_DRAFT_NAMES[target] and
            receipt.get("target") == target and
            receipt.get("draft_sha256") == hashlib.sha256(draft_raw).hexdigest() and
            receipt.get("original_image_sha256") == record["image_sha256"] and
            receipt.get("buffer_asset_url") == image and
            receipt.get("buffer_status") == "draft" and
            receipt.get("buffer_due_at") is None and
            isinstance(receipt.get("channel_id"), str) and
            isinstance(receipt.get("buffer_post_id"), str) and
            re.fullmatch(r"[a-f0-9]{24}", receipt["buffer_post_id"]),
            "Original verified draft receipt no longer matches approved PF-01")
    return receipt


def verify_post(post: object, target: str, record: dict, receipt: dict,
                *, due_at: str | None) -> None:
    image = record["media"]["images"][0]["url"]
    require(isinstance(post, dict) and
            post.get("id") == receipt["buffer_post_id"] and
            post.get("channelId") == receipt["channel_id"] and
            str(post.get("channelService", "")).lower() == target and
            post.get("status") == "draft" and
            (post.get("dueAt") is None if due_at is None else
             same_instant(post.get("dueAt"), due_at)) and
            post.get("text") == record["text"],
            "Existing PF-01 post, channel, text, status or dueAt differs")
    assets = post.get("assets")
    require(isinstance(assets, list) and len(assets) == 1 and
            isinstance(assets[0], dict) and assets[0].get("type") == "image" and
            assets[0].get("source") == image,
            "The original verified PF-01 image must remain attached")
    if due_at is not None:
        require(post.get("shareMode") == "customScheduled" and
                post.get("schedulingType") == "automatic",
                "A pre-scheduled draft must have the exact customScheduled mode")


def live_preschedule(target: str, *, env: dict[str, str] | None = None,
                     query=None, get_receipt=None, put_receipt=None,
                     now: datetime | None = None) -> None:
    env = dict(os.environ if env is None else env)
    require(target in TIMES, "Unknown PF-01 target")
    verify_event(target, env)
    require("createPost" not in EDIT and "shareNow" not in EDIT and
            "saveToDraft: true" in EDIT and "mode: customScheduled" in EDIT,
            "Mutation must only edit an existing unpublished draft")
    planned = datetime.fromisoformat(TIMES[target].replace("Z", "+00:00"))
    clock = now or datetime.now(timezone.utc)
    require(planned > clock + timedelta(minutes=30),
            "Pre-scheduled time is too near or already in the past")
    github_key, buffer_key = env.get("GITHUB_TOKEN", ""), env.get("BUFFER_API_KEY", "")
    require(bool(github_key and buffer_key) and env.get("BUFFER_BRAND") == "picturefix",
            "Dedicated PictureFix Buffer and GitHub credentials are required")
    buffer_key = bridge.normalize_picturefix_api_key(buffer_key)
    query = query or bridge.buffer_graphql
    get_receipt = get_receipt or bridge.fetch_receipt
    put_receipt = put_receipt or bridge.put_receipt

    path = bridge.PICTUREFIX_DRAFT_NAMES[target]
    _, _, raw = bridge.read_draft(path)
    record = json.loads(raw)
    require(record.get("format_version") == 3 and record.get("brand") == "picturefix" and
            record.get("target") == target, "Unapproved or mismatched PictureFix file")
    source = load_verified_original(github_key, target, record, raw, get_receipt=get_receipt)
    channels = bridge.discover_picturefix_channels(buffer_key)
    require(source["channel_id"] == channels[target], "PictureFix channel verification failed")
    post_id = source["buffer_post_id"]

    original = query(buffer_key, READ, {"id": post_id}).get("post")
    verify_post(original, target, record, source, due_at=None)
    receipt_path = RECEIPTS[target]
    require(get_receipt(github_key, receipt_path) is None,
            "An existing pre-schedule receipt forbids a repeat mutation")

    pending = {
        "state": "pending_manual_reconciliation_on_failure",
        "draft_file": path,
        "target": target,
        "buffer_post_id": post_id,
        "channel_id": source["channel_id"],
        "planned_due_at_utc": TIMES[target],
        "original_image_sha256": record["image_sha256"],
        "github_run_id": env.get("GITHUB_RUN_ID", "unknown"),
    }
    sha = put_receipt(github_key, receipt_path, pending,
                      "picturefix: reserve original PF-01 draft pre-schedule")
    # No automatic retry after this point, even after an API/network error.
    result = query(buffer_key, EDIT, {"id": post_id, "dueAt": TIMES[target]})
    mutation = result.get("editPost") if isinstance(result, dict) else None
    returned = mutation.get("post") if isinstance(mutation, dict) else None
    require(isinstance(returned, dict) and returned.get("id") == post_id and
            returned.get("status") == "draft" and
            returned.get("channelId") == source["channel_id"] and
            same_instant(returned.get("dueAt"), TIMES[target]),
            "Buffer did not confirm unchanged draft with exact dueAt; stop for manual review")
    verified = query(buffer_key, READ, {"id": post_id}).get("post")
    verify_post(verified, target, record, source, due_at=TIMES[target])
    pending.update({
        "state": "verified_existing_prescheduled_unpublished_draft_with_image",
        "buffer_status": "draft",
        "buffer_due_at": TIMES[target],
        "buffer_asset_url": record["media"]["images"][0]["url"],
        "verified_at_utc": datetime.now(timezone.utc).isoformat(),
    })
    put_receipt(github_key, receipt_path, pending,
                "picturefix: verify existing PF-01 draft scheduled for approval", sha=sha)
    print(f"PICTUREFIX_PF01_PRESCHEDULE_PASS target={target} post_id={post_id} "
          f"dueAt={TIMES[target]} status=draft image=preserved no queue/publish", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", choices=sorted(TIMES), required=True)
    parser.add_argument("--send", action="store_true")
    args = parser.parse_args()
    if not args.send:
        parser.error("No implicit Buffer mutation: --send required")
    try:
        live_preschedule(args.target)
    except (PrescheduleBlocked, RuntimeError, ValueError, OSError, json.JSONDecodeError) as exc:
        print("PICTUREFIX_PF01_PRESCHEDULE_BLOCKED", type(exc).__name__,
              str(exc)[:180], file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
