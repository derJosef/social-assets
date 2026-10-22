#!/usr/bin/env python3
"""Fail-closed one-time provenance for the already reviewed 2026-10-21 selfie assets.

These campaigns were built and SHA/Logo-QA-verified by GitHub PR #46,
not by an Adobe-imported AIAGENT_BRIEF issue. This module NEVER creates posts.
It binds independently reviewed media and the three editorial texts to
one immutable preflight proof. No arbitrary campaign may opt in.
"""
from __future__ import annotations

import json
from pathlib import Path

ALLOWED_CAMPAIGNS = {
    "2026-10-21-fingerabdruck-selfie-01": {
        "final_sha256": "696572b6f831f2d2226c78e2861265dcf954f1be6ba6da6f746f1284919ec7ea",
        "source_sha256": "d79b4d60f4ddaaa2d110b6991f05329f5d5e42c86c59738d17675ca9eba98d19",
    },
    "2026-10-21-fingerabdruck-selfie-02": {
        "final_sha256": "05584c90aa6c66203943cd465317778da164a38a84f941ebca19078ab7ce0e61",
        "source_sha256": "4d3bcef3a0d05d58c25462db7d657f1801dd126f2dafe45638235073bfa06f61",
    },
    "2026-10-21-fingerabdruck-selfie-03": {
        "final_sha256": "536fadcac3c5d01a403c34030ccc483de73249dc8a949ff4df34b463c77e3f2e",
        "source_sha256": "473ed3e6e5816f72b71c3b5fdeacabcea7476bb78f0c230ca3d5e734c9e99a3b",
    },
}
LOGO_ORIGINAL_SHA256 = "15dc410d1a05b96c13466ddf3052ba9cc783cdd7252b74f4fb5c3f886510dea0"
PREVIOUS_ASSET_QA_RUN = "https://github.com/derJosef/social-assets/actions/runs/39618529301"
PLATFORMS = frozenset(("linkedin", "facebook", "instagram"))


class ReviewedProvenanceBlocked(ValueError):
    pass


def require(ok, message):
    if not ok:
        raise ReviewedProvenanceBlocked(message)


def checked_file(root: Path, relative: str) -> Path:
    path = (root / relative).resolve()
    require(path.is_relative_to(root.resolve()) and path.is_file(), "Belegdatei fehlt oder liegt ausserhalb des Repos")
    require(path.stat().st_size < 70_000, "Belegdatei zu gross")
    return path


def load_verified_posts(root: Path, campaign: str, evidence: dict) -> dict:
    """Return the 3 strictly matched editorial texts, never a release authority."""
    require(campaign in ALLOWED_CAMPAIGNS, "Nicht freigegebene PR-Staging-Kampagne")
    fixed = ALLOWED_CAMPAIGNS[campaign]
    path = f"reviewed-campaign-provenance/{campaign}.json"
    proof = json.loads(checked_file(root, path).read_text(encoding="utf-8"))
    require(isinstance(proof, dict) and set(proof) == {
        "format_version", "brand", "campaign_id", "execution_mode", "origin",
        "source_pr", "source_qa_run", "image_review", "image_sha256", "prepared_content"
    }, "Ungültiges begrenztes Kampagnen-Provenienzschema")
    require(proof["format_version"] == 1 and proof["brand"] == "ai-agent-builder"
            and proof["campaign_id"] == campaign and proof["execution_mode"] == "drafts"
            and proof["origin"] == "github_reviewed_existing_staged_artwork"
            and proof["source_pr"] == 46 and proof["source_qa_run"] == PREVIOUS_ASSET_QA_RUN,
            "Provenienz darf nur auf die vorher bestandene Originalbild-QA verweisen")
    review_path = f"visual-reviews/{campaign}.json"
    receipt_path = f"visual-reviews/{campaign}-build-receipt.json"
    require(proof["image_review"] == review_path, "Falscher Visual-Review-Pfad")
    review = json.loads(checked_file(root, review_path).read_text(encoding="utf-8"))
    receipt = json.loads(checked_file(root, receipt_path).read_text(encoding="utf-8"))
    require(review.get("source_sha256") == fixed["source_sha256"]
            and receipt.get("source_png_sha256") == fixed["source_sha256"],
            "Originalquellen-SHA weicht vom bereits geprüften PR #46 ab")
    require(evidence.get("status") == "eligible_for_draft_only"
            and evidence.get("campaign") == campaign
            and evidence.get("image_sha256") == fixed["final_sha256"]
            and proof["image_sha256"] == fixed["final_sha256"]
            and receipt.get("final_sha256") == fixed["final_sha256"],
            "Finalbild-SHA oder vollständiges Quality-Gate passt nicht")
    require(receipt.get("logo_original_sha256") == LOGO_ORIGINAL_SHA256
            and receipt.get("size") == [1080, 1350]
            and receipt.get("status") == "asset_technical_qa_passed_only_NOT_buffer_published"
            and (receipt.get("logo_qa") or {}).get("logo_verified") is True
            and (receipt.get("logo_qa") or {}).get("validator") == "personalos_canonical",
            "Original-Logo-/Abmessungen-/Bild-QA-Receipt passt nicht")
    review_criteria = review.get("visual_review")
    require(isinstance(review_criteria, dict) and
            all(review_criteria.get(key) is True for key in (
                "no_people", "no_robot", "no_foreign_logo", "no_generated_text",
                "plausible_details", "matches_topic", "heading_and_logo_space"
            )), "Visuelle Review-Kriterien nicht vollstaendig bestätigt")
    prepared = proof["prepared_content"]
    require(isinstance(prepared, dict) and set(prepared) == {"posts"}, "Unvollständiger Textbeleg")
    posts = prepared["posts"]
    require(isinstance(posts, dict) and set(posts) == PLATFORMS
            and all(isinstance(value, str) and len(value.strip()) >= 250
                    for value in posts.values()),
            "Drei vollständige geprüfte Post-Texte fehlen")
    return posts
