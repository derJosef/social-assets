#!/usr/bin/env python3
"""One-time PictureFix PF-03 dated DRAFT sender, using the existing Buffer API bridge.

Intentionally separate from AI Agent Builder's automatic-campaign authority
and PF-01's completed single-shot workflow. Never queues or publishes.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sys
from zoneinfo import ZoneInfo

from scripts import buffer_draft as bridge


AGENT_LOGIN = "derJosef-agents"
AGENT_ID = 350701981
ISSUE_NUMBER = 64
ISSUE_TITLE = "PICTUREFIX BUFFER DRAFT CONTROL"
CAMPAIGN_ID = "PF-03"
MEDIA_COMMIT = "15554013fc2e4b188c26b478b4e7b596684eecb8"
LOGO_BLOB = "0cd926e6631209dd4e5c8029dfb72c29bbf89ea8"
ROOT = Path(__file__).resolve().parents[2]
SOURCE = "https://raw.githubusercontent.com/derJosef/social-assets/" + MEDIA_COMMIT + "/media/images/"

SPEC = {
    "facebook": {
        "file": "PictureFix_PF03_Facebook_Instagram_1080x1350.png",
        "image_sha256": "9e2a4e8340c155d568a8cd3d39f86f320651d83473db8421e45f6c2b62cc37bd",
        "due_at": "2026-12-01T11:00:00Z",
        "local": "2026-12-01T12:00:00+01:00",
    },
    "instagram": {
        "file": "PictureFix_PF03_Facebook_Instagram_1080x1350.png",
        "image_sha256": "9e2a4e8340c155d568a8cd3d39f86f320651d83473db8421e45f6c2b62cc37bd",
        "due_at": "2026-12-01T17:00:00Z",
        "local": "2026-12-01T18:00:00+01:00",
    },
    "pinterest": {
        "file": "PictureFix_PF03_Pinterest_1000x1500.png",
        "image_sha256": "0e008d198a3eeccf593333ffd600c586155f18bfa4cf1c63560300022656033c",
        "due_at": "2026-12-03T09:00:00Z",
        "local": "2026-12-03T10:00:00+01:00",
    },
}

COMMANDS = {target: f"PF03_{target.upper()}_DATED_DRAFT_ONLY" for target in SPEC}
READ = """
query VerifyPF03DatedDraft($id: PostId!) {
  post(input: { id: $id }) {
    id channelId channelService status dueAt text shareMode schedulingType
    assets { type source }
  }
}
"""


class PF03Blocked(RuntimeError):
    """Fail closed on unclear authority, provenance, media or Buffer state."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise PF03Blocked(message)


def parse_utc(value: str) -> datetime:
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise PF03Blocked("Invalid PF-03 UTC time") from exc
    require(result.tzinfo is not None, "PF-03 time must have a time zone")
    return result.astimezone(timezone.utc)


def verify_event(target: str, env: dict[str, str]) -> None:
    require(target in SPEC, "Unknown PF-03 target")
    require(env.get("GITHUB_REPOSITORY") == bridge.REPOSITORY and
            env.get("GITHUB_REF") == "refs/heads/main" and
            env.get("GITHUB_EVENT_NAME") == "issue_comment" and
            env.get("GITHUB_RUN_ATTEMPT") == "1" and
            env.get("GITHUB_ACTOR") == AGENT_LOGIN and
            env.get("GITHUB_ACTOR_ID") == str(AGENT_ID),
            "Only the original authorized GitHub comment on main is allowed")
    event_path = Path(env.get("GITHUB_EVENT_PATH") or "/nonexistent-github-event")
    require(event_path.is_file() and event_path.stat().st_size < 100_000,
            "A real signed-in GitHub event is required")
    event = json.loads(event_path.read_text(encoding="utf-8"))
    issue, comment = event.get("issue") or {}, event.get("comment") or {}
    require(event.get("action") == "created" and
            issue.get("number") == ISSUE_NUMBER and
            issue.get("title") == ISSUE_TITLE and
            not issue.get("pull_request") and
            (issue.get("user") or {}).get("id") == AGENT_ID and
            (comment.get("user") or {}).get("id") == AGENT_ID and
            comment.get("body") == COMMANDS[target],
            "Only one exact authorized PF-03 command is accepted")


