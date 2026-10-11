#!/usr/bin/env python3
"""Render an existing campaign manifest for human review, entirely offline.

This script never approves a campaign, calls Buffer, schedules or publishes.
The existing manifest remains the single source of proposed posting times.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[1]
BERLIN = ZoneInfo("Europe/Berlin")
TARGETS = ("linkedin", "facebook", "instagram")
CAMPAIGN_RE = re.compile(r"^20\d{2}-\d{2}-\d{2}-[a-z0-9]+(?:-[a-z0-9]+)*$")
MANIFEST_RE = re.compile(r"^campaign-manifests/(20\d{2}-\d{2}-\d{2}-[a-z0-9]+(?:-[a-z0-9]+)*)\.json$")
SHA_RE = re.compile(r"^[0-9a-f]{64}$")
IMAGE_RE = re.compile(r"^media/images/[a-zA-Z0-9][a-zA-Z0-9_.-]{0,119}\.png$")
MAX_READ = 128_000


class PreviewBlocked(ValueError):
    """Invalid or ambiguous preview input; no data is changed."""


def require(condition: bool, reason: str) -> None:
    if not condition:
        raise PreviewBlocked(reason)


def read_file(root: Path, relative: str, max_bytes: int = MAX_READ) -> bytes:
    base = root.resolve(strict=True)
    target = (base / relative).resolve(strict=True)
    require(target.is_relative_to(base) and target.is_file(), "Unzulässiger Datei-Pfad")
    require(target.stat().st_size <= max_bytes, "Datei zu groß")
    return target.read_bytes()


def parse_json(raw: bytes) -> dict:
    def unique(pairs: list[tuple[str, object]]) -> dict:
        result = {}
        for name, value in pairs:
            require(name not in result, "Doppelter JSON-Schlüssel")
            result[name] = value
        return result

    try:
        data = json.loads(raw.decode("utf-8"), object_pairs_hook=unique)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PreviewBlocked("Ungültiges JSON") from exc
    require(isinstance(data, dict), "JSON-Objekt erforderlich")
    return data


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def parse_time(value: dict, now: datetime) -> tuple[datetime, str]:
    require(isinstance(value, dict) and set(value) == {"local", "utc"},
            "Termin braucht genau local und utc")
    local_raw, utc_raw = value["local"], value["utc"]
    require(isinstance(local_raw, str) and isinstance(utc_raw, str), "Ungültiger Termin")
    require(re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d[+-]\d\d:\d\d", local_raw) is not None,
            "Lokaler Termin muss Offset und Sekunden enthalten")
    require(re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", utc_raw) is not None,
            "UTC-Zeit muss mit Z enden")
    try:
        local = datetime.fromisoformat(local_raw)
        utc = datetime.fromisoformat(utc_raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise PreviewBlocked("Nicht interpretierbares Datum") from exc
    require(local.utcoffset() is not None and local == utc,
            "Berlin- und UTC-Zeit passen nicht zusammen")
    berlin = utc.astimezone(BERLIN)
    require(local == berlin and local.utcoffset() == berlin.utcoffset(),
            "Ungültiger Berlin-Offset / Sommer- oder Winterzeit")
    require(utc > now, "Terminvorschlag liegt in der Vergangenheit")
    return berlin, utc_raw


def check_collisions(root: Path, campaign: str, proposals: list[dict]) -> None:
    """Conservatively reject reused slots, without claiming live Buffer availability."""
    reserved = []
    for path in sorted((root / "campaign-manifests").glob("*.json")):
        if path.stem == campaign:
            continue
        prior = parse_json(read_file(root, f"campaign-manifests/{path.name}"))
        for target, times in (prior.get("posting_times") or {}).items():
            if target in TARGETS and isinstance(times, dict):
                utc_raw = times.get("utc")
                require(isinstance(utc_raw, str) and re.fullmatch(
                    r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", utc_raw) is not None,
                    "Zeitangabe in anderem Manifest ungültig")
                reserved.append((target, datetime.fromisoformat(utc_raw.replace("Z", "+00:00")), path.name))
    for path in sorted((root / "ready-to-schedule").glob("*.json")):
        request = parse_json(read_file(root, f"ready-to-schedule/{path.name}"))
        target, utc_raw = request.get("target"), request.get("publish_at_utc")
        if target not in TARGETS:
            continue
        require(isinstance(utc_raw, str) and re.fullmatch(
            r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", utc_raw) is not None,
            "Zeitangabe in Terminierungsauftrag ungültig")
        reserved.append((target, datetime.fromisoformat(utc_raw.replace("Z", "+00:00")), path.name))
        for proposal in proposals:
            require(request.get("draft_file") != proposal["draft_file"],
                    "Für diesen Entwurf existiert bereits ein Terminierungsauftrag; Buffer gesondert prüfen")
    for proposal in proposals:
        utc = datetime.fromisoformat(proposal["utc"].replace("Z", "+00:00"))
        for target, other, source in reserved:
            require(target != proposal["target"] or abs(utc - other) >= timedelta(minutes=90),
                    f"Zeitkollision für {target} mit {source}")


def inspect(root: Path, manifest_path: str, now: datetime | None = None) -> dict:
    match = MANIFEST_RE.fullmatch(manifest_path)
    require(match is not None, "Nur Einzelmanifest unter campaign-manifests/ erlaubt")
    campaign = match.group(1)
    require(CAMPAIGN_RE.fullmatch(campaign) is not None, "Kampagnenname ungültig")
    timestamp = now or datetime.now(timezone.utc)
    require(timestamp.tzinfo is not None, "now muss mit Zeitzone übergeben werden")

    manifest_raw = read_file(root, manifest_path)
    manifest = parse_json(manifest_raw)
    require(manifest.get("campaign_id") == campaign and manifest.get("brand") == "ai-agent-builder",
            "Manifest gehört nicht zur erwarteten AI-Agent-Builder-Kampagne")
    posts, timings = manifest.get("posts"), manifest.get("posting_times")
    require(isinstance(posts, dict) and set(posts) == set(TARGETS),
            "Alle drei Plattform-Drafts müssen vorhanden sein")
    require(isinstance(timings, dict) and set(timings) == set(TARGETS),
            "Alle drei Terminvorschläge müssen vorhanden sein")

    image = manifest.get("image")
    require(isinstance(image, dict) and isinstance(image.get("final"), str)
            and IMAGE_RE.fullmatch(image["final"]) is not None,
            "Ungültiger Bildpfad")
    require(isinstance(image.get("sha256"), str) and SHA_RE.fullmatch(image["sha256"]) is not None,
            "Ungültiger Bild-Fingerprint")
    require(digest(read_file(root, image["final"], 20_000_000)) == image["sha256"],
            "Bild wurde gegenüber dem Manifest verändert")

    proposals = []
    for target in TARGETS:
        path = f"ready-for-buffer/auto-{campaign}-{target}.json"
        require(posts[target] == path, f"Entwurf für {target} falsch zugeordnet")
        draft_raw = read_file(root, path)
        draft = parse_json(draft_raw)
        require(draft.get("target") == target and draft.get("format_version") == 2,
                f"Ungültiger Entwurf für {target}")
        require(isinstance(draft.get("text"), str) and draft["text"].strip(),
                f"Beitragstext für {target} fehlt")
        media = draft.get("media")
        expected_url = f"https://raw.githubusercontent.com/derJosef/social-assets/main/{image['final']}"
        require(isinstance(media, dict) and media.get("type") == "images"
                and isinstance(media.get("images"), list) and len(media["images"]) == 1
                and isinstance(media["images"][0], dict)
                and media["images"][0].get("url") == expected_url,
                f"Bild im {target}-Entwurf passt nicht zum geprüften Kampagnenbild")
        local, utc_raw = parse_time(timings[target], timestamp)
        proposals.append({
            "target": target, "draft_file": path, "draft_sha256": digest(draft_raw),
            "text": draft["text"], "local": local.isoformat(timespec="seconds"),
            "utc": utc_raw,
        })
    check_collisions(root, campaign, proposals)

    # A live status cannot be inferred from GitHub files; even a receipt may be stale.
    return {"campaign_id": campaign, "manifest_sha256": digest(manifest_raw),
            "image": image["final"], "image_sha256": image["sha256"],
            "posts": proposals, "review_state": "PROPOSAL_ONLY"}


def render_markdown(review: dict) -> str:
    lines = [
        f"# Termin- und Beitragsvorschau – {review['campaign_id']}", "",
        "> **NICHT FREIGEGEBEN.** Diese Vorschau ist kein Buffer-Status, keine Brief-Freigabe,",
        "> keine Terminierung und keine Veröffentlichungsfreigabe.", "",
        "## Terminvorschläge (Europe/Berlin)", "",
        "| Plattform | Datum und Uhrzeit in Berlin | UTC |", "| --- | --- | --- |",
    ]
    for post in review["posts"]:
        dt = datetime.fromisoformat(post["local"])
        label = "LinkedIn" if post["target"] == "linkedin" else post["target"].title()
        lines.append(f"| {label} | {dt:%d.%m.%Y %H:%M} "
                     f"({'MESZ' if dt.utcoffset() == timedelta(hours=2) else 'MEZ'}) "
                     f"| `{post['utc']}` |")
    lines.extend(["", "## Bildvorschau", "",
                  f"![Kampagnenbild](https://raw.githubusercontent.com/derJosef/social-assets/main/{review['image']})", "",
                  f"Bild-SHA256: `{review['image_sha256']}`", "",
                  "## Texte zur Prüfung", ""])
    for post in review["posts"]:
        label = "LinkedIn" if post["target"] == "linkedin" else post["target"].title()
        lines.extend([f"### {label}", "", post["text"], "",
                      f"Entwurf: `{post['draft_file']}`", "",
                      f"Entwurfs-SHA256: `{post['draft_sha256']}`", ""])
    lines.extend(["## Technische Bindung", "",
                  f"Manifest-SHA256: `{review['manifest_sha256']}`", "",
                  "**Nächster Schritt:** Der fertige Plan kann Josef zur Entscheidung vorgelegt werden.",
                  "Erst seine gesonderte, überprüfbare Termin- und Veröffentlichungsfreigabe",
                  "darf einen anderen Workflow zum Einplanen in Buffer berechtigen.",
                  "Dieses Skript hat weder Buffer- noch GitHub-Schreibfunktionen.", ""])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Kampagne und Termine offline als Markdown prüfen")
    parser.add_argument("--manifest", required=True)
    args = parser.parse_args()
    try:
        print(render_markdown(inspect(ROOT, args.manifest)))
        return 0
    except (PreviewBlocked, OSError, KeyError, TypeError, ValueError) as exc:
        print(f"VORSCHAU_BLOCKIERT: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
