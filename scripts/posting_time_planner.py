#!/usr/bin/env python3
"""Select research-backed *proposed* campaign times, never Buffer schedules.

The findings below are population-level 2026 Buffer benchmarks, NOT a claim
about Josef's followers. Existing manifests and scheduling requests reserve
timeslots; this module reads them but never writes to either directory.
"""

from __future__ import annotations

import json
import re
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo


BERLIN = ZoneInfo("Europe/Berlin")
TARGETS = ("linkedin", "facebook", "instagram")
MIN_REVIEW_DAYS = 5
MAX_LOOKAHEAD_DAYS = 56  # Extend when the 35-day window is filled by immutable reservations
MIN_CHANNEL_GAP = timedelta(days=3)
UTC_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")

# (weekday with Monday=0, local hour), ranked editorial pilot candidates.
# Independently checked Buffer AND Sprout Social 2026 data on 2026-10-12.
# Different source populations disagree, especially Facebook overall;
# Sprout's Software & Tech segment also supports weekday mornings.
# These are audience-level hypotheses, not Josef's own engagement statistics.
SLOTS = {
    "linkedin": ((2, 16), (3, 17), (1, 16), (2, 15)),
    "facebook": ((3, 9), (2, 8), (1, 8), (4, 8)),
    "instagram": ((2, 18), (2, 12), (1, 19)),
}

RESEARCH_CHECKED_AT = date(2026, 10, 12)
RESEARCH_URLS = {
    "linkedin": (
        "https://buffer.com/resources/best-time-to-post-on-linkedin/",
        "https://sproutsocial.com/insights/best-times-to-post-on-linkedin/",
    ),
    "facebook": (
        "https://buffer.com/resources/best-time-to-post-on-facebook/",
        "https://sproutsocial.com/insights/best-times-to-post-on-facebook/",
    ),
    "instagram": (
        "https://buffer.com/resources/when-is-the-best-time-to-post-on-instagram/",
        "https://sproutsocial.com/insights/best-times-to-post-on-instagram/",
    ),
}


class TimePlanningBlocked(ValueError):
    """Cannot safely propose a time from the available GitHub evidence."""


def require(ok: bool, message: str) -> None:
    if not ok:
        raise TimePlanningBlocked(message)


def read_json(root: Path, path: Path) -> dict:
    base = root.resolve(strict=True)
    actual = path.resolve(strict=True)
    require(actual.is_relative_to(base) and actual.is_file(), "Fremder Reservierungspfad")
    require(actual.stat().st_size <= 128_000, "Reservierungsdatei zu groß")

    def unique_keys(pairs):
        found = {}
        for key, value in pairs:
            require(key not in found, "Doppelter JSON-Schlüssel in Reservierung")
            found[key] = value
        return found

    try:
        data = json.loads(actual.read_text(encoding="utf-8"), object_pairs_hook=unique_keys)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise TimePlanningBlocked("Reservierungsdatei enthält ungültiges JSON") from exc
    require(isinstance(data, dict), "Reservierung muss JSON-Objekt sein")
    return data


def parse_utc(raw: object) -> datetime:
    require(isinstance(raw, str) and UTC_PATTERN.fullmatch(raw) is not None,
            "Reservierungszeit muss ISO-8601 UTC mit Z sein")
    try:
        return datetime.strptime(raw, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError as exc:
        raise TimePlanningBlocked("Ungültige Reservierungszeit") from exc


def load_reserved(root: Path) -> dict[str, set[datetime]]:
    """Include unapproved proposals to avoid clashes; never infer live status."""
    reserved = {target: set() for target in TARGETS}
    for path in sorted((root / "campaign-manifests").glob("*.json")):
        manifest = read_json(root, path)
        times = manifest.get("posting_times", {})
        require(isinstance(times, dict), "Zeitwerte in vorhandenem Manifest ungültig")
        for target, record in times.items():
            if target not in TARGETS:
                continue
            require(isinstance(record, dict), "Zeitwert in vorhandenem Manifest ungültig")
            reserved[target].add(parse_utc(record.get("utc")))

    for path in sorted((root / "ready-to-schedule").glob("*.json")):
        request = read_json(root, path)
        target = request.get("target")
        if target in TARGETS:
            reserved[target].add(parse_utc(request.get("publish_at_utc")))
    return reserved


def propose_times(
    today: date, root: Path, *, research_checked_at: date = RESEARCH_CHECKED_AT
) -> dict[str, dict[str, str]]:
    """Return Berlin + UTC; stop if independent research is older than 30 days."""
    require(isinstance(today, date) and not isinstance(today, datetime), "today muss Datum sein")
    require(isinstance(research_checked_at, date)
            and not isinstance(research_checked_at, datetime)
            and 0 <= (today - research_checked_at).days <= 30,
            "Postingzeiten-Recherche aelter als 30 Tage oder aus der Zukunft")
    require(set(RESEARCH_URLS) == set(TARGETS), "Quellennachweise je Kanal fehlen")
    for target in TARGETS:
        references = RESEARCH_URLS[target]
        require(len(references) >= 2
                and any("buffer.com/" in uri for uri in references)
                and any("sproutsocial.com/" in uri for uri in references),
                f"Zwei unabhängige Postingzeiten-Studien fehlen: {target}")
    earliest = today + timedelta(days=MIN_REVIEW_DAYS)
    cutoff = today + timedelta(days=MAX_LOOKAHEAD_DAYS)
    reserved = load_reserved(root)
    result = {}

    for target in TARGETS:
        ranked = []
        for day_offset in range((cutoff - earliest).days + 1):
            day = earliest + timedelta(days=day_offset)
            for rank, (weekday, hour) in enumerate(SLOTS[target]):
                if day.weekday() != weekday:
                    continue
                local = datetime.combine(day, time(hour), tzinfo=BERLIN)
                proposed_utc = local.astimezone(timezone.utc)
                if any(abs(proposed_utc - old) < MIN_CHANNEL_GAP
                       for old in reserved[target]):
                    continue
                # One preferred-slot tier is worth eight days of waiting.
                # This gives a stronger slot some priority without making a
                # campaign wait weeks for an already crowded primary slot.
                penalty = 8 * rank + day_offset
                ranked.append((penalty, day, rank, proposed_utc, local))

        require(bool(ranked), f"Kein konfliktfreies Zeitfenster für {target} in {MAX_LOOKAHEAD_DAYS} Tagen")
        _, _, _, proposed_utc, local = min(ranked)
        result[target] = {
            "local": local.isoformat(timespec="seconds"),
            "utc": proposed_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
    return result
