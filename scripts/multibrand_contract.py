#!/usr/bin/env python3
"""Read-only multibrand job contract. No image generation, credentials or publishing."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "automation/multibrand/brands.json"
BRAND_RE = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\\Z")
RUN_RE = re.compile(r"20[0-9]{2}-[0-9]{2}-[0-9]{2}-[a-z0-9]+(?:-[a-z0-9]+)*\\Z")
KINDS = ("social", "news", "rotation")
PERMISSIONS = {"social_draft", "social_publish", "news_publish", "rotation_publish"}
FORMATS = {"news_formats", "rotation_formats"}
RESERVED = {"secret", "token", "api_key", "password", "credential"}

class ConfigurationBlocked(ValueError):
    pass

def require(condition: bool, message: str) -> None:
    if not condition:
        raise ConfigurationBlocked(message)

def check_no_secrets(obj) -> None:
    if isinstance(obj, dict):
        for key, value in obj.items():
            require(key.lower() not in RESERVED, "Secrets must never appear in public profiles")
            check_no_secrets(value)
    elif isinstance(obj, list):
        for value in obj:
            check_no_secrets(value)

def load_registry(path: Path = REGISTRY) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(data, dict) and set(data) == {"schema_version", "configuration_status", "brands"},
            "Invalid registry envelope")
    require(data["schema_version"] == 1 and data["configuration_status"] == "pilot-only-no-deployment",
            "Only read-only registry pilot is supported")
    brands = data["brands"]
    require(isinstance(brands, dict) and brands, "Brand registry empty")
    check_no_secrets(data)
    for brand_id, profile in brands.items():
        require(bool(BRAND_RE.fullmatch(brand_id)), "Unsafe brand id")
        require(isinstance(profile, dict), "Brand profile must be an object")
        require(isinstance(profile.get("display_name"), str) and profile["display_name"],
                "Brand must have a display name")
        require(profile.get("logo_policy") in (
            "josef-original-sha-verified", "own-original-logo-not-josef", "unconfigured"
        ), "Missing brand-specific logo policy")
        website = profile.get("website")
        require(isinstance(website, dict) and set(website) == {
            "domain", "repository", "news_formats", "rotation_formats", "rotation_sections"
        }, "Incomplete website boundary")
        require(website["domain"] is None or (
            isinstance(website["domain"], str) and
            re.fullmatch(r"[a-z0-9.-]+", website["domain"]) is not None
        ), "Website domain must be verified ASCII domain or null")
        require(website["repository"] is None or (
            isinstance(website["repository"], str) and
            re.fullmatch(r"[A-Za-z0-9_-]+/[A-Za-z0-9_.-]+", website["repository"]) is not None
        ), "Invalid target repository")
        for key in FORMATS:
            variants = website[key]
            require(isinstance(variants, dict), "Formats must be a mapping")
            for name, dimensions in variants.items():
                require(name in ("desktop", "mobile", "thumbnail"), "Unrecognized format")
                require(isinstance(dimensions, list) and len(dimensions) == 2 and
                        all(type(value) is int and 400 <= value <= 4000 for value in dimensions),
                        "Invalid pixel dimensions")
        sections = website["rotation_sections"]
        require(isinstance(sections, list) and len(sections) == len(set(sections)) and
                all(isinstance(s, str) and BRAND_RE.fullmatch(s) for s in sections),
                "Duplicate or unsafe rotation section")
        channels = profile.get("social_channels")
        require(isinstance(channels, list) and len(channels) == len(set(channels)) and
                all(s in ("linkedin", "facebook", "instagram", "pinterest") for s in channels),
                "Unsupported or duplicate social channel")
        permissions = profile.get("permissions")
        require(isinstance(permissions, dict) and set(permissions) == PERMISSIONS and
                all(type(v) is bool for v in permissions.values()), "Invalid permission matrix")
        require(not permissions["social_publish"] and not permissions["news_publish"] and
                not permissions["rotation_publish"], "Pilot must never authorize publication")
        if brand_id != "ai-agent-builder":
            require(not permissions["social_draft"], "Other brands require separate draft consent")
        if permissions["social_draft"]:
            require(channels and brand_id == "ai-agent-builder", "Missing AI Agent Builder channels")
        if website["repository"] is None:
            require(not permissions["rotation_publish"] and not permissions["news_publish"],
                    "Cannot deliver to unknown repository")
    return data

def plan_job(brand_id: str, kind: str, run_id: str, registry: dict | None = None) -> dict:
    registry = registry if registry is not None else load_registry()
    require(kind in KINDS, "Unknown job type")
    require(bool(BRAND_RE.fullmatch(brand_id)), "Invalid brand id")
    require(bool(RUN_RE.fullmatch(run_id)), "Invalid run id")
    require(brand_id in registry["brands"], "Unknown brand")
    profile = registry["brands"][brand_id]
    site = profile["website"]
    prefix = f"generated/{brand_id}/{kind}/{run_id}/"
    outputs = []
    if kind == "social":
        for channel in profile["social_channels"]:
            outputs.append({"channel": channel, "path": prefix + channel + "-1080x1350.png",
                            "dimensions": [1080, 1350], "format": "png"})
        allowed_draft = profile["permissions"]["social_draft"]
    elif kind == "news":
        for variant, dims in site["news_formats"].items():
            outputs.append({"variant": variant, "path": prefix +
                            f"{variant}-{dims[0]}x{dims[1]}.webp",
                            "dimensions": dims, "format": "webp"})
        allowed_draft = False
    else:
        for section in site["rotation_sections"]:
            for variant, dims in site["rotation_formats"].items():
                outputs.append({"section": section, "variant": variant,
                                "path": prefix + section + "/" +
                                f"{variant}-{dims[0]}x{dims[1]}.webp",
                                "dimensions": dims, "format": "webp"})
        allowed_draft = False
    return {
        "brand_id": brand_id, "kind": kind, "run_id": run_id,
        "status": "offline-plan-only", "namespace": prefix,
        "outputs": outputs, "count": len(outputs),
        "permission_to_create_buffer_drafts": allowed_draft,
        "permission_to_publish": False,
        "website_repo": site["repository"] if kind != "social" else None,
        "logo_policy": profile["logo_policy"],
        "require_visual_review": True,
        "require_asset_hash_and_duplicate_check": True,
        "require_independent_delivery_receipt": True
    }

def main() -> None:
    parser = argparse.ArgumentParser(description="Offline brand isolation and asset plan")
    parser.add_argument("--brand", required=True)
    parser.add_argument("--kind", required=True, choices=KINDS)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    print(json.dumps(plan_job(args.brand, args.kind, args.run_id),
                     ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
