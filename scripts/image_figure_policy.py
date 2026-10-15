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
