#!/usr/bin/env python3
"""Offline 4:5 PNG normalization before the existing Adobe transfer.

Source and output SHA256 are explicit. This never proves visual QA, model
context, person rights, brand legitimacy or permission to post on Buffer.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image, UnidentifiedImageError

SIZE = (1080, 1350)
MAX_INPUT_BYTES = 16_000_000
MAX_DIMENSION = 4096
MAX_ASPECT_ERROR = 0.006


class ImageNormalizationBlocked(ValueError):
    """Source cannot safely be scaled to the approved 4:5 canvas."""


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def normalize(source: Path, output: Path, report: Path) -> dict:
    if not source.is_file() or not 0 < source.stat().st_size <= MAX_INPUT_BYTES:
        raise ImageNormalizationBlocked("Source PNG missing or exceeds 16 MB")
    if output.exists() or report.exists() or source.resolve() in (
        output.resolve(), report.resolve(),
    ) or output.resolve() == report.resolve():
        raise ImageNormalizationBlocked("No overwrite, alias, or destructive retry")
    try:
        with Image.open(source) as original:
            if original.format != "PNG":
                raise ImageNormalizationBlocked("Source must be PNG")
            w, h = original.size
            if (w < SIZE[0] or h < SIZE[1]
                    or max(w, h) > MAX_DIMENSION
                    or abs(w / h - SIZE[0] / SIZE[1]) > MAX_ASPECT_ERROR):
                raise ImageNormalizationBlocked("Source is not sufficiently close to 4:5 or too small")
            original.verify()
        with Image.open(source) as original:
            # No cropping, content generation, geometric rotation, or brand overlay.
            resized = original.convert("RGB").resize(SIZE, Image.Resampling.LANCZOS)
    except (OSError, UnidentifiedImageError, Image.DecompressionBombError) as exc:
        raise ImageNormalizationBlocked("Unreadable or unsafe PNG") from exc

    output.parent.mkdir(parents=True, exist_ok=True)
    report.parent.mkdir(parents=True, exist_ok=True)
    try:
        with output.open("xb") as dst:
            resized.save(dst, format="PNG")
        with Image.open(output) as final:
            if final.format != "PNG" or final.size != SIZE:
                raise ImageNormalizationBlocked("Normalized file not exact PNG 1080x1350")
            final.verify()
        result = {
            "schema_version": 1,
            "operation": "lanczos_scale_no_crop",
            "source_sha256": sha256(source),
            "source_size": [w, h],
            "output_sha256": sha256(output),
            "output_size": list(SIZE),
            "format": "PNG",
            "image_visual_qa_passed": False,
            "model_context_verified": False,
            "rights_and_platform_checks_verified": False,
            "buffer_or_publication_permitted": False,
        }
        with report.open("x", encoding="utf-8") as dst:
            json.dump(result, dst, ensure_ascii=False, indent=2)
            dst.write("\n")
        return result
    except BaseException:
        output.unlink(missing_ok=True)
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(normalize(args.source, args.output, args.report)))
        return 0
    except (OSError, ImageNormalizationBlocked) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    raise SystemExit(main())
