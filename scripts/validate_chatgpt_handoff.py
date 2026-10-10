#!/usr/bin/env python3
"""Offline preflight for a ChatGPT-created campaign brief on a review branch.

This is a STRUCTURAL check. It never marks external claims as fact-checked.
It does not call Buffer or a model, make HTTP requests, or publish anything.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from social_orchestrator import load_brief, assess_generated, available, Blocked

BRIEF = re.compile(r"^orchestration/briefs/20\d{2}-\d{2}-\d{2}-[a-z0-9]+(?:-[a-z0-9]+)*\.json$")

def validate(relative_path: str, root: Path = ROOT) -> dict:
    if not BRIEF.fullmatch(relative_path):
        raise ValueError("Nur datierte Kampagnenaufträge direkt unter orchestration/briefs/ zulässig")
    location = (root / relative_path).resolve(strict=True)
    if not location.is_relative_to(root.resolve()) or not location.is_file():
        raise ValueError("Ungültige Brief-Datei")
    if location.stat().st_size > 75_000:
        raise ValueError("Öffentlicher Auftrag zu umfangreich")
    import social_orchestrator
    original = social_orchestrator.ROOT
    try:
        social_orchestrator.ROOT = root
        data = load_brief(relative_path)
        if data.get("execution_mode") != "drafts":
            raise ValueError("Handoff muss ausdrücklich drafts fordern")
        if "prepared_content" not in data:
            raise ValueError("ChatGPT-Abo-Übergabe erfordert bereits fertig redigierte Texte")
        assess_generated(data["prepared_content"])
        available(data["campaign_id"])
    finally:
        social_orchestrator.ROOT = original
    return {
        "status": "offline_structure_pass",
        "campaign_id": data["campaign_id"],
        "platforms": ["linkedin", "facebook", "instagram"],
        "automatic_publication": False,
        "note": "Struktur geprüft; keine inhaltliche Faktenbestätigung und keine Buffer-Aktion."
    }

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--brief",required=True)
    args=p.parse_args()
    try:
        print(json.dumps(validate(args.brief),ensure_ascii=False))
        return 0
    except (ValueError, KeyError, TypeError, OSError, Blocked) as err:
        print("HANDOFF BLOCKED:",type(err).__name__,str(err)[:250],file=sys.stderr)
        return 1

if __name__=="__main__":
    raise SystemExit(main())
