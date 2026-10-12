#!/usr/bin/env python3
"""Read-only Buffer reconciliation and canonical review snapshot for ChatGPT.

There is no mutation, scheduling, retry or publishing action in this module.
Always trust the post read back from Buffer rather than the local draft alone.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

if __package__:
    from .buffer_draft import (
        buffer_graphql, fetch_receipt, receipt_path, planned_due_at, verified_dated_post,
    )
else:
    from buffer_draft import (
        buffer_graphql, fetch_receipt, receipt_path, planned_due_at, verified_dated_post,
    )

ROOT = Path(__file__).resolve().parents[1]
BERLIN = ZoneInfo("Europe/Berlin")
TARGETS = ("linkedin", "facebook", "instagram")
CAMPAIGN_RE = re.compile(r"20\d{2}-\d{2}-\d{2}-[a-z0-9]+(?:-[a-z0-9]+)*\Z")
POST_ID_RE = re.compile(r"[0-9a-f]{24}\Z")
IMAGE_COMMIT_RE = re.compile(r"[0-9a-f]{40}\Z")
BUFFER_DASHBOARD = "https://publish.buffer.com"
IMAGE_PREFIX = "https://raw.githubusercontent.com/derJosef/social-assets/"

# All fields are documented on Buffer's Post and Asset types. Buffer exposes
# no stable authenticated draft-editor permalink; NEVER fabricate one.
POST_QUERY = """
query InspectOrchestratedPost($id: PostId!) {
  post(input: { id: $id }) {
    id channelId channelService status dueAt text
    assets { type source }
  }
}
"""


def load_expected(campaign: str, target: str) -> tuple[str, str]:
    """Use only the immutable QA-prepared text and Git-commit-pinned artwork."""
    filename = ROOT / f"ready-for-buffer/auto-{campaign}-{target}.json"
    obj = json.loads(filename.read_text(encoding="utf-8"))
    if not isinstance(obj, dict) or obj.get("target") != target or obj.get("format_version") != 2:
        raise RuntimeError(f"Invalid prepared Buffer draft for {target}")
    text = obj.get("text")
    image = obj.get("media")
    images = image.get("images") if isinstance(image, dict) else None
    if (not isinstance(text, str) or not text.strip()
            or image.get("type") != "images" or not isinstance(images, list)
            or len(images) != 1 or not isinstance(images[0], dict)):
        raise RuntimeError(f"Prepared text or verified image missing for {target}")
    url = images[0].get("url")
    if not isinstance(url, str) or not url.startswith(IMAGE_PREFIX):
        raise RuntimeError(f"Prepared image not on canonical asset host for {target}")
    suffix = url[len(IMAGE_PREFIX):].split("/")
    if (len(suffix) != 3 or not IMAGE_COMMIT_RE.fullmatch(suffix[0])
            or suffix[1] != "media" or suffix[2] != "images"):
        # Canonical full path has four slash-separated parts below commit.
        suffix = url[len(IMAGE_PREFIX):].split("/")
    if (len(suffix) != 4 or not IMAGE_COMMIT_RE.fullmatch(suffix[0])
            or suffix[1] != "media" or suffix[2] != "images"
            or suffix[3] != f"{campaign}-branded.png"):
        raise RuntimeError(f"Prepared image not pinned to a Git commit for {target}")
    return text, url


def buffer_image_source(record: dict, target: str) -> str:
    assets = record.get("assets")
    if not isinstance(assets, list) or len(assets) != 1 or not isinstance(assets[0], dict):
        raise RuntimeError(f"Buffer image attachment missing or ambiguous: {target}")
    asset = assets[0]
    if str(asset.get("type", "")).lower() != "image":
        raise RuntimeError(f"Buffer media is not an image for {target}")
    source = asset.get("source")
    if not isinstance(source, str) or len(source) > 1600:
        raise RuntimeError(f"Buffer image URL missing for {target}")
    parsed = urllib.parse.urlsplit(source)
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username
            or parsed.password or parsed.port is not None
            or parsed.hostname in ("localhost",) or parsed.hostname.endswith(".local")):
        raise RuntimeError(f"Buffer media URL is not an allowed HTTPS resource: {target}")
    return source


def decode_receipt(receipt: object, target: str) -> dict:
    if not isinstance(receipt, dict) or not isinstance(receipt.get("content"), str):
        raise RuntimeError(f"Missing GitHub receipt for {target}")
    try:
        decoded = base64.b64decode(receipt["content"], validate=True)
        record = json.loads(decoded)
    except (ValueError, UnicodeError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Corrupt delivery receipt for {target}") from exc
    if not isinstance(record, dict):
        raise RuntimeError(f"Delivery receipt is not JSON object: {target}")
    return record


def local_time(utc_text: str) -> str:
    utc = datetime.fromisoformat(utc_text.replace("Z", "+00:00"))
    if utc.tzinfo is None or utc.utcoffset() != timezone.utc.utcoffset(utc):
        raise RuntimeError("Draft time is not UTC")
    return utc.astimezone(BERLIN).isoformat(timespec="seconds")


def verify(campaign: str) -> dict:
    if not CAMPAIGN_RE.fullmatch(campaign):
        raise ValueError("Ungültige Kampagnenkennung")
    token = os.environ.get("GITHUB_TOKEN", "")
    buffer_token = os.environ.get("BUFFER_API_KEY", "")
    if not token or not buffer_token:
        raise RuntimeError("Missing API credentials for independent Buffer verification")

    output: dict[str, dict] = {}
    used_ids, used_channels = set(), set()
    for target in TARGETS:
        draft_file = f"ready-for-buffer/auto-{campaign}-{target}.json"
        expected_due = planned_due_at(draft_file, target)
        if expected_due is None:
            raise RuntimeError(f"Missing planned date for {target}")
        prepared_text, prepared_image = load_expected(campaign, target)
        receipt = decode_receipt(fetch_receipt(token, receipt_path(draft_file)), target)
        if (receipt.get("state") != "verified_prescheduled_draft_not_queued"
                or receipt.get("draft_file") != draft_file
                or receipt.get("target") != target
                or receipt.get("due_at_utc") != expected_due):
            raise RuntimeError(f"Receipt not an independently verified dated draft: {target}")
        post_id, channel_id = receipt.get("buffer_post_id"), receipt.get("channel_id")
        if not isinstance(post_id, str) or not POST_ID_RE.fullmatch(post_id):
            raise RuntimeError(f"Buffer post ID missing for {target}")
        if not isinstance(channel_id, str) or not channel_id or len(channel_id) > 200:
            raise RuntimeError(f"Buffer channel ID missing for {target}")
        if post_id in used_ids or channel_id in used_channels:
            raise RuntimeError("Three separate Buffer posts and channels are required")
        used_ids.add(post_id)
        used_channels.add(channel_id)

        post = buffer_graphql(buffer_token, POST_QUERY, {"id": post_id}).get("post")
        if not verified_dated_post(post, post_id=post_id,
                                  channel_id=channel_id, due_at=expected_due):
            raise RuntimeError(f"Buffer status/date unclear or not draft for {target}")
        if not isinstance(post, dict) or str(post.get("channelService", "")).lower() != target:
            raise RuntimeError(f"Buffer post belongs to wrong service for {target}")
        if post.get("text") != prepared_text:
            raise RuntimeError(f"Buffer text differs from the prepared post for {target}")
        actual_image = buffer_image_source(post, target)

        output[target] = {
            "post_id": post_id, "channel_id": channel_id,
            "service": target, "status": "draft",
            "dueAt": expected_due, "scheduled_local": local_time(expected_due),
            "text": post["text"], "review_image_url": prepared_image,
            "buffer_asset_url": actual_image,
            "image_attached_in_buffer": True,
            "buffer_dashboard_url": BUFFER_DASHBOARD,
            "buffer_link_kind": "official_dashboard_not_direct_post",
            "buffer_direct_post_url": None,
            "editorial_approval": "pending_after_draft",
            "published": False,
        }
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--campaign", required=True)
    parser.add_argument("--report", required=True)
    args = parser.parse_args()
    try:
        found = verify(args.campaign)
        path = Path(args.report)
        info = json.loads(path.read_text(encoding="utf-8"))
        info["buffer_verification"] = {
            "status": "PASS", "checked_at": datetime.now(timezone.utc).isoformat(),
            "posts": found,
        }
        info["state"] = "buffer_drafts_verified"
        path.write_text(json.dumps(info, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        # Do not echo full posts or all media URLs to CI stdout.
        print("BUFFER_VERIFICATION_PASS 3/3 draft, dates, text, image present (no queue)")
    except Exception as err:
        print("BUFFER_VERIFICATION_BLOCKED", type(err).__name__, str(err)[:260], file=sys.stderr)
        sys.exit(1)
