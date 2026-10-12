#!/usr/bin/env python3
"""Fail closed if the LIVE social campaign is not running on protected refs.

Read-only GitHub public branch metadata. This gate runs before image API calls,
output writes or any Buffer interaction; smoke/offline tests do not need it.
Repository owner must configure protections through their authorized UI.
"""
from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.request

REPOSITORY = "derJosef/social-assets"
REF = "refs/heads/main"
SHA_RE = re.compile(r"[a-f0-9]{40}\Z")
API = "https://api.github.com/repos/derJosef/social-assets/branches/"


class ActivationBlocked(RuntimeError):
    pass


def branch_metadata(branch: str, token: str) -> dict:
    if branch not in ("main", "automation-receipts"):
        raise ActivationBlocked("Unexpected branch requested")
    req = urllib.request.Request(
        API + branch,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": "Bearer " + token,
            "User-Agent": "social-draft-first-activation-guard/1.0",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            raw = response.read(128 * 1024)
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as exc:
        raise ActivationBlocked("GitHub branch verification unavailable") from None
    try:
        body = json.loads(raw)
    except (UnicodeError, ValueError):
        raise ActivationBlocked("GitHub returned invalid branch metadata") from None
    if not isinstance(body, dict) or body.get("name") != branch:
        raise ActivationBlocked("GitHub returned unexpected branch metadata")
    return body


def check(
    repo: str, ref: str, commit_sha: str, token: str
) -> dict:
    if repo != REPOSITORY or ref != REF or not SHA_RE.fullmatch(commit_sha):
        raise ActivationBlocked("Live drafts require exact main GitHub ref")
    if not token:
        raise ActivationBlocked("No GitHub credential for protected branch check")
    main = branch_metadata("main", token)
    ledger = branch_metadata("automation-receipts", token)
    if main.get("protected") is not True:
        raise ActivationBlocked("main is not protected: draft pipeline BLOCKED")
    if ledger.get("protected") is not True:
        raise ActivationBlocked("automation-receipts is not protected: draft pipeline BLOCKED")
    head = main.get("commit")
    if not isinstance(head, dict) or head.get("sha") != commit_sha:
        raise ActivationBlocked("main moved during this run: no new Buffer drafts")
    ledger_head = ledger.get("commit")
    if (not isinstance(ledger_head, dict) or
            not isinstance(ledger_head.get("sha"), str) or
            not SHA_RE.fullmatch(ledger_head["sha"])):
        raise ActivationBlocked("Receipt branch lacks an identifiable Git commit")
    return {
        "status": "PASS", "main_protected": True,
        "receipt_branch_protected": True,
        "main_commit": commit_sha, "ledger_commit": ledger_head["sha"],
        "buffer_mutations": 0, "image_provider_calls": 0,
    }


def main() -> int:
    try:
        result = check(
            os.environ.get("GITHUB_REPOSITORY", ""),
            os.environ.get("GITHUB_REF", ""),
            os.environ.get("GITHUB_SHA", ""),
            os.environ.get("GITHUB_TOKEN", ""),
        )
    except ActivationBlocked as exc:
        print("PRODUCTION_ACTIVATION_BLOCKED:", str(exc)[:180], file=sys.stderr)
        return 1
    print("PRODUCTION_ACTIVATION_PASS:", json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
