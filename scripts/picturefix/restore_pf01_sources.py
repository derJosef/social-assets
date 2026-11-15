#!/usr/bin/env python3
"""Restore exactly the two Josef-uploaded PictureFix PF-01 style references.

The .part files are *binary* fragments of the uploaded PNGs. Fragments exist
because the GitHub file-transfer connector has a request-size limit. This
utility makes no image edits and does not publish or queue Buffer posts.
"""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import struct

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PARTS = REPO_ROOT / "media/source-images/picturefix/pf01/parts"
DEFAULT_OUTPUT = REPO_ROOT / "media/source-images/picturefix/pf01/reconstructed"
SOURCES = {
    "PictureFix_Stilreferenz_01_freigegeben.png": {
        "parts": 5,
        "sha256": "5b4b189d7a82d6f6610f146444514f8da9955f44651cc5f56d86048c364df792",
        "size": 3155095,
        "dimensions": (1122, 1402),
    },
    "PictureFix_Stilvergleich_02_fruehe_Variante.png": {
        "parts": 4,
        "sha256": "5c5fc47003b2fbb40be35f1c20a22b356b2441d6f0d93b3e9d2480453c04633a",
        "size": 3009445,
        "dimensions": (1122, 1402),
    },
}


def restore(parts_dir: Path, output_dir: Path) -> None:
    verified: list[tuple[Path, bytes]] = []
    for filename, spec in SOURCES.items():
        paths = [parts_dir / f"{filename}.part{i:02d}" for i in range(1, spec["parts"] + 1)]
        data = b"".join(path.read_bytes() for path in paths)
        sha = hashlib.sha256(data).hexdigest()
        if len(data) != spec["size"] or sha != spec["sha256"]:
            raise ValueError(f"Original-byte verification failed for {filename}: {sha}")
        if not data.startswith(b"\x89PNG\r\n\x1a\n") or data[12:16] != b"IHDR":
            raise ValueError(f"Not a valid PNG header: {filename}")
        dimensions = struct.unpack(">II", data[16:24])
        if dimensions != spec["dimensions"]:
            raise ValueError(f"Dimensions mismatch for {filename}: {dimensions}")
        destination = output_dir / filename
        if destination.exists() and destination.read_bytes() != data:
            raise FileExistsError(f"Refusing to overwrite nonidentical file: {destination}")
        verified.append((destination, data))
    output_dir.mkdir(parents=True, exist_ok=True)
    for destination, data in verified:
        destination.write_bytes(data)
        print(f"VERIFIED {destination.name}: {hashlib.sha256(data).hexdigest()}")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--parts-dir", type=Path, default=DEFAULT_PARTS)
    p.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = p.parse_args()
    restore(args.parts_dir, args.output_dir)


if __name__ == "__main__":
    main()
