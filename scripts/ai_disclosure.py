#!/usr/bin/env python3
"""Deterministic "Powered by AI" caption and independently repeatable pixel gate.

This only handles the caption layer. It cannot establish whether an image contains
a real person, whether AI altered them, or whether Josef approved that depiction.
Those are documented human review gates in social_portfolio_scene.py.
"""
from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFont

SIZE = (1080, 1350)
TEXT = "Powered by AI"
FONT_SIZE = 42
MARGIN = 54
TEXT_COLOR = (245, 247, 250)  # off-white #F5F7FA
BACKGROUND = (7, 17, 31)     # navy #07111F
MIN_CONTRAST = 4.5


class DisclosureError(ValueError):
    """Missing, forged, unreadable or overlapping disclosure."""


def luminance(rgb: tuple[int, int, int]) -> float:
    def channel(value: int) -> float:
        srgb = value / 255
        return srgb / 12.92 if srgb <= 0.04045 else ((srgb + 0.055) / 1.055) ** 2.4
    return sum(weight * channel(v) for weight, v in zip((0.2126, 0.7152, 0.0722), rgb))


def contrast_ratio(a: tuple[int, int, int], b: tuple[int, int, int]) -> float:
    la, lb = luminance(a), luminance(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


def load_font(path: Path) -> ImageFont.FreeTypeFont:
    if not path.is_file():
        raise DisclosureError("Inter font file missing; cannot render or verify Powered by AI")
    try:
        font = ImageFont.truetype(str(path), FONT_SIZE)
    except OSError as exc:
        raise DisclosureError("Inter font file cannot be read") from exc
    # The production GitHub job downloads Google's Inter variable TTF at
    # /tmp/Inter.ttf. Its default axis is usually Regular, not Josefs
    # approved Inter Medium. Request the actual named Medium instance.
    if path.name == "Inter.ttf":
        try:
            font.set_variation_by_name("Medium")
        except OSError as exc:
            raise DisclosureError("Production Inter Medium instance unavailable") from exc
    return font


def geometry(font: ImageFont.FreeTypeFont) -> tuple[int, int, int, int]:
    """The outer navy capsule; 54px from left text edge, 54px from lower edge."""
    probe = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    _, _, width, height = probe.textbbox((0, 0), TEXT, font=font, anchor="lt")
    x, bottom = MARGIN, SIZE[1] - MARGIN
    y = bottom - height - 8
    return (x - 8, y - 6, x + width + 8, bottom)


def draw_disclosure(image: Image.Image, font: ImageFont.FreeTypeFont) -> tuple[int, int, int, int]:
    if image.size != SIZE:
        raise DisclosureError("Disclosure requires an exact 1080x1350 canvas")
    if contrast_ratio(TEXT_COLOR, BACKGROUND) < MIN_CONTRAST:
        raise DisclosureError("Powered by AI contrast under 4.5:1")
    box = geometry(font)
    if not (0 <= box[0] < box[2] < SIZE[0] and 0 <= box[1] < box[3] < SIZE[1]):
        raise DisclosureError("Powered by AI caption does not fit the canvas")
    d = ImageDraw.Draw(image)
    d.rounded_rectangle((box[0], box[1], box[2] - 1, box[3] - 1),
                        radius=6, fill=BACKGROUND)
    d.text((MARGIN, box[1] + 6), TEXT, font=font, fill=TEXT_COLOR, anchor="lt")
    return box


def apply_to_base(base_path: Path, font_path: Path) -> dict:
    """Apply only to a just-created base image; verify before the original-logo step."""
    font = load_font(font_path)
    with Image.open(base_path) as image:
        unmarked = image.convert("RGB")
    labeled = unmarked.copy()
    box = draw_disclosure(labeled, font)
    labeled.save(base_path, "PNG")
    verify_against_original(unmarked, base_path, font_path)
    return {"text": TEXT, "box": list(box), "font": "Inter Medium",
            "font_size_px": FONT_SIZE, "margin_px": MARGIN,
            "contrast_ratio": round(contrast_ratio(TEXT_COLOR, BACKGROUND), 2),
            "pixel_verified": True}


def verify_against_original(unmarked: Image.Image, labeled_path: Path,
                            font_path: Path) -> None:
    """Re-render from untouched base; rejects any change outside this exact recipe."""
    font = load_font(font_path)
    expected = unmarked.convert("RGB")
    draw_disclosure(expected, font)
    with Image.open(labeled_path) as image:
        actual = image.convert("RGB")
    if actual.size != SIZE or ImageChops.difference(expected, actual).getbbox():
        raise DisclosureError("Powered by AI artwork differs from the exact trusted overlay")


def verify_label_region(base_path: Path, font_path: Path) -> tuple[int, int, int, int]:
    """Independent repeatable gate: exact glyph pixels and colors inside opaque label."""
    font = load_font(font_path)
    box = geometry(font)
    expected = Image.new("RGB", SIZE, BACKGROUND)
    draw_disclosure(expected, font)
    with Image.open(base_path) as image:
        actual = image.convert("RGB")
        # convert("RGB") drops alpha; a transparent caption would still match.
        opaque = image.convert("RGBA").crop(box).getextrema()[3] == (255, 255)
    if actual.size != SIZE:
        raise DisclosureError("Caption base not 1080x1350")
    if not opaque:
        raise DisclosureError("Powered by AI caption is not fully opaque")
    # The four rounded corners are transparent to the original scene. Compare
    # only pixels actually owned by the caption, not the background corners.
    mask = Image.new("L", SIZE, 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        (box[0], box[1], box[2] - 1, box[3] - 1), radius=6, fill=255
    )
    delta = ImageChops.difference(expected, actual)
    owned = Image.composite(delta, Image.new("RGB", SIZE), mask)
    if owned.crop(box).getbbox():
        raise DisclosureError("Powered by AI missing, altered, too small, or low contrast")
    return box


def verify_no_logo_overlap(final_path: Path,
                           caption_box: tuple[int, int, int, int]) -> None:
    """Use placement stamped by the canonical compositor; do not infer logo location."""
    with Image.open(final_path) as final:
        raw = final.info.get("logo_placement")
        if not raw:
            raise DisclosureError("No canonical logo placement in final PNG")
        placement = json.loads(raw)
        if final.size != SIZE:
            raise DisclosureError("Incorrect final image dimensions")
    pad = int(placement["gap"]) + int(placement["stroke"]) if placement["frame"] else 0
    w = int(placement["logo_width"]) + 2 * pad
    h = int(placement["logo_height"]) + 2 * pad
    margin = int(placement["margin"])
    corner = (placement.get("logo_only_corner") if placement.get("logo_only")
              else {"top-left": "bottom-right", "top-right": "bottom-left",
                    "bottom-left": "top-right", "bottom-right": "top-left"}.get(placement["heading_corner"]))
    if corner not in {"top-left", "top-right", "bottom-left", "bottom-right"}:
        raise DisclosureError("Unsupported canonical logo corner")
    x = margin if corner.endswith("left") else SIZE[0] - margin - w
    y = margin if corner.startswith("top") else SIZE[1] - margin - h
    logo_box = (x, y, x+w, y+h)
    a, b = caption_box, logo_box
    if a[0] < b[2] and a[2] > b[0] and a[1] < b[3] and a[3] > b[1]:
        raise DisclosureError("Powered by AI overlaps original logo")


def verify_final_disclosure(base_path: Path, final_path: Path,
                            font_path: Path) -> tuple[int, int, int, int]:
    """Check the exact approved glyphs in BOTH images, plus logo placement.

    Canonical placement metadata alone cannot establish that the final pixels
    still show the caption. Recheck the final composite after the logo step.
    """
    caption = verify_label_region(base_path, font_path)
    verify_no_logo_overlap(final_path, caption)
    verify_label_region(final_path, font_path)
    return caption
