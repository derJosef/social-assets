#!/usr/bin/env python3
"""Offline staged responsive images for a single brand and job.

The agent/generator supplies separately composed, SHA-pinned source images.
This module only resizes when aspect ratios already match; it never crops,
upscales, draws a logo, changes a website, or contacts a social provider.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import tempfile
from pathlib import Path

from PIL import Image, UnidentifiedImageError

from multibrand_contract import ConfigurationBlocked, plan_job, require
from multibrand_asset_gate import validate_assets

HEX64 = re.compile(r"[0-9a-f]{64}\Z")
MAX_SOURCE_BYTES = 32 * 1024 * 1024
ASPECT_TOLERANCE = 0.008


def safe_source(base: Path, text: str, brand: str, kind: str, run_id: str) -> Path:
    require(isinstance(text, str), "Image input path must be text")
    root = base.resolve(strict=True)
    prefix = f"inputs/{brand}/{kind}/{run_id}/"
    require(text.startswith(prefix) and text.endswith((".png", ".webp")),
            "Source outside its own brand, job or run")
    require(not any(part in ("", ".", "..") for part in Path(text).parts),
            "Unsafe source name")
    path = (root / text).resolve(strict=True)
    require(path.is_relative_to(root) and path.is_file(),
            "Source must be a regular file inside input checkout")
    return path


def preflight_sources(spec: dict, checkout: Path, registry: dict | None = None) -> tuple[dict, list]:
    require(isinstance(spec, dict) and set(spec) == {
        "brand_id", "kind", "run_id", "sources"
    }, "Only immutable source job fields supported")
    brand, kind, run_id = spec["brand_id"], spec["kind"], spec["run_id"]
    require(all(isinstance(v, str) for v in (brand, kind, run_id)),
            "Run identity must be strings")
    require(kind in ("news", "rotation"), "Only website images supported here")
    plan = plan_job(brand, kind, run_id, registry)
    expected = {entry["path"]: entry for entry in plan["outputs"]}
    provided = spec["sources"]
    require(isinstance(provided, list) and len(provided) == len(expected) and expected,
            "Exactly the expected responsive images are required")
    seen_outputs, seen_sources, seen_hashes = set(), set(), set()
    checked = []
    for item in provided:
        require(isinstance(item, dict) and set(item) == {
            "output_path", "input_path", "sha256"
        }, "Invalid source entry schema")
        target_name, input_name, claimed_hash = (
            item["output_path"], item["input_path"], item["sha256"]
        )
        require(isinstance(target_name, str) and target_name in expected
                and target_name not in seen_outputs, "Unknown or duplicate output")
        require(isinstance(claimed_hash, str) and HEX64.fullmatch(claimed_hash),
                "Missing real source SHA256")
        source = safe_source(checkout, input_name, brand, kind, run_id)
        require(input_name not in seen_sources, "Input file reused across outputs")
        size = source.stat().st_size
        require(0 < size <= MAX_SOURCE_BYTES, "Source image exceeds size policy")
        actual_hash = hashlib.sha256(source.read_bytes()).hexdigest()
        require(actual_hash == claimed_hash, "Source SHA mismatch")
        if kind == "rotation":
            require(actual_hash not in seen_hashes, "Repeated source image in rotation")
        target_w, target_h = expected[target_name]["dimensions"]
        try:
            with Image.open(source) as image:
                require(image.format in ("PNG", "WEBP"),
                        "Source must really be PNG or WebP")
                image.verify()
            with Image.open(source) as image:
                width, height = image.size
                require(width >= target_w and height >= target_h,
                        "Refuse to upscale small responsive source")
                require(abs(width / height - target_w / target_h) <= ASPECT_TOLERANCE,
                        "Wrong aspect ratio; generate a dedicated composition instead of crop")
        except (UnidentifiedImageError, OSError, ValueError) as exc:
            raise ConfigurationBlocked("Damaged or invalid source image") from exc
        checked.append((target_name, source, (target_w, target_h)))
        seen_outputs.add(target_name)
        seen_sources.add(input_name)
        seen_hashes.add(actual_hash)
    return plan, checked


def stage_images(spec: dict, checkout: Path, output_root: Path,
                 registry: dict | None = None) -> dict:
    """Build atomically into generated/<brand>/<kind>/<run>/ with no overwrites."""
    plan, checked = preflight_sources(spec, checkout, registry)
    brand, kind, run_id = spec["brand_id"], spec["kind"], spec["run_id"]
    dest_root = output_root.resolve(strict=True)
    relative = Path("generated") / brand / kind / run_id
    final = dest_root / relative
    require(not final.exists(), "Refuse to overwrite existing campaign assets")
    parent = final.parent
    parent.mkdir(parents=True, exist_ok=True)
    work_root = dest_root / "generated" / brand / kind
    with tempfile.TemporaryDirectory(prefix=".stage-", dir=work_root) as temp:
        temp_path = Path(temp)
        assets = []
        for output_name, source, dimensions in checked:
            file_name = Path(output_name).relative_to(relative)
            dest = temp_path / file_name
            dest.parent.mkdir(parents=True, exist_ok=True)
            with Image.open(source) as image:
                mode = "RGBA" if "A" in image.getbands() else "RGB"
                resized = image.convert(mode).resize(dimensions, Image.Resampling.LANCZOS)
                resized.save(dest, "WEBP", quality=92, method=6, exact=True)
            assets.append({
                "path": output_name,
                "sha256": hashlib.sha256(dest.read_bytes()).hexdigest()
            })
        manifest = {"brand_id": brand, "kind": kind,
                    "run_id": run_id, "assets": assets}
        # Verify actual bytes/dimensions against the contract BEFORE atomic promotion.
        # A temporary checkout uses the same required output names.
        # Only move files into place after every output exists and validates locally.
        for item in assets:
            target = temp_path / Path(item["path"]).relative_to(relative)
            with Image.open(target) as image:
                require(image.format == "WEBP", "Unexpected staged format")
                image.verify()
        (temp_path / "asset-manifest.json").write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        require(not final.exists(), "Concurrent output already exists")
        temp_path.rename(final)
    # Complete readback with the shared technical gate; never mark visual approval.
    return validate_assets(manifest, dest_root, registry)


def main() -> None:
    parser = argparse.ArgumentParser(description="Offline responsive staging, no publishing")
    parser.add_argument("--sources", type=Path, required=True)
    parser.add_argument("--checkout", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    spec = json.loads(args.sources.read_text(encoding="utf-8"))
    print(json.dumps(stage_images(spec, args.checkout, args.output_root),
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
