#!/usr/bin/env python3
"""Render a strictly logo-free, evidence-friendly campaign background from JSON.

The logo is never drawn here. Its insertion and verification belong exclusively
to the pinned PersonalOS-derived scripts/logo_composite.py.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

W = H = 1080
FONT_PATH = Path("/tmp/Inter.ttf")
REQUEST_RE = re.compile(r"^artwork-requests/(20\d{2}-\d{2}-\d{2})-[a-z0-9]+(?:-[a-z0-9]+)*\.json$")
BRAND = "ai-agent-builder"


def check_string(v, cap, field):
    if not isinstance(v, str) or not v.strip() or len(v) > cap or "\n" in v:
        raise ValueError(f"{field}: nonempty text max {cap} chars, single line required")
    return v.strip()


def read_spec(path: str, root: Path) -> dict:
    if not REQUEST_RE.fullmatch(path):
        raise ValueError("only artwork-requests/YYYY-MM-DD-<slug>.json is allowed")
    p = (root / path).resolve(strict=True)
    if not p.is_file() or not p.is_relative_to(root.resolve()):
        raise ValueError("invalid request file")
    spec = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(spec, dict) or set(spec) != {
        "format_version", "brand", "campaign_id", "badge", "headline",
        "subtitle", "cards", "closing"
    }:
        raise ValueError("unrecognized request schema")
    campaign = p.stem
    if spec["format_version"] != 1 or spec["brand"] != BRAND or spec["campaign_id"] != campaign:
        raise ValueError("brand/campaign mismatch")
    for key, cap in (("badge", 26), ("headline", 65), ("subtitle", 92), ("closing", 76)):
        check_string(spec[key], cap, key)
    cards = spec["cards"]
    if not isinstance(cards, list) or len(cards) != 3:
        raise ValueError("three numbered process cards required")
    for i, card in enumerate(cards):
        if not isinstance(card, dict) or set(card) != {"title", "description"}:
            raise ValueError("invalid process card")
        check_string(card["title"], 22, "title")
        check_string(card["description"], 56, "description")
    return spec


def load_font(path: Path, size: int, weight: str = ""):
    if not path.is_file():
        raise RuntimeError("Inter font unavailable; refuse unbranded fallback")
    f = ImageFont.truetype(str(path), size)
    if weight:
        try:
            f.set_variation_by_name(weight)
        except (OSError, ValueError):
            pass
    return f


def wrap_to_pixels(draw, text, font, width, max_lines):
    lines = []
    line = ""
    for word in text.split():
        candidate = (line + " " + word).strip()
        if draw.textlength(candidate, font=font) > width and line:
            lines.append(line)
            line = word
        else:
            line = candidate
    if line:
        lines.append(line)
    if len(lines) > max_lines or any(draw.textlength(s, font=font) > width for s in lines):
        raise ValueError(f"text does not fit safe area: {text}")
    return lines


def render_background(spec: dict, out: Path, font_path: Path = FONT_PATH) -> tuple[int, int, int, int]:
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        raise FileExistsError("never overwrite existing brand background: " + str(out))
    im = Image.new("RGB", (W, H))
    px = im.load()
    for y in range(H):
        for x in range(W):
            t = 0.52*x/W + 0.48*y/H
            px[x,y] = (7+round(7*t), 17+round(13*t), 31+round(23*t))
    d = ImageDraw.Draw(im, "RGBA")
    for x in range(48, W, 48):
        d.line([(x, 0), (x, H)], fill=(124, 156, 209, 13), width=1)
    for y in range(48, H, 48):
        d.line([(0, y), (W, y)], fill=(124, 156, 209, 13), width=1)
    small = load_font(font_path, 19)
    titlefont = load_font(font_path, 67, "Bold")
    subtitlefont = load_font(font_path, 28)
    cardtitle = load_font(font_path, 23)
    carddesc = load_font(font_path, 17)
    closingfont = load_font(font_path, 24)
    d.rounded_rectangle((56, 58, 330, 101), radius=21,
                        fill=(19,35,58,255), outline=(124,156,209,110), width=2)
    d.text((76, 69), spec["badge"], font=small, fill="#B6C4D0")
    headline = wrap_to_pixels(d, spec["headline"].upper(), titlefont, 915, 2)
    heading_end = 0
    for i, line in enumerate(headline):
        y = 150 + i * 88
        d.text((58, y), line, font=titlefont,
               fill="#F5F7FA" if i == 0 else "#7C9CD1")
        bbox = d.textbbox((58, y), line, font=titlefont)
        heading_end = max(heading_end, bbox[2])
    if heading_end > 1017:
        raise ValueError("heading intersects the edge")
    hbox = (58, 145, max(heading_end, 70), 328)
    subt = wrap_to_pixels(d, spec["subtitle"], subtitlefont, 950, 2)
    for i, line in enumerate(subt):
        d.text((60, 353 + i*39), line, font=subtitlefont, fill="#F5F7FA")
    d.line((106, 584, 973, 584), fill=(124, 156, 209, 125), width=5)
    for i, card in enumerate(spec["cards"]):
        x = (62, 395, 728)[i]
        d.rounded_rectangle((x, 475, x + 289, 744), radius=21,
                            fill=(19,35,58,245), outline=(124,156,209,130), width=2)
        d.rounded_rectangle((x+19, 494, x+85, 556), radius=12, fill=(37,64,107,255))
        d.text((x+31, 506), str(i+1).zfill(2), font=load_font(font_path, 30), fill="#F5F7FA")
        names = wrap_to_pixels(d, card["title"].upper(), cardtitle, 250, 1)
        d.text((x+19, 620), names[0], font=cardtitle, fill="#F5F7FA")
        descs = wrap_to_pixels(d, card["description"], carddesc, 255, 2)
        for j, line in enumerate(descs):
            d.text((x+19, 670+j*26), line, font=carddesc, fill="#B6C4D0")
        d.ellipse((x+126, 574, x+146, 594), fill="#147D78")
    d.line((60, 816, 700, 816), fill=(124,156,209,100), width=2)
    close = wrap_to_pixels(d, spec["closing"], closingfont, 635, 2)
    for i, line in enumerate(close):
        d.text((60, 850 + i*35), line, font=closingfont, fill="#F5F7FA")
    d.text((60, 1015), "AI AGENT BUILDER | PRAXISREIHE", font=load_font(font_path, 18),
           fill="#7C9CD1")
    im.save(out, format="PNG", optimize=True)
    print("BACKGROUND_PASS:", out, "heading_box=", ",".join(map(str,hbox)))
    return hbox


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--request", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--heading-output", required=True)
    p.add_argument("--font", default=str(FONT_PATH))
    args = p.parse_args()
    root = Path.cwd()
    spec = read_spec(args.request, root)
    heading = render_background(spec, root/args.output, Path(args.font))
    (root/args.heading_output).write_text(",".join(map(str, heading)), encoding="ascii")


if __name__ == "__main__":
    main()
