#!/usr/bin/env python3
"""Offline allowlist compiler for a brand-free image-generation handoff.

Never contacts a model, GitHub, Adobe, Buffer or PersonalOS. A compiled job
is NOT evidence that a model was invoked in an isolated conversation.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

SCENES = {
    "document-review": "a modern workbench for controlled document inspection",
    "cad-check": "a technical workstation with abstract CAD geometry on unmarked displays",
    "industrial-quality": "a precise industrial quality-control station",
    "approval-flow": "a physical workflow for reviewing and authorizing blank documents",
    "data-validation": "a technical data-validation workspace with unmarked display surfaces",
}
STEPS = {
    "receive": "a clearly identifiable intake station",
    "inspect": "a detailed visual inspection station",
    "compare": "a comparison station with aligned unmarked materials",
    "verify": "a verification station with precise technical instruments",
    "decide": "a distinct human-governed decision point represented without any person",
    "release": "a controlled output station",
    "archive": "an orderly archive station for blank documents",
}
COMPOSITIONS = {
    "connected-three": "three physically connected stations in one continuous scene",
    "central-focus": "three distinct stages arranged around a central control point",
    "diagonal-depth": "three linked process stations receding diagonally into the scene",
}
ALLOWED_KEYS = {"version", "scene", "steps", "composition", "figure"}
MAX_SPEC_BYTES = 8192


class InvalidCleanRoomSpec(ValueError):
    """Structured handoff violates the strictly constrained interface."""


def compile_prompt(spec: object) -> str:
    if not isinstance(spec, dict) or set(spec) != ALLOWED_KEYS:
        raise InvalidCleanRoomSpec("Only the five allowlisted fields are permitted")
    if type(spec["version"]) is not int or spec["version"] != 1:
        raise InvalidCleanRoomSpec("Only version 1 is supported")
    scene, composition, figure, steps = (
        spec["scene"], spec["composition"], spec["figure"], spec["steps"]
    )
    if type(scene) is not str or scene not in SCENES:
        raise InvalidCleanRoomSpec("Unknown scene identifier")
    if type(composition) is not str or composition not in COMPOSITIONS:
        raise InvalidCleanRoomSpec("Unknown composition identifier")
    if type(figure) is not str or figure not in ("none", "hologram"):
        raise InvalidCleanRoomSpec("Only no figure or an unambiguously stylized hologram is supported")
    if not isinstance(steps, list) or len(steps) != 3 or any(
        type(step) is not str or step not in STEPS for step in steps
    ) or len(set(steps)) != 3:
        raise InvalidCleanRoomSpec("Exactly three different allowlisted stages are required")
    descriptions = "; ".join(STEPS[step] for step in steps)
    figure_instruction = (
        "No people, silhouettes, hands or robots. "
        if figure == "none" else
        "Include exactly one clearly artificial blue/cyan glowing human-shaped "
        "wireframe hologram pointing at the inspection process. Its face, skin "
        "and clothing must not look like a real photograph of a person. "
        "No realistic faces or bodies and no robots. "
    )
    return (
        "Create a single standalone raw image, not a poster or advertisement. "
        f"Depict {SCENES[scene]}: {COMPOSITIONS[composition]}, "
        f"in this order: {descriptions}. "
        "Realistically rendered 3D technical environment, physically plausible mechanisms, "
        "dimensional depth, "
        "dark navy and graphite with subtle cyan illumination, restrained cinematic lighting. "
        "Portrait composition, 4:5 aspect ratio; preserve the entire scene. "
        "Show only unprinted, neutral surfaces. " + figure_instruction +
        "No letters, numbers, signage, markings, emblems, typography or watermarks. "
        "Use no reference images and invent no identifying marks."
    )


def compiled_job(spec: object) -> dict:
    prompt = compile_prompt(spec)
    return {
        "schema_version": 1,
        "generator_prompt": prompt,
        "generator_prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        "reference_images": [],
        "isolation_verified": False,
        "human_visual_review": "pending",
        "purpose": "raw_image_only",
    }


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict:
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise InvalidCleanRoomSpec("Duplicate JSON field")
        obj[key] = value
    return obj


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.spec.stat().st_size > MAX_SPEC_BYTES:
        parser.error("Input spec too large")
    try:
        spec = json.loads(args.spec.read_text(encoding="utf-8"),
                          object_pairs_hook=_reject_duplicate_keys)
        job = compiled_job(spec)
    except (ValueError, UnicodeError) as exc:
        parser.error(str(exc))
    # Exclusive create prevents changes to previously reviewed jobs.
    with args.output.open("x", encoding="utf-8") as handle:
        json.dump(job, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
