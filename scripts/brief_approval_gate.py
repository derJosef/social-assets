#!/usr/bin/env python3
"""Proposed, read-only campaign-brief approval gate.

This module is deliberately NOT wired into production GitHub Actions yet.
An offline schema check is never an authorization. Live authorization also
requires independently authenticated GitHub merge provenance and a protected
main branch. Nothing in this module calls Buffer or writes to GitHub.
"""

from __future__ import annotations

import argparse
import base64
import binascii
import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Callable


ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = "derJosef/social-assets"
APPROVER = "derJosef"
TARGETS = ("linkedin", "facebook", "instagram")
CID = r"20\d{2}-\d{2}-\d{2}-[a-z0-9]+(?:-[a-z0-9]+)*"
POST_RE = re.compile(rf"^ready-for-buffer/auto-({CID})-(linkedin|facebook|instagram)\.json$")
SHA_RE = re.compile(r"^[a-f0-9]{64}$")
SOURCE_RE = re.compile(r"^media/source-images/[a-zA-Z0-9][a-zA-Z0-9_.-]{0,119}\.png$")
FIELDS = frozenset({
    "format_version", "campaign_id", "brief_path", "brief_sha256",
    "image_review_path", "image_review_sha256", "source_sha256",
    "targets", "purpose", "state",
})


