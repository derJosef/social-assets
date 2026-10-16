#!/usr/bin/env python3
"""Bind a NORMALIZED ChatGPT PNG to a pinned Adobe handoff without any network.

This is stage 2 of the existing two-stage protocol:
  1. normalize_chatgpt_raw_png.py writes a new 1080x1350 image + receipt.
  2. Upload *that* image to Adobe, then provide its actual short link here.

This tool never accesses Adobe, GitHub, a model or Buffer. A finished
chatgpt_image object is INPUT DATA for the existing owner-authored brief,
not permission to publish and not proof of context isolation.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image

try:
    from scripts.chatgpt_image_import import inspect_brief, ChatImageBlocked
except ImportError:
    from chatgpt_image_import import inspect_brief, ChatImageBlocked

SIZE = (1080, 1350)
MAX_PNG = 16_000_000
NORMALIZED_OPERATION = "lanczos_scale_no_crop"


class AdobeHandoffBlocked(ValueError):
    """Invalid provenance, review, URL or conflict. No handoff is produced."""


def file_sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def prepare(*, normalized: Path, receipt: Path, visual_review: Path,
            adobe_url: str, campaign_id: str, output: Path) -> dict:
    if output.exists():
        raise AdobeHandoffBlocked("Never overwrite an existing handoff")
    paths = {p.resolve() for p in (normalized, receipt, visual_review, output)}
    if len(paths) != 4:
        raise AdobeHandoffBlocked("Input and output paths must not alias")
    if not normalized.is_file() or not receipt.is_file() or not visual_review.is_file():
        raise AdobeHandoffBlocked("Normalized PNG, its receipt and the visual review are required")
    if not 0 < normalized.stat().st_size <= MAX_PNG:
        raise AdobeHandoffBlocked("Normalized PNG exceeds the 16 MB file limit")

    try:
        receipt_data = json.loads(receipt.read_text(encoding="utf-8"))
        review = json.loads(visual_review.read_text(encoding="utf-8"))
    except (UnicodeError, json.JSONDecodeError, OSError) as exc:
        raise AdobeHandoffBlocked("Missing or malformed handoff evidence") from exc
    if not isinstance(receipt_data, dict):
        raise AdobeHandoffBlocked("Normalization receipt must be an object")
    mandatory = {
        "schema_version": 1,
        "operation": NORMALIZED_OPERATION,
        "output_size": list(SIZE),
        "format": "PNG",
        "image_visual_qa_passed": False,
        "model_context_verified": False,
        "rights_and_platform_checks_verified": False,
        "buffer_or_publication_permitted": False,
    }
    if any(receipt_data.get(key) != value or type(receipt_data.get(key)) is not type(value)
           for key, value in mandatory.items()):
        raise AdobeHandoffBlocked("Normalization receipt has invalid provenance/gate flags")
    if not isinstance(receipt_data.get("source_sha256"), str) or len(
        receipt_data["source_sha256"]
    ) != 64:
        raise AdobeHandoffBlocked("Source fingerprint missing")
    if receipt_data.get("output_sha256") != file_sha(normalized):
        raise AdobeHandoffBlocked("PNG bytes differ from normalization receipt")
    try:
        with Image.open(normalized) as im:
            if im.format != "PNG" or im.size != SIZE:
                raise AdobeHandoffBlocked("Output must be 1080x1350 PNG")
            im.verify()
    except (OSError, Image.DecompressionBombError) as exc:
        raise AdobeHandoffBlocked("Unreadable normalized PNG") from exc

    if not isinstance(review, dict) or set(review) not in (
        {"visual_review", "review_evidence"},
        {"visual_review", "review_evidence", "figure_review"},
        {"visual_review", "review_evidence", "person_checks_evidence"},
    ):
        raise AdobeHandoffBlocked("Only explicit supported visual review fields allowed")
    image = {
        "transport": "adobe_transfer",
        "url": adobe_url,
        "sha256": receipt_data["output_sha256"],  # NEVER source_sha256
        **review,
    }
    brief = {
        "campaign_id": campaign_id,
        "brand": "ai-agent-builder",
        "execution_mode": "drafts",
        "image_review": f"visual-reviews/{campaign_id}.json",
        "chatgpt_image": image,
    }
    try:
        verified_campaign, checked = inspect_brief(brief)
    except (ChatImageBlocked, KeyError, TypeError) as exc:
        raise AdobeHandoffBlocked(f"Existing draft import gate rejected the handoff: {exc}") from None
    if verified_campaign != campaign_id or checked != image:
        raise AdobeHandoffBlocked("Importer changed the image handoff unexpectedly")
    payload = {"chatgpt_image": image}
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as stream:
        json.dump(payload, stream, indent=2, ensure_ascii=False)
        stream.write("\n")
    return {
        "campaign": campaign_id,
        "source_sha256": receipt_data["source_sha256"],
        "normalized_sha256": receipt_data["output_sha256"],
        "normalized_pixels": list(SIZE),
        "adobe_url": adobe_url,
        "payload_path": str(output),
        "image_generator_context_verified": False,
        "buffer_requests": 0,
        "publication_requests": 0,
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--normalized", required=True, type=Path)
    p.add_argument("--receipt", required=True, type=Path)
    p.add_argument("--visual-review", required=True, type=Path)
    p.add_argument("--adobe-url", required=True)
    p.add_argument("--campaign", required=True)
    p.add_argument("--output", required=True, type=Path)
    args = p.parse_args()
    try:
        result = prepare(
            normalized=args.normalized, receipt=args.receipt,
            visual_review=args.visual_review,
            adobe_url=args.adobe_url, campaign_id=args.campaign,
            output=args.output,
        )
    except (OSError, ValueError) as exc:
        p.error(str(exc))
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
