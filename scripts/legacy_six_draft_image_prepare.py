#!/usr/bin/env python3
"""Prepare TWO replacement 4:5 branded images for SIX EXISTING Buffer drafts.

Stage only source, original-logo-verified artwork and evidence on a dedicated
immutable branch. NO Buffer API calls, edits, queues, posts or date changes.
Source image bytes MUST match the real Adobe transfer output SHA, and the
canonical existing social_portfolio_scene original-logo/pixel QA remains mandatory.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
from pathlib import Path

from PIL import Image

try:
    from scripts.chatgpt_image_import import fetch_image
    from scripts.social_portfolio_scene import build
except ImportError:
    from chatgpt_image_import import fetch_image
    from social_portfolio_scene import build

ROOT = Path(__file__).resolve().parents[1]
SIZE = (1080, 1350)
LEGACY = (
    {
        "key": "2026-10-16-legacy-wer-liest-mit-4x5",
        "topic": "Wer liest bei deinem KI-Chat mit?",
        "adobe_url": "https://at.adobe.com/xJC6aVh2hPgh9EnZ",
        "sha256": "74a7debcc3d5598fa328fc9a5c0376c9cd2797ed2d722ed7a9c4e6ec5c3abfd7",
        "ids": {
            "linkedin": "6ac8d5a926e224ee545ee6b5",
            "facebook": "6ac8d5ab26e224ee545ee761",
            "instagram": "6ac8d5ae26e224ee545ee809",
        },
        "review": (
            "ChatGPT inspected the actual rendered source: glowing central AI infrastructure "
            "with connected transparent servers, cloud, data storage and monitoring paths. "
            "No human, robot, recognizable branding or readable generated text; clear "
            "lower-right safe logo area. NOT a human visual inspection or publication approval."
        ),
    },
    {
        "key": "2026-10-16-legacy-ein-agent-drei-tests-4x5",
        "topic": "Ein Agent. Drei Tests.",
        "adobe_url": "https://at.adobe.com/wuislato0VUYlaeT",
        "sha256": "95f82aa8b82c749a89d73e5f1ba34bb4a2521c31f9043bf80dffaee328406c7a",
        "ids": {
            "linkedin": "6ac8961e7d9f9f33012bc9cd",
            "facebook": "6ac89617f07e682de6a98b36",
            "instagram": "6ac8961b7d9f9f33012bc803",
        },
        "review": (
            "ChatGPT inspected the actual generated image: three connected stylized "
            "technical inspection stages of a prototype, with blue and amber scanning "
            "effects. There are no people, robots, third-party marks, or readable letters. "
            "Lower-right area is suitable for separately attached canonical logo. "
            "NOT a human inspection or publication approval."
        ),
    },
)
# The owner comment is a short-lived transfer ticket, NOT a source of trust.
# Exact PNG digests, 4:5 dimensions and original-logo QA remain immutable.
FRESH_CONFIRM = "LEGACY_IMAGE_FRESH_LINKS_ONCE_20261017"
FRESH_URL = re.compile(r"https://at\.adobe\.com/[A-Za-z0-9_-]{8,90}\Z")
FRESH_KEYS = ("wer_liest_mit", "ein_agent_drei_tests")


def parse_owner_image_event(path: Path) -> dict[str, str]:
    if path.stat().st_size > 300_000:
        raise ValueError("Event too large for image-only transfer")
    event = json.loads(path.read_text(encoding="utf-8"))
    issue = event.get("issue") or {}
    comment = event.get("comment") or {}
    if (event.get("action") != "created" or issue.get("number") != 19
            or issue.get("user", {}).get("login") != "derJosef"
            or comment.get("user", {}).get("login") != "derJosef"
            or issue.get("pull_request")):
        raise ValueError("Only authorized owner issue #19 event may supply links")
    body = comment.get("body")
    if not isinstance(body, str) or len(body) > 350:
        raise ValueError("Malformed owner image transfer ticket")
    lines = body.split("\n")
    if len(lines) != 3 or lines[0] != FRESH_CONFIRM:
        raise ValueError("Invalid image ticket confirmation or line count")
    result = {}
    for field, line in zip(FRESH_KEYS, lines[1:]):
        label = field + "="
        if not line.startswith(label):
            raise ValueError("Malformed image-ticket field")
        url = line[len(label):]
        if not FRESH_URL.fullmatch(url):
            raise ValueError("Image-ticket URLs must be approved Adobe HTTPS shortlinks")
        result[field] = url
    if len(set(result.values())) != 2:
        raise ValueError("Both images must use distinct transfer URLs")
    return result


VISUAL = dict(no_people=True, no_robot=True, no_foreign_logo=True,
              no_generated_text=True, plausible_details=True,
              matches_topic=True, heading_and_logo_space=True)


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def paths(root: Path, key: str) -> dict[str, Path]:
    return {
        "source": root / f"media/source-images/{key}-source.png",
        "base": root / f"media/source-images/{key}-base.png",
        "final": root / f"media/images/{key}-branded.png",
        "review": root / f"visual-reviews/{key}.json",
        "receipt": root / f"artwork-receipts/{key}.json",
    }


def stage(root: Path = ROOT, *, fetch=fetch_image, builder=build,
          font: Path = Path("/tmp/Inter.ttf"),
          fresh_urls: dict[str, str] | None = None) -> list[dict]:
    # NEVER overwrite even one previously prepared campaign image.
    for info in LEGACY:
        if any(p.exists() for p in paths(root, info["key"]).values()):
            raise ValueError("Image repair was already prepared; no repeat or overwrite")

    if fresh_urls is not None and set(fresh_urls) != set(FRESH_KEYS):
        raise ValueError("Exactly two fresh Adobe links required")
    result = []
    for info, topic_key in zip(LEGACY, FRESH_KEYS):
        dest = paths(root, info["key"])
        transfer_url = fresh_urls[topic_key] if fresh_urls is not None else info["adobe_url"]
        raw = fetch(transfer_url)
        if not isinstance(raw, bytes):
            raise ValueError("Adobe download returned non-bytes; source image never accepted")
        if sha256(raw) != info["sha256"]:
            # Safe diagnostic values only: no URL, redirect target, raw
            # response body, token, personal data, or image content is logged.
            signature = (
                "png" if raw.startswith(b"\x89PNG\r\n\x1a\n")
                else "jpeg" if raw.startswith(b"\xff\xd8\xff")
                else "html" if raw.lstrip().lower().startswith((b"<!doctype html", b"<html"))
                else "unknown"
            )
            raise ValueError(
                "Adobe bytes do not match original ChatGPT normalized image SHA; "
                f"topic={info['key']}; received_sha256={sha256(raw)}; "
                f"bytes={len(raw)}; signature={signature}"
            )
        with Image.open(io.BytesIO(raw)) as im:
            if im.format != "PNG" or im.size != SIZE:
                raise ValueError("Expected full-resolution 1080x1350 PNG")
            im.verify()
        spec = {
            "format_version": 1,
            "brand": "ai-agent-builder",
            "source": dest["source"].relative_to(root).as_posix(),
            "source_sha256": info["sha256"],
            "layout": "logo_only", "heading": None,
            "visual_review": dict(VISUAL),
            "review_evidence": info["review"],
            "chatgpt_review": {
                "kind": "chatgpt_visual_inspection_draft_only",
                "source_sha256": info["sha256"],
            },
        }
        for p in dest.values():
            p.parent.mkdir(parents=True, exist_ok=True)
        with dest["source"].open("xb") as f:
            f.write(raw)
        with dest["review"].open("x", encoding="utf-8") as f:
            json.dump(spec, f, indent=2, ensure_ascii=False)
        qa = builder(dest["review"], root, dest["base"], dest["final"],
                     font, root / "media/brand/logo-pauderer-original.png")
        if (not isinstance(qa, dict) or qa.get("status") != "verified_image_only"
                or qa.get("source_sha256") != info["sha256"]
                or qa.get("layout") != "logo_only"
                or qa.get("size") != list(SIZE)
                or qa.get("logo_qa", {}).get("logo_verified") is not True
                or qa.get("sha256") != sha256(dest["final"].read_bytes())):
            raise ValueError("Canonical logo or image QA did not pass")
        receipt = {
            "kind": "legacy_draft_image_repair_preparation",
            "brand": "ai-agent-builder",
            "topic": info["topic"], "old_draft_ids": info["ids"],
            "source_sha256": info["sha256"],
            "source_adobe_url": transfer_url,
            "final_sha256": qa["sha256"],
            "final": dest["final"].relative_to(root).as_posix(),
            "original_logo_qa": qa["logo_qa"],
            "buffer_mutations": 0,
            "buffer_status_changed": False,
            "publication_authorized": False,
            "image_model_context_isolation_verified": False,
        }
        with dest["receipt"].open("x", encoding="utf-8") as f:
            json.dump(receipt, f, indent=2, ensure_ascii=False)
        result.append(receipt)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--github-event", type=Path)
    args = parser.parse_args()
    if not args.prepare_only:
        parser.error("No implicit live action; use --prepare-only")
    try:
        urls = parse_owner_image_event(args.github_event) if args.github_event else None
        result = stage(fresh_urls=urls)
    except (OSError, ValueError, RuntimeError) as exc:
        parser.error(str(exc)[:250])
    for item in result:
        print("LEGACY_IMAGE_QA_PASS", item["final"], item["final_sha256"],
              "buffer_mutations=0, no_publish")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
