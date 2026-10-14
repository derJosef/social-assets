#!/usr/bin/env python3
"""Offline pre-transfer probe: compare an actual image with a compiled clean-room job.

Does not contact any service, attest actual model context, auto-approve images,
change brand artwork, or transfer media to Adobe, GitHub or Buffer.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

from PIL import Image, UnidentifiedImageError

try:
    from scripts.cleanroom_image_brief import compiled_job
except ModuleNotFoundError:
    from cleanroom_image_brief import compiled_job

EXPECTED_SIZE = (1080, 1350)
MAX_IMAGE_BYTES = 16_000_000
REVIEW_KEYS = (
    "no_people", "no_robot", "no_foreign_logo", "no_generated_text",
    "plausible_details", "matches_topic", "heading_and_logo_space",
)
MARK_KEYS = {"no_foreign_logo", "no_generated_text"}


class InvalidProbe(ValueError):
    """Missing, invalid or fabricated test inputs."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def assess(spec: object, job: object, image_path: Path, review: object | None = None) -> dict:
    """Technical evidence only. No status here authorizes Adobe/Buffer/publication."""
    # Recompilation prevents smuggling a bespoke branded prompt even if
    # the injected prompt also has a matching, self-consistent SHA256.
    expected = compiled_job(spec)
    if not isinstance(job, dict) or job != expected:
        raise InvalidProbe("Compiled job differs from the allowlisted, unmodified prompt")
    if not image_path.is_file() or not 0 < image_path.stat().st_size <= MAX_IMAGE_BYTES:
        raise InvalidProbe("PNG missing or outside the 16 MB hard limit")

    failures: list[str] = []
    try:
        with Image.open(image_path) as im:
            image_type, size = im.format, im.size
            im.verify()
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError) as exc:
        raise InvalidProbe("Not an intact, readable image") from exc
    if image_type != "PNG":
        failures.append("not_png")
    if size != EXPECTED_SIZE:
        failures.append("wrong_pixel_dimensions")

    checked = "not_provided"
    pending: list[str] = []
    if review is not None:
        if not isinstance(review, dict) or set(review) != {"visual_review", "review_evidence"}:
            raise InvalidProbe("Visual review must have exact known fields")
        flags = review["visual_review"]
        if not isinstance(flags, dict) or set(flags) != set(REVIEW_KEYS):
            raise InvalidProbe("Incomplete or unexpected visual review fields")
        evidence = review["review_evidence"]
        if not isinstance(evidence, str) or not 45 <= len(evidence) <= 800 or (
            "ChatGPT" not in evidence or "NOT a human" not in evidence
        ):
            raise InvalidProbe("Actual ChatGPT inspection evidence missing")
        for key in REVIEW_KEYS:
            flag = flags[key]
            if flag is True:
                continue
            if key in MARK_KEYS and flag is None:
                pending.append(key)
            elif flag is False:
                failures.append("visual_" + key)
            else:
                raise InvalidProbe("Only a small ambiguous logo/text marking may be unresolved")
        if pending and not re.search(
            r"unscharf|unklar|uneindeutig|unleserlich|ambig|uncertain|unreadable",
            evidence, re.I,
        ):
            raise InvalidProbe("Undetermined marks need explicit evidence")
        checked = "chatgpt_nonhuman_review"

    # Even a matching image does not prove which context the host sent to
    # the model; the native ChatGPT image tool has no auditable request trace.
    if failures:
        state = "BLOCKED"
    elif review is None:
        state = "AWAITING_VISUAL_REVIEW"
    else:
        state = "PROVISIONAL_ONLY_UNVERIFIED_CONTEXT"
    return {
        "schema_version": 1,
        "state": state,
        "hard_failures": failures,
        "unresolved_marks": pending,
        "raw_image_sha256": sha256_file(image_path),
        "raw_image_bytes": image_path.stat().st_size,
        "raw_image_format": image_type,
        "raw_image_size": list(size),
        "required_image_size": list(EXPECTED_SIZE),
        "generator_prompt_sha256": expected["generator_prompt_sha256"],
        "reference_images_declared": [],
        "actual_generator_context_verified": False,
        "actual_model_prompt_verified": False,
        "visual_review_kind": checked,
        "transfer_permitted": False,
        "buffer_action_permitted": False,
        "publication_permitted": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", required=True, type=Path)
    parser.add_argument("--job", required=True, type=Path)
    parser.add_argument("--image", required=True, type=Path)
    parser.add_argument("--review", type=Path)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()
    try:
        spec = json.loads(args.spec.read_text(encoding="utf-8"))
        job = json.loads(args.job.read_text(encoding="utf-8"))
        review = json.loads(args.review.read_text(encoding="utf-8")) if args.review else None
        result = assess(spec, job, args.image, review)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        parser.error(str(exc))
    with args.report.open("x", encoding="utf-8") as out:
        json.dump(result, out, ensure_ascii=False, indent=2)
        out.write("\n")
    print("CLEANROOM_PROBE", result["state"], result["hard_failures"])
    # No current state authorizes a model-context claim or downstream transfer.
    # Fail closed for shell callers even if format and visual checks look good.
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