class ApprovalBlocked(ValueError):
    """Fail-closed result; it never authorizes a Buffer operation."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ApprovalBlocked(message)


def repo_bytes(root: Path, relative: str, *, max_size: int = 100_000) -> bytes:
    root = root.resolve(strict=True)
    candidate = (root / relative).resolve(strict=True)
    require(candidate.is_relative_to(root) and candidate.is_file(), "Datei ausserhalb des Repositorys")
    require(candidate.stat().st_size <= max_size, "Unzulässig grosse Freigabe-/Quelldatei")
    return candidate.read_bytes()


def parse_json(raw: bytes, label: str) -> dict:
    def unique_keys(pairs: list[tuple[str, object]]) -> dict:
        result = {}
        for key, value in pairs:
            require(key not in result, f"Doppelter JSON-Schlüssel in {label}")
            result[key] = value
        return result

    try:
        obj = json.loads(raw.decode("utf-8"), object_pairs_hook=unique_keys)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ApprovalBlocked(f"Ungültiges JSON: {label}") from exc
    require(isinstance(obj, dict), f"{label} muss ein JSON-Objekt sein")
    return obj


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def inspect_local(draft_path: str, root: Path = ROOT) -> tuple[str, bytes]:
    """Validate a proposed approval record; NEVER return authorization alone."""
    matched = POST_RE.fullmatch(draft_path)
    require(matched is not None, "Nur zugeordnete auto-Kampagnenentwürfe sind zulässig")
    campaign, platform = matched.groups()
    approval_path = f"orchestration/approvals/{campaign}.json"
    raw = repo_bytes(root, approval_path)
    approval = parse_json(raw, "Brief-Freigabe")
    require(set(approval) == FIELDS, "Unerwartetes oder fehlendes Freigabefeld")
    require(type(approval["format_version"]) is int and approval["format_version"] == 1,
            "Unbekannte Freigabeformatversion")
    require(approval["campaign_id"] == campaign, "Falsche Kampagnenbindung")
    require(approval["purpose"] == "unscheduled_buffer_draft_only", "Unzulässiger Freigabezweck")
    require(approval["state"] == "approved", "Freigabe fehlt oder wurde widerrufen")
    require(approval["targets"] == list(TARGETS) and platform in approval["targets"],
            "Unzulässige Plattformfreigabe")

    brief_path = f"orchestration/briefs/{campaign}.json"
    review_path = f"visual-reviews/{campaign}.json"
    require(approval["brief_path"] == brief_path and approval["image_review_path"] == review_path,
            "Brief- oder Reviewpfad passt nicht zur Kampagne")
    for field in ("brief_sha256", "image_review_sha256", "source_sha256"):
        require(isinstance(approval[field], str) and SHA_RE.fullmatch(approval[field]) is not None,
                f"Ungültiger SHA256-Wert: {field}")
    brief_bytes = repo_bytes(root, brief_path)
    review_bytes = repo_bytes(root, review_path)
    require(sha256(brief_bytes) == approval["brief_sha256"], "Brief nach Freigabe geändert")
    require(sha256(review_bytes) == approval["image_review_sha256"], "Bildreview nach Freigabe geändert")
    brief = parse_json(brief_bytes, "Kampagnen-Brief")
    review = parse_json(review_bytes, "Bildreview")
    require(brief.get("campaign_id") == campaign and brief.get("brand") == "ai-agent-builder"
            and brief.get("image_review") == review_path and brief.get("execution_mode") == "drafts",
            "Brief gehört nicht zu dieser freigegebenen Kampagne")
    require("prepared_content" in brief, "Redaktionell vorbereiteter Brief fehlt")
    source = review.get("source")
    require(isinstance(source, str) and SOURCE_RE.fullmatch(source) is not None,
            "Unzulässiger Quellbildpfad")
    require(review.get("source_sha256") == approval["source_sha256"]
            and sha256(repo_bytes(root, source, max_size=20_000_000)) == approval["source_sha256"],
            "Quellbild stimmt nicht mit der Freigabe überein")
    return approval_path, raw


def github_get(api_path: str, token: str) -> object:
    """Read-only GitHub API helper; never sends a write request."""
    require(bool(token), "GitHub-Lesetoken fehlt")
    req = urllib.request.Request(
        f"https://api.github.com/repos/{REPOSITORY}/{api_path}",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "social-assets-brief-approval-gate/1.0",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.load(resp)
    except (urllib.error.HTTPError, urllib.error.URLError, ValueError) as exc:
        raise ApprovalBlocked("GitHub-Freigabebeleg konnte nicht sicher gelesen werden") from exc


def verify_github_provenance(
    approval_path: str,
    expected_bytes: bytes,
    api_get: Callable[[str], object],
) -> dict:
    """Require a protected, single-file PR that Josef himself merged to main."""
    branch = api_get("branches/main")
    require(isinstance(branch, dict) and branch.get("protected") is True,
            "main ist nicht geschützt: Freigabequelle ist nicht vertrauenswürdig")

    encoded = urllib.parse.quote(approval_path, safe="/")
    current = api_get(f"contents/{encoded}?ref=main")
    require(isinstance(current, dict) and current.get("encoding") == "base64",
            "Freigabe auf main nicht vollständig lesbar")
    try:
        remote = base64.b64decode(current["content"], validate=False)
    except (TypeError, ValueError, binascii.Error, KeyError) as exc:
        raise ApprovalBlocked("Freigabeinhalt auf main ist ungültig") from exc
    require(remote == expected_bytes, "Lokale Freigabe weicht von geschütztem main ab")

    commits = api_get(f"commits?path={encoded}&sha=main&per_page=1")
    require(isinstance(commits, list) and len(commits) == 1
            and isinstance(commits[0], dict), "Letzter Freigabe-Commit fehlt")
    commit_sha = commits[0].get("sha")
    require(isinstance(commit_sha, str) and re.fullmatch(r"[a-f0-9]{40}", commit_sha),
            "Ungültiger Freigabe-Commit")
    prs = api_get(f"commits/{commit_sha}/pulls")
    require(isinstance(prs, list), "PR-Herkunft nicht prüfbar")
    for candidate in prs:
        if not isinstance(candidate, dict) or not isinstance(candidate.get("number"), int):
            continue
        number = candidate["number"]
        # The associated-PR list is a shortened representation. Only the
        # individual PR endpoint reliably gives the merged_by account.
        pr = api_get(f"pulls/{number}")
        require(isinstance(pr, dict), "GitHub-PR-Nachweis unvollständig")
        merged_by = pr.get("merged_by") or {}
        base = pr.get("base") or {}
        base_repo = base.get("repo") or {}
        if not (isinstance(merged_by, dict) and merged_by.get("login") == APPROVER
                and pr.get("merged_at") and base.get("ref") == "main"
                and isinstance(base_repo, dict)
                and base_repo.get("full_name") == REPOSITORY
                and pr.get("number") == number):
            continue
        files = api_get(f"pulls/{number}/files?per_page=100")
        if (isinstance(files, list) and len(files) == 1
                and isinstance(files[0], dict)
                and files[0].get("filename") == approval_path
                and files[0].get("status") in ("added", "modified")):
            return {"approval_path": approval_path, "approved_pr": number,
                    "merged_by": APPROVER, "commit": commit_sha}
    raise ApprovalBlocked("Keine eigenständige, durch Josef gemergte Brief-Freigabe nachweisbar")


def authorize_draft(
    draft_path: str,
    root: Path = ROOT,
    api_get: Callable[[str], object] | None = None,
) -> dict:
    """Authorize only when local bindings AND protected GitHub provenance agree."""
    require(os.environ.get("GITHUB_REPOSITORY") == REPOSITORY
            and os.environ.get("GITHUB_REF") == "refs/heads/main",
            "Live-Freigabeprüfung nur auf social-assets/main erlaubt")
    path, raw = inspect_local(draft_path, root)
    if api_get is None:
        token = os.environ.get("GITHUB_TOKEN", "")
        require(bool(token), "GitHub-Token fehlt")
        api_get = lambda endpoint: github_get(endpoint, token)
    return verify_github_provenance(path, raw, api_get)


def main() -> int:
    parser = argparse.ArgumentParser(description="Brief-Freigabe: reine Prüfung, ohne Buffer-Schreibvorgang")
    parser.add_argument("--draft", required=True, help="ready-for-buffer/auto-...-<plattform>.json")
    parser.add_argument("--lint-only", action="store_true",
                        help="Nur lokale Prüfsummen/Struktur; KEINE Autorisierung, kein Netzwerk")
    args = parser.parse_args()
    try:
        if args.lint_only:
            inspect_local(args.draft)
            print("LOCAL_CHECK_OK: Dies ist KEINE Buffer-Freigabe; GitHub-Provenienz ungeprüft.")
        else:
            evidence = authorize_draft(args.draft)
            print("BRIEF_APPROVED_DRAFT_ONLY:", json.dumps(evidence, sort_keys=True))
        return 0
    except (ApprovalBlocked, OSError, KeyError, TypeError) as exc:
        print(f"BRIEF_APPROVAL_BLOCKED: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
