#!/usr/bin/env python3
"""Validate an append-only, GitHub-Issue-backed editorial run journal.

The journal is written through the *derJosef-agents* GitHub connection before
research starts, then updated with issue comments. This module does not write
to GitHub, run a model or create Buffer posts. It validates the snapshots that
the producing agent reads back, and gives a conservative resume decision.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

SCHEMA_VERSION = 1
ISSUE_PREFIX = "AIAGENT_RUN_LOG: "
PHASES = ("start", "inventory", "research", "copy", "image", "transfer",
          "github", "actions", "buffer", "readback", "finish")
STATES = frozenset(("STARTED", "PASS", "ERROR", "BLOCKED", "SKIPPED"))
SIDE_EFFECT_PHASES = frozenset(("github", "actions", "buffer", "readback"))
TARGETS = frozenset(("linkedin", "facebook", "instagram"))
SENSITIVE = re.compile(
    r"(?i)(?:\bBearer\s+[^\s]+|\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9_]{16,}"
    r"|\bsk-(?:proj-)?[A-Za-z0-9_-]{16,}|\b(?:api[_-]?key|token|password|secret)\s*[:=]\s*\S+)")


class JournalError(ValueError):
    """Malformed or unsafe persistent evidence; fail closed."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise JournalError(message)


def _timestamp(raw: object) -> datetime:
    require(isinstance(raw, str) and raw.endswith("Z"), "timestamp requires UTC Z")
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise JournalError("invalid UTC timestamp") from exc
    require(parsed.tzinfo is not None and parsed.utcoffset().total_seconds() == 0,
            "timestamp must be UTC")
    return parsed


def _no_secrets(value: object) -> None:
    # Never persist raw requests/responses, credentials, or error tracebacks.
    if isinstance(value, dict):
        for key, item in value.items():
            require(not SENSITIVE.search(str(key)), "potential secret key")
            _no_secrets(item)
    elif isinstance(value, list):
        for item in value:
            _no_secrets(item)
    elif isinstance(value, str):
        require(len(value) <= 4000 and not SENSITIVE.search(value),
                "potential secret in journal; replace with sanitized summary")


def new_header(run_id: str, automation_id: str, mode: str, *,
               started_at: str | None = None) -> dict:
    try:
        run_id = str(uuid.UUID(run_id))
        automation_id = str(uuid.UUID(automation_id))
    except (ValueError, TypeError) as exc:
        raise JournalError("run_id and automation_id must be UUIDs") from exc
    require(mode in ("scheduled", "controlled_test"), "unexpected run mode")
    timestamp = started_at or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    _timestamp(timestamp)
    return {"schema_version": SCHEMA_VERSION, "run_id": run_id,
            "automation_id": automation_id, "mode": mode, "started_at": timestamp,
            "publication_allowed": False, "journal_type": "ai-agent-builder"}


def validate_header(header: dict) -> str:
    require(isinstance(header, dict) and set(header) == {
        "schema_version", "run_id", "automation_id", "mode", "started_at",
        "publication_allowed", "journal_type"}, "invalid journal header")
    require(header["schema_version"] == SCHEMA_VERSION and header["publication_allowed"] is False
            and header["journal_type"] == "ai-agent-builder", "unsafe journal header")
    new_header(header["run_id"], header["automation_id"], header["mode"],
               started_at=header["started_at"])
    _no_secrets(header)
    return header["run_id"]


def _verify_receipts(receipts: object) -> None:
    require(isinstance(receipts, list) and len(receipts) == 3,
            "readback PASS requires exactly 3 live Buffer receipts")
    for rec in receipts:
        require(isinstance(rec, dict) and set(rec) == {
            "target", "post_id", "channel_id", "status", "due_at"},
            "incomplete Buffer receipt")
        require(rec["target"] in TARGETS and rec["status"] == "draft"
                and rec["post_id"] and rec["channel_id"]
                and all(isinstance(rec[k], str) and len(rec[k]) <= 140
                        for k in ("post_id", "channel_id")),
                "live Buffer receipt is not a valid draft")
        _timestamp(rec["due_at"])
    require({rec["target"] for rec in receipts} == TARGETS,
            "all three platforms required")
    require(len({rec["post_id"] for rec in receipts}) == 3 and
            len({rec["channel_id"] for rec in receipts}) == 3,
            "duplicate Buffer post or channel")


