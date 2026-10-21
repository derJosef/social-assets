#!/usr/bin/env python3
"""One-time *draft-only* builder: three fingerprint-selfie campaign graphics.

Uses the repository's existing reviewed scene/layout and immutable logo compositor.
Never accesses Buffer, website hosting, or publication workflows.
"""
from __future__ import annotations
import hashlib
import json
import subprocess
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "media/source-images/2026-10-21-fingerabdruck-selfies"
CAMPAIGN = "2026-10-21-fingerabdruck-selfie"
SPECS = (
    ("01", "01-selfie.jpg", "DEIN FINGERABDRUCK IM SELFIE?"),
    ("02", "02-smartphone.jpg", "KANN KI DEIN SMARTPHONE ENTSPERREN?"),
    ("03", "03-datenschutz.jpg", "3 TIPPS ZUM SCHUTZ DEINER DATEN"),
)
LOGO_HASH = "15dc410d1a05b96c13466ddf3052ba9cc783cdd7252b74f4fb5c3f886510dea0"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def artifacts(number: str) -> dict[str, Path]:
    slug = f"{CAMPAIGN}-{number}"
    return {
        "source": ROOT / f"media/source-images/{slug}-source.png",
        "base": ROOT / f"media/source-images/{slug}-base.png",
        "final": ROOT / f"media/images/{slug}.png",
        "spec": ROOT / f"visual-reviews/{slug}.json",
        "receipt": ROOT / f"visual-reviews/{slug}-build-receipt.json",
    }


def assert_source(image: Image.Image, path: Path) -> None:
    w, h = image.size
    if w < 1080 or h < 1350 or abs(w / h - 0.8) > 0.006:
        raise ValueError(f"Ungeeignete 4:5-Bildabmessung {path}: {w} x {h}")


def prepare_spec(number: str, source_file: Path, heading: str) -> dict:
    sha = digest(source_file)
    relative = source_file.relative_to(ROOT).as_posix()
    return {
        "format_version": 1,
        "brand": "ai-agent-builder",
        "source": relative,
        "source_sha256": sha,
        "layout": "headline",
        "heading": heading,
        "visual_review": {
            "no_people": True, "no_robot": True,
            "no_foreign_logo": True, "no_generated_text": True,
            "plausible_details": True, "matches_topic": True,
            "heading_and_logo_space": True,
        },
        "review_evidence": (
            f"ChatGPT visually inspected raw campaign motive {number} on 2026-10-21. "
            "Only an isolated human hand or device appears, no identifiable face, "
            "no robot, foreign logo or generated text; visualized fingerprints "
            "are illustrative rather than real biometrics. NOT a human review. "
            "Josef must visually approve the complete branded image before publication."
        ),
        "chatgpt_review": {
            "kind": "chatgpt_visual_inspection_draft_only",
            "source_sha256": sha,
        },
    }


def build() -> list[dict]:
    logo = ROOT / "media/brand/logo-pauderer-original.png"
    if digest(logo) != LOGO_HASH:
        raise ValueError("UNVERAENDERTES ORIGINALLOGO NICHT GEFUNDEN")
    output = []
    for number, filename, headline in SPECS:
        p = artifacts(number)
        if any(path.exists() for path in p.values()):
            raise FileExistsError("Ausgabedatei existiert, fail-closed: " + number)
        source_jpg = ASSETS / filename
        with Image.open(source_jpg) as image:
            assert_source(image, source_jpg)
            image.convert("RGB").save(p["source"], "PNG", compress_level=2)
        spec = prepare_spec(number, p["source"], headline)
        p["spec"].parent.mkdir(parents=True, exist_ok=True)
        p["spec"].write_text(json.dumps(spec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        cmd = [
            sys.executable, str(ROOT / "scripts/social_portfolio_scene.py"),
            "--spec", str(p["spec"]), "--base", str(p["base"]),
            "--final", str(p["final"]),
            "--logo", str(logo), "--font", "/tmp/Inter.ttf",
        ]
        result = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, check=True)
        receipt = json.loads(result.stdout.strip().splitlines()[-1])
        if receipt.get("size") != [1080, 1350] or receipt.get("logo_qa", {}).get("logo_verified") is not True:
            raise RuntimeError("Bildgroesse oder originalgetreues Logo nicht verifiziert: " + number)
        if digest(p["final"]) != receipt["sha256"]:
            raise RuntimeError("Finalbild-Hash widerspruechlich: " + number)
        verified = {
            "number": number,
            "subject": headline,
            "source_jpg_sha256": digest(source_jpg),
            "source_png_sha256": digest(p["source"]),
            "base_sha256": digest(p["base"]),
            "final_sha256": receipt["sha256"],
            "logo_original_sha256": digest(logo),
            "size": receipt["size"],
            "logo_qa": receipt["logo_qa"],
            "final_image": p["final"].relative_to(ROOT).as_posix(),
            "status": "asset_technical_qa_passed_only_NOT_buffer_published",
        }
        p["receipt"].write_text(json.dumps(verified, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        output.append(verified)
    return output


if __name__ == "__main__":
    print(json.dumps(build(), ensure_ascii=False, indent=2))
