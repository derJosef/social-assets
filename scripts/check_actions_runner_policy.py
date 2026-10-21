#!/usr/bin/env python3
"""Repository-specific runner lint. No API, secrets, external packages or writes.

Default: ubuntu-slim for ALL new jobs. The explicitly named legacy standard
jobs below are grandfathered only, NOT evidence that Standard is necessary.
Promoting an exception to new jobs or relaxing the policy requires a code review.
"""
from __future__ import annotations
import re
import sys
from pathlib import Path

# Existing jobs only, inventory 2026-10-21. Reassess after CI measurements.
LEGACY_STANDARD_JOBS = frozenset({
    "approved-wer-liest-release-20261017.yml/approved-release",
    "buffer-auto-drafts.yml/create-drafts",
    "buffer-auto-schedule.yml/schedule-existing-drafts",
    "buffer-current-editorial-audit.yml/audit",
    "buffer-diagnostics.yml/inspect",
    "buffer-draft-live-review.yml/inspect",
    "buffer-draft.yml/draft",
    "buffer-existing-campaign-readback.yml/read-only",
    "buffer-one-time-image-draft-probe.yml/image-draft-one-time",
    "buffer-prescheduled-draft-probe.yml/single-linkedin-draft",
    "legacy-six-buffer-inplace-image-update.yml/repair",
    "legacy-six-draft-images-only.yml/prepare",
    "social-campaign-orchestrator.yml/orchestrate",
    "social-model-connection-test.yml/probe",
    "social-portfolio-scene-pr.yml/offline",
    "social-visual-brand-test.yml/create-and-verify",
})

ROOT_KEY = re.compile(r"^[A-Za-z_][\w-]*:", re.M)
JOB_KEY = re.compile(r"^  ([A-Za-z_][\w-]*):\s*(?:#.*)?$", re.M)
RUNNER_KEY = re.compile(r"^    runs-on:\s*(.*?)\s*$", re.M)
USES_KEY = re.compile(r"^    uses:\s*\S+", re.M)


def evaluate(source: str, filename: str) -> list[str]:
    errors: list[str] = []
    jobs = re.search(r"^jobs:\s*(?:#.*)?$", source, re.M)
    if not jobs:
        return [f"{filename}: jobs: missing"]
    tail = source[jobs.end():]
    boundary = ROOT_KEY.search(tail)
    if boundary:
        tail = tail[:boundary.start()]
    indices = list(JOB_KEY.finditer(tail))
    if not indices:
        return [f"{filename}: no parseable jobs"]
    for index, match in enumerate(indices):
        job_name = match.group(1)
        body = tail[match.end():indices[index + 1].start() if index + 1 < len(indices) else len(tail)]
        labels = RUNNER_KEY.findall(body)
        identifier = f"{filename}/{job_name}"
        if not labels:
            if not USES_KEY.search(body):
                errors.append(f"{identifier}: runs-on missing (or unsupported YAML formatting)")
            continue
        if len(labels) != 1:
            errors.append(f"{identifier}: exactly one runs-on key is required")
            continue
        value = labels[0].split(" #", 1)[0].strip().strip("\"'")
        if value == "ubuntu-slim":
            continue
        if value == "ubuntu-24.04" and identifier in LEGACY_STANDARD_JOBS:
            continue
        errors.append(
            f"{identifier}: runner {value!r} is not allowed. "
            "New jobs must use ubuntu-slim; Standard requires documented exception "
            "and review, not an unapproved fallback."
        )
    return errors


def scan(root: Path) -> list[str]:
    folder = root / ".github" / "workflows"
    if not folder.is_dir():
        return ["Missing .github/workflows directory"]
    errors: list[str] = []
    files = sorted(list(folder.glob("*.yml")) + list(folder.glob("*.yaml")))
    if not files:
        return ["No workflows found"]
    for item in files:
        errors.extend(evaluate(item.read_text(encoding="utf-8"), item.name))
    return errors


if __name__ == "__main__":
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
    issues = scan(root)
    for issue in issues:
        print("RUNNER_POLICY_ERROR", issue, file=sys.stderr)
    if issues:
        raise SystemExit(1)
    print("RUNNER_POLICY_PASS: all jobs either ubuntu-slim or explicitly grandfathered")