def validate_event(event: dict, run_id: str) -> None:
    require(isinstance(event, dict) and {
        "schema_version", "run_id", "phase", "state", "recorded_at"} <= set(event)
            and set(event) <= {"schema_version", "run_id", "phase", "state",
                                 "recorded_at", "evidence", "error", "receipts", "resolved_by"},
            "invalid journal event fields")
    require(event["schema_version"] == SCHEMA_VERSION and event["run_id"] == run_id,
            "journal run mismatch")
    require(event["phase"] in PHASES and event["state"] in STATES,
            "unknown production phase or state")
    _timestamp(event["recorded_at"])
    _no_secrets(event)
    if event["state"] == "ERROR":
        require("error" in event, "tool ERROR requires sanitized diagnostic")
    if event["state"] == "BLOCKED" and "error" not in event:
        evidence = event.get("evidence")
        require(isinstance(evidence, dict) and isinstance(evidence.get("reason"), str)
                and bool(evidence["reason"].strip()),
                "BLOCKED requires a concrete reason or tool error")
    if "error" in event:
        err = event["error"]
        require(event["state"] in ("ERROR", "BLOCKED") and isinstance(err, dict)
                and set(err) == {"tool", "kind", "summary"}
                and all(isinstance(s, str) and 1 <= len(s) <= 240 for s in err.values()),
                "only redacted typed tool errors are allowed")
    if event["state"] == "PASS" and event["phase"] == "readback":
        _verify_receipts(event.get("receipts"))
    else:
        require("receipts" not in event, "unverified Buffer receipts are not accepted")
    if "resolved_by" in event:
        require(isinstance(event["resolved_by"], str) and
                8 <= len(event["resolved_by"]) <= 250,
                "reconciliation needs a concrete evidence reference")


def resume_decision(header: dict, events: list[dict]) -> dict:
    run_id = validate_header(header)
    require(isinstance(events, list), "events must be an ordered list")
    if not events:
        return {"decision": "STOP", "phase": "start",
                "reason": "GitHub issue exists, but no persisted START PASS checkpoint"}
    latest: dict[str, dict] = {}
    current_idx = 0
    last_time = _timestamp(header["started_at"])
    for index, item in enumerate(events):
        validate_event(item, run_id)
        phase = item["phase"]
        idx = PHASES.index(phase)
        current = latest.get(phase)
        # No jumping over a missing gate or recycling a passed gate.
        if index == 0:
            require(phase == "start" and item["state"] == "PASS", "start checkpoint missing")
        elif idx > current_idx:
            require(idx == current_idx + 1 and latest[PHASES[current_idx]]["state"] == "PASS",
                    "phase advanced without a successful checkpoint")
            current_idx = idx
        else:
            require(idx == current_idx, "backward replay of a prior phase")
            require(current is not None and current["state"] in ("STARTED", "ERROR", "BLOCKED"),
                    "duplicate successful phase")
            require(item["state"] != "STARTED", "phase already in progress")
            if current["state"] in ("ERROR", "BLOCKED"):
                require("resolved_by" in item,
                        "failed phase requires verified reconciliation")
        when = _timestamp(item["recorded_at"])
        require(when >= last_time, "journal event timestamps must be ordered")
        last_time = when
        latest[phase] = item
    last = latest[PHASES[current_idx]]
    phase = last["phase"]
    state = last["state"]
    if state == "PASS":
        if phase == "finish":
            return {"decision": "DONE", "phase": phase, "reason": "3/3 live-readback recorded"}
        return {"decision": "NEXT", "phase": PHASES[current_idx+1],
                "reason": "previous phase checkpointed; do not replay"}
    if phase in SIDE_EFFECT_PHASES:
        return {"decision": "RECONCILE", "phase": phase,
                "reason": "possible GitHub/Buffer side effect; inspect remote state first; no blind retry"}
    return {"decision": "INSPECT", "phase": phase,
            "reason": "inspect saved artifacts, tools and errors before resuming this phase"}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Offline resume safety check for a GitHub issue journal")
    ap.add_argument("snapshot", type=Path, help="JSON {header: GitHub issue body, events: ordered comments}")
    args = ap.parse_args(argv)
    try:
        content = json.loads(args.snapshot.read_text(encoding="utf-8"))
        decision = resume_decision(content["header"], content["events"])
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps({"decision": "STOP", "reason": str(exc)[:200]}))
        return 2
    print(json.dumps(decision, ensure_ascii=False))
    return 0 if decision["decision"] in ("NEXT", "DONE") else 3


if __name__ == "__main__":
    sys.exit(main())
