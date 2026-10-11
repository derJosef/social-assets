#!/usr/bin/env python3
"""One-time, manually approved Buffer draft-with-time capability probe.

This file is NOT part of the production draft/scheduling paths. It has no
publication, queue, edit or deletion mutation. Its only Buffer mutation is a
single `createPost(saveToDraft:true, mode:customScheduled, dueAt:...)` call.
The fixed GitHub reservation blocks retries even after an ambiguous failure.
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timedelta, timezone

from buffer_draft import (
    REPOSITORY, buffer_graphql, fetch_receipt,
    put_receipt, resolve_channel,
)


CONFIRMATION = "DATIERTER_DRAFT_EINMALTEST_OHNE_QUEUE"
RECEIPT = "delivery-receipts/2026-10-11-prescheduled-draft-probe.json"
TARGET = "linkedin"
TEST_TEXT_PREFIX = "INTERNER TECHNISCHER TEST – NICHT VERÖFFENTLICHEN."

CREATE_PRESET_DRAFT = """
mutation CreatePresetDraft($text: String!, $channelId: ChannelId!, $dueAt: DateTime!) {
  createPost(input: {
    text: $text
    channelId: $channelId
    schedulingType: automatic
    mode: customScheduled
    dueAt: $dueAt
    saveToDraft: true
    assets: []
  }) {
    __typename
    ... on PostActionSuccess { post { id channelId status dueAt } }
    ... on MutationError { message }
  }
}
"""

READ_POST = """
query VerifyPresetDraft($id: PostId!) {
  post(input: { id: $id }) { id channelId status dueAt }
}
"""


def check_execution_guard(env: dict[str, str]) -> None:
    """Fail before any network call unless an owner starts it on main once."""
    required = {
        "GITHUB_REPOSITORY": REPOSITORY,
        "GITHUB_REF": "refs/heads/main",
        "GITHUB_EVENT_NAME": "workflow_dispatch",
        "GITHUB_ACTOR": "derJosef",
        "GITHUB_RUN_ATTEMPT": "1",
        "PROBE_CONFIRMATION": CONFIRMATION,
    }
    for name, expected in required.items():
        if env.get(name) != expected:
            raise RuntimeError(f"Sicherheitssperre: {name} stimmt nicht mit dem Einmaltest überein")
    if not env.get("GITHUB_RUN_ID", "").isdigit():
        raise RuntimeError("Sicherheitssperre: GitHub-Run-ID fehlt")
    if not env.get("GITHUB_TOKEN") or not env.get("BUFFER_API_KEY"):
        raise RuntimeError("GitHub- oder Buffer-Secret fehlt")


def future_time(now: datetime) -> str:
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("Test benötigt eine Zeitzone")
    # Far enough away that even an unexpected scheduling failure cannot cause
    # immediate publication. This is a test marker, not a campaign proposal.
    when = (now.astimezone(timezone.utc) + timedelta(days=120)).replace(
        hour=12, minute=0, second=0, microsecond=0
    )
    return when.strftime("%Y-%m-%dT%H:%M:%SZ")


def verified_post(record: object, *, post_id: str, channel_id: str, due_at: str) -> bool:
    if not isinstance(record, dict) or not isinstance(record.get("dueAt"), str):
        return False
    try:
        recorded_time = datetime.fromisoformat(record["dueAt"].replace("Z", "+00:00"))
        expected_time = datetime.fromisoformat(due_at.replace("Z", "+00:00"))
        matches_time = (
            recorded_time.tzinfo is not None
            and recorded_time.astimezone(timezone.utc) == expected_time
        )
    except ValueError:
        return False
    return (
        record.get("id") == post_id
        and record.get("channelId") == channel_id
        and str(record.get("status", "")).lower() == "draft"
        and matches_time
    )


def live_probe(env: dict[str, str], *, now: datetime) -> None:
    check_execution_guard(env)
    github_token = env["GITHUB_TOKEN"]
    buffer_token = env["BUFFER_API_KEY"]

    # Permanent single-use marker. Its existence blocks every later attempt.
    # A pending record stays pending on ANY error: never blindly retry.
    if fetch_receipt(github_token, RECEIPT) is not None:
        raise RuntimeError("Test wurde bereits reserviert; kein zweiter Buffer-Aufruf")
    channel_id = resolve_channel(buffer_token, TARGET, env.get("BUFFER_CHANNEL_ID", "").strip())
    due_at = future_time(now)
    run_id = env["GITHUB_RUN_ID"]
    receipt = {
        "probe": "one-time-prescheduled-draft",
        "target": TARGET,
        "due_at_utc": due_at,
        "state": "pending_manual_reconciliation_on_failure",
        "github_run_id": run_id,
    }
    sha = put_receipt(
        github_token, RECEIPT, receipt,
        "buffer probe: reserve exactly one future-dated draft test",
    )

    # NEVER create the post before the durable reservation has succeeded.
    text = f"{TEST_TEXT_PREFIX} GitHub-Testlauf {run_id}."
    variables = {"text": text, "channelId": channel_id, "dueAt": due_at}
    response = buffer_graphql(buffer_token, CREATE_PRESET_DRAFT, variables)
    created = response.get("createPost")
    post = created.get("post") if isinstance(created, dict) else None
    if not isinstance(post, dict) or not isinstance(post.get("id"), str) or not post["id"]:
        raise RuntimeError("Buffer-Antwort nicht eindeutig; Test bleibt gesperrt und pending")

    # Even if Buffer unexpectedly scheduled the test, preserve its ID for
    # prompt supervised remediation. Never mutate it again automatically.
    post_id = post["id"]
    receipt.update({"buffer_post_id": post_id, "state": "created_requires_independent_check"})
    sha = put_receipt(
        github_token, RECEIPT, receipt,
        "buffer probe: identify created post before independent status check", sha=sha,
    )
    print(f"Einmaltest-Post-ID: {post_id}; Verifikation läuft. Kein automatischer Retry.")
    if not verified_post(post, post_id=post_id, channel_id=channel_id, due_at=due_at):
        raise RuntimeError("ALARM: Antwort ist kein datierter Draft. Buffer sofort manuell prüfen")

    confirmed = buffer_graphql(buffer_token, READ_POST, {"id": post_id}).get("post")
    if not verified_post(confirmed, post_id=post_id, channel_id=channel_id, due_at=due_at):
        raise RuntimeError("ALARM: Buffer-Readback bestätigt keinen datierten Draft")

    receipt["state"] = "verified_prescheduled_draft_not_queued"
    put_receipt(
        github_token, RECEIPT, receipt,
        "buffer probe: independently verified draft status and reserved date", sha=sha,
    )
    print(f"PASS: Status draft, dueAt={due_at}, Kanal LinkedIn. Keine Queue-/Publikationsaktion.")
    print(f"Einmaliger Prüfbeleg: {RECEIPT}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Einmaliger manueller Test: datierter Buffer-Draft")
    parser.add_argument("--live", action="store_true", help="Nur aus bewusst gestarteter GitHub Action")
    args = parser.parse_args()
    if not args.live:
        print("Kein Buffer-Zugriff. Für Live-Test ist --live im manuellen GitHub-Workflow nötig.")
        return 0
    try:
        live_probe(dict(os.environ), now=datetime.now(timezone.utc))
    except (RuntimeError, ValueError, OSError) as exc:
        print(f"TEST NICHT BESTÄTIGT: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
