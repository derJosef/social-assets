#!/usr/bin/env python3
"""Prepared SINGLE-USE Buffer LinkedIn image-draft probe.

Only a personally started GitHub workflow_dispatch on protected main can run
this script. Never queues, publishes, edits, deletes, or retries any post.
The approved original campaign and its pending receipt are never reused.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

try:
    from scripts.buffer_draft import (
        REPOSITORY, CREATE_DATED_DRAFT, resolve_channel, buffer_graphql,
        fetch_receipt, put_receipt, verified_dated_post, validate_media_url,
    )
    from scripts.buffer_error_diagnostics import safe_mutation_diagnosis
except ImportError:
    from buffer_draft import (
        REPOSITORY, CREATE_DATED_DRAFT, resolve_channel, buffer_graphql,
        fetch_receipt, put_receipt, verified_dated_post, validate_media_url,
    )
    from buffer_error_diagnostics import safe_mutation_diagnosis

TARGET = "linkedin"
CONFIRMATION = "BILD_DATIERTER_DRAFT_EINMALTEST_NUR_BUFFER"
PROBE_ID = "2026-10-16-buffer-image-draft-probe-001"
RECEIPT = "delivery-receipts/2026-10-16-buffer-image-prescheduled-draft-probe.json"
# The image belongs to a previously built TEST campaign; only a pinned
# original-logo-verified artwork commit is reused, never the old draft ID.
IMAGE_COMMIT = "b535972ce7f788b7150edfede56093f0371c349a"
IMAGE_NAME = "2026-10-15-drei-kontrollpunkte-e2e-branded.png"
IMAGE_URL = (
    f"https://raw.githubusercontent.com/{REPOSITORY}/{IMAGE_COMMIT}/"
    f"media/images/{IMAGE_NAME}"
)
IMAGE_SHA256 = "31da8e5364587b58d011c83f17ae8caab437c9af490995808db742de95feb496"
ALT = "Technische drei Prüfschritte mit einer deutlich künstlichen blauen Hologrammfigur"
TEXT_PREFIX = "INTERNER TECHNISCHER TEST – NICHT VERÖFFENTLICHEN."
READ_IMAGE_DRAFT = """
query VerifyOneImageDraft($id: PostId!) {
  post(input: { id: $id }) {
    id channelId status dueAt text
    assets { source mimeType }
  }
}
"""


def future_time(now: datetime) -> str:
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("Einmaltest benötigt gültige Zeitzone")
    future = (now.astimezone(timezone.utc) + timedelta(days=120)).replace(
        hour=12, minute=0, second=0, microsecond=0
    )
    return future.strftime("%Y-%m-%dT%H:%M:%SZ")


def guarded_environment(env: dict[str, str]) -> None:
    expected = {
        "GITHUB_REPOSITORY": REPOSITORY,
        "GITHUB_REF": "refs/heads/main",
        "GITHUB_EVENT_NAME": "workflow_dispatch",
        "GITHUB_ACTOR": "derJosef",
        "GITHUB_RUN_ATTEMPT": "1",
        "PROBE_CONFIRMATION": CONFIRMATION,
    }
    for k, v in expected.items():
        if env.get(k) != v:
            raise RuntimeError(f"Einmaltest wegen {k} gesperrt")
    if not env.get("GITHUB_RUN_ID", "").isdigit() or not env.get("GITHUB_TOKEN") or not env.get("BUFFER_API_KEY"):
        raise RuntimeError("Einmaltest benötigt GitHub-Run-ID und erlaubte Secrets")


def preflight_image(*, fetch=None) -> None:
    """Only BEFORE pending receipt: verify the exact, immutable GitHub image.

    No API mutation and no access to Buffer. Limit bytes, time, redirects,
    and SHA. A public URL working here is not proof Buffer can fetch it.
    """
    validate_media_url(IMAGE_URL, "images")
    if fetch is None:
        def fetch(url):
            req = urllib.request.Request(url, headers={"User-Agent": "social-assets-image-probe"})
            with urllib.request.urlopen(req, timeout=15) as response:
                return response.read(10_000_001)
    try:
        raw = fetch(IMAGE_URL)
    except (TimeoutError, OSError, urllib.error.URLError):
        raise RuntimeError("Bild vor Versand nicht öffentlich abrufbar") from None
    if (not isinstance(raw, bytes) or not 0 < len(raw) <= 10_000_000
            or hashlib.sha256(raw).hexdigest() != IMAGE_SHA256):
        raise RuntimeError("Unveränderliches Markenbild vor Versand nicht SHA-verifiziert")
    # Explicitly disallow an accidental HTML response even when the URL is well formed.
    if raw[:8] != b"\x89PNG\r\n\x1a\n":
        raise RuntimeError("Markenbild kein PNG")


def verify_image_draft(record: object, *, post_id: str, channel_id: str,
                       due_at: str, text: str) -> bool:
    if not verified_dated_post(record, post_id=post_id, channel_id=channel_id, due_at=due_at):
        return False
    if record.get("text") != text:
        return False
    assets = record.get("assets")
    return (
        isinstance(assets, list) and len(assets) == 1
        and isinstance(assets[0], dict)
        and assets[0].get("source") == IMAGE_URL
        and assets[0].get("mimeType") == "image/png"
    )


def run_probe(env: dict[str, str], *, now: datetime, fetch=None) -> None:
    guarded_environment(env)
    github_token, buffer_token = env["GITHUB_TOKEN"], env["BUFFER_API_KEY"]
    # The pending receipt for the failed 15 October E2E is independent and
    # must not be changed, deleted, bypassed, or retried.
    if fetch_receipt(github_token, RECEIPT) is not None:
        raise RuntimeError("Einmaltest bereits reserviert: kein zweiter Buffer-Aufruf")
    preflight_image(fetch=fetch)
    channel_id = resolve_channel(buffer_token, TARGET, env.get("BUFFER_CHANNEL_ID", "").strip())
    due_at = future_time(now)  # deliberately far in future, BUT MUST remain draft.
    run_id = env["GITHUB_RUN_ID"]
    text = f"{TEXT_PREFIX} Bildvergleich mit dem erfolgreichen Text-Entwurf. {PROBE_ID}. GitHub-Lauf {run_id}."
    pending = {
        "probe": PROBE_ID, "target": TARGET,
        "state": "pending_manual_reconciliation_on_failure",
        "github_run_id": run_id,
        "image_sha256": IMAGE_SHA256,
        "due_at_utc": due_at,
    }
    sha = put_receipt(github_token, RECEIPT, pending, "buffer: reserve single-use image draft probe")
    variables = {
        "text": text, "channelId": channel_id, "dueAt": due_at,
        "assets": [{"image": {"url": IMAGE_URL, "metadata": {"altText": ALT}}}],
        "metadata": None,  # exact known production LinkedIn image payload
    }
    # Only mutation in the whole probe; any failure immediately stops here.
    result = buffer_graphql(buffer_token, CREATE_DATED_DRAFT, variables)
    action = result.get("createPost") if isinstance(result, dict) else None
    post = action.get("post") if isinstance(action, dict) else None
    if not isinstance(post, dict) or not isinstance(post.get("id"), str) or not post["id"]:
        error_type, category = safe_mutation_diagnosis(action)
        raise RuntimeError(
            f"Buffer nicht bestätigt ({error_type}; Diagnosekategorie={category}). "
            "Pending bleibt; kein Retry."
        )
    post_id = post["id"]
    pending.update({"state": "created_requires_independent_check", "buffer_post_id": post_id})
    sha = put_receipt(github_token, RECEIPT, pending, "buffer: identify image draft", sha=sha)
    if not verified_dated_post(post, post_id=post_id, channel_id=channel_id, due_at=due_at):
        raise RuntimeError("ALARM: Buffer Antwort nicht datierter Draft; keine weitere Mutation")
    readback = buffer_graphql(buffer_token, READ_IMAGE_DRAFT, {"id": post_id}).get("post")
    if not verify_image_draft(readback, post_id=post_id, channel_id=channel_id,
                              due_at=due_at, text=text):
        raise RuntimeError("ALARM: Buffer-Readback bestätigt Bild/Draft/Datum/Text nicht")
    pending["state"] = "verified_prescheduled_image_draft_not_queued"
    put_receipt(github_token, RECEIPT, pending, "buffer: independently verify single image draft", sha=sha)
    print(f"PASS: genau ein LinkedIn-Draft mit Bild und Zukunftstermin; Post-ID={post_id}; keine Queue")
    print(f"Prüfbeleg: {RECEIPT}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args()
    if not args.live:
        print("OFFLINE ONLY: keine Buffer-Aktion. Eigentümerfreigabe für Workflow-Dispatch nötig.")
        return 0
    try:
        run_probe(dict(os.environ), now=datetime.now(timezone.utc))
    except (RuntimeError, ValueError, OSError) as exc:
        print(f"BILD-DRAFT NICHT BESTÄTIGT: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
