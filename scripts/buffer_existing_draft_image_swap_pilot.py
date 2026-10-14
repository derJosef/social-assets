#!/usr/bin/env python3
"""One preapproved LinkedIn draft: two-phase snapshot and image-only edit.

This is NOT the autonomous campaign orchestrator. No createPost, queue,
schedule, publication or retry. Never run an edit without an independently
archived complete snapshot of the current Buffer post.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

if __package__:
    from .buffer_draft import buffer_graphql
else:
    from buffer_draft import buffer_graphql

POST_ID = "6ac8961e7d9f9f33012bc9cd"
CHANNEL_ID = "6aac167eea19ca0bde6ada5b"
SOURCE_PREFIX = "https://raw.githubusercontent.com/derJosef/social-assets/"
PINNED_RE = re.compile(
    r"https://raw\.githubusercontent\.com/derJosef/social-assets/"
    r"([0-9a-f]{40})/media/images/([a-z0-9][a-z0-9_.-]{1,125})\.png\Z"
)
SHA_RE = re.compile(r"[0-9a-f]{64}\Z")
GET_POST = """
query SnapshotPilotPost($id: PostId!) {
  post(input: {id: $id}) {
    id channelId channelService status dueAt text createdAt
    assets { type source }
  }
}
"""
# Asset-only: all other fields omitted, not even saveToDraft or mode.
EDIT_POST = """
mutation ReplacePilotImageOnly($id: PostId!, $assets: [AssetInput!]) {
  editPost(input: {id: $id, assets: $assets}) {
    __typename
    ... on PostActionSuccess {
      post { id channelId channelService status dueAt text createdAt
             assets { type source } }
    }
    ... on MutationError { message }
  }
}
"""


class PilotBlocked(RuntimeError):
    pass


def _canonical(x: object) -> bytes:
    return json.dumps(x, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def validate_post(post: object) -> dict:
    if not isinstance(post, dict) or post.get("id") != POST_ID:
        raise PilotBlocked("Post-ID mismatch")
    if post.get("channelId") != CHANNEL_ID or str(post.get("channelService", "")).lower() != "linkedin":
        raise PilotBlocked("Wrong Buffer channel")
    if post.get("status") != "draft" or post.get("dueAt") is not None:
        raise PilotBlocked("Only an unscheduled, non-approved draft may be edited")
    if not isinstance(post.get("text"), str) or len(post["text"]) < 100:
        raise PilotBlocked("Current text missing or suspicious")
    if not isinstance(post.get("createdAt"), str) or not post["createdAt"]:
        raise PilotBlocked("Creation timestamp missing")
    assets = post.get("assets")
    if not isinstance(assets, list) or len(assets) != 1:
        raise PilotBlocked("Expected exactly one original image asset")
    if str(assets[0].get("type", "")).lower() != "image":
        raise PilotBlocked("Current media is not an image")
    if not isinstance(assets[0].get("source"), str) or not assets[0]["source"].startswith("https://"):
        raise PilotBlocked("Current image source missing")
    return post


def get_post(*, get=buffer_graphql, token: str) -> dict:
    return validate_post(get(token, GET_POST, {"id": POST_ID}).get("post"))


def save_snapshot(post: dict, destination: Path, now: datetime | None = None) -> dict:
    post = validate_post(post)
    now = now or datetime.now(timezone.utc)
    record = {
        "kind": "private_before_image_swap",
        "post_id": POST_ID,
        "created_at": now.isoformat(timespec="seconds"),
        "sha256": hashlib.sha256(_canonical(post)).hexdigest(),
        "post": post,
    }
    if destination.exists():
        raise PilotBlocked("Never overwrite the existing original snapshot")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return record


def load_snapshot(path: Path, now: datetime | None = None) -> dict:
    if not path.is_file():
        raise PilotBlocked("Archived snapshot not provided")
    record = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(record, dict) or set(record) != {"kind", "post_id", "created_at", "sha256", "post"}:
        raise PilotBlocked("Snapshot corrupted or wrong schema")
    if record["kind"] != "private_before_image_swap" or record["post_id"] != POST_ID:
        raise PilotBlocked("Snapshot from wrong pilot")
    validate_post(record["post"])
    if hashlib.sha256(_canonical(record["post"])).hexdigest() != record["sha256"]:
        raise PilotBlocked("Snapshot fingerprint mismatch")
    now = now or datetime.now(timezone.utc)
    created = datetime.fromisoformat(record["created_at"])
    if created.tzinfo is None or not 0 <= (now - created).total_seconds() <= 1200:
        raise PilotBlocked("Snapshot stale; obtain fresh read-only state")
    return record


def _url_check(url: str, sha: str) -> None:
    if not isinstance(url, str) or not PINNED_RE.fullmatch(url):
        raise PilotBlocked("Image must be a commit-pinned public PNG in the canonical repo")
    if not isinstance(sha, str) or not SHA_RE.fullmatch(sha):
        raise PilotBlocked("Invalid PNG SHA256")


def validate_image(url: str, sha: str, *, download=None) -> None:
    _url_check(url, sha)
    if download is None:
        def download(u):
            request = urllib.request.Request(u, headers={"User-Agent": "social-assets-image-swap-pilot/1"})
            with urllib.request.urlopen(request, timeout=20) as resp:
                return resp.read(12 * 1024 * 1024 + 1)
    raw = download(url)
    if not isinstance(raw, bytes) or len(raw) > 12 * 1024 * 1024 or len(raw) < 100:
        raise PilotBlocked("Image missing or oversized")
    if hashlib.sha256(raw).hexdigest() != sha:
        raise PilotBlocked("Image bytes differ from approved SHA256")
    if raw[:8] != b"\x89PNG\r\n\x1a\n" or raw[12:16] != b"IHDR":
        raise PilotBlocked("Not a PNG")
    width = int.from_bytes(raw[16:20], "big")
    height = int.from_bytes(raw[20:24], "big")
    if (width, height) != (1080, 1350):
        raise PilotBlocked("Required 1080x1350 branded PNG")


def verify_same_state(actual: dict, before: dict) -> None:
    validate_post(actual)
    if _canonical(actual) != _canonical(before):
        raise PilotBlocked("Buffer post changed after snapshot; no edit allowed")


def _check_after(after: dict, before: dict) -> None:
    validate_post(after)
    for key in ("id", "channelId", "channelService", "status", "dueAt", "text", "createdAt"):
        if after.get(key) != before.get(key):
            raise PilotBlocked("Unexpected mutation of protected post field: " + key)
    if after["assets"] == before["assets"]:
        raise PilotBlocked("Media attachment unchanged; edit not independently verified")
    if len(after["assets"]) != 1 or str(after["assets"][0].get("type", "")).lower() != "image":
        raise PilotBlocked("New Buffer media missing")


def edit_once(snapshot: dict, url: str, sha: str, *, get=buffer_graphql,
              download=None, token: str) -> dict:
    before = snapshot["post"]
    _url_check(url, sha)
    validate_image(url, sha, download=download)
    current = get_post(get=get, token=token)
    verify_same_state(current, before)
    # Only ONE mutation; never retry on ambiguous remote result.
    response = get(token, EDIT_POST, {
        "id": POST_ID,
        "assets": [{"image": {"url": url}}],
    }).get("editPost")
    if not isinstance(response, dict) or response.get("__typename") != "PostActionSuccess":
        raise PilotBlocked("Buffer image edit failed or unknown response, no retry")
    result = response.get("post")
    if not isinstance(result, dict):
        raise PilotBlocked("Buffer did not return changed post, no retry")
    # Fresh independent readback from Buffer after the write.
    after = get_post(get=get, token=token)
    _check_after(after, before)
    return {
        "status": "PASS", "post_id": POST_ID,
        "unchanged_text": True, "unchanged_status": True,
        "unchanged_due_at": True, "changed_asset_count": len(after["assets"]),
        "old_asset_url": before["assets"][0]["source"],
        "new_asset_url": after["assets"][0]["source"],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=("snapshot", "edit"), required=True)
    parser.add_argument("--snapshot", required=True)
    parser.add_argument("--image-url")
    parser.add_argument("--image-sha256")
    args = parser.parse_args()
    token = os.environ.get("BUFFER_API_KEY")
    if os.environ.get("GITHUB_ACTIONS") != "true" or not token:
        raise PilotBlocked("Only authorized GitHub Actions can access Buffer")
    path = Path(args.snapshot)
    try:
        if args.phase == "snapshot":
            record = save_snapshot(get_post(token=token), path)
            print("PILOT_SNAPSHOT_PASS", POST_ID, record["sha256"])
        else:
            record = load_snapshot(path)
            result = edit_once(record, args.image_url, args.image_sha256, token=token)
            # No confidential text/source urls in public CI log.
            print("PILOT_IMAGE_EDIT_PASS", result["post_id"],
                  "draft status/text/date unchanged; one image attached")
        return 0
    except Exception as exc:
        print("PILOT_BLOCKED", type(exc).__name__, str(exc)[:200], file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