def read_pf03(target: str, *, now: datetime | None = None) -> tuple[str, dict, bytes, list[dict]]:
    require(target in SPEC, "Unknown PF-03 target")
    path = f"drafts/picturefix-pf03-{target}.json"
    file = ROOT / path
    require(file.is_file() and file.stat().st_size < 100_000,
            "Missing or oversized immutable PF-03 draft")
    raw = file.read_bytes()
    record = json.loads(raw.decode("utf-8"))
    expected = {"format_version", "campaign_id", "brand", "target", "text", "media",
                "image_sha256", "logo_git_blob_sha1", "due_at_local", "due_at_utc"}
    if target == "pinterest":
        expected |= {"pinterest_title", "pinterest_url"}
    require(isinstance(record, dict) and set(record) == expected and
            record.get("format_version") == 3 and
            record.get("campaign_id") == CAMPAIGN_ID and
            record.get("brand") == "picturefix" and record.get("target") == target and
            record.get("logo_git_blob_sha1") == LOGO_BLOB,
            "PF-03 brand, provenance, path or field allowlist mismatch")
    spec = SPEC[target]
    require(record.get("image_sha256") == spec["image_sha256"] and
            record.get("due_at_utc") == spec["due_at"] and
            record.get("due_at_local") == spec["local"],
            "PF-03 media hash or scheduled time was edited")
    due = parse_utc(spec["due_at"])
    local = datetime.fromisoformat(spec["local"])
    require(local.astimezone(ZoneInfo("Europe/Berlin")) == local and
            local.astimezone(timezone.utc) == due,
            "PF-03 Berlin and UTC times disagree")
    clock = now or datetime.now(timezone.utc)
    require(clock.tzinfo is not None and due > clock.astimezone(timezone.utc) + timedelta(minutes=30),
            "PF-03 target time has expired or is too near")
    text = record.get("text")
    require(isinstance(text, str) and 40 <= len(text) <= 2200 and
            "KI-generierte" in text and ("Restaurierungs" in text or "Restaurierung" in text) and
            "kein tatsächliches restaurierungsergebnis" in text.lower(),
            "PF-03 disclosure, non-affiliation or copy failed")
    if target == "pinterest":
        require(isinstance(record["pinterest_title"], str) and
                10 <= len(record["pinterest_title"]) <= 100 and
                record["pinterest_url"] == "https://picturefix.de",
                "Pinterest title or site link not approved")
    media = record.get("media")
    require(isinstance(media, dict) and set(media) == {"type", "images"} and
            media.get("type") == "images" and
            isinstance(media.get("images"), list) and len(media["images"]) == 1,
            "PF-03 requires one attached real image")
    img = media["images"][0]
    require(isinstance(img, dict) and set(img) == {"url", "alt_text"} and
            img.get("url") == SOURCE + spec["file"] and
            isinstance(img.get("alt_text"), str) and
            "KI-generierte" in img["alt_text"] and "kein restaurierungsergebnis" in img["alt_text"].lower(),
            "PF-03 exact image URI or alt-text disclosure failed")
    local_image = ROOT / "media" / "images" / spec["file"]
    require(local_image.is_file() and
            hashlib.sha256(local_image.read_bytes()).hexdigest() == spec["image_sha256"],
            "Local PF-03 PNG differs from independently verified artwork")
    assets = bridge.parse_assets(raw)  # Existing Buffer GraphQL AssetInput conversion.
    require(len(assets) == 1 and assets[0]["image"]["url"] == img["url"],
            "Invalid image payload")
    return path, record, raw, assets


def verify_post(post: object, record: dict, channel_id: str, post_id: str) -> None:
    require(isinstance(post, dict) and post.get("id") == post_id and
            post.get("channelId") == channel_id and
            str(post.get("channelService", "")).lower() == record["target"] and
            post.get("status") == "draft" and post.get("text") == record["text"] and
            parse_utc(str(post.get("dueAt", ""))) == parse_utc(record["due_at_utc"]) and
            post.get("shareMode") == "customScheduled" and
            post.get("schedulingType") == "automatic",
            "Buffer did not independently confirm the exact unpublished, dated PF-03 draft")
    media = post.get("assets")
    require(isinstance(media, list) and len(media) == 1 and
            isinstance(media[0], dict) and media[0].get("type") == "image" and
            media[0].get("source") == record["media"]["images"][0]["url"],
            "Buffer PF-03 image source does not match verified PNG")


