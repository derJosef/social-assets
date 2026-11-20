#!/usr/bin/env python3
"""Normalize GitHub Actions step outcomes into the persistent run receipt.

No raw stdout/stderr, headers or secrets enter the public receipt. Complete
diagnostics remain in the corresponding GitHub Actions job log. This program
does not call Buffer, GitHub, or any remote service.
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path

TOOLS = {
    "checkout": "actions/checkout@v5",
    "setup": "actions/setup-python@v6",
    "deps": "pip install",
    "offline": "python3 -m unittest",
    "request": "brief intake and git diff",
    "guard": "production_activation_guard.py",
    "collision": "git ls-remote",
    "image_import": "chatgpt_image_import.py",
    "preflight": "prepared_brief_preflight.py",
    "reservations": "git fetch / campaign_reservations.py",
    "font": "curl / sha256sum",
    "build": "social_orchestrator.py",
    "freeze": "git commit / git push",
    "send": "buffer_draft.py",
    "readback": "orchestrator_verify_buffer.py",
}
OUTCOMES = {"success": "PASS", "failure": "FAIL", "skipped": "NOT_RUN",
            "cancelled": "CANCELLED"}


def build_report(report: dict, outcomes: dict[str, str], *, repo: str,
                 run_id: str, job_status: str) -> dict:
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo) or not run_id.isdecimal():
        raise ValueError("invalid Actions run reference")
    if job_status not in ("success", "failure", "cancelled"):
        raise ValueError("invalid job status")
    if not isinstance(report, dict):
        raise ValueError("report must be an object")
    log_url = f"https://github.com/{repo}/actions/runs/{run_id}"
    normalized = {}
    errors = []
    for step, outcome in outcomes.items():
        if step not in TOOLS or outcome not in OUTCOMES:
            raise ValueError("unknown Action step or outcome")
        normalized[step] = {"status": OUTCOMES[outcome], "tool": TOOLS[step]}
        if outcome == "failure":
            errors.append({"step": step, "tool": TOOLS[step],
                           "kind": "step_failure", "summary": "See protected/masked Actions step log",
                           "log_url": log_url})
    result = dict(report)
    result["action_steps"] = normalized
    result["action_errors"] = errors
    result["github_run_id"] = run_id
    result["github_run_url"] = log_url
    # Existing social_weekly_review.validate() and consumers require this key.
    result["job_status"] = job_status
    result["job_status_at_receipt"] = job_status
    result["receipt_at"] = datetime.now(timezone.utc).isoformat()
    # The receipt-writing step has not completed yet. Its outcome must be
    # independently confirmed with the final Actions job + GitHub readback.
    result["receipt_state"] = "WRITE_PENDING"
    send = outcomes.get("send")
    readback = outcomes.get("readback")
    if send in ("failure", "success", "cancelled") and readback != "success":
        result["resume_safety"] = "RECONCILE_BUFFER"
        result["buffer_verification"] = {"status": "UNVERIFIED"}
        result["state"] = "blocked"
    elif job_status != "success" or errors:
        result["resume_safety"] = "INSPECT_BEFORE_RESTART"
        result["state"] = "blocked"
    elif readback == "success" and result.get("buffer_verification", {}).get("status") != "PASS":
        result["resume_safety"] = "RECONCILE_BUFFER"
        result["buffer_verification"] = {"status": "UNVERIFIED"}
        result["state"] = "blocked"
    else:
        result["resume_safety"] = "FINAL_ACTIONS_CONFIRMATION_REQUIRED"
    return result


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--outcomes", type=Path, required=True)
    ap.add_argument("--repo", required=True)
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--job-status", required=True)
    ap.add_argument("--campaign", default="preflight")
    ns = ap.parse_args(argv)
    try:
        original = json.loads(ns.report.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        original = {"state": "blocked_before_preparation", "steps": {}}
    outcomes = json.loads(ns.outcomes.read_text(encoding="utf-8"))
    result = build_report(original, outcomes, repo=ns.repo,
                          run_id=ns.run_id, job_status=ns.job_status)
    result["campaign"] = result.get("campaign") or ns.campaign
    ns.output.parent.mkdir(parents=True, exist_ok=True)
    ns.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n",
                         encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
