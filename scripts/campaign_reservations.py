#!/usr/bin/env python3
"""Read-only import of previous automated posting slots from Git remote refs.

Output branches deliberately do not modify protected main. In a GitHub
Actions checkout on main, safely materialize only their manifests as local
untracked planning input. Never trust branch data as campaign approval.
"""
from __future__ import annotations

import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
REF_PREFIX = "refs/remotes/origin/automation/campaign/"
CID = re.compile(r"20\d{2}-\d{2}-\d{2}-[a-z0-9]+(?:-[a-z0-9]+)*")
UTC = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")
TARGETS = {"linkedin", "facebook", "instagram"}


def git_bytes(root: Path, *args: str) -> bytes:
    return subprocess.check_output(["git", *args], cwd=root, stderr=subprocess.DEVNULL)


def checked_manifest(raw: bytes, campaign: str) -> None:
    if len(raw) > 100_000:
        raise ValueError("Kampagnenmanifest im Output-Branch zu groß")
    data = json.loads(raw.decode("utf-8"))
    if not isinstance(data, dict) or data.get("brand") != "ai-agent-builder" or data.get("campaign_id") != campaign:
        raise ValueError("Fremdes oder ungebundenes Reservierungsmanifest")
    times = data.get("posting_times")
    if not isinstance(times, dict) or set(times) != TARGETS:
        raise ValueError("Reservierung braucht alle drei Plattformtermine")
    for timing in times.values():
        if not isinstance(timing, dict) or set(timing) != {"utc", "local"} or not isinstance(timing["utc"], str) or not UTC.fullmatch(timing["utc"]):
            raise ValueError("Unvollständiges Zeitformat der Reservierung")
        utc = datetime.strptime(timing["utc"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        if not isinstance(timing["local"], str):
            raise ValueError("Zeitzone der Reservierung fehlt")
        local = datetime.fromisoformat(timing["local"])
        if local.tzinfo is None or local.astimezone(timezone.utc) != utc or utc.astimezone(ZoneInfo("Europe/Berlin")) != local:
            raise ValueError("Zeitzone der historischen Kampagne passt nicht")


def import_manifests(root: Path = ROOT) -> list[str]:
    refs = git_bytes(root, "for-each-ref", "--format=%(refname)", REF_PREFIX).decode("utf-8").splitlines()
    if len(refs) > 250:
        raise ValueError("Zu viele Output-Branches: manuelle Prüfung erforderlich")
    # Prepare all candidate writes before materializing even one file.
    to_write: list[tuple[Path, bytes]] = []
    for ref in refs:
        if not ref.startswith(REF_PREFIX) or not CID.fullmatch(ref[len(REF_PREFIX):]):
            raise ValueError("Unzulässige Branch-ID im Reservierungsregister")
        campaign = ref[len(REF_PREFIX):]
        file = f"campaign-manifests/{campaign}.json"
        raw = git_bytes(root, "show", f"{ref}:{file}")
        checked_manifest(raw, campaign)
        local = root / file
        if local.exists():
            if local.read_bytes() != raw:
                raise ValueError("Widerspruch zwischen main- und Output-Manifest")
        else:
            to_write.append((local, raw))
    for path, raw in to_write:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
    return [str(path.relative_to(root)) for path, _ in to_write]


if __name__ == "__main__":
    imported = import_manifests()
    print("PRIOR_CAMPAIGN_RESERVATIONS_LOADED:", len(imported))
