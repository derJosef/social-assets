#!/usr/bin/env python3
"""Import an image actually created/inspected in ChatGPT via the proven Adobe link.

One owner-authored issue provides URL+SHA256+explicit seven-criterion visual
inspection. The GitHub runner downloads only HTTPS from Adobe-linked hosts,
checks the exact PNG bytes and size, and stages source + canonical review.
This tool has no image model, Buffer, schedule, publication or GitHub writes.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

from PIL import Image, UnidentifiedImageError

ROOT = Path(__file__).resolve().parents[1]
SIZE = (1080, 1350)
MAX_PNG = 16_000_000
SHA_RE = re.compile(r"[a-f0-9]{64}\Z")
CAMPAIGN_RE = re.compile(r"20\d{2}-\d{2}-\d{2}-[a-z0-9]+(?:-[a-z0-9]+)*\Z")
TRANSFER_RE = re.compile(r"https://at\.adobe\.com/[A-Za-z0-9_-]{8,90}/?\Z")
CHECKS = ("no_people", "no_robot", "no_foreign_logo", "no_generated_text",
          "plausible_details", "matches_topic", "heading_and_logo_space")
ALLOWED_HOSTS = ("adobe.com", "adobe.io", "adobecc.com",
                 "adobecontent.io", "amazonaws.com", "cloudfront.net")


class ChatImageBlocked(ValueError):
    pass


def require(ok: bool, msg: str) -> None:
    if not ok:
        raise ChatImageBlocked(msg)


def safe_location(url: str) -> str:
    try:
        parts = urllib.parse.urlsplit(url)
    except ValueError:
        raise ChatImageBlocked("Ungültiger Adobe-Downloadlink") from None
    host = (parts.hostname or "").lower()
    require(parts.scheme == "https" and host
            and (any(host == d or host.endswith("." + d) for d in ALLOWED_HOSTS))
            and parts.username is None and parts.password is None
            and parts.port is None and not parts.fragment,
            "Nur Adobe-HTTPS-Download und vertrauenswürdige Adobe-CDN-Redirects")
    return host


class SafeRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        safe_location(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch_image(url: str) -> bytes:
    require(TRANSFER_RE.fullmatch(url) is not None,
            "Eingang ausschließlich über echten Adobe-Kurzlink; keine fremden URLs")
    safe_location(url)
    opener = urllib.request.build_opener(SafeRedirect)
    req = urllib.request.Request(url, headers={
        "User-Agent": "ChatGPT-GitHub-Image-Transfer/1.0",
        "Accept": "image/png,application/octet-stream",
    })
    with opener.open(req, timeout=50) as resp:
        declared = resp.headers.get("Content-Length")
        if declared and declared.isdigit():
            require(int(declared) <= MAX_PNG, "Adobe-Bild zu groß")
        data = resp.read(MAX_PNG + 1)
    require(0 < len(data) <= MAX_PNG, "Adobe-Bild fehlt oder überschreitet Dateilimit")
    return data


def inspect_brief(brief: dict) -> tuple[str, dict]:
    require(isinstance(brief, dict), "Kein Kampagnenbrief")
    cid = brief.get("campaign_id")
    require(isinstance(cid, str) and CAMPAIGN_RE.fullmatch(cid) is not None,
            "Ungültige Kampagnenkennung")
    require(brief.get("brand") == "ai-agent-builder"
            and brief.get("execution_mode") == "drafts"
            and brief.get("image_review") == f"visual-reviews/{cid}.json",
            "Marke, Modus oder Bildreview passen nicht")
    img = brief.get("chatgpt_image")
    require(isinstance(img, dict) and set(img) ==
            {"transport", "url", "sha256", "visual_review", "review_evidence"},
            "ChatGPT-Bildtransport fehlt – keine automatische kostenpflichtige Bild-API")
    require(img["transport"] == "adobe_transfer"
            and isinstance(img["url"], str)
            and TRANSFER_RE.fullmatch(img["url"]) is not None,
            "Nur früher erprobter Adobe-Transfer")
    require(isinstance(img["sha256"], str)
            and SHA_RE.fullmatch(img["sha256"]) is not None,
            "SHA256-Pinning des ChatGPT-PNG fehlt")
    checks = img["visual_review"]
    require(isinstance(checks, dict) and set(checks) == set(CHECKS)
            and all(checks[k] is True for k in CHECKS),
            "Sieben echte ChatGPT-Bildsichtprüfungen erforderlich; keine Person/Logo/Text")
    evidence = img["review_evidence"]
    require(isinstance(evidence, str) and 45 <= len(evidence) <= 800
            and "ChatGPT" in evidence and "NOT a human" in evidence,
            "Nur tatsächlich durchgeführte ChatGPT-Sichtprüfung angeben; keine menschliche Freigabe erfinden")
    return cid, img


def import_image(brief_file: str, root: Path = ROOT, *, fetch=fetch_image) -> dict:
    root = root.resolve()
    relative = Path(brief_file)
    require(not relative.is_absolute() and re.fullmatch(
        r"orchestration/briefs/20\d{2}-\d{2}-\d{2}-[a-z0-9]+(?:-[a-z0-9]+)*\.json",
        relative.as_posix()) is not None, "Unzulässiger Kampagnenpfad")
    src_brief = (root / relative).resolve()
    require(src_brief.is_relative_to(root) and src_brief.is_file(), "Brief fehlt")
    brief = json.loads(src_brief.read_text(encoding="utf-8"))
    cid, img = inspect_brief(brief)
    require(relative.stem == cid, "Kampagnen-ID und Dateiname unterscheiden sich")
    src = root / f"media/source-images/{cid}-source.png"
    review = root / f"visual-reviews/{cid}.json"
    require(not src.exists() and not review.exists(), "Kampagnenbild existiert bereits; kein Retry")
    raw = fetch(img["url"])
    require(isinstance(raw, bytes) and 0 < len(raw) <= MAX_PNG,
            "Ungültige Downloadbytes")
    require(hashlib.sha256(raw).hexdigest() == img["sha256"],
            "Adobe-Transfer SHA256 stimmt nicht mit ChatGPT-Original überein")
    try:
        with Image.open(io.BytesIO(raw)) as original:
            require(original.format == "PNG" and original.size == SIZE,
                    "ChatGPT-PNG muss vor dem Upload 1080 x 1350 (4:5) haben")
            original.verify()
    except (OSError, ValueError, Image.DecompressionBombError, UnidentifiedImageError) as exc:
        if isinstance(exc, ChatImageBlocked):
            raise
        raise ChatImageBlocked("Bilddaten sind beschädigt oder kein PNG") from exc
    spec = {
        "format_version": 1, "brand": "ai-agent-builder",
        "source": src.relative_to(root).as_posix(),
        "source_sha256": img["sha256"], "layout": "logo_only",
        "heading": None, "visual_review": img["visual_review"],
        "review_evidence": img["review_evidence"],
    }
    src.parent.mkdir(parents=True, exist_ok=True)
    review.parent.mkdir(parents=True, exist_ok=True)
    with src.open("xb") as out:
        out.write(raw)
    try:
        if __package__:
            from .social_portfolio_scene import validate_spec
        else:
            from social_portfolio_scene import validate_spec
        require(validate_spec(spec, root) == src,
                "Kanonischer Bild- und Review-Gate gescheitert")
        with review.open("x", encoding="utf-8") as out:
            json.dump(spec, out, ensure_ascii=False, indent=2)
            out.write("\n")
    except BaseException:
        src.unlink(missing_ok=True)
        review.unlink(missing_ok=True)
        raise
    return {"campaign": cid, "source_sha256": img["sha256"],
            "review": review.relative_to(root).as_posix(),
            "transport": "adobe_transfer_hash_verified",
            "human_review": "pending_after_buffer_draft",
            "model_requests": 0, "buffer_requests": 0}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--brief", required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(import_image(args.brief), ensure_ascii=False))
        return 0
    except (ChatImageBlocked, OSError, ValueError) as exc:
        print("CHATGPT_IMAGE_IMPORT_BLOCKED:", str(exc)[:250], file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
