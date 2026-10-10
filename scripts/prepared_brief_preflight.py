#!/usr/bin/env python3
"""Validate a ChatGPT-prepared AI Agent Builder campaign without network or Buffer.

This is the mandatory fail-closed entry gate for the low-cost prepared_content
route. It checks only structure, fingerprint, file existence and collisions,
NOT whether editorial claims are independently true.
"""
from __future__ import annotations

import argparse
import json

import social_orchestrator as orchestrator


def check_prepared(brief_path: str) -> dict:
    brief = orchestrator.load_brief(brief_path)
    orchestrator.require(brief["execution_mode"] == "drafts",
                         "Prepared handoff requires execution_mode=drafts")
    orchestrator.require("prepared_content" in brief,
                         "Variante A verlangt fertig vorbereitete Texte in prepared_content")
    orchestrator.assess_generated(brief["prepared_content"])
    orchestrator.available(brief["campaign_id"])
    review = json.loads(
        (orchestrator.ROOT / brief["image_review"]).read_text(encoding="utf-8")
    )
    report = {
        "campaign_id": brief["campaign_id"],
        "mode": "chatgpt_prepared_content",
        "status": "structure_and_image_source_checked",
        "brand": brief["brand"],
        "image_layout": review["layout"],
        "source_sha256": review["source_sha256"],
        "post_channels": list(orchestrator.TARGETS),
        "six_hats_present": True,
        "risks_documented": len(brief["prepared_content"]["risks"]),
        "model_requests": 0,
        "buffer_requests": 0,
        "scheduling_requests": 0,
        "publication_requests": 0,
        "editorial_fact_verification": "requires_separate_source_and_human_review",
    }
    return report


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--brief", required=True)
    args = p.parse_args()
    report = check_prepared(args.brief)
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
