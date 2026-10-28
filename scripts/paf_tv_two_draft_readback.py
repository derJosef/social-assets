#!/usr/bin/env python3
"""Read-only Buffer verification of exactly two owner-approved PAF-TV drafts.

Run only after the one-time createPost execution. Validate the immutable
GitHub receipt and query Buffer independently for ID, channel, text and draft
status. Never create/edit/publish/queue a post.
"""
from __future__ import annotations
import base64
import hashlib
import json
import os
from pathlib import Path
import sys
from buffer_draft import (
    REPOSITORY, ROOT, buffer_graphql, channel_preference,
    fetch_receipt, read_draft, receipt_path, resolve_channel,
)

DRAFTS = (
    "drafts/paf-tv-interview-clip01-facebook.json",
    "drafts/paf-tv-interview-clip01-instagram.json",
)

READ_POST = """
query PafTvReadDraft($id: PostId!) {
  post(input: {id: $id}) {
    id
    channelId
    status
    text
  }
}
"""

def require(ok: bool, message: str) -> None:
    if not ok:
        raise RuntimeError(message)

def decode_receipt(file: object) -> dict:
    require(isinstance(file, dict), "GitHub receipt is missing")
    encoded = file.get("content")
    require(isinstance(encoded, str) and len(encoded) < 30000, "Receipt is missing or too large")
    try:
        decoded = base64.b64decode(encoded, validate=False)
        document = json.loads(decoded.decode("utf-8"))
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("Cannot decode receipt") from exc
    require(isinstance(document, dict), "Receipt is not an object")
    return document

def verify_draft(draft_path: str, github_token: str, buffer_token: str,
                 cache: dict | None = None) -> str:
    require(draft_path in DRAFTS, "Not an approved PAF-TV draft file")
    canonical_path, text, raw = read_draft(draft_path)
    require(canonical_path == draft_path, "Wrong draft path")
    target = json.loads(raw.decode("utf-8"))["target"]
    require(target in ("facebook", "instagram"), "Unexpected Buffer target")
    stored = fetch_receipt(github_token, receipt_path(draft_path))
    receipt = decode_receipt(stored)
    require(receipt.get("state") == "draft_created", "Receipt does not confirm a draft")
    require(receipt.get("draft_file") == draft_path and receipt.get("target") == target,
            "Wrong receipt for this channel")
    require(receipt.get("draft_sha256") == hashlib.sha256(raw).hexdigest(),
            "Draft differs from verified GitHub receipt")
    post_id = receipt.get("buffer_post_id")
    require(isinstance(post_id, str) and 5 <= len(post_id) <= 100,
            "Buffer post ID missing")
    channel = resolve_channel(buffer_token, target, channel_preference(target),
                              channel_cache=cache)
    post = buffer_graphql(buffer_token, READ_POST, {"id":post_id}).get("post")
    require(isinstance(post, dict)
            and post.get("id") == post_id
            and post.get("channelId") == channel
            and str(post.get("status","")).lower() == "draft"
            and post.get("text") == text,
            "Independent Buffer readback did not verify unchanged draft")
    print(f"PAF_TV_BUFFER_DRAFT_READBACK_PASS {target} post_id={post_id} status=draft",flush=True)
    return post_id

def main():
    require(os.environ.get("GITHUB_REPOSITORY") == REPOSITORY and
            os.environ.get("GITHUB_REF") == "refs/heads/main",
            "Must run in social-assets/main")
    github_token = os.environ.get("GITHUB_TOKEN","")
    buffer_token = os.environ.get("BUFFER_API_KEY","")
    require(github_token and buffer_token,"Read-only credentials missing")
    cache = {}
    posts = [verify_draft(path, github_token, buffer_token,cache) for path in DRAFTS]
    require(len(set(posts)) == 2,"Duplicate post IDs detected")
    print("PAF_TV_TWO_INDEPENDENT_DRAFTS_VERIFIED_NO_SCHEDULE_NO_PUBLICATION",flush=True)

if __name__=="__main__":
    try:
        main()
    except (RuntimeError, ValueError) as exc:
        print("PAF_TV_DRAFT_READBACK_STOP "+str(exc),file=sys.stderr)
        raise SystemExit(1)
