#!/usr/bin/env python3
"""Strict draft-only no-heading verification using the unchanged logo compositor.

This is a *separate* verification profile under review, NOT a change to the
canonical PersonalOS/logo_composite implementation and not production approval.
The sole inapplicable headline-presence check must be explicitly accounted for;
all other canonical checks must pass, with no unexpected skips or omissions.
"""
from __future__ import annotations

import json
from pathlib import Path

from PIL import Image

from logo_composite import PNG_KEY, Placement, LogoError, verify_files

SIZE = (1080, 1350)
HEADING_CHECK = "Ueberschrift sichtbar, ohne Ueberlagerung, in der Ueberschriftsecke"
# Canonical check names are a locked interface. Drift in the upstream verifier
# is a reason to refuse, not to silently relax this gate.
REQUIRED_CHECKS = frozenset({
    "Originalvorlage",
    "Seitenverhaeltnis",
    "Bildgroesse",
    "Logo unveraendert (Innenformen, Farben, Rahmen)",
    "Weisser Aussenrahmen gleichmaessig",
    "Uebrige Bildinhalte unveraendert",
    "Logo vollstaendig sichtbar",
    "Sicherheitsabstand zum Bildrand",
    "Logo diagonal gegenueber der Hauptueberschrift",
})


class LogoOnlyError(ValueError):
    """The explicitly reviewed no-heading variant did not pass strict QA."""


def verify_logo_only(final: Path, base: Path, original: Path) -> dict:
    with Image.open(final) as im:
        if im.size != SIZE:
            raise LogoOnlyError("Final image must be exactly 1080x1350")
        raw = im.text.get(PNG_KEY)
        if raw is None:
            raise LogoOnlyError("Missing authentic logo placement metadata")
        try:
            placement = Placement(**json.loads(raw))
        except (TypeError, KeyError, ValueError, json.JSONDecodeError) as exc:
            raise LogoOnlyError("Invalid placement metadata") from exc
    if placement.canvas_width != SIZE[0] or placement.canvas_height != SIZE[1]:
        raise LogoOnlyError("Inconsistent stored canvas size")
    if placement.heading_corner != "top-left" or placement.logo_corner != "bottom-right":
        raise LogoOnlyError("Logo-only composition must place original logo bottom-right")
    if not placement.frame or placement.stroke < 1:
        raise LogoOnlyError("The authentic logo must have its verified white outer border")
    with Image.open(base) as im:
        if im.size != SIZE:
            raise LogoOnlyError("Base image must be exactly 1080x1350")
    try:
        code, checks = verify_files(final, base, original, heading_box=None)
    except (LogoError, OSError, ValueError, KeyError, TypeError) as exc:
        raise LogoOnlyError("Canonical verification could not complete") from exc
    result = {c.name: c.status for c in checks}
    if len(checks) != len(REQUIRED_CHECKS) + 1 or len(result) != len(checks):
        raise LogoOnlyError("Canonical verifier changed: unknown, missing or duplicate checks")
    if set(result) != REQUIRED_CHECKS | {HEADING_CHECK}:
        raise LogoOnlyError("Canonical verifier checks have changed")
    if result[HEADING_CHECK] != "skipped" or code != 2:
        raise LogoOnlyError("No-heading profile must explicitly account for absent heading")
    failures = {k: v for k, v in result.items() if k != HEADING_CHECK and v != "ok"}
    if failures:
        raise LogoOnlyError(f"Logo authenticity/geometry checks failed: {failures}")
    # A skipped heading check is not a PASS from the canonical verifier:
    # this gate accepts *only* the user-approved no-heading design profile.
    return {"profile": "logo_only", "size": list(SIZE), "logo_corner": "bottom-right",
            "canonical_checks_passed": len(REQUIRED_CHECKS),
            "not_applicable": [HEADING_CHECK], "status": "verified_logo_only_draft"}


if __name__ == "__main__":
    raise SystemExit("Use from social_portfolio_scene.py; no standalone publishing action")
