#!/usr/bin/env python3
"""Select short-horizon, research-backed *proposed* campaign times.

The findings below are population-level 2026 Buffer benchmarks, NOT a claim
about Josef's followers. GitHub campaign manifests and scheduling requests
are historical proposals, not proof that a slot is occupied in Buffer.
Only a separately verified live Buffer queue may block slots. Without one,
the resulting dates are tentative and require a live queue check before
activation. This module never publishes or changes Buffer posts.
"""

from __future__ import annotations

import re
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo


BERLIN = ZoneInfo("Europe/Berlin")
TARGETS = ("linkedin", "facebook", "instagram")
MIN_REVIEW_DAYS = 5
MAX_LOOKAHEAD_DAYS = 21  # Never silently push a new campaign months into the future
MIN_CHANNEL_GAP = timedelta(days=3)


def editorial_day_allowed(day: date, *, blackouts: frozenset[date] = frozenset()) -> bool:
    """Only explicitly supplied editorial blackouts apply; SLOTS filters weekdays."""
    return day not in blackouts

UTC_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")

# (weekday with Monday=0, local hour), ranked editorial pilot candidates.
# Rechecked independently on 2026-11-20: Buffer (Sep/Oct 2026) and
# Sprout Social (Mar 2026), with differing Facebook peak-hour findings.
# Different source populations disagree, especially Facebook overall;
# Sprout's Software & Tech segment also supports weekday mornings.
# These are audience-level hypotheses, not Josef's own engagement statistics.
SLOTS = {
    "linkedin": ((2, 16), (3, 17), (1, 16), (2, 15)),
    "facebook": ((3, 9), (2, 8), (1, 8), (4, 8)),
    "instagram": ((2, 18), (2, 12), (1, 19)),
}

RESEARCH_CHECKED_AT = date(2026, 11, 20)
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


def parse_utc(raw: object) -> datetime:
    require(isinstance(raw, str) and UTC_PATTERN.fullmatch(raw) is not None,
            "Reservierungszeit muss ISO-8601 UTC mit Z sein")
    try:
        return datetime.strptime(raw, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError as exc:
        raise TimePlanningBlocked("Ungültige Reservierungszeit") from exc


def load_reserved(
    root: Path, *, verified_buffer_slots: dict[str, list[str]] | None = None
) -> dict[str, set[datetime]]:
    """Use only times independently verified as scheduled in live Buffer.

    ``root`` is kept for caller compatibility. Neither historical manifests
    nor approved GitHub requests certify the current Buffer queue. The caller
    must obtain ``verified_buffer_slots`` from a current Buffer readback; no
    data means no asserted occupancy, not proof that the queue is empty.
    """
    require(isinstance(root, Path), "Projektpfad fehlt")
    reserved = {target: set() for target in TARGETS}
    if verified_buffer_slots is None:
        return reserved
    require(isinstance(verified_buffer_slots, dict)
            and set(verified_buffer_slots).issubset(TARGETS),
            "Live-Buffer-Belegung hat ungültige Kanäle")
    for target, times in verified_buffer_slots.items():
        require(isinstance(times, list), "Live-Buffer-Zeiten müssen eine Liste sein")
        for raw in times:
            reserved[target].add(parse_utc(raw))
    return reserved


def propose_times(
    today: date, root: Path, *, research_checked_at: date = RESEARCH_CHECKED_AT,
    verified_buffer_slots: dict[str, list[str]] | None = None,
    blackouts: frozenset[date] = frozenset(),
) -> dict[str, dict[str, str]]:
    """Return tentative Berlin + UTC; stop if research is older than 30 days.

    A caller without a verified live queue MUST recheck Buffer before using
    the proposal to schedule anything. Proposals alone never reserve slots.
    """
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
    require(isinstance(blackouts, frozenset)
            and all(isinstance(d, date) and not isinstance(d, datetime) for d in blackouts),
            "Redaktionssperren müssen ein Datums-Set sein")
    reserved = load_reserved(root, verified_buffer_slots=verified_buffer_slots)
    result = {}

    for target in TARGETS:
        ranked = []
        for day_offset in range((cutoff - earliest).days + 1):
            day = earliest + timedelta(days=day_offset)
            if not editorial_day_allowed(day, blackouts=blackouts):
                continue
            for rank, (weekday, hour) in enumerate(SLOTS[target]):
                if day.weekday() != weekday:
                    continue
                local = datetime.combine(day, time(hour), tzinfo=BERLIN)
                proposed_utc = local.astimezone(timezone.utc)
                if any(abs(proposed_utc - old) < MIN_CHANNEL_GAP
                       for old in reserved[target]):
                    continue
                # Prefer researched primary slots but penalize a weaker tier
                # by only three days; never skip weeks for a minor preference.
                penalty = 3 * rank + day_offset
                ranked.append((penalty, rank, proposed_utc, local))

        require(bool(ranked), f"Kein konfliktfreies Zeitfenster für {target} in {MAX_LOOKAHEAD_DAYS} Tagen; Buffer prüfen")
        _, _, proposed_utc, local = min(ranked)
        result[target] = {
            "local": local.isoformat(timespec="seconds"),
            "utc": proposed_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
    return result
