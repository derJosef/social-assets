#!/usr/bin/env python3
"""One-time move of three existing Telekom–Mistral DRAFT dates to news day.

The mutation contains neither content, media, tags, metadata nor any queue or
publish operation. Buffer must confirm status=draft on every independent read.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

try:
    from scripts.buffer_draft import REPOSITORY, buffer_graphql, fetch_receipt, put_receipt
    from scripts.legacy_six_buffer_image_edit import POST_QUERY
    from scripts.aab_telekom_mistral_image_refresh import NEW_IMAGE_URL, same_instant
except ImportError:
    from buffer_draft import REPOSITORY, buffer_graphql, fetch_receipt, put_receipt
    from legacy_six_buffer_image_edit import POST_QUERY
    from aab_telekom_mistral_image_refresh import NEW_IMAGE_URL, same_instant


AGENT_ID = 350701981
TRIGGER_PR = 82
TRIGGER = "AAB_TELEKOM_MISTRAL_MOVE_THREE_EXISTING_DRAFT_DATES_TO_NEWS_DAY_20261120_ONCE"
BATCH = "delivery-receipts/2026-11-20-telekom-mistral-three-draft-dates-batch.json"
BERLIN = ZoneInfo("Europe/Berlin")
POSTS = {
    "facebook": {
        "id": "6afff0ab738ce4635f93ac57",
        "channel_id": "6ac781e46a5c39ccb64fe01c",
        "old": "2026-12-03T08:00:00Z", "new": "2026-11-20T12:00:00Z",
        "local": "2026-11-20T13:00:00+01:00",
    },
    "linkedin": {
        "id": "6afff0a57b0a126cebb56f34",
        "channel_id": "6aac167eea19ca0bde6ada5b",
        "old": "2026-12-09T15:00:00Z", "new": "2026-11-20T14:30:00Z",
        "local": "2026-11-20T15:30:00+01:00",
    },
    "instagram": {
        "id": "6afff0b14c1afd05defcc931",
        "channel_id": "6ac79a686a5c39ccb650f94b",
        "old": "2026-12-02T17:00:00Z", "new": "2026-11-20T17:00:00Z",
        "local": "2026-11-20T18:00:00+01:00",
    },
}

EDIT = """
mutation MoveExistingNewsDraftDate($id: PostId!, $dueAt: DateTime!) {
  editPost(input: {
    id: $id
    mode: customScheduled
    dueAt: $dueAt
    saveToDraft: true
  }) {
    __typename
    ... on PostActionSuccess { post { id channelId status dueAt } }
    ... on MutationError { message }
  }
}
"""


class Blocked(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise Blocked(message)


def utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    require(parsed.tzinfo is not None, "Zeitpunkt ohne Zeitzone")
    return parsed.astimezone(timezone.utc)


def contract(now: datetime | None = None) -> None:
    require(len(POSTS) == 3 and len({p["id"] for p in POSTS.values()}) == 3,
            "Nur genau drei bestehende Buffer-Post-IDs")
    require("createPost" not in EDIT and "shareNow" not in EDIT and
            "saveToDraft: true" in EDIT and "dueAt: $dueAt" in EDIT and
            "text:" not in EDIT and "assets:" not in EDIT and
            "metadata:" not in EDIT and "tagIds:" not in EDIT and
            "schedulingType:" not in EDIT,
            "Mutation darf keine Veröffentlichung oder Contentänderung ermöglichen")
    now = now or datetime.now(timezone.utc)
    for channel, post in POSTS.items():
        require(utc(post["new"]).astimezone(BERLIN).isoformat(timespec="seconds") == post["local"],
                f"MEZ-Konvertierung falsch: {channel}")
        require(utc(post["new"]) < utc(post["old"]) and
                utc(post["new"]) > now + timedelta(minutes=20),
                f"Frühester neuer Termin bereits zu nah oder vergangen: {channel}")


def validate_event(path: Path, env: dict) -> None:
    require(env.get("GITHUB_REPOSITORY") == REPOSITORY and
            env.get("GITHUB_REF") == "refs/heads/main" and
            env.get("GITHUB_EVENT_NAME") == "issue_comment" and
            env.get("GITHUB_RUN_ATTEMPT") == "1" and
            env.get("GITHUB_ACTOR") == "derJosef-agents" and
            env.get("GITHUB_ACTOR_ID") == str(AGENT_ID),
            "Nur erster Lauf der zugelassenen Agentenidentität auf main")
    require(path.is_file() and path.stat().st_size < 100_000,
            "GitHub-Ereignis fehlt oder ist zu groß")
    event = json.loads(path.read_text(encoding="utf-8"))
    issue, comment = event.get("issue") or {}, event.get("comment") or {}
    require(event.get("action") == "created" and
            issue.get("number") == TRIGGER_PR and issue.get("pull_request") and
            (issue.get("user") or {}).get("id") == AGENT_ID and
            (comment.get("user") or {}).get("id") == AGENT_ID and
            comment.get("body") == TRIGGER,
            "Genaue und einmalige Autorisierung fehlt")


def fingerprint(raw: dict) -> str:
    immutable = ("id", "channelId", "channelService", "status", "text",
                 "shareMode", "schedulingType", "tags", "assets", "metadata")
    stable = {k: raw.get(k) for k in immutable}
    return hashlib.sha256(json.dumps(stable, sort_keys=True,
                                     ensure_ascii=False).encode()).hexdigest()


def verify(raw: object, channel: str, *, after: bool = False) -> str:
    p = POSTS[channel]
    require(isinstance(raw, dict) and raw.get("id") == p["id"] and
            raw.get("channelId") == p["channel_id"] and
            str(raw.get("channelService", "")).lower() == channel,
            f"Falsche Buffer-Post/Kanal-Identität: {channel}")
    expected_time = p["new"] if after else p["old"]
    require(raw.get("status") == "draft" and
            same_instant(raw.get("dueAt"), expected_time) and
            raw.get("shareMode") == "customScheduled" and
            raw.get("schedulingType") == "automatic",
            f"Status/Entwurfszeit/Modus abgewichen: {channel}, "
            f"status={raw.get('status')!r}, dueAt={raw.get('dueAt')!r}")
    require(isinstance(raw.get("text"), str) and len(raw["text"].strip()) > 100,
            f"Beitragstext fehlt: {channel}")
    require(isinstance(raw.get("tags"), list) and
            all(isinstance(t, dict) and isinstance(t.get("id"), str)
                for t in raw["tags"]),
            f"Tags nicht eindeutig: {channel}")
    require(isinstance(raw.get("assets"), list) and
            len(raw["assets"]) == 1 and
            raw["assets"][0].get("type") == "image" and
            raw["assets"][0].get("source") == NEW_IMAGE_URL and
            raw["assets"][0].get("mimeType") == "image/png",
            f"Freigegebenes Cyan-T-Motiv nicht vorhanden: {channel}")
    return fingerprint(raw)


def receipt_path(channel: str) -> str:
    return f"delivery-receipts/2026-11-20-telekom-mistral-draft-date-{channel}.json"


def live_move(*, get=buffer_graphql, get_receipt=fetch_receipt,
              write_receipt=put_receipt, env: dict | None = None) -> None:
    env = dict(os.environ if env is None else env)
    require(bool(env.get("GITHUB_EVENT_PATH")), "GitHub-Ereignispfad fehlt")
    validate_event(Path(env["GITHUB_EVENT_PATH"]), env)
    key, token = env.get("BUFFER_API_KEY"), env.get("GITHUB_TOKEN")
    require(bool(key and token), "Buffer- bzw. GitHub-Verbindung fehlt")
    contract()
    before = {}
    for channel, post in POSTS.items():
        raw = get(key, POST_QUERY, {"id": post["id"]}).get("post")
        before[channel] = verify(raw, channel)
    require(get_receipt(token, BATCH) is None,
            "Bereits reservierter Gesamtvorgang: kein automatischer Retry")
    for channel in POSTS:
        require(get_receipt(token, receipt_path(channel)) is None,
                f"Bereits reserviert: {channel}")

    batch = {
        "campaign": "2026-11-20-telekom-mistral-news-date-correction",
        "run_id": env.get("GITHUB_RUN_ID"),
        "state": "pending_manual_reconciliation_on_failure",
        "post_ids": [p["id"] for p in POSTS.values()],
        "change_scope": "draft_due_at_only; never publish",
    }
    batch_sha = write_receipt(token, BATCH, batch, "reserve three existing draft date edits")
    for channel, p in POSTS.items():
        contract()
        raw = get(key, POST_QUERY, {"id": p["id"]}).get("post")
        require(verify(raw, channel) == before[channel],
                f"Inhalt geändert seit Vorprüfung: {channel}")
        item = {
            "channel": channel, "post_id": p["id"],
            "old_due_at_utc": p["old"], "new_due_at_utc": p["new"],
            "new_local_berlin": p["local"],
            "immutable_fingerprint": before[channel],
            "run_id": env.get("GITHUB_RUN_ID"),
            "state": "pending_manual_reconciliation_on_failure",
        }
        receipt = receipt_path(channel)
        sha = write_receipt(token, receipt, item, "reserve existing draft date change")
        result = get(key, EDIT, {"id": p["id"], "dueAt": p["new"]}).get("editPost")
        candidate = result.get("post") if isinstance(result, dict) else None
        require(isinstance(candidate, dict) and candidate.get("id") == p["id"] and
                candidate.get("channelId") == p["channel_id"] and
                candidate.get("status") == "draft" and
                same_instant(candidate.get("dueAt"), p["new"]),
                f"Buffer-Mutation unbestätigt: {channel}; NICHT wiederholen")
        live = get(key, POST_QUERY, {"id": p["id"]}).get("post")
        require(verify(live, channel, after=True) == before[channel],
                f"Unabhängige Prüfung fehlgeschlagen: {channel}")
        item["state"] = "verified_existing_draft_due_at_only"
        item["verified_at_utc"] = datetime.now(timezone.utc).isoformat()
        write_receipt(token, receipt, item,
                      "verified existing Buffer draft date without publication", sha=sha)
        print("AAB_NEWS_DRAFT_DATE_PASS", channel, p["id"], p["local"],
              "status=draft, image/text/tags/metadata intact", flush=True)
    batch["state"] = "verified_three_draft_dates_only_no_publish"
    batch["verified_at_utc"] = datetime.now(timezone.utc).isoformat()
    write_receipt(token, BATCH, batch, "verified three Buffer draft dates", sha=batch_sha)
    print("AAB_ALL_THREE_NEWS_DRAFT_DATES_VERIFIED_NO_PUBLISH", flush=True)


def main() -> int:
    require(sys.argv[1:] == ["--live"], "Nur expliziter geschützter Live-Lauf")
    live_move()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (Blocked, ValueError, RuntimeError, OSError, json.JSONDecodeError) as exc:
        print("AAB_NEWS_DRAFT_DATES_BLOCKED", type(exc).__name__,
              str(exc)[:220], file=sys.stderr)
        raise SystemExit(1)
