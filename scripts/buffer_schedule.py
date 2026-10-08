#!/usr/bin/env python3
"""Schedule an EXISTING Buffer draft after a separate, explicit approval.

Never creates a second post. GitHub Actions may run --schedule only for a newly
added file in ready-to-schedule/. --dry-run is network-free and read-only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Sibling module is part of the existing social-assets integration.
from buffer_draft import (  # type: ignore
    REPOSITORY,
    buffer_graphql,
    channel_preference,
    fetch_receipt,
    put_receipt,
    receipt_path,
    resolve_channel,
)

ROOT = Path(__file__).resolve().parents[1]
REQUEST_RE = re.compile(r"^ready-to-schedule/[a-zA-Z0-9][a-zA-Z0-9_.-]{0,119}\.json$")
DRAFT_RE = re.compile(r"^ready-for-buffer/[a-zA-Z0-9][a-zA-Z0-9_.-]{0,119}\.json$")
UTC_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")

GET_POST = """
query GetPost($id: PostId!) {
  post(input: { id: $id }) { id channelId text status dueAt }
}
"""
SCHEDULE_EXISTING_DRAFT = """
mutation ScheduleExistingDraft($id: PostId!, $dueAt: DateTime!, $text: String!) {
  editPost(input: {
    id: $id
    text: $text
    schedulingType: automatic
    mode: customScheduled
    dueAt: $dueAt
    saveToDraft: false
  }) {
    __typename
    ... on PostActionSuccess { post { id channelId status dueAt } }
    ... on MutationError { message }
  }
}
"""


def local_file(relative: str) -> Path:
    path = (ROOT / relative).resolve(strict=True)
    if not path.is_relative_to(ROOT) or not path.is_file():
        raise ValueError("Datei außerhalb des Repositorys oder keine Datei.")
    return path


def inspect_request(request_file: str, now: datetime | None = None) -> dict:
    """Validate the approval, draft, and original delivery receipt offline."""
    if not REQUEST_RE.fullmatch(request_file):
        raise ValueError("Freigabe muss eine einzelne JSON-Datei in ready-to-schedule/ sein.")
    request_bytes = local_file(request_file).read_bytes()
    if len(request_bytes) > 8192:
        raise ValueError("Freigabedatei ist zu groß.")
    request = json.loads(request_bytes)
    if not isinstance(request, dict) or set(request) != {
        "format_version", "target", "draft_file", "publish_at_utc", "approved_for_scheduling"
    }:
        raise ValueError("Unbekanntes Freigabeformat.")
    if request["format_version"] != 1 or request["approved_for_scheduling"] is not True:
        raise ValueError("Explizite Terminierungsfreigabe fehlt.")
    target = request["target"]
    draft_file = request["draft_file"]
    if target not in ("linkedin", "facebook", "instagram") or not isinstance(draft_file, str) or not DRAFT_RE.fullmatch(draft_file):
        raise ValueError("Ungültiger Kanal oder Entwurfspfad.")
    due = request["publish_at_utc"]
    if not isinstance(due, str) or not UTC_RE.fullmatch(due):
        raise ValueError("Veröffentlichungszeit muss ISO-8601 UTC mit Sekunden und Z sein.")
    due_dt = datetime.strptime(due, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    current = now or datetime.now(timezone.utc)
    if due_dt <= current + timedelta(minutes=2):
        raise ValueError("Veröffentlichungszeit ist nicht mindestens zwei Minuten in der Zukunft.")

    draft_raw = local_file(draft_file).read_bytes()
    draft = json.loads(draft_raw)
    if not isinstance(draft, dict) or draft.get("target") != target:
        raise ValueError("Kanal der Freigabe und des Entwurfs stimmt nicht überein.")
    delivery_file = receipt_path(draft_file)
    delivery = json.loads(local_file(delivery_file).read_text(encoding="utf-8"))
    if (delivery.get("state") != "draft_created"
            or delivery.get("draft_file") != draft_file
            or delivery.get("target") != target
            or delivery.get("draft_sha256") != hashlib.sha256(draft_raw).hexdigest()
            or not isinstance(delivery.get("buffer_post_id"), str)
            or not delivery["buffer_post_id"]):
        raise ValueError("Kein passender, bestätigter Buffer-Entwurf vorhanden.")

    digest = hashlib.sha256(request_file.encode("utf-8")).hexdigest()[:24]
    return {
        "request_file": request_file,
        "request_sha256": hashlib.sha256(request_bytes).hexdigest(),
        "target": target,
        "draft_file": draft_file,
        "text": draft["text"],
        "post_id": delivery["buffer_post_id"],
        "due_at": due,
        "receipt_path": f"schedule-receipts/{digest}.json",
    }


def schedule(info: dict) -> None:
    if os.environ.get("GITHUB_REPOSITORY") != REPOSITORY or os.environ.get("GITHUB_REF") != "refs/heads/main":
        raise RuntimeError("Terminierung nur durch GitHub Actions auf social-assets/main.")
    token = os.environ.get("BUFFER_API_KEY", "")
    github_token = os.environ.get("GITHUB_TOKEN", "")
    if not token or not github_token:
        raise RuntimeError("Buffer- oder GitHub-Token fehlt.")
    channel_id = resolve_channel(token, info["target"], channel_preference(info["target"]))
    post = buffer_graphql(token, GET_POST, {"id": info["post_id"]}).get("post")
    if not isinstance(post, dict) or post.get("id") != info["post_id"]:
        raise RuntimeError("Buffer-Beitrag nicht eindeutig abrufbar.")
    if post.get("channelId") != channel_id or post.get("status") != "draft" or post.get("text") != info["text"]:
        raise RuntimeError("Beitrag wurde bereits verändert/terminiert oder Kanal ist falsch. Kein Versand.")

    receipt = info["receipt_path"]
    if fetch_receipt(github_token, receipt) is not None:
        raise RuntimeError("Terminierungsbeleg existiert bereits. Keine Wiederholung; Buffer prüfen.")
    pending = {
        "request_file": info["request_file"], "request_sha256": info["request_sha256"],
        "draft_file": info["draft_file"], "target": info["target"],
        "buffer_post_id": info["post_id"], "due_at": info["due_at"],
        "state": "pending_manual_reconciliation_on_failure",
        "github_run_id": os.environ.get("GITHUB_RUN_ID", "unknown"),
    }
    receipt_sha = put_receipt(github_token, receipt, pending, f"buffer: reserve scheduling {info['request_file']}")
    # The reservation is deliberately irreversible on uncertain API results.
    # The API's edit validator requires the existing text explicitly, even though
    # the docs say omission should preserve it. Preflight compared it byte-for-byte.
    result = buffer_graphql(token, SCHEDULE_EXISTING_DRAFT, {"id": info["post_id"], "dueAt": info["due_at"], "text": info["text"]})
    action = result.get("editPost")
    changed = action.get("post") if isinstance(action, dict) else None
    if not isinstance(changed, dict) or changed.get("id") != info["post_id"]:
        reason = action.get("message", "") if isinstance(action, dict) else ""
        if isinstance(reason, str):
            # Only the known-public campaign text may appear in an API error.
            # Never print API keys or multiline text into this public repo's logs.
            for secret in (token, github_token, info["text"]):
                if secret:
                    reason = reason.replace(secret, "[REDACTED]")
            reason = re.sub(r"[\r\n\t]+", " ", reason)[:240]
        else:
            reason = ""
        typename = action.get("__typename", "Unknown") if isinstance(action, dict) else "Unknown"
        raise RuntimeError(f"Buffer-Terminierung abgewiesen ({typename}): {reason}. Pending-Beleg manuell prüfen.")
    # Do not report success until Buffer's scheduled time matches the requested time.
    returned = changed.get("dueAt", "")
    try:
        returned_utc = datetime.fromisoformat(returned.replace("Z", "+00:00"))
        expected_utc = datetime.fromisoformat(info["due_at"].replace("Z", "+00:00"))
    except (AttributeError, ValueError) as exc:
        raise RuntimeError("Buffer hat keinen gültigen Termin zurückgegeben; manuell prüfen.") from exc
    if returned_utc != expected_utc or changed.get("channelId") != channel_id or changed.get("status") == "draft":
        raise RuntimeError("Buffer bestätigte nicht den erwarteten geplanten Beitrag; manuell prüfen.")
    pending["state"] = "scheduled"
    put_receipt(github_token, receipt, pending, f"buffer: confirmed scheduled {info['request_file']}", sha=receipt_sha)
    print(f"Erfolg: bestehender {info['target']}-Entwurf {info['post_id']} für {info['due_at']} terminiert.")
    print(f"Beleg: {receipt}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Einen vorhandenen Buffer-Entwurf nach Freigabe terminieren.")
    parser.add_argument("--request", required=True)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--schedule", action="store_true")
    args = parser.parse_args()
    try:
        info = inspect_request(args.request)
        if args.dry_run:
            print(f"DRY-RUN OK: {info['target']} {info['post_id']} -> {info['due_at']} (keine API-Aufrufe)")
        else:
            schedule(info)
    except (RuntimeError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"Fehler: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
