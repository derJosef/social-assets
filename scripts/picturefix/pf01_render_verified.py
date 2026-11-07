#!/usr/bin/env python3
"""Fail-closed logo compositing for PictureFix PF-01; never renders a substitute logo.

Requires the exact original PictureFix Web logo (verified by Git blob SHA-1)
and both previously approved logo-free draft PNGs (verified by SHA-256).
Does not touch the PictureFix application or Buffer.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from io import BytesIO
from zipfile import ZipFile, ZIP_DEFLATED

from PIL import Image, ImageDraw, ImageChops

LOGO_GIT_SHA = "0cd926e6631209dd4e5c8029dfb72c29bbf89ea8"
INPUTS = {
    "facebook_instagram": {
        "name": "PictureFix_01_Facebook_Instagram_1080x1350_ENTWURF_ohne_Logo.png",
        "sha256": "93c33a57e070626427c43e68327041a7b5c5a648256f045ccace793802ea7a92",
        "size": (1080, 1350),
        "output": "PictureFix_PF01_Facebook_Instagram_1080x1350_zur_Freigabe.png",
    },
    "pinterest": {
        "name": "PictureFix_01_Pinterest_1000x1500_ENTWURF_ohne_Logo.png",
        "sha256": "77c977abebd8d8b420586fe0efd16590eab08e4908434d4aded51c039586fcbe",
        "size": (1000, 1500),
        "output": "PictureFix_PF01_Pinterest_1000x1500_zur_Freigabe.png",
    },
}

def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def git_blob_sha(data: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(data)).encode("ascii") + b"\0" + data).hexdigest()

def load_verified(path: Path, *, expected_sha256: str | None = None, expected_blob: str | None = None) -> Image.Image:
    data = path.read_bytes()
    if expected_sha256 and sha256(data) != expected_sha256:
        raise ValueError(f"SHA-256 mismatch: {path.name}; refuse output")
    if expected_blob and git_blob_sha(data) != expected_blob:
        raise ValueError(f"Original PictureFix logo mismatch: {path.name}; refuse output")
    img = Image.open(BytesIO(data))
    img.load()
    if img.format != "PNG":
        raise ValueError(f"Not a PNG: {path.name}")
    return img.convert("RGBA")

def composite_exact(base: Image.Image, logo: Image.Image, role: str) -> tuple[Image.Image, tuple[int, int, int, int]]:
    """Apply only proportional scaling + alpha compositing to genuine logo pixels."""
    if role not in INPUTS:
        raise ValueError("Unknown PF-01 role")
    expected_size = INPUTS[role]["size"]
    if base.size != expected_size:
        raise ValueError(f"Bad draft dimensions for {role}: {base.size}")
    if logo.size[0] < 200 or logo.size[1] < 40:
        raise ValueError("Logo unexpectedly small")
    w, h = base.size
    target_w = 270 if role == "facebook_instagram" else 262
    target_h = round(logo.height * target_w / logo.width)
    resized = logo.resize((target_w, target_h), Image.Resampling.LANCZOS)
    x = w - target_w - 50
    y = (h - target_h - 76) if role == "facebook_instagram" else 1340
    pad_x, pad_y = 15, 13
    rect = (x - pad_x, y - pad_y, x + target_w + pad_x, y + target_h + pad_y)
    result = base.copy().convert("RGBA")
    panel = Image.new("RGBA", base.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(panel)
    d.rounded_rectangle(rect, radius=15, fill=(250, 247, 241, 230))
    result = Image.alpha_composite(result, panel)
    result.alpha_composite(resized, (x, y))
    return result, rect

def render(draft_dir: Path, logo_path: Path, dest: Path) -> dict:
    # Verify every input and fail without writing anything if one is wrong.
    logo_bytes = logo_path.read_bytes()
    if git_blob_sha(logo_bytes) != LOGO_GIT_SHA:
        raise ValueError("Unverified logo. Exact original required.")
    logo = load_verified(logo_path, expected_blob=LOGO_GIT_SHA)
    originals = {}
    for key, spec in INPUTS.items():
        originals[key] = load_verified(draft_dir / spec["name"], expected_sha256=spec["sha256"])
    if not dest.exists():
        dest.mkdir(parents=True, exist_ok=True)
    manifest = {"project": "PictureFix PF-01", "status": "zur visuellen Einzelfreigabe – nicht automatisch veröffentlichen", "logo_git_blob_sha1": LOGO_GIT_SHA, "files": []}
    outputs = []
    for key, spec in INPUTS.items():
        img, rect = composite_exact(originals[key], logo, key)
        output = dest / spec["output"]
        img.save(output, format="PNG", optimize=True)
        actual = Image.open(output); actual.load()
        if actual.size != tuple(spec["size"]):
            raise AssertionError("Wrong output dimensions")
        # Pixel-preservation check: nothing outside logo panel is changed.
        mask = Image.new("L", img.size, 0)
        ImageDraw.Draw(mask).rectangle(rect, fill=255)
        out_cmp = img.copy().convert("RGBA")
        draft_cmp = originals[key].copy().convert("RGBA")
        out_cmp.paste((0, 0, 0, 0), (0, 0, img.width, img.height), mask)
        draft_cmp.paste((0, 0, 0, 0), (0, 0, img.width, img.height), mask)
        if ImageChops.difference(out_cmp.convert("RGB"), draft_cmp.convert("RGB")).getbbox() is not None:
            raise AssertionError("Unexpected pixel changes outside logo region")
        outputs.append(output)
        manifest["files"].append({"role": key, "filename": output.name, "sha256": sha256(output.read_bytes()), "size": list(img.size), "logo_panel_rect": list(rect)})
    mf = dest / "PictureFix_PF01_QA_Manifest.json"
    mf.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    outputs.append(mf)
    zpath = dest / "PictureFix_PF01_zur_Freigabe.zip"
    with ZipFile(zpath, "w", compression=ZIP_DEFLATED, compresslevel=6) as z:
        for path in outputs:
            z.write(path, arcname=path.name)
    with ZipFile(zpath) as z:
        if z.testzip() is not None or any(s.endswith(".zip") for s in z.namelist()):
            raise AssertionError("Invalid or nested ZIP")
    manifest["zip_sha256"] = sha256(zpath.read_bytes())
    return manifest

def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--draft-dir", type=Path, required=True)
    ap.add_argument("--logo", type=Path, required=True, help="Exact PictureFixLogo_Web.png")
    ap.add_argument("--output-dir", type=Path, required=True)
    args = ap.parse_args()
    print(json.dumps(render(args.draft_dir, args.logo, args.output_dir), ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
