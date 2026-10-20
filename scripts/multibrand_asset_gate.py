#!/usr/bin/env python3
"""Strict offline image-output checker for all brands/job types. No mutation."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

from PIL import Image
from multibrand_contract import ConfigurationBlocked, load_registry, plan_job, require

MAX_ASSET_BYTES = 24 * 1024 * 1024
SHA_RE = re.compile(r"[0-9a-f]{64}\\Z")
SUPPORTED_FORMATS = {"png": "PNG", "webp": "WEBP"}

def validate_assets(manifest: dict, assets_root: Path, registry: dict | None = None) -> dict:
    require(isinstance(manifest, dict) and set(manifest) == {
        "brand_id", "kind", "run_id", "assets"
    }, "Unrecognized delivery manifest fields")
    brand = manifest["brand_id"]
    kind = manifest["kind"]
    run_id = manifest["run_id"]
    require(all(isinstance(v, str) for v in (brand, kind, run_id)),
            "Manifest identity must be strings")
    plan = plan_job(brand, kind, run_id,
                    registry if registry is not None else load_registry())
    expected = {item["path"]: item for item in plan["outputs"]}
    supplied = manifest["assets"]
    require(isinstance(supplied, list) and len(supplied) == len(expected) and expected,
            "Missing images, unconfigured brand or wrong asset count")
    digests = set()
    paths = set()
    result = []
    root = assets_root.resolve(strict=True)
    for entry in supplied:
        require(isinstance(entry, dict) and set(entry) == {"path", "sha256"},
                "Only pinned image path and hash are allowed")
        path = entry["path"]
        digest = entry["sha256"]
        require(isinstance(path, str) and path in expected and path not in paths,
                "Wrong brand, job, file or duplicate path")
        paths.add(path)
        require(isinstance(digest, str) and SHA_RE.fullmatch(digest) is not None,
                "Invalid asset SHA256")
        absolute = (root / path).resolve(strict=True)
        require(absolute.is_relative_to(root) and absolute.is_file(),
                "Asset escapes allowed checkout")
        require(0 < absolute.stat().st_size <= MAX_ASSET_BYTES,
                "Image file too large or empty")
        actual = hashlib.sha256(absolute.read_bytes()).hexdigest()
        require(actual == digest, "Image bytes differ from manifest hash")
        with Image.open(absolute) as image:
            image.verify()
        with Image.open(absolute) as image:
            require(image.format == SUPPORTED_FORMATS[expected[path]["format"]],
                    "Image has wrong internal PNG/WebP format")
            require(list(image.size) == expected[path]["dimensions"],
                    "Responsive image dimensions do not match profile")
        # For website menu rotation, no identical binary file may appear anywhere.
        if kind == "rotation":
            require(digest not in digests, "Repeated identical menu image")
        digests.add(digest)
        result.append({"path": path, "sha256": digest,
                       "dimensions": expected[path]["dimensions"]})
    return {
        "status": "technical-image-qa-pass",
        "brand_id": brand, "kind": kind, "run_id": run_id,
        "checked_count": len(result),
        "visual_review": "still-required",
        "publishing": "not-authorized",
        "assets": result
    }

def main() -> None:
    parser = argparse.ArgumentParser(description="Offline image gate; cannot publish")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--checkout", type=Path, default=Path("."))
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    print(json.dumps(validate_assets(manifest, args.checkout),
                     ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
