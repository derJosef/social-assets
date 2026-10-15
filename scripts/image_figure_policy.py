"""Restricted classification of stylized figures for raw image draft QA.

No image recognition takes place. Caller must supply truthful visual evidence.
This only authorizes a *clearly artificial* non-photorealistic hologram class;
realistic people and AI-altered photographs require a separate rights/disclosure gate.
"""
from __future__ import annotations

import re

HOLOGRAM_KIND = "stylized_hologram"
FIGURE_FIELDS = {"kind", "photorealistic_ai_face", "ai_altered_real_person"}
EVIDENCE_MARKER = re.compile(
    r"hologram|holograf|wireframe|drahtgitter|digital(?:e|er|es|en)?\s+(?:figur|menschengestalt)",
    re.IGNORECASE,
)


class FigureClassificationError(ValueError):
    """No valid evidence of a nonphotorealistic approved figure."""


def classify_figure(flags: dict, figure_review: object, evidence: str) -> str:
    """Return 'none' or 'hologram' after checking the exact review contract.

    No classification result is a human sign-off or publication approval.
    """
    if not isinstance(flags, dict) or type(flags.get("no_people")) is not bool:
        raise FigureClassificationError("no_people must be explicitly boolean")
    if figure_review is None:
        if flags["no_people"] is not True:
            raise FigureClassificationError("Any depicted figure needs an explicit classification")
        return "none"
    if not isinstance(figure_review, dict) or set(figure_review) != FIGURE_FIELDS:
        raise FigureClassificationError("Unknown or incomplete figure review fields")
    if (figure_review["kind"] != HOLOGRAM_KIND
            or figure_review["photorealistic_ai_face"] is not False
            or figure_review["ai_altered_real_person"] is not False
            or flags["no_people"] is not False):
        raise FigureClassificationError("Photorealistic or ambiguous person cannot pass hologram route")
    if not isinstance(evidence, str) or not EVIDENCE_MARKER.search(evidence):
        raise FigureClassificationError("An explicit holographic figure description is required")
    return "hologram"

# This is an auditable *requirements check*, not evidence of Josef granting
# special one-off permission. Never claim the model can verify persons' rights.
PERSON_REVIEW_KEYS = (
    "photorealistic_ai_face", "ai_altered_real_person",
    "rights_checked", "no_misrepresentation_checked", "platform_checked",
)
PERSON_EVIDENCE_KEYS = (
    "rights_basis", "misrepresentation_assessment", "platform_assessment",
)


class PersonReviewError(ValueError):
    """Unverified person rights, identity presentation, or platform obligations."""


def validate_person_review(flags: object, evidence: object) -> str:
    """Classify and gate any non-holographic person.

    A record says checks were documented and passed, not that legal rights were
    independently established or that publication was authorized.
    """
    if not isinstance(flags, dict) or set(flags) != (
            {"no_people"} | set(PERSON_REVIEW_KEYS)):
        raise PersonReviewError("Complete person review fields required")
    if any(type(flags[k]) is not bool for k in (("no_people",) + PERSON_REVIEW_KEYS)):
        raise PersonReviewError("Person review checks require actual booleans")
    if flags["no_people"]:
        if flags["photorealistic_ai_face"] or flags["ai_altered_real_person"] or any(
            flags[k] for k in ("rights_checked", "no_misrepresentation_checked", "platform_checked")
        ) or evidence is not None:
            raise PersonReviewError("Person-free scene must not claim completed person checks")
        return "none"
    if not all(flags[k] is True for k in (
        "rights_checked", "no_misrepresentation_checked", "platform_checked"
    )):
        raise PersonReviewError("Rights, misrepresentation and platform checks must all pass")
    if not isinstance(evidence, dict) or set(evidence) != set(PERSON_EVIDENCE_KEYS):
        raise PersonReviewError("Three distinct person-check evidence fields are required")
    for key in PERSON_EVIDENCE_KEYS:
        note = evidence[key]
        if (not isinstance(note, str) or not 40 <= len(note.strip()) <= 600
                or any(ord(c) < 32 and c not in "\t" for c in note)):
            raise PersonReviewError("Person-check evidence incomplete or malformed: " + key)
    return "person_checks_documented"
