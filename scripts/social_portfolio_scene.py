#!/usr/bin/env python3
"""Build a 4:5 AI Agent Builder scene from an independently reviewed source.

This tool never generates a logo, never edits an existing Buffer post, and never
publishes. Manual visual QA is essential: pixel inspection cannot reliably
detect people, hallucinated labels, marks, or incorrect technical details.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

SIZE = (1080, 1350)
SOURCE_RE = re.compile(r"media/source-images/[a-z0-9][a-z0-9_.-]*\.png\Z")
REVIEW_KEYS = (
    "no_people", "no_robot", "no_foreign_logo", "no_generated_text",
    "plausible_details", "matches_topic", "heading_and_logo_space",
)
LOGO_SHA = "15dc410d1a05b96c13466ddf3052ba9cc783cdd7252b74f4fb5c3f886510dea0"


class InvalidScene(ValueError):
    """Refuse an unsafe, unverified, or mismatching source."""


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def validate_spec(spec: dict, root: Path) -> Path:
    if not isinstance(spec, dict) or set(spec) != {
        "format_version", "brand", "source", "source_sha256", "layout",
        "heading", "visual_review", "review_evidence"
    }:
        raise InvalidScene("Exact version-1 scene specification required")
    if spec["format_version"] != 1 or spec["brand"] != "ai-agent-builder":
        raise InvalidScene("Only AI Agent Builder version 1 allowed")
    source = spec["source"]
    if not isinstance(source, str) or not SOURCE_RE.fullmatch(source):
        raise InvalidScene("Source must be an approved in-repository PNG path")
    if spec["layout"] not in ("headline", "logo_only"):
        raise InvalidScene("Only headline and logo_only profiles are recognized")
    heading = spec["heading"]
    if spec["layout"] == "logo_only":
        if heading is not None:
            raise InvalidScene("Logo-only variant must have a genuinely absent heading")
    elif not isinstance(heading, str) or not 5 <= len(heading) <= 65 or any(
        c in heading for c in "\r\n\t"
    ):
        raise InvalidScene("Headline layout requires one nonempty, single-line heading")
    review = spec["visual_review"]
    if not isinstance(review, dict) or set(review) != set(REVIEW_KEYS):
        raise InvalidScene("Every visual review field must be provided")
    if any(review[k] is not True for k in REVIEW_KEYS):
        raise InvalidScene("Visual review incomplete; do not use this artwork")
    evidence = spec["review_evidence"]
    if not isinstance(evidence, str) or len(evidence.strip()) < 15:
        raise InvalidScene("Independent manual review evidence is required")
    source_path = (root / source).resolve()
    if not source_path.is_relative_to(root.resolve()) or not source_path.is_file():
        raise InvalidScene("Source file missing or outside asset repository")
    ssha = spec["source_sha256"]
    if not isinstance(ssha, str) or not re.fullmatch(r"[0-9a-f]{64}", ssha):
        raise InvalidScene("Invalid source fingerprint")
    if digest(source_path) != ssha:
        raise InvalidScene("Source changed since visual review")
    with Image.open(source_path) as im:
        im.verify()
    with Image.open(source_path) as im:
        w, h = im.size
    if w < SIZE[0] or h < SIZE[1] or abs(w / h - 0.8) > 0.006:
        raise InvalidScene("Approved 4:5 artwork must be at least 1080x1350; no auto-crop")
    return source_path


def layout_heading(draw: ImageDraw.ImageDraw, heading: str, font: ImageFont.FreeTypeFont):
    words = heading.upper().split()
    lines, current = [], ""
    for word in words:
        candidate = (current + " " + word).strip()
        if draw.textlength(candidate, font=font) <= 885:
            current = candidate
        elif current:
            lines.append(current)
            current = word
        else:
            raise InvalidScene("Heading contains a word too wide for the image")
    if current:
        lines.append(current)
    if len(lines) > 3 or any(draw.textlength(s, font=font) > 885 for s in lines):
        raise InvalidScene("Heading would not fit three mobile-readable lines")
    return lines


def render_base(source_path: Path, dest: Path, heading: str | None, font_path: Path,
                *, allow_existing: bool = False) -> tuple[int, int, int, int] | None:
    if dest.exists() and not allow_existing:
        raise FileExistsError("Never overwrite a previous campaign image")
    with Image.open(source_path) as original:
        im = original.convert("RGB").resize(SIZE, Image.Resampling.LANCZOS)
    if heading is None:
        # True logo-only layout: do not insert heading, labels, dimming veil
        # or placeholder box. Original-brand logo is composed separately.
        dest.parent.mkdir(parents=True, exist_ok=True)
        im.save(dest, format="PNG")
        return None
    if not font_path.is_file():
        raise InvalidScene("Inter font missing")
    font = ImageFont.truetype(str(font_path), 67)
    # Contrast veil only over an intentionally quiet upper-left zone.
    veil = Image.new("RGBA", SIZE, (0, 0, 0, 0))
    layer = ImageDraw.Draw(veil, "RGBA")
    for y in range(0, 525):
        a = round(197 * (1 - y / 525) ** 1.3)
        layer.line((0, y, 960, y), fill=(7, 17, 31, a), width=1)
    im = Image.alpha_composite(im.convert("RGBA"), veil)
    draw = ImageDraw.Draw(im)
    lines = layout_heading(draw, heading, font)
    x, y, step = 58, 78, 91
    boxes = []
    for n, line in enumerate(lines):
        yy = y + n * step
        draw.text((x, yy), line, font=font, fill="#F5F7FA", stroke_width=0)
        boxes.append(draw.textbbox((x, yy), line, font=font))
    # Logo is always independently placed in the opposite, lower-right corner.
    heading_box = (max(0, min(b[0] for b in boxes) - 5),
                   max(0, min(b[1] for b in boxes) - 7),
                   max(b[2] for b in boxes) + 5,
                   max(b[3] for b in boxes) + 7)
    dest.parent.mkdir(parents=True, exist_ok=True)
    im.convert("RGB").save(dest, format="PNG")
    return heading_box


def build(spec_path: Path, root: Path, base: Path, final: Path,
          font: Path, logo: Path) -> dict:
    if base.exists() or final.exists():
        raise FileExistsError("Existing campaign image must not be overwritten")
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    source = validate_spec(spec, root)
    if not logo.is_file() or digest(logo) != LOGO_SHA:
        raise InvalidScene("Verified immutable Pauderer logo unavailable")
    bbox = render_base(source, base, spec["heading"], font)
    final.parent.mkdir(parents=True, exist_ok=True)
    def call(*args):
        subprocess.run([sys.executable, str(root / "scripts/logo_composite.py"),
                        *map(str, args)], cwd=root, check=True)
    try:
        call("compose", base, final, "--original", logo,
             "--heading-corner", "top-left",
             "--frame", "on", "--margin-ratio", "0.05", "--stroke-ratio", "0.03")
        if spec["layout"] == "logo_only":
            # Explicit, fail-closed profile: the canonical verifier returns 2
            # for absent headings; our independent gate checks every other
            # named requirement, rejects unknown/skipped checks, and requires
            # the original logo to be in the verified lower-right position.
            from logo_only_gate import verify_logo_only
            qa = verify_logo_only(final, base, logo)
        else:
            if bbox is None:
                raise InvalidScene("Missing mandatory heading rectangle")
            call("verify", final, base, "--original", logo,
                 "--heading-corner", "top-left",
                 "--heading-box", ",".join(map(str, bbox)))
            qa = {"profile": "headline", "status": "verified_image_only"}
    except (subprocess.CalledProcessError, OSError, ValueError):
        final.unlink(missing_ok=True)
        raise
    return {"size": list(SIZE), "sha256": digest(final),
            "source_sha256": digest(source), "heading_box": list(bbox) if bbox else None,
            "layout": spec["layout"], "logo_qa": qa, "status": "verified_image_only"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--final", type=Path, required=True)
    parser.add_argument("--font", type=Path, default=Path("/tmp/Inter.ttf"))
    parser.add_argument("--logo", type=Path, default=Path("media/brand/logo-pauderer-original.png"))
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    spec_path = (root / args.spec).resolve()
    base_path = (root / args.base).resolve()
    final_path = (root / args.final).resolve()
    logo_path = (root / args.logo).resolve()
    if not spec_path.is_relative_to(root) or not re.fullmatch(
        r"visual-reviews/[a-z0-9][a-z0-9_.-]*\.json", spec_path.relative_to(root).as_posix()
    ):
        raise InvalidScene("Review specification must be under visual-reviews/")
    for destination, directory in ((base_path, "media/source-images/"),
                                   (final_path, "media/images/")):
        if not destination.is_relative_to(root):
            raise InvalidScene("Output must remain inside the asset repository")
        relative = destination.relative_to(root).as_posix()
        if not relative.startswith(directory) or not re.fullmatch(
            r"[a-z0-9][a-z0-9_.-]*\.png", relative[len(directory):]
        ):
            raise InvalidScene("Only new PNG outputs in the approved media directories")
    print(json.dumps(build(spec_path, root, base_path, final_path,
                           args.font, logo_path), ensure_ascii=False))


if __name__ == "__main__":
    main()
