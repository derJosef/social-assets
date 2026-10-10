#!/usr/bin/env python3
"""Fail-closed quality gate for autonomous AI Agent Builder Buffer drafts.

This does NOT call Buffer. It is run once for the complete newly-added
three-platform campaign BEFORE any network mutation of Buffer is allowed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from buffer_draft import read_draft

ROOT = Path(__file__).resolve().parents[1]
BRAND = "ai-agent-builder"
TARGETS = ("linkedin", "facebook", "instagram")
NAME_RE = re.compile(
    r"^ready-for-buffer/auto-(20\d{2}-\d{2}-\d{2})-([a-z0-9]+(?:-[a-z0-9]+)*)-(linkedin|facebook|instagram)\.json$"
)
REQUIRED_CHECKS = (
    "novelty", "claims_with_sources", "language_and_cta", "six_hats",
    "privacy_and_rights", "brand_image", "posting_time_research"
)
IMG_BASE = "https://raw.githubusercontent.com/derJosef/social-assets/main/"
HEADING_CORNERS = {"top-left", "top-right", "bottom-left", "bottom-right"}
PATH_IMG_RE = re.compile(r"^media/images/[a-zA-Z0-9][a-zA-Z0-9_.-]{0,119}\.png$")
PATH_BASE_RE = re.compile(r"^media/source-images/[a-zA-Z0-9][a-zA-Z0-9_.-]{0,119}\.png$")


def require(ok: bool, reason: str) -> None:
    if not ok:
        raise ValueError(reason)


def require_file(name: str) -> Path:
    p = (ROOT / name).resolve(strict=True)
    require(p.is_relative_to(ROOT) and p.is_file(), "Datei fehlt/ausserhalb des Repositorys: " + name)
    return p


def parse_utc(value: str) -> datetime:
    require(isinstance(value, str) and bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", value)),
            "publish_at_utc muss YYYY-MM-DDTHH:MM:SSZ sein")
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def check_campaign(post_paths: list[str], today: date | None = None, verify_image: bool = True) -> dict:
    today = today or datetime.now(timezone.utc).date()
    require(len(post_paths) == 3 and len(set(post_paths)) == 3,
            "Jede automatische Kampagne benoetigt genau drei eindeutige Plattformbeitraege")
    matched = [NAME_RE.fullmatch(p) for p in post_paths]
    require(all(matched), "Nur neue auto-Draft-Dateinamen erlaubt")
    date_slug = {(m.group(1), m.group(2)) for m in matched}
    require(len(date_slug) == 1, "Alle drei Posts muessen derselben Kampagne zugeordnet sein")
    stamp, slug = next(iter(date_slug))
    require({m.group(3) for m in matched} == set(TARGETS), "linkedin/facebook/instagram genau einmal erforderlich")
    campaign = f"{stamp}-{slug}"
    manifest_path = f"campaign-manifests/{campaign}.json"
    manifest = json.loads(require_file(manifest_path).read_text(encoding="utf-8"))
    require(isinstance(manifest, dict), "Manifest ist kein JSON-Objekt")
    require(set(manifest) == {
        "format_version", "brand", "campaign_id", "checked_at", "sources",
        "checks", "image", "posts", "posting_times"
    }, "Falsche Manifest-Schluessel")
    require(manifest["format_version"] == 1 and manifest["brand"] == BRAND
            and manifest["campaign_id"] == campaign, "Brand/Campaign-ID passt nicht")
    checked = date.fromisoformat(manifest["checked_at"])
    require(timedelta(days=0) <= today - checked <= timedelta(days=30),
            "Recherche-/QA-Nachweis fehlt, ist veraltet oder liegt in der Zukunft")
    sources = manifest["sources"]
    require(isinstance(sources, list) and len(sources) >= 2,
            "Mindestens zwei externe, belegte Recherchequellen erforderlich")
    domains = set()
    for source in sources:
        require(isinstance(source, dict) and set(source) == {"url", "published_at", "checked_at"},
                "Quellen brauchen url, published_at und checked_at")
        u = urlsplit(source["url"])
        require(u.scheme == "https" and bool(u.netloc) and not u.username and not u.password,
                "Nur direkte HTTPS-Quellen")
        require(u.netloc.lower() not in ("github.com", "raw.githubusercontent.com", "buffer.com"),
                "Keine bloessen Asset-/Plattformlinks als Recherchequellen")
        domains.add(u.netloc.lower())
        published = date.fromisoformat(source["published_at"])
        source_checked = date.fromisoformat(source["checked_at"])
        require(published <= source_checked <= today, "Unplausible Quelle: Publikations- oder Abrufdatum")
    require(len(domains) >= 2, "Mindestens zwei voneinander getrennte Quellen-Domains")
    checks = manifest["checks"]
    require(isinstance(checks, dict) and set(checks) == set(REQUIRED_CHECKS)
            and all(checks[k] is True for k in REQUIRED_CHECKS),
            "Einer oder mehrere fachliche/markenbezogene QA-Nachweise fehlen")
    entries = manifest["posts"]
    require(isinstance(entries, dict) and set(entries) == set(TARGETS)
            and set(entries.values()) == set(post_paths), "Post-Zuordnung im Manifest falsch")
    image = manifest["image"]
    require(isinstance(image, dict), "Unvollstaendiger Bildnachweis")
    legacy_keys={"final","base","sha256","heading_corner","heading_box"}
    new_keys=legacy_keys | {"layout","review_spec","source_sha256"}
    require(set(image) in (legacy_keys,new_keys),
            "Unerwartete Bildmetadaten: kein ungeprueftes Layout zulassen")
    require(isinstance(image["final"], str) and PATH_IMG_RE.fullmatch(image["final"]),
            "Finales Bild muss PNG unter media/images/ sein")
    require(isinstance(image["base"], str) and PATH_BASE_RE.fullmatch(image["base"]),
            "Logo-freies Basisbild unter media/source-images/ erforderlich")
    new_format=set(image)==new_keys
    if new_format:
        from social_portfolio_scene import validate_spec
        review_path=image["review_spec"]
        require(isinstance(review_path,str) and review_path==f"visual-reviews/{campaign}.json",
                "Review muss exakt zur Kampagne gehoeren")
        source_spec=json.loads(require_file(review_path).read_text(encoding="utf-8"))
        try:
            source=validate_spec(source_spec,ROOT)
        except (ValueError,OSError) as e:
            raise ValueError(f"Visuelle Quellfreigabe ungueltig: {e}") from e
        require(source_spec["layout"]==image["layout"],
                "Review-Layout und Manifest widersprechen sich")
        require(image["layout"] in ("logo_only","headline"),
                "Unbekannter 4:5-Modus")
        require(image["source_sha256"]==source_spec["source_sha256"]
                and hashlib.sha256(source.read_bytes()).hexdigest()==image["source_sha256"],
                "Unguenstiger Bildquellenfingerabdruck")
        from PIL import Image
        with Image.open(require_file(image["final"])) as fp:
            require(fp.size==(1080,1350),"4:5-PNG muss 1080x1350 sein")
        if image["layout"]=="logo_only":
            require(image["heading_corner"] is None and image["heading_box"] is None,
                    "Logo-only braucht keine Fake-Ueberschrift")
        else:
            require(image["heading_corner"] in HEADING_CORNERS
                    and isinstance(image["heading_box"],list)
                    and len(image["heading_box"])==4
                    and all(type(v) is int and v>=0 for v in image["heading_box"]),
                    "Headline muss korrektes Bounding-Box-Format haben")
    else:
        require(image["heading_corner"] in HEADING_CORNERS
                and isinstance(image["heading_box"], list)
                and len(image["heading_box"]) == 4
                and all(type(v) is int and v >= 0 for v in image["heading_box"]),
                "Legacy Heading-Box/Ecke fehlt")
    final = require_file(image["final"])
    require_file(image["base"])
    digest = hashlib.sha256(final.read_bytes()).hexdigest()
    require(re.fullmatch(r"[a-f0-9]{64}", str(image["sha256"])) is not None
            and digest == image["sha256"], "Bildpruefsumme stimmt nicht")
    if verify_image:
        cmd = [
            sys.executable, str(ROOT / "scripts/logo_composite.py"), "verify",
            image["final"], image["base"], "--original",
            "media/brand/logo-pauderer-original.png"
        ]
        if not new_format or image["layout"]=="headline":
            cmd.extend(["--heading-corner",image["heading_corner"],
                        "--heading-box",",".join(str(n) for n in image["heading_box"])])
        subprocess.run(cmd, cwd=ROOT, check=True)
    for target in TARGETS:
        filename = entries[target]
        relative, _, raw = read_draft(filename)
        require(relative == filename, "Unzulaessiger Buffer-Post-Pfad")
        item = json.loads(raw)
        require(item["format_version"] == 2 and item["target"] == target,
                "Plattform/Format falsch")
        media = item["media"]
        require(media["type"] == "images" and len(media["images"]) == 1
                and media["images"][0]["url"] == IMG_BASE + image["final"],
                "Nur das zuvor verifizierte Original-Logo-Bild ist zulaessig")
    times = manifest["posting_times"]
    require(isinstance(times, dict) and set(times) == set(TARGETS), "Drei Plattformzeiten erforderlich")
    for target in TARGETS:
        t = times[target]
        require(isinstance(t, dict) and set(t) == {"local", "utc"},
                "Zeitnachweis benoetigt local und utc")
        local = datetime.fromisoformat(t["local"])
        require(local.tzinfo is not None, "Lokaler Termin muss Zeitzonen-Offset haben")
        tz = ZoneInfo("Europe/Berlin")
        proposed = parse_utc(t["utc"])
        require(local.astimezone(timezone.utc) == proposed
                and proposed.astimezone(tz).isoformat(timespec="seconds") == local.isoformat(timespec="seconds"),
                "Fehler bei Europe/Berlin-Zeitzone oder Sommerzeit")
        require(proposed > datetime.now(timezone.utc) + timedelta(minutes=10),
                "Terminvorschlag muss mindestens zehn Minuten in der Zukunft liegen")
    return {"campaign": campaign, "targets": list(TARGETS), "image_sha256": digest,
            "status": "eligible_for_draft_only", "scheduling": "proposal_only"}


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--posts", nargs="+", required=True)
    args = p.parse_args()
    try:
        info = check_campaign(args.posts)
        print("AUTONOMOUS_DRAFT_GATE PASS:", json.dumps(info, ensure_ascii=False))
        print("WICHTIG: ausschliesslich Buffer-Entwuerfe; weder Scheduling noch Publish.")
        return 0
    except (ValueError, KeyError, TypeError, OSError, subprocess.CalledProcessError) as e:
        print(f"AUTONOMOUS_DRAFT_GATE BLOCKED: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
