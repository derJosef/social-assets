#!/usr/bin/env python3
"""Reject unapproved/draft/social artwork as input for permanent website news.

This gate accepts a FRESH READ-ONLY Buffer GET and the byte-verified final image.
It cannot publish, edit posts or create new images.
"""
from __future__ import annotations
import hashlib
import io
import re
from PIL import Image, UnidentifiedImageError

class NewsSourceBlocked(ValueError):
    pass

SHA64 = re.compile(r"[0-9a-f]{64}\Z")
POST_ID = re.compile(r"[0-9a-f]{24}\Z")
GIT_SHA = re.compile(r"[0-9a-f]{40}\Z")
ASSET = re.compile(r"media/images/[a-zA-Z0-9_-]+\.png\Z")

def require(condition, message):
    if not condition:
        raise NewsSourceBlocked(message)

def pinned_image_url(commit, path):
    require(isinstance(commit, str) and GIT_SHA.fullmatch(commit),
            "Image must use immutable Git SHA (never main)")
    require(isinstance(path, str) and ASSET.fullmatch(path),
            "Invalid final PNG path")
    return f"https://raw.githubusercontent.com/derJosef/social-assets/{commit}/{path}"

def verify_published_news_source(
    *, brand, post, expected_post_id, expected_channel,
    image_commit, image_path, expected_image_sha256, actual_image_bytes
):
    require(brand == "ai-agent-builder", "Other brands need separate consent")
    require(isinstance(expected_post_id, str) and POST_ID.fullmatch(expected_post_id),
            "Invalid post ID")
    require(expected_channel in ("linkedin", "facebook", "instagram"),
            "Invalid Buffer channel")
    require(isinstance(post, dict) and post.get("id") == expected_post_id,
            "Current Buffer post ID mismatch")
    require(str(post.get("channelService", "")).lower() == expected_channel,
            "Buffer channel mismatch")
    require(post.get("status") == "sent",
            "Only actual Buffer sent posts are eligible; drafts/scheduled BLOCKED")
    text = post.get("text")
    require(isinstance(text, str) and text.strip(),
            "Current Buffer text missing")
    url = pinned_image_url(image_commit, image_path)
    media = post.get("assets")
    require(isinstance(media, list) and len(media) == 1,
            "Published post requires exactly one current image")
    asset = media[0]
    require(isinstance(asset, dict) and asset.get("source") == url and
            str(asset.get("type", "")).lower() == "image" and
            asset.get("mimeType") == "image/png",
            "Current Buffer image differs from final pinned image")
    require(isinstance(expected_image_sha256, str) and
            SHA64.fullmatch(expected_image_sha256),
            "Expected final image SHA256 missing")
    require(isinstance(actual_image_bytes, bytes) and
            len(actual_image_bytes) >= 10000 and
            actual_image_bytes.startswith(b"\x89PNG\r\n\x1a\n") and
            hashlib.sha256(actual_image_bytes).hexdigest() == expected_image_sha256,
            "Current final original bytes or SHA256 do not match")
    try:
        with Image.open(io.BytesIO(actual_image_bytes)) as image:
            require(image.format == "PNG" and image.size == (1080, 1350),
                    "Final published image must be actual 1080x1350 PNG")
            image.verify()
    except (UnidentifiedImageError, OSError) as exc:
        raise NewsSourceBlocked("Published PNG is corrupt") from exc
    return {
        "state": "verified_published_source_for_news_draft",
        "brand": brand, "buffer_post_id": expected_post_id,
        "buffer_channel": expected_channel, "buffer_status": "sent",
        "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "final_image_url": url, "final_image_sha256": expected_image_sha256,
        "website_publication_authorized": False,
        "visual_review": "required"
    }