def send(target: str, *, env: dict[str, str] | None = None, query=None,
         get_receipt=None, put_receipt=None, now: datetime | None = None) -> None:
    env = dict(os.environ if env is None else env)
    verify_event(target, env)
    require(env.get("BUFFER_BRAND") == "picturefix" and
            bool(env.get("BUFFER_API_KEY")) and bool(env.get("GITHUB_TOKEN")),
            "Dedicated PictureFix and GitHub credentials required")
    require("saveToDraft: true" in bridge.CREATE_DATED_DRAFT and
            "mode: customScheduled" in bridge.CREATE_DATED_DRAFT and
            "shareNow" not in bridge.CREATE_DATED_DRAFT,
            "Only a custom-dated, non-publishing Buffer mutation is allowed")
    path, record, raw, assets = read_pf03(target, now=now)
    buffer_token = bridge.normalize_picturefix_api_key(env["BUFFER_API_KEY"])
    github_token = env["GITHUB_TOKEN"]
    query = query or bridge.buffer_graphql
    get_receipt = get_receipt or bridge.fetch_receipt
    put_receipt = put_receipt or bridge.put_receipt
    channel_id = bridge.discover_picturefix_channels(buffer_token)[target]
    board_id = bridge.discover_picturefix_board(buffer_token, channel_id) if target == "pinterest" else ""
    bridge.verify_media_access(assets)
    bridge.verify_picturefix_image_bytes(record, assets)

    receipt = bridge.receipt_path(path)
    require(get_receipt(github_token, receipt) is None,
            "PF-03 already has a one-shot receipt; no duplicate createPost")
    pending = {
        "state": "pending_manual_reconciliation_on_failure",
        "campaign": CAMPAIGN_ID, "draft_file": path, "target": target,
        "draft_sha256": hashlib.sha256(raw).hexdigest(),
        "original_image_sha256": record["image_sha256"],
        "planned_due_at_utc": record["due_at_utc"],
        "channel_id": channel_id,
        "github_run_id": env.get("GITHUB_RUN_ID", "unknown"),
    }
    receipt_sha = put_receipt(github_token, receipt, pending,
                              f"picturefix PF-03 reserve one dated draft {target}")
    variables = {
        "text": record["text"], "channelId": channel_id, "assets": assets,
        "dueAt": record["due_at_utc"],
        "metadata": bridge.platform_metadata(
            target, pinterest_board_id=board_id,
            pinterest_title=record.get("pinterest_title", ""),
            pinterest_url=record.get("pinterest_url", ""),
        ),
    }
    result = query(buffer_token, bridge.CREATE_DATED_DRAFT, variables)
    action = result.get("createPost") if isinstance(result, dict) else None
    post = action.get("post") if isinstance(action, dict) else None
    require(isinstance(post, dict) and isinstance(post.get("id"), str) and
            re.fullmatch(r"[a-f0-9]{24}", post["id"]),
            "Unclear Buffer createPost response: pending receipt, no automatic retry")
    post_id = post["id"]
    pending.update({"state": "created_requires_independent_check", "buffer_post_id": post_id})
    receipt_sha = put_receipt(github_token, receipt, pending,
                              f"picturefix PF-03 capture Buffer ID {target}", sha=receipt_sha)
    require(post.get("status") == "draft" and post.get("channelId") == channel_id and
            parse_utc(str(post.get("dueAt", ""))) == parse_utc(record["due_at_utc"]),
            "Buffer creation response is not a dated draft; stop without retry")
    independently_read = query(buffer_token, READ, {"id": post_id}).get("post")
    verify_post(independently_read, record, channel_id, post_id)
    pending.update({
        "state": "verified_prescheduled_draft_not_queued_with_image",
        "buffer_status": "draft", "buffer_due_at": record["due_at_utc"],
        "buffer_post_id": post_id,
        "buffer_asset_url": record["media"]["images"][0]["url"],
        "verified_at_utc": datetime.now(timezone.utc).isoformat(),
    })
    put_receipt(github_token, receipt, pending,
                f"picturefix PF-03 verified dated draft {target}", sha=receipt_sha)
    print(f"PF03_DATED_DRAFT_PASS target={target} post_id={post_id} "
          f"dueAt={record['due_at_utc']} status=draft image=verified no queue/publish", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", choices=sorted(SPEC), required=True)
    parser.add_argument("--send", action="store_true")
    args = parser.parse_args()
    if not args.send:
        parser.error("Explicit --send required, no implicit Buffer mutation")
    try:
        send(args.target)
    except (PF03Blocked, RuntimeError, ValueError, OSError, json.JSONDecodeError) as exc:
        print("PF03_DATED_DRAFT_BLOCKED", type(exc).__name__, str(exc)[:180], file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
