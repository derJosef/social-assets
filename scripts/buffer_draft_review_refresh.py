#!/usr/bin/env python3
"""Read-only final-review refresh for Josefs edited Buffer drafts.

Never calls createPost/editPost, never enqueues or publishes. Uses the
immutable original verification receipt only for post identity; current
text, picture, status and dueAt always come from Buffer on demand.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

if __package__:
    from .orchestrator_verify_buffer import POST_QUERY, buffer_graphql, buffer_image_source
    from .social_weekly_review import TARGETS, validate
else:
    from orchestrator_verify_buffer import POST_QUERY, buffer_graphql, buffer_image_source
    from social_weekly_review import TARGETS, validate

BERLIN = ZoneInfo("Europe/Berlin")


class LiveReviewBlocked(RuntimeError):
    pass


def read_time(value: object) -> tuple[str | None, str | None]:
    if value is None:
        return None, None
    if not isinstance(value, str) or not value.endswith("Z"):
        raise LiveReviewBlocked("Draft date is not an ISO-8601 UTC value")
    try:
        date = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise LiveReviewBlocked("Invalid Buffer time") from exc
    if date.utcoffset() != timezone.utc.utcoffset(date):
        raise LiveReviewBlocked("Buffer date must be UTC")
    return value, date.astimezone(BERLIN).isoformat(timespec="seconds")


def refresh(original: dict, *, now: datetime | None = None) -> dict:
    campaign, old_posts = validate(original)
    key = os.environ.get("BUFFER_API_KEY")
    if not key:
        raise LiveReviewBlocked("Read-only Buffer access is not configured")
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise LiveReviewBlocked("Current time needs timezone")

    result = {"campaign": campaign, "state": "read_only_drafts_inspected",
              "checked_at": now.astimezone(timezone.utc).isoformat(),
              "no_queue_or_publish": True, "posts": {}}
    for channel in TARGETS:
        old = old_posts[channel]
        raw = buffer_graphql(key, POST_QUERY, {"id": old["post_id"]}).get("post")
        if not isinstance(raw, dict):
            raise LiveReviewBlocked(f"Buffer post missing for {channel}")
        if (raw.get("id") != old["post_id"]
                or raw.get("channelId") != old["channel_id"]
                or str(raw.get("channelService", "")).lower() != channel):
            raise LiveReviewBlocked(f"Buffer identity or channel changed for {channel}")
        if str(raw.get("status", "")).lower() != "draft":
            raise LiveReviewBlocked(f"Post is no longer an unpublished Buffer draft: {channel}")
        if not isinstance(raw.get("text"), str) or not raw["text"].strip():
            raise LiveReviewBlocked(f"Buffer draft text missing: {channel}")
        source = buffer_image_source(raw, channel)
        due, berlin = read_time(raw.get("dueAt"))
        future = False
        if due is not None:
            date = datetime.fromisoformat(due.replace("Z", "+00:00"))
            future = date > now.astimezone(timezone.utc)
        changes = [name for name, changed in (
            ("text", raw["text"] != old["text"]),
            ("media", source != old["buffer_asset_url"]),
            ("time", due != old["dueAt"]),
        ) if changed]
        result["posts"][channel] = {
            "post_id": old["post_id"], "channel_id": old["channel_id"],
            "status": "draft", "channelService": channel,
            "current_text": raw["text"], "current_image_url": source,
            "current_due_at": due, "current_local": berlin,
            "has_future_date": future, "changes_since_original": changes,
            "original_text_overwritten": False,
            "buffer_dashboard_url": old["buffer_dashboard_url"],
            "buffer_direct_post_url": None,
            "editable_live_buffer_copy_authoritative": True,
        }
    result["all_three_still_drafts"] = True
    result["all_three_future_dated"] = all(
        p["has_future_date"] for p in result["posts"].values()
    )
    result["any_manual_changes"] = any(
        p["changes_since_original"] for p in result["posts"].values()
    )
    result["editorial_approval_required"] = True
    result["publish_or_schedule_authorized"] = False
    # Caller may show changes to Josef but may NOT mutate/schedule Buffer.
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--verified-report", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    try:
        value = json.loads(Path(args.verified_report).read_text(encoding="utf-8"))
        checked = refresh(value)
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(checked, ensure_ascii=False, indent=2) + "\n",
                       encoding="utf-8")
        print("BUFFER_LIVE_REVIEW_READ_ONLY",
              "3/3 drafts; edits detected" if checked["any_manual_changes"]
              else "3/3 drafts; original copy unchanged",
              "future_dated=", checked["all_three_future_dated"])
        return 0
    except (LiveReviewBlocked, ValueError, RuntimeError, OSError, json.JSONDecodeError) as exc:
        print("BUFFER_LIVE_REVIEW_BLOCKED", type(exc).__name__, str(exc)[:220], file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
