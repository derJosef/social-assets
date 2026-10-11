#!/usr/bin/env python3
"""Bind generated social-image URLs to an already committed Git object.

Offline file conversion only: no network access, no GitHub/Buffer mutation.
The caller must commit the reviewed image first, then run this pinning step,
then re-run the full campaign gate before pushing the complete output branch.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CID_RE = re.compile(r"20\d{2}-\d{2}-\d{2}-[a-z0-9]+(?:-[a-z0-9]+)*")
SHA_RE = re.compile(r"[0-9a-f]{40}")
TARGETS = ("linkedin", "facebook", "instagram")
PREFIX = "https://raw.githubusercontent.com/derJosef/social-assets/"


def pin(campaign: str, image_commit: str, root: Path = ROOT) -> list[str]:
    if not CID_RE.fullmatch(campaign) or not SHA_RE.fullmatch(image_commit):
        raise ValueError("Ungültige Kampagnen-ID oder Bild-Commit")
    path = f"media/images/{campaign}-branded.png"
    image = root / path
    if not image.is_file():
        raise ValueError("Freigegebenes Bild fehlt")
    # Prove that the immutable commit contains the EXACT local image bytes.
    expected_blob = subprocess.check_output(
        ["git", "rev-parse", f"{image_commit}:{path}"], cwd=root, text=True,
    ).strip()
    actual_blob = subprocess.check_output(
        ["git", "hash-object", path], cwd=root, text=True,
    ).strip()
    if not SHA_RE.fullmatch(expected_blob) or expected_blob != actual_blob:
        raise ValueError("Unveränderlicher Git-Commit enthält nicht das geprüfte Bild")
    manifest = json.loads((root / f"campaign-manifests/{campaign}.json").read_text(encoding="utf-8"))
    if (manifest.get("campaign_id") != campaign or manifest.get("image", {}).get("final") != path
            or manifest["image"]["sha256"] != hashlib.sha256(image.read_bytes()).hexdigest()):
        raise ValueError("Manifest und Image-Commit sind nicht identisch")

    expected_old = PREFIX + "main/" + path
    expected_new = PREFIX + image_commit + "/" + path
    prepared = []
    for target in TARGETS:
        name = f"ready-for-buffer/auto-{campaign}-{target}.json"
        if manifest["posts"].get(target) != name:
            raise ValueError("Manifest/Post-Bindung falsch")
        file = root / name
        obj = json.loads(file.read_text(encoding="utf-8"))
        if (obj.get("target") != target or obj.get("format_version") != 2
                or obj.get("media", {}).get("type") != "images"
                or len(obj["media"].get("images", [])) != 1
                or obj["media"]["images"][0].get("url") != expected_old):
            raise ValueError("Unbekannter oder bereits gepinnter Post; keine Teiländerungen")
        obj["media"]["images"][0]["url"] = expected_new
        prepared.append((file, json.dumps(obj, indent=2, ensure_ascii=False) + "\n"))
    for file, data in prepared:
        file.write_text(data, encoding="utf-8")
    return [str(file.relative_to(root)) for file, _ in prepared]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--campaign", required=True)
    parser.add_argument("--image-commit", required=True)
    args = parser.parse_args()
    changed = pin(args.campaign, args.image_commit)
    print("PINNED_IMMUTABLE_IMAGE", args.image_commit, ", ".join(changed))


if __name__ == "__main__":
    main()
