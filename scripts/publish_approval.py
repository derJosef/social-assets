#!/usr/bin/env python3
"""Read-only, fail-closed proof of human GitHub Environment approval.

Run AFTER GitHub Environment required-reviewer hold. All values are bound to
the actual GitHub Actions run and read directly from GitHub's Approvals API;
no user-created JSON or static environment marker counts as approval.
"""
from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.request

REPO = "derJosef/social-assets"
ENVIRONMENT = "buffer-publish"
LOGIN = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?$")
RUN_ID = re.compile(r"^[1-9][0-9]{0,17}$")


def validate_approvals(approvals: object, *, actor: str, triggering_actor: str,
                       allowed_logins: str, environment: str = ENVIRONMENT) -> str:
    """Return the actual GitHub approver login or fail without approving anything."""
    if not isinstance(approvals, list):
        raise RuntimeError("GitHub Approvals API lieferte keine Liste. Veröffentlichung gesperrt.")
    allowed = [name.strip() for name in allowed_logins.split(",") if name.strip()]
    if not allowed or len(set(allowed)) != len(allowed) or any(
        not LOGIN.fullmatch(name) for name in allowed
    ):
        raise RuntimeError("BUFFER_APPROVER_LOGINS fehlt oder ist ungültig.")
    if not actor or not triggering_actor or not LOGIN.fullmatch(actor) or not LOGIN.fullmatch(triggering_actor):
        raise RuntimeError("GitHub-Auslöseridentität ist nicht verlässlich.")
    # GitHub login names are case-insensitive.
    allowed_lower = {name.lower() for name in allowed}
    for item in approvals:
        if not isinstance(item, dict) or item.get("state") != "approved":
            continue
        user = item.get("user")
        environments = item.get("environments")
        if not isinstance(user, dict) or not isinstance(environments, list):
            continue
        approver = user.get("login")
        if (not isinstance(approver, str) or not LOGIN.fullmatch(approver)
                or approver.lower() not in allowed_lower
                or approver.lower() in {actor.lower(), triggering_actor.lower()}):
            continue
        if any(isinstance(e, dict) and e.get("name") == environment for e in environments):
            return approver
    raise RuntimeError("Keine gültige Genehmigung eines unabhängigen GitHub-Prüfers vorhanden.")


def verify_current_run(*, environ: dict | None = None, urlopen=None) -> str:
    """Read GitHub's approval audit for THIS running workflow, never local claims."""
    env = os.environ if environ is None else environ
    if env.get("GITHUB_REPOSITORY") != REPO or env.get("GITHUB_REF") != "refs/heads/main":
        raise RuntimeError("Approvals-Abfrage nur für den freigegebenen Main-Workflow.")
    if env.get("GITHUB_EVENT_NAME") != "workflow_dispatch":
        raise RuntimeError("Approvals-Abfrage nur für manuell gestarteten Workflow.")
    run_id = env.get("GITHUB_RUN_ID", "")
    if not RUN_ID.fullmatch(run_id):
        raise RuntimeError("GITHUB_RUN_ID fehlt oder ist ungültig.")
    token = env.get("GITHUB_TOKEN", "")
    if not token:
        raise RuntimeError("GitHub-Token für lesende Approval-Prüfung fehlt.")
    allowed = env.get("BUFFER_APPROVER_LOGINS", "")
    # Validate configuration before reaching out to GitHub.
    if not allowed or not all(LOGIN.fullmatch(v.strip()) for v in allowed.split(",") if v.strip()):
        raise RuntimeError("BUFFER_APPROVER_LOGINS ist nicht konfiguriert.")
    opener = urllib.request.urlopen if urlopen is None else urlopen
    url = f"https://api.github.com/repos/{REPO}/actions/runs/{run_id}/approvals"
    request = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "ai-agent-builder-publish-approval/1.0",
    })
    try:
        with opener(request, timeout=20) as response:
            payload = json.load(response)
    except (urllib.error.URLError, urllib.error.HTTPError, ValueError, OSError) as exc:
        # Never disclose GitHub auth token or provider response body.
        raise RuntimeError(f"GitHub-Approval-Abfrage fehlgeschlagen ({type(exc).__name__}); Veröffentlichung gesperrt.") from None
    return validate_approvals(payload, actor=env.get("GITHUB_ACTOR", ""),
                              triggering_actor=env.get("GITHUB_TRIGGERING_ACTOR", ""),
                              allowed_logins=allowed)


if __name__ == "__main__":
    try:
        approver = verify_current_run()
    except RuntimeError as error:
        print(f"APPROVAL BLOCKED: {error}", file=sys.stderr)
        raise SystemExit(1)
    print(f"APPROVAL PASS: Environment {ENVIRONMENT}; unabhängiger Prüfer {approver}; aktueller GitHub-Run.")
