#!/usr/bin/env python3
"""One-time deletion of only THREE superseded customer-mail Buffer drafts.

The three new drafts must already exist, be in the same channels, and have
identical LIVE post text before deleting a single old draft. No scheduling.
Exact operation only: authenticated GitHub Actions main with unique request.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import sys
from pathlib import Path

from scripts import buffer_draft as api

ROOT = Path(__file__).resolve().parents[1]
AUDIT = "cleanup-audit/2026-10-10-kundenmail-v2-image-replacement.json"
REQUEST = "cleanup-requests/2026-10-10-kundenmail-v2-replace-three-drafts.json"
IMAGE_PATH = "media/images/2026-10-10-kundenmail-pruefpunkt-portfolio-v2-logo-only.png"
IMAGE_SHA = "9103a36e4239a433244acaddab7d3f1af6308e5dac5e4238656ed60b70a95230"
IMAGE_URL = "https://raw.githubusercontent.com/derJosef/social-assets/main/" + IMAGE_PATH

# These are historical verified campaign IDs. NO wildcard/lookup-based deletion.
CASES = (
    ("linkedin", "6ac9e964c4de2d2b121be215", "6aca9d9fd9cab260a7d7b34c", "6aac167eea19ca0bde6ada5b"),
    ("facebook", "6ac9e967b07d37ac9764aac6", "6aca9d99bba9419ccb148eba", "6ac781e46a5c39ccb64fe01c"),
    ("instagram", "6ac9e96ac4de2d2b121be2e2", "6aca9d9cf91f772d45a67ff7", "6ac79a686a5c39ccb650f94b"),
)

GET_POST = """
query VerifyImageReplacementDraft($id: PostId!) {
  post(input: {id:$id}) { id text status dueAt channelId }
}
"""
DELETE_POST = """
mutation DeleteExactSupersededDraft($id: PostId!) {
  deletePost(input: {id:$id}) {
    __typename
    ... on DeletePostSuccess { id }
    ... on MutationError { message }
  }
}
"""


def read_receipt(token: str, file: str) -> dict:
    response = api.fetch_receipt(token, api.receipt_path(file))
    if not isinstance(response, dict) or not isinstance(response.get("content"), str):
        raise RuntimeError(f"GitHub draft receipt missing: {file}")
    try:
        return json.loads(base64.b64decode(response["content"].replace("\n", ""), validate=True))
    except (ValueError, TypeError) as e:
        raise RuntimeError("GitHub receipt not readable") from e


def read_post(token: str, post_id: str, text: str, channel: str) -> dict:
    result = api.buffer_graphql(token, GET_POST, {"id": post_id}).get("post")
    if not isinstance(result, dict):
        raise RuntimeError(f"Buffer post missing: {post_id}")
    if result.get("id") != post_id or result.get("status") != "draft":
        raise RuntimeError(f"Incorrect Buffer post identity/state: {post_id}")
    if result.get("dueAt") is not None:
        raise RuntimeError(f"Post has scheduling metadata: {post_id}")
    if result.get("channelId") != channel:
        raise RuntimeError(f"Buffer channel mismatch: {post_id}")
    if result.get("text") != text:
        raise RuntimeError(f"Buffer text changed or does not match original: {post_id}")
    return result


def ensure_safe_input(github_token: str) -> dict:
    if os.environ.get("GITHUB_REPOSITORY") != "derJosef/social-assets":
        raise RuntimeError("Repository mismatch")
    if os.environ.get("GITHUB_REF") != "refs/heads/main":
        raise RuntimeError("Only social-assets/main allowed")
    expected = {
        "operation": "delete_only_three_superseded_kundenmail_drafts",
        "campaign": "2026-10-10-kundenmail-kein-befehl-005",
        "date": "2026-10-10",
        "old_ids": [o for _, o, _, _ in CASES],
        "new_ids": [n for _, _, n, _ in CASES],
        "image_sha256": IMAGE_SHA,
    }
    request = json.loads((ROOT / REQUEST).read_text("utf-8"))
    if request != expected:
        raise RuntimeError("One-time request does not exactly match allowlist")
    if api.fetch_receipt(github_token, AUDIT) is not None:
        raise RuntimeError("Audit file already exists: NEVER repeat deletion")
    if hashlib.sha256((ROOT / IMAGE_PATH).read_bytes()).hexdigest() != IMAGE_SHA:
        raise RuntimeError("Verified final image has changed")
    if len(CASES) != 3 or len({o for _, o, _, _ in CASES}) != 3:
        raise RuntimeError("Expected exactly three unique historical IDs")
    return expected


def check_case(buffer_token: str, github_token: str, target: str,
               old_id: str, new_id: str, channel: str) -> dict:
    old_file = f"ready-for-buffer/auto-2026-10-10-kundenmail-kein-befehl-005-{target}.json"
    new_file = f"ready-for-buffer/replace-2026-10-10-kundenmail-kein-befehl-005-v2-{target}.json"
    old_bytes = (ROOT / old_file).read_bytes()
    new_bytes = (ROOT / new_file).read_bytes()
    old_draft, new_draft = json.loads(old_bytes), json.loads(new_bytes)
    if old_draft.get("text") != new_draft.get("text"):
        raise RuntimeError(f"Texts differ in GitHub for {target}")
    if old_draft.get("target") != new_draft.get("target") or old_draft.get("target") != target:
        raise RuntimeError(f"Wrong target {target}")
    if new_draft.get("media", {}).get("type") != "images":
        raise RuntimeError(f"Not image post {target}")
    images = new_draft.get("media", {}).get("images")
    if not isinstance(images, list) or len(images) != 1 or images[0].get("url") != IMAGE_URL:
        raise RuntimeError(f"Wrong final image {target}")
    for file, file_bytes, required_id in (
        (old_file, old_bytes, old_id), (new_file, new_bytes, new_id)
    ):
        receipt = read_receipt(github_token, file)
        if (receipt.get("state") != "draft_created"
            or receipt.get("buffer_post_id") != required_id
            or receipt.get("draft_file") != file
            or receipt.get("target") != target
            or receipt.get("draft_sha256") != hashlib.sha256(file_bytes).hexdigest()):
            raise RuntimeError(f"Receipt not identity-safe: {file}")
    text = old_draft["text"]
    read_post(buffer_token, old_id, text, channel)
    read_post(buffer_token, new_id, text, channel)
    return {
        "target": target, "old_id": old_id, "replacement_id": new_id,
        "buffer_channel_id": channel,
        "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "status_old_preflight": "draft", "status_new_preflight": "draft",
        "dueAt_old_preflight": None, "dueAt_new_preflight": None,
        "media_url_new": IMAGE_URL, "media_sha256": IMAGE_SHA,
        "deletion": "pending",
    }


def main() -> None:
    key = os.environ.get("BUFFER_API_KEY", "").strip()
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if not key or not token:
        raise RuntimeError("Missing API authorization")
    ensure_safe_input(token)
    # All six live Buffer posts checked BEFORE any mutation.
    checked = [check_case(key, token, *case) for case in CASES]
    print("PREDELETE_PASS: all six live drafts and six receipts checked; exact text, channels, no schedule")
    audit = {
        "date": "2026-10-10",
        "campaign": "2026-10-10-kundenmail-kein-befehl-005",
        "purpose": "Replace 3 old Buffer drafts by 3 verified image-only new drafts; preserve exact platform texts",
        "github_run_id": os.environ.get("GITHUB_RUN_ID"),
        "status": "reserved_before_first_deletion",
        "confirmed_deleted": 0,
        "items": checked,
    }
    audit_sha = api.put_receipt(token, AUDIT, audit, "audit(buffer): reserve verified 3-draft image replacement")
    for item in audit["items"]:
        old_id, new_id, channel, target = (
            item["old_id"], item["replacement_id"], item["buffer_channel_id"], item["target"]
        )
        text = json.loads((ROOT / f"ready-for-buffer/auto-2026-10-10-kundenmail-kein-befehl-005-{target}.json").read_text())["text"]
        # Just-in-time check: never delete an old draft if its new replacement changed/disappeared.
        read_post(key, old_id, text, channel)
        read_post(key, new_id, text, channel)
        reply = api.buffer_graphql(key, DELETE_POST, {"id": old_id}).get("deletePost")
        if not isinstance(reply, dict) or reply.get("id") != old_id:
            raise RuntimeError(f"Buffer did not confirm exact delete {old_id}: audit retained; manual review needed")
        item["deletion"] = "confirmed_by_buffer"
        audit["confirmed_deleted"] += 1
        audit["status"] = "in_progress" if audit["confirmed_deleted"] < 3 else "three_superseded_drafts_deleted"
        audit_sha = api.put_receipt(token, AUDIT, audit, f"audit(buffer): delete confirmed for {target} {old_id}", sha=audit_sha)
        print(f"DELETE_CONFIRMED: {target} old={old_id}, replacement={new_id}")
    print("COMPLETE: exactly three superseded Buffer drafts deleted; new drafts untouched, not scheduled or published")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("CLEANUP_BLOCKED", type(exc).__name__, str(exc)[:250], file=sys.stderr)
        raise
