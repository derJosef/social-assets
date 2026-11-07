#!/usr/bin/env python3
"""Transfer one LinkedIn/Facebook/Instagram post as a Buffer draft, never queue.

No external calls in dry-run mode. Live sending is only possible with --send,
configured GitHub Actions secrets and a reservation receipt in this repository.
Approved auto-campaign drafts can carry a future dueAt while remaining drafts.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
import re
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

try:
    from .buffer_error_diagnostics import safe_mutation_diagnosis
    from .buffer_rate_limits import report_limits, retry_after_seconds
except ImportError:
    from buffer_error_diagnostics import safe_mutation_diagnosis
    from buffer_rate_limits import report_limits, retry_after_seconds

ROOT = Path(__file__).resolve().parents[1]
BUFFER_ENDPOINT = "https://api.buffer.com"
REPOSITORY = "derJosef/social-assets"
RECEIPT_BRANCH = "automation-receipts"

# The only Buffer mutation in this script. There is no scheduling or publish path.
CREATE_DRAFT = """
mutation CreateDraft($text: String!, $channelId: ChannelId!, $assets: [AssetInput!]!, $metadata: PostInputMetaData) {
  createPost(input: {
    text: $text
    channelId: $channelId
    schedulingType: automatic
    mode: addToQueue
    saveToDraft: true
    assets: $assets
    metadata: $metadata
  }) {
    __typename
    ... on PostActionSuccess { post { id text } }
    ... on MutationError { message }
  }
}
"""

# The one-off live acceptance run #38179032859 proved this exact Buffer mode:
# dueAt is stored on a DRAFT, never queued for automatic publication.
CREATE_DATED_DRAFT = """
mutation CreateDatedDraft($text: String!, $channelId: ChannelId!, $assets: [AssetInput!]!, $metadata: PostInputMetaData, $dueAt: DateTime!) {
  createPost(input: {
    text: $text
    channelId: $channelId
    schedulingType: automatic
    mode: customScheduled
    dueAt: $dueAt
    saveToDraft: true
    assets: $assets
    metadata: $metadata
  }) {
    __typename
    ... on PostActionSuccess { post { id channelId status dueAt } }
    ... on MutationError { message }
  }
}
"""

READ_DATED_DRAFT = """
query VerifyDatedDraft($id: PostId!) {
  post(input: { id: $id }) { id channelId status dueAt }
}
"""

# Same Buffer GraphQL adapter; isolated undated brand preview only.
READ_PICTUREFIX_DRAFT = """
query VerifyPictureFixDraft($id: PostId!) {
  post(input: { id: $id }) {
    id channelId channelService status dueAt text
    assets { type source }
  }
}
"""
PICTUREFIX_LOGO_BLOB = "0cd926e6631209dd4e5c8029dfb72c29bbf89ea8"
PICTUREFIX_DRAFT_NAMES = {
    "facebook": "drafts/picturefix-pf01-facebook.json",
    "instagram": "drafts/picturefix-pf01-instagram.json",
    "pinterest": "drafts/picturefix-pf01-pinterest.json",
}
PICTUREFIX_IMAGE_NAME = "PictureFix_PF01_Facebook_Instagram_1080x1350_zur_Freigabe.png"
PICTUREFIX_PINTEREST_IMAGE_NAME = "PictureFix_PF01_Pinterest_1000x1500_zur_Freigabe.png"
PICTUREFIX_IMAGE_NAMES = {
    "facebook": PICTUREFIX_IMAGE_NAME,
    "instagram": PICTUREFIX_IMAGE_NAME,
    "pinterest": PICTUREFIX_PINTEREST_IMAGE_NAME,
}
PICTUREFIX_IMAGE_SIZES = {
    "facebook": (1080, 1350),
    "instagram": (1080, 1350),
    "pinterest": (1000, 1500),
}
# Buffer's public GraphQL schema exposes organization names and channel names.
# Discovery fails closed unless the PictureFix account has the exact approved
# organization and three connected profiles. Never enumerate AAB channels.
PICTUREFIX_EXPECTED_PROFILES = {
    "facebook": "PictureFix Fotorestaurierung",
    "instagram": "picturefix.de",
    "pinterest": "picturefixde",
}
GET_PICTUREFIX_ORGANIZATIONS = """
query PictureFixOrganizations {
  account { organizations { id name channelCount } }
}
"""
GET_PICTUREFIX_CHANNELS = """
query PictureFixChannels($organizationId: OrganizationId!) {
  channels(input: { organizationId: $organizationId }) {
    id name service organizationId isDisconnected isLocked
  }
}
"""
GET_PICTUREFIX_PINTEREST_BOARDS = """
query PictureFixPinterestBoards($id: ChannelId!) {
  channel(input: { id: $id }) {
    id
    metadata {
      ... on PinterestMetadata {
        boards { serviceId }
      }
    }
  }
}
"""

AUTO_DRAFT_RE = re.compile(
    r"^ready-for-buffer/auto-(20\d{2}-\d{2}-\d{2}-[a-z0-9]+(?:-[a-z0-9]+)*)-"
    r"(linkedin|facebook|instagram)\.json$"
)

GET_ORGANIZATIONS = """
query GetOrganizations {
  account { organizations { id } }
}
"""

GET_CHANNELS = """
query GetChannels($organizationId: OrganizationId!) {
  channels(input: { organizationId: $organizationId }) {
    id
    service
  }
}
"""


def json_http(url: str, *, token: str, method: str = "GET", payload: dict | None = None) -> dict:
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(
        url,
        method=method,
        data=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json" if "api.github.com/" in url else "application/json",
            "Content-Type": "application/json",
            "User-Agent": "social-assets-buffer-draft/1.0",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=25) as response:
            if urllib.parse.urlsplit(url).hostname == "api.buffer.com":
                report_limits(response.headers)
            result = json.load(response)
            if not isinstance(result, dict):
                raise RuntimeError("Unerwartetes API-Antwortformat.")
            return result
    except urllib.error.HTTPError as exc:
        # Never retry a draft mutation: Buffer might have created the post already.
        # Do not expose credentials, partition keys or confidential response bodies.
        if exc.code == 429 and urllib.parse.urlsplit(url).hostname == "api.buffer.com":
            report_limits(exc.headers)
            delay = retry_after_seconds(exc.headers)
            wait = f"{delay}s" if delay is not None else "unbekannt"
            raise RuntimeError(
                f"Buffer API-Limit erreicht (HTTP 429); Retry-After={wait}. "
                "Kein automatischer Retry. Restkontingent/Buffer-Drafts prüfen."
            ) from exc
        raise RuntimeError(f"HTTP {exc.code} bei {urllib.parse.urlsplit(url).hostname}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError("API-Verbindung fehlgeschlagen.") from exc


def buffer_graphql(token: str, query: str, variables: dict) -> dict:
    result = json_http(
        BUFFER_ENDPOINT,
        token=token,
        method="POST",
        payload={"query": query, "variables": variables},
    )
    if result.get("errors"):
        raise RuntimeError("Buffer meldet einen GraphQL-Fehler (Details im Buffer-Konto prüfen).")
    data = result.get("data")
    if not isinstance(data, dict):
        raise RuntimeError("Buffer hat keine gültigen Daten zurückgegeben.")
    return data


def read_draft(given_path: str) -> tuple[str, str, bytes]:
    """Only read a JSON file from drafts/ or ready-for-buffer/, never other paths."""
    path = (ROOT / given_path).resolve(strict=True)
    allowed = ("drafts", "ready-for-buffer")
    accepted_path = None
    for folder in allowed:
        folder_root = (ROOT / folder).resolve()
        if path.is_relative_to(folder_root):
            relative = path.relative_to(folder_root)
            if len(relative.parts) != 1:
                raise ValueError("Entwurfsdateien dürfen keine Unterordner verwenden.")
            accepted_path = f"{folder}/{relative.as_posix()}"
            break
    if accepted_path is None:
        raise ValueError("Die Datei muss unter drafts/ oder ready-for-buffer/ liegen.")
    if path.suffix.lower() != ".json" or not path.is_file():
        raise ValueError("Eine vorhandene JSON-Datei im freigegebenen Ordner ist erforderlich.")
    raw = path.read_bytes()
    if len(raw) > 100_000:
        raise ValueError("Entwurfsdatei ist zu groß.")
    record = json.loads(raw.decode("utf-8"))
    if not isinstance(record, dict) or record.get("target") not in ("linkedin", "facebook", "instagram", "pinterest"):
        raise ValueError("Unzulässiger Zielkanal.")
    fmt = record.get("format_version")
    if record["target"] == "pinterest" and fmt != 3:
        raise ValueError("Pinterest ist nur für den kontrollierten PictureFix-Pilot erlaubt.")
    if fmt == 1 and set(record) != {"format_version", "target", "text"}:
        raise ValueError("Format 1 erlaubt nur format_version, target und text.")
    if fmt == 2 and set(record) != {"format_version", "target", "text", "media"}:
        raise ValueError("Format 2 benötigt genau format_version, target, text und media.")
    if fmt == 3:
        # A new brand may not inherit the original AI-Agent-Builder draft authority.
        expected = {"format_version", "brand", "target", "text", "media",
                    "image_sha256", "logo_git_blob_sha1"}
        if record["target"] == "pinterest":
            expected |= {"pinterest_title", "pinterest_url"}
        if set(record) != expected or record["brand"] != "picturefix":
            raise ValueError("PictureFix requires its complete brand-specific draft.")
        if record["target"] == "pinterest":
            title = record["pinterest_title"]
            if not isinstance(title, str) or not 1 <= len(title.strip()) <= 100:
                raise ValueError("PictureFix Pinterest requires a short pin title.")
            if record["pinterest_url"] != "https://picturefix.de":
                raise ValueError("PictureFix Pinterest uses only the verified homepage URL.")
        target = record["target"]
        if target not in PICTUREFIX_DRAFT_NAMES or accepted_path != PICTUREFIX_DRAFT_NAMES[target]:
            raise ValueError("PictureFix allows only two fixed PF-01 draft filenames.")
        if (not isinstance(record["image_sha256"], str)
                or not re.fullmatch(r"[0-9a-f]{64}", record["image_sha256"])
                or record["logo_git_blob_sha1"] != PICTUREFIX_LOGO_BLOB):
            raise ValueError("PictureFix approved source image/logo provenance missing.")
        media = record["media"]
        if (not isinstance(media, dict) or set(media) != {"type", "images"}
                or media.get("type") != "images"
                or not isinstance(media.get("images"), list) or len(media["images"]) != 1):
            raise ValueError("PictureFix PF-01 requires exactly one image.")
        image = media["images"][0]
        if not isinstance(image, dict) or set(image) != {"url", "alt_text"}:
            raise ValueError("PictureFix image requires URL and alt text.")
        url = validate_media_url(image["url"], "images")
        suffix = url[len(MEDIA_HOST_PREFIX):]
        commit, slash, media_path = suffix.partition("/")
        if (not slash or not re.fullmatch(r"[a-f0-9]{40}", commit)
                or media_path != "media/images/" + PICTUREFIX_IMAGE_NAMES[target]):
            raise ValueError("PictureFix needs a pinned final PF-01 image with original logo.")
    if fmt not in (1, 2, 3):
        raise ValueError("Unbekanntes Entwurfsformat.")
    target = record["target"]
    assets = parse_assets(raw)
    if target == "instagram" and not assets:
        raise ValueError("Instagram benötigt mindestens ein Bild oder Video, reiner Text ist nicht erlaubt.")
    if target != "linkedin" and any("document" in asset for asset in assets):
        raise ValueError("PDF-Dokumente sind ausschließlich für LinkedIn freigegeben.")
    if target in ("facebook", "instagram") and len(assets) > 10:
        raise ValueError("Facebook und Instagram erlauben in dieser Integration maximal 10 Bilder.")
    text = record["text"]
    limit = 2200 if target == "instagram" else 3000
    if not isinstance(text, str) or not text.strip() or len(text) > limit:
        raise ValueError(f"Text ist leer, ungültig oder länger als {limit} Zeichen.")
    return accepted_path, text, raw



# This public repository owns all media. Never send private URLs or tokens to Buffer.
MEDIA_HOST_PREFIX = "https://raw.githubusercontent.com/derJosef/social-assets/"
# Exactly the six approved, SHA-checked HostEurope PAF-TV exports, no generic external hosts.
PAF_VIDEO_BASE = "https://pauderer.de/assets/videos/social/"
PAF_VIDEO_FILENAMES = frozenset(
    f"PAF-TV_{number}_{slug}_{ratio}.mp4"
    for number, slug in (
        ("01", "ki-agenten"), ("02", "familienfoto"), ("03", "datenschutz")
    )
    for ratio in ("4x5", "9x16")
)
PAF_VIDEO_SIZES = {
    "PAF-TV_01_ki-agenten_4x5.mp4": 26304919,
    "PAF-TV_01_ki-agenten_9x16.mp4": 29094103,
    "PAF-TV_02_familienfoto_4x5.mp4": 22168912,
    "PAF-TV_02_familienfoto_9x16.mp4": 23865581,
    "PAF-TV_03_datenschutz_4x5.mp4": 18643541,
    "PAF-TV_03_datenschutz_9x16.mp4": 21181140,
}


def validate_paf_video_url(value: object) -> str:
    """No redirects, private hosts, query strings or arbitrary server paths."""
    if not isinstance(value, str) or len(value) > 320:
        raise ValueError("Ungültige Video-URL.")
    parsed = urllib.parse.urlsplit(value)
    if (
        parsed.scheme != "https" or parsed.netloc != "pauderer.de"
        or parsed.username or parsed.password or parsed.port
        or parsed.query or parsed.fragment
        or not value.startswith(PAF_VIDEO_BASE)
        or value[len(PAF_VIDEO_BASE):] not in PAF_VIDEO_FILENAMES
    ):
        raise ValueError("Nur freigegebene PAF-TV-MP4 auf pauderer.de zulässig.")
    return value


MEDIA_NAME_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,119}$")


def validate_media_url(value: object, category: str) -> str:
    if not isinstance(value, str) or len(value) > 320:
        raise ValueError("Ungültige Medien-URL.")
    parsed = urllib.parse.urlsplit(value)
    if (
        parsed.scheme != "https"
        or parsed.netloc != "raw.githubusercontent.com"
        or parsed.query or parsed.fragment
        or parsed.username or parsed.password or parsed.port
        or not value.startswith(MEDIA_HOST_PREFIX)
    ):
        raise ValueError("Medien müssen direkt aus dem öffentlichen social-assets/media/ kommen.")
    repo_suffix = value[len(MEDIA_HOST_PREFIX):]
    git_ref, slash, suffix = repo_suffix.partition("/")
    if not slash or (git_ref != "main" and not re.fullmatch(r"[0-9a-f]{40}", git_ref)):
        raise ValueError("Medien-Ref muss main oder ein unveränderlicher Git-Commit sein.")
    if not suffix.startswith("media/"):
        raise ValueError("Medien müssen unter media/ liegen.")
    suffix = suffix[len("media/"):]
    parts = suffix.split("/")
    if len(parts) != 2 or parts[0] != category or not MEDIA_NAME_RE.fullmatch(parts[1]):
        raise ValueError("Medienpfad muss ein Dateiname unter media/images oder media/documents sein.")
    extension = Path(parts[1]).suffix.lower()
    if category == "images" and extension not in {".png", ".jpg", ".jpeg", ".webp"}:
        raise ValueError("Unterstützt werden PNG, JPG und WebP.")
    if category == "documents" and extension != ".pdf":
        raise ValueError("Ein Karussell-Dokument muss eine PDF-Datei sein.")
    return value


def parse_assets(raw: bytes) -> list[dict]:
    """Validate declarative assets. Offline: no network call, no Buffer mutation."""
    record = json.loads(raw.decode("utf-8"))
    if record.get("format_version") == 1:
        return []
    if record.get("format_version") not in (2, 3):
        raise ValueError("Unbekanntes Entwurfsformat.")
    media = record.get("media")
    if not isinstance(media, dict):
        raise ValueError("Format 2 benötigt ein media-Objekt.")
    kind = media.get("type")
    if kind == "images":
        if set(media) != {"type", "images"}:
            raise ValueError("Bilder benötigen type und images.")
        images = media["images"]
        if not isinstance(images, list) or not 1 <= len(images) <= 20:
            raise ValueError("Pro LinkedIn-Beitrag sind 1 bis 20 Bilder zulässig.")
        assets = []
        for image in images:
            if not isinstance(image, dict) or set(image) != {"url", "alt_text"}:
                raise ValueError("Pro Bild sind url und alt_text erforderlich.")
            url = validate_media_url(image["url"], "images")
            alt = image["alt_text"]
            if not isinstance(alt, str) or not 1 <= len(alt.strip()) <= 1000:
                raise ValueError("Ein sinnvoller Bild-Alternativtext ist erforderlich.")
            assets.append({"image": {"url": url, "metadata": {"altText": alt.strip()}}})
        if len(set(x["image"]["url"] for x in assets)) != len(assets):
            raise ValueError("Doppelte Bild-URLs in einem Beitrag sind nicht zulässig.")
        return assets
    if kind == "video":
        if set(media) != {"type", "url"}:
            raise ValueError("Video benötigt nur type und url.")
        return [{"video": {"url": validate_paf_video_url(media["url"])}}]
    if kind == "document":
        if set(media) != {"type", "url", "thumbnail_url", "title"}:
            raise ValueError("PDF benötigt type, url, thumbnail_url und title.")
        pdf_url = validate_media_url(media["url"], "documents")
        thumb_url = validate_media_url(media["thumbnail_url"], "images")
        title = media["title"]
        if not isinstance(title, str) or not 1 <= len(title.strip()) <= 120:
            raise ValueError("Ein PDF-Dokumenttitel ist erforderlich.")
        return [{"document": {
            "url": pdf_url, "thumbnailUrl": thumb_url, "title": title.strip()
        }}]
    raise ValueError("Medientyp nur images, video oder document.")


def verify_media_access(assets: list[dict]) -> None:
    """Media preflight: public HTTPS + size and complete video HTTP download.

    Video full-body checking happens BEFORE reserving a Buffer draft receipt and
    can thus fail without risking duplicate Buffer posts. No video bytes are
    ever written to the repository.
    """
    for asset in assets:
        kind = next(iter(asset))
        media = asset[kind]
        pairs = [(media["url"], kind)]
        if kind == "document":
            pairs.append((media["thumbnailUrl"], "image"))
        for url, category in pairs:
            if category == "video":
                expected_size = PAF_VIDEO_SIZES[url[len(PAF_VIDEO_BASE):]]
                expected_mime = "video/mp4"
                size_limit = 95_000_000
            elif category == "document":
                expected_size = None
                expected_mime = "application/pdf"
                size_limit = 100_000_000
            else:
                expected_size = None
                expected_mime = "image/"
                size_limit = 10_000_000
            try:
                request = urllib.request.Request(
                    url, method="HEAD",
                    headers={"User-Agent": "social-assets-buffer-draft/1.0"}
                )
                with urllib.request.urlopen(request, timeout=25) as response:
                    if category == "video" and (response.geturl() != url or response.status != 200):
                        raise RuntimeError("Video-URL leitet um oder liefert kein HTTP 200.")
                    typ = response.headers.get("Content-Type", "").lower()
                    length = response.headers.get("Content-Length")
                    if typ and not (typ.startswith(expected_mime) or
                                    typ.startswith("application/octet-stream")):
                        raise RuntimeError("Unerwarteter Medien-MIME-Type.")
                    if category == "video" and (length is None or
                                                int(length) != expected_size):
                        raise RuntimeError("Video-Dateigröße stimmt nicht mit Release überein.")
                    if length is not None and int(length) > size_limit:
                        raise RuntimeError("Mediendatei überschreitet das Größenlimit.")
                if category == "video":
                    request = urllib.request.Request(
                        url, headers={"User-Agent": "social-assets-buffer-draft/1.0",
                                      "Accept-Encoding": "identity"}
                    )
                    total = 0
                    header = bytearray()
                    digest = hashlib.sha256()
                    with urllib.request.urlopen(request, timeout=110) as response:
                        if response.geturl() != url or response.status != 200:
                            raise RuntimeError("Vollständiger MP4-Download ist nicht direkt möglich.")
                        if not response.headers.get("Content-Type", "").lower().startswith("video/mp4"):
                            raise RuntimeError("Vollständiger Abruf ist kein MP4.")
                        while True:
                            chunk = response.read(1024 * 1024)
                            if not chunk:
                                break
                            if len(header) < 64:
                                header.extend(chunk[:64 - len(header)])
                            total += len(chunk)
                            if total > expected_size:
                                raise RuntimeError("Vollständiger MP4-Abruf ist zu groß.")
                            digest.update(chunk)
                    if total != expected_size or b"ftyp" not in header[:24]:
                        raise RuntimeError("MP4 beim vollständigen Herunterladen beschädigt.")
                    print(f"MP4_FULL_GET_VERIFIED {url.rsplit('/', 1)[-1]} "
                          f"bytes={total} sha256={digest.hexdigest()}", flush=True)
            except urllib.error.HTTPError as exc:
                raise RuntimeError(f"Medien-Link nicht öffentlich abrufbar: HTTP {exc.code}.") from exc
            except urllib.error.URLError as exc:
                raise RuntimeError("Öffentliche Medien-URL ist nicht erreichbar.") from exc


def verify_auto_image_bytes(draft_path: str, assets: list[dict]) -> None:
    """Check fetched image bytes against approved local artwork before Buffer sees it.

    A SHA URL is immutable, but its commit could name a different image. HEAD
    alone proves access, not identity. Verify both before reserving a receipt.
    """
    match = AUTO_DRAFT_RE.fullmatch(draft_path)
    if match is None or not assets:
        return
    manifest_path = ROOT / "campaign-manifests" / (match.group(1) + ".json")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    expected = manifest["image"]["sha256"]
    if not isinstance(expected, str) or not re.fullmatch(r"[0-9a-f]{64}", expected):
        raise RuntimeError("Fehlender geprüfter Bild-Fingerprint")
    for asset in assets:
        if "image" not in asset:
            raise RuntimeError("Auto-Kampagnen benötigen geprüfte Bilder")
        url = asset["image"]["url"]
        try:
            with urllib.request.urlopen(urllib.request.Request(
                url, headers={"User-Agent": "social-assets-buffer-draft/1.0"}), timeout=25,
            ) as response:
                raw = response.read(10_000_001)
        except (urllib.error.HTTPError, urllib.error.URLError) as exc:
            raise RuntimeError("Gepinntes öffentliches Bild nicht abrufbar") from exc
        if len(raw) > 10_000_000 or hashlib.sha256(raw).hexdigest() != expected:
            raise RuntimeError("GitHub-Bildinhalt stimmt nicht mit dem freigegebenen Bild überein")



def verify_picturefix_image_bytes(record: dict, assets: list[dict]) -> None:
    """Verify the real immutable PNG bytes before any Buffer side effect."""
    if record.get("format_version") != 3:
        return
    if len(assets) != 1 or "image" not in assets[0]:
        raise RuntimeError("PictureFix needs exactly one original image.")
    url = assets[0]["image"]["url"]
    try:
        with urllib.request.urlopen(urllib.request.Request(
            url, headers={"User-Agent": "social-assets-picturefix-draft/1.0"}
        ), timeout=45) as response:
            if response.status != 200 or response.geturl() != url:
                raise RuntimeError("PictureFix image redirected or not HTTP 200.")
            raw_image = response.read(10_000_001)
    except (urllib.error.HTTPError, urllib.error.URLError) as exc:
        raise RuntimeError("PictureFix original PNG not accessible.") from exc
    if (len(raw_image) > 10_000_000 or
            hashlib.sha256(raw_image).hexdigest() != record["image_sha256"]):
        raise RuntimeError("PictureFix image SHA-256 verification failed.")
    if (len(raw_image) < 24 or raw_image[:8] != bytes((137, 80, 78, 71, 13, 10, 26, 10))
            or raw_image[12:16] != b"IHDR"
            or (int.from_bytes(raw_image[16:20], "big"),
                int.from_bytes(raw_image[20:24], "big")) != PICTUREFIX_IMAGE_SIZES[record["target"]]):
        raise RuntimeError("PictureFix PNG signature/dimensions mismatch.")
    # A matching filename and IHDR header are insufficient: decode and
    # verify all PNG chunks, including checksums, before Buffer is touched.
    from io import BytesIO
    from PIL import Image, UnidentifiedImageError
    try:
        with Image.open(BytesIO(raw_image)) as verified:
            if verified.format != "PNG" or verified.size != PICTUREFIX_IMAGE_SIZES[record["target"]]:
                raise RuntimeError("PictureFix PNG dimensions or structure invalid.")
            verified.verify()
    except (OSError, SyntaxError, ValueError, UnidentifiedImageError) as exc:
        raise RuntimeError("PictureFix original PNG decoding/integrity failed.") from exc


def verified_picturefix_post(post: object, *, post_id: str, channel_id: str,
                             target: str, original_text: str) -> str | None:
    """Independent Buffer GET confirms unpublished image-bearing post."""
    if not isinstance(post, dict):
        return None
    if (post.get("id") != post_id or post.get("channelId") != channel_id
            or str(post.get("channelService", "")).lower() != target
            or str(post.get("status", "")).lower() != "draft"
            or post.get("dueAt") is not None or post.get("text") != original_text):
        return None
    media = post.get("assets")
    if (not isinstance(media, list) or len(media) != 1 or not isinstance(media[0], dict)
            or str(media[0].get("type", "")).lower() != "image"):
        return None
    url = media[0].get("source")
    if not isinstance(url, str) or len(url) > 1600:
        return None
    parsed = urllib.parse.urlsplit(url)
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username
            or parsed.password or parsed.port is not None or parsed.fragment):
        return None
    return url


def platform_metadata(target: str, *, video: bool = False, pinterest_board_id: str = "",
                      pinterest_title: str = "", pinterest_url: str = "") -> dict | None:
    """Mandatory channel-specific post input metadata, independent of publication mode."""
    if target == "facebook":
        return {"facebook": {"type": "post"}}
    if target == "instagram":
        return {"instagram": {"type": "reel" if video else "post", "shouldShareToFeed": True}}
    if target == "pinterest":
        if not pinterest_board_id or not pinterest_title or pinterest_url != "https://picturefix.de":
            raise ValueError("Verified Pinterest board, title and destination required.")
        return {"pinterest": {"boardServiceId": pinterest_board_id,
                              "title": pinterest_title, "url": pinterest_url}}
    if target == "linkedin":
        return None
    raise ValueError("Ungültiger Zielkanal.")



def receipt_path(draft_path: str) -> str:
    # One receipt per immutable draft filename; changing a sent file cannot resend it.
    digest = hashlib.sha256(draft_path.encode("utf-8")).hexdigest()[:24]
    return f"delivery-receipts/{digest}.json"


def github_contents_url(receipt: str) -> str:
    escaped = urllib.parse.quote(receipt, safe="/")
    return f"https://api.github.com/repos/{REPOSITORY}/contents/{escaped}"


def fetch_receipt(token: str, receipt: str) -> dict | None:
    # Historical, already-spent reservations live on main. They must remain
    # authoritative even after new receipts move to the automation branch.
    try:
        historical = json_http(github_contents_url(receipt) + "?ref=main", token=token)
    except RuntimeError as exc:
        if str(exc) != "HTTP 404 bei api.github.com":
            raise
    else:
        return historical
    # A missing receipt and a missing branch are both 404 on /contents. Fail
    # closed unless the independently provisioned ledger branch exists.
    json_http(f"https://api.github.com/repos/{REPOSITORY}/branches/{RECEIPT_BRANCH}", token=token)
    try:
        return json_http(github_contents_url(receipt) + f"?ref={RECEIPT_BRANCH}", token=token)
    except RuntimeError as exc:
        if str(exc) == "HTTP 404 bei api.github.com":
            return None
        raise


def put_receipt(token: str, receipt: str, content: dict, message: str, sha: str | None = None) -> str:
    payload = {
        "message": message,
        "content": base64.b64encode(
            (json.dumps(content, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        ).decode("ascii"),
        "branch": RECEIPT_BRANCH,
    }
    if sha:
        payload["sha"] = sha
    response = json_http(github_contents_url(receipt), token=token, method="PUT", payload=payload)
    saved = response.get("content") or {}
    if not saved.get("sha"):
        raise RuntimeError("GitHub hat den Empfangsbeleg nicht bestätigt.")
    return saved["sha"]


def resolve_channel(token: str, target: str, preferred_id: str = "",
                    *, channel_cache: dict | None = None) -> str:
    """Select one matching Buffer service; optionally reuse read-only lookup in this run."""
    if target not in ("linkedin", "facebook", "instagram", "pinterest"):
        raise ValueError("Unbekannter Buffer-Kanal.")
    # A cache is passed only during one CLI batch. No cross-run / persistent cache.
    if channel_cache is not None and "index" in channel_cache:
        index = channel_cache["index"]
    else:
        account = buffer_graphql(token, GET_ORGANIZATIONS, {}).get("account")
        if not isinstance(account, dict) or not isinstance(account.get("organizations"), list):
            raise RuntimeError("Buffer-Organisationen konnten nicht gelesen werden.")
        index = {"linkedin": set(), "facebook": set(), "instagram": set(), "pinterest": set()}
        for organization in account["organizations"]:
            org_id = organization.get("id") if isinstance(organization, dict) else None
            if not isinstance(org_id, str) or not org_id:
                raise RuntimeError("Buffer hat eine ungültige Organisations-ID geliefert.")
            channels = buffer_graphql(token, GET_CHANNELS, {"organizationId": org_id}).get("channels")
            if not isinstance(channels, list):
                raise RuntimeError("Buffer-Kanäle konnten nicht gelesen werden.")
            for channel in channels:
                if not isinstance(channel, dict):
                    raise RuntimeError("Buffer hat einen ungültigen Kanal geliefert.")
                service = str(channel.get("service", "")).lower()
                if service in index and channel.get("id"):
                    index[service].add(str(channel["id"]))
        if channel_cache is not None:
            channel_cache["index"] = index
    candidates = index[target]
    if preferred_id:
        if preferred_id not in candidates:
            raise RuntimeError(f"Vorgegebene Kanal-ID passt nicht zu einem {target}-Kanal.")
        return preferred_id
    if not candidates:
        raise RuntimeError(f"Kein {target}-Kanal in Buffer verbunden oder für den API-Schlüssel sichtbar.")
    if len(candidates) != 1:
        raise RuntimeError(
            f"Mehrere {target}-Kanäle gefunden; eindeutige BUFFER_*_CHANNEL_ID erforderlich."
        )
    return next(iter(candidates))


def resolve_linkedin_channel(token: str, preferred_id: str = "") -> str:
    """Compatibility for the original LinkedIn tests."""
    return resolve_channel(token, "linkedin", preferred_id)


def channel_preference(target: str) -> str:
    name = {
        "linkedin": "BUFFER_CHANNEL_ID",
        "facebook": "BUFFER_FACEBOOK_CHANNEL_ID",
        "instagram": "BUFFER_INSTAGRAM_CHANNEL_ID",
        "pinterest": "BUFFER_PINTEREST_CHANNEL_ID",
    }[target]
    return os.environ.get(name, "").strip()


def normalize_picturefix_api_key(raw: str) -> str:
    """Discard accidental outer paste whitespace; never log or silently rewrite token contents."""
    if not isinstance(raw, str):
        raise RuntimeError("Missing dedicated PictureFix Buffer API key.")
    key = raw.strip(" \t\r\n")
    if not key:
        raise RuntimeError("Missing dedicated PictureFix Buffer API key.")
    if key.lower().startswith("bearer "):
        raise RuntimeError("PictureFix Buffer secret must contain only the raw API key, not 'Bearer'.")
    if any(not 33 <= ord(char) <= 126 for char in key):
        raise RuntimeError("PictureFix Buffer API key has invalid internal whitespace or control characters.")
    return key


def discover_picturefix_channels(token: str, *, channel_cache: dict | None = None) -> dict:
    """Only accept the one genuine PictureFix organization and three known profiles.

    Returns Buffer-internal IDs without persisting, printing or guessing them.
    Separate AAB credentials, channels and workflows remain unaffected.
    """
    if channel_cache is not None and "picturefix_verified" in channel_cache:
        return channel_cache["picturefix_verified"]
    account = buffer_graphql(token, GET_PICTUREFIX_ORGANIZATIONS, {}).get("account")
    orgs = account.get("organizations") if isinstance(account, dict) else None
    if (not isinstance(orgs, list) or len(orgs) != 1
            or not isinstance(orgs[0], dict)
            or orgs[0].get("name") != "PictureFix"
            or orgs[0].get("channelCount") != 3):
        raise RuntimeError("Dedicated Buffer token must belong to the single 3-channel PictureFix organization.")
    org_id = orgs[0].get("id")
    if not isinstance(org_id, str) or not org_id:
        raise RuntimeError("Invalid PictureFix Buffer organization ID.")
    channels = buffer_graphql(token, GET_PICTUREFIX_CHANNELS,
                              {"organizationId": org_id}).get("channels")
    if not isinstance(channels, list) or len(channels) != 3:
        raise RuntimeError("PictureFix must have exactly three accessible channels.")
    verified = {}
    for channel in channels:
        if not isinstance(channel, dict):
            raise RuntimeError("Unexpected PictureFix channel data.")
        service = channel.get("service")
        name = channel.get("name")
        channel_id = channel.get("id")
        if (service not in PICTUREFIX_EXPECTED_PROFILES
                or name != PICTUREFIX_EXPECTED_PROFILES[service]
                or channel.get("organizationId") != org_id
                or channel.get("isDisconnected") is not False
                or channel.get("isLocked") is not False
                or not isinstance(channel_id, str) or not channel_id
                or service in verified):
            raise RuntimeError("A PictureFix channel does not match the confirmed profile or is not usable.")
        configured = channel_preference(service)
        if configured and configured != channel_id:
            raise RuntimeError("Configured PictureFix channel ID disagrees with live Buffer channel.")
        verified[service] = channel_id
    if set(verified) != set(PICTUREFIX_EXPECTED_PROFILES):
        raise RuntimeError("One of the three PictureFix channel profiles is missing.")
    if len(set(verified.values())) != 3:
        raise RuntimeError("PictureFix channel ID collision.")
    if channel_cache is not None:
        channel_cache["picturefix_verified"] = verified
    return verified


def discover_picturefix_board(token: str, channel_id: str) -> str:
    """Use an explicitly configured board or the *single* available board.

    Multiple boards need an explicit user choice: never pin to an arbitrary one.
    """
    response = buffer_graphql(token, GET_PICTUREFIX_PINTEREST_BOARDS, {"id": channel_id})
    channel = response.get("channel")
    metadata = channel.get("metadata") if isinstance(channel, dict) else None
    if (not isinstance(channel, dict) or channel.get("id") != channel_id
            or not isinstance(metadata, dict)
            or not isinstance(metadata.get("boards"), list)):
        raise RuntimeError("Cannot verify Pinterest board ownership in PictureFix.")
    boards = metadata["boards"]
    if not boards:
        raise RuntimeError("PictureFix Pinterest board list is empty in Buffer API; refresh the Pinterest channel.")
    ids = [board["serviceId"] for board in boards
           if isinstance(board, dict) and isinstance(board.get("serviceId"), str)
           and board["serviceId"].strip()]
    if len(ids) != len(boards) or len(set(ids)) != len(ids):
        raise RuntimeError("PictureFix Pinterest board metadata is incomplete or duplicated.")
    explicit = os.environ.get("BUFFER_PICTUREFIX_PINTEREST_BOARD_SERVICE_ID", "").strip()
    if explicit:
        if explicit not in ids:
            raise RuntimeError("Configured Pinterest board is not connected to PictureFix.")
        return explicit
    if len(ids) != 1:
        raise RuntimeError("PictureFix has multiple Pinterest boards; the chosen board must be configured.")
    return ids[0]


def verify_picturefix_board(token: str, channel_id: str, board_service_id: str) -> None:
    """Pinterest requires a selected board, verified against the actual PictureFix channel."""
    if (not isinstance(board_service_id, str) or not board_service_id.strip()
            or len(board_service_id) > 128):
        raise RuntimeError("A dedicated PictureFix Pinterest board ID is required.")
    response = buffer_graphql(token, GET_PICTUREFIX_PINTEREST_BOARDS, {"id": channel_id})
    channel = response.get("channel")
    if not isinstance(channel, dict) or channel.get("id") != channel_id:
        raise RuntimeError("PictureFix Pinterest channel cannot be read independently.")
    metadata = channel.get("metadata")
    if not isinstance(metadata, dict) or not isinstance(metadata.get("boards"), list):
        raise RuntimeError("PictureFix Pinterest boards are not available.")
    board_ids = {board.get("serviceId") for board in metadata["boards"]
                 if isinstance(board, dict) and isinstance(board.get("serviceId"), str)}
    if board_service_id not in board_ids:
        raise RuntimeError("Configured Pinterest board is not on the selected PictureFix channel.")


def planned_due_at(draft_path: str, target: str, *, now: datetime | None = None) -> str | None:
    """Bind an auto-draft's time to its manifest, never to editable draft fields.

    Legacy `ready-for-buffer/` entries lack three-channel quality evidence and stay blocked.
    Directly dispatched `drafts/` entries keep their original undated behavior.
    """
    match = AUTO_DRAFT_RE.fullmatch(draft_path)
    if match is None:
        if draft_path.startswith("ready-for-buffer/"):
            raise RuntimeError("Legacy-ready-for-buffer ohne gebundene Kampagnen-Qualitaetspruefung gesperrt")
        if not draft_path.startswith("drafts/"):
            raise RuntimeError("Unbekannter Entwurfseingang")
        return None
    campaign, named_target = match.groups()
    if target != named_target:
        raise RuntimeError("Kanal in Dateiname und Inhalt stimmt nicht überein")
    manifest_file = (ROOT / "campaign-manifests" / f"{campaign}.json").resolve(strict=True)
    if not manifest_file.is_relative_to(ROOT.resolve()) or manifest_file.stat().st_size > 100_000:
        raise RuntimeError("Manifestpfad oder -größe unzulässig")
    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    if (not isinstance(manifest, dict) or manifest.get("brand") != "ai-agent-builder"
            or manifest.get("campaign_id") != campaign):
        raise RuntimeError("Kampagnenmanifest ist nicht gebunden")
    posts = manifest.get("posts")
    if not isinstance(posts, dict) or posts.get(target) != draft_path:
        raise RuntimeError("Post und Manifest widersprechen sich")
    timings = manifest.get("posting_times")
    if not isinstance(timings, dict) or set(timings) != {"linkedin", "facebook", "instagram"}:
        raise RuntimeError("Drei Plattformtermine fehlen")
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        raise RuntimeError("Zeitprüfung benötigt eine Zeitzone")
    tz = ZoneInfo("Europe/Berlin")
    parsed = {}
    for name, timing in timings.items():
        if not isinstance(timing, dict) or set(timing) != {"local", "utc"}:
            raise RuntimeError("Unvollständiger Zeitnachweis")
        utc_text = timing["utc"]
        if not isinstance(utc_text, str) or not re.fullmatch(
            r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", utc_text
        ):
            raise RuntimeError("Termin benötigt sekundengenaues UTC-Format")
        utc = datetime.strptime(utc_text, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        local = datetime.fromisoformat(timing["local"])
        if (local.tzinfo is None or local.astimezone(timezone.utc) != utc
                or utc.astimezone(tz).isoformat(timespec="seconds") != local.isoformat(timespec="seconds")
                or utc <= current + timedelta(minutes=10)):
            raise RuntimeError("Ungültiger, abgelaufener oder falsch konvertierter Termin")
        parsed[name] = utc
    return timings[target]["utc"]


def authorize_auto_dated_draft(draft_path: str) -> dict:
    """Require campaign QA before Buffer, not Josef's approval before draft.

    The separate personal decision happens only on the finished Buffer posts.
    Image-source, logo, disclosure, time and three-platform gates remain.
    """
    if __package__:
        from .autonomous_campaign_gate import check_campaign
    else:
        from autonomous_campaign_gate import check_campaign
    match = AUTO_DRAFT_RE.fullmatch(draft_path)
    if match is None:
        raise RuntimeError("Automatischer datierter Entwurf benötigt eindeutige Kampagne")
    campaign = match.group(1)
    targets = ("linkedin", "facebook", "instagram")
    posts = [f"ready-for-buffer/auto-{campaign}-{target}.json" for target in targets]
    evidence = check_campaign(posts, verify_image=True)
    if (not isinstance(evidence, dict) or evidence.get("status") != "eligible_for_draft_only"
            or evidence.get("campaign") != campaign
            or evidence.get("targets") != list(targets)):
        raise RuntimeError("Unvollständiger Drei-Kanal-Kampagnen-Qualitätsnachweis")
    # Either the standard fully verified owner-Issue brief or the narrowly
    # allowlisted, already independently logo-QA-tested GitHub PR #46 assets.
    # Never accept an arbitrary missing / improvised issue brief.
    brief_path = ROOT / "orchestration" / "briefs" / f"{campaign}.json"
    if brief_path.is_file():
        brief = json.loads(brief_path.read_text(encoding="utf-8"))
        if (not isinstance(brief, dict) or brief.get("campaign_id") != campaign
                or brief.get("brand") != "ai-agent-builder"
                or brief.get("execution_mode") != "drafts"
                or brief.get("image_review") != f"visual-reviews/{campaign}.json"):
            raise RuntimeError("Unpassender Kampagnen-Brief zur Bildprüfung")
        prepared = brief.get("prepared_content")
        expected_posts = prepared.get("posts") if isinstance(prepared, dict) else None
    else:
        try:
            from .reviewed_staged_provenance import load_verified_posts
        except ImportError:
            from reviewed_staged_provenance import load_verified_posts
        expected_posts = load_verified_posts(ROOT, campaign, evidence)
    if not isinstance(expected_posts, dict) or set(expected_posts) != set(targets):
        raise RuntimeError("Geprüfte plattformspezifische Brief-Texte fehlen")
    for target, filename in zip(targets, posts):
        _, actual, _ = read_draft(filename)
        if actual != expected_posts[target]:
            raise RuntimeError("Buffer-Draft-Text weicht vom vorbereiteten geprüften Brief ab")
    return {"campaign": campaign, "quality_gate": "passed",
            "image_sha256": evidence.get("image_sha256", "")}


def verified_dated_post(record: object, *, post_id: str, channel_id: str, due_at: str) -> bool:
    """Require the independent Buffer readback to agree on ID, channel, status, UTC."""
    if not isinstance(record, dict):
        return False
    try:
        due = datetime.fromisoformat(str(record.get("dueAt", "")).replace("Z", "+00:00"))
        expected = datetime.fromisoformat(due_at.replace("Z", "+00:00"))
    except ValueError:
        return False
    return (record.get("id") == post_id and record.get("channelId") == channel_id
            and str(record.get("status", "")).lower() == "draft"
            and due.tzinfo is not None and due.astimezone(timezone.utc) == expected)


def check_connection() -> None:
    buffer_key = os.environ.get("BUFFER_API_KEY", "")
    if not buffer_key:
        raise RuntimeError("BUFFER_API_KEY fehlt als GitHub-Secret.")
    channel_cache = {}
    for target in ("linkedin", "facebook", "instagram"):
        resolve_channel(buffer_key, target, channel_preference(target), channel_cache=channel_cache)
    print("Verbindungstest erfolgreich: LinkedIn, Facebook und Instagram eindeutig gefunden.")
    print("Nur Buffer-Daten gelesen. Kein Entwurf erstellt, nichts eingeplant oder veröffentlicht.")


def check_picturefix_connection() -> None:
    """Read-only tenant preflight: no receipts, drafts, posts or publishing."""
    if (os.environ.get("GITHUB_REPOSITORY") != REPOSITORY
            or os.environ.get("GITHUB_REF") != "refs/heads/main"
            or os.environ.get("GITHUB_EVENT_NAME") != "issue_comment"
            or os.environ.get("GITHUB_ACTOR") != "derJosef-agents"
            or os.environ.get("BUFFER_BRAND") != "picturefix"):
        raise RuntimeError("PictureFix tenant preflight only allowed by the control issue on main.")
    token = normalize_picturefix_api_key(os.environ.get("BUFFER_API_KEY", ""))
    channels = discover_picturefix_channels(token)
    discover_picturefix_board(token, channels["pinterest"])
    print("PICTUREFIX_READ_ONLY_PREFLIGHT_PASS: separate PictureFix org, three exact active profiles and Pinterest board; no posts, receipts, queue or schedule.")



def send_draft(draft_path: str, text: str, raw: bytes, *, channel_cache: dict | None = None) -> None:
    if os.environ.get("GITHUB_REPOSITORY") != REPOSITORY or os.environ.get("GITHUB_REF") != "refs/heads/main":
        raise RuntimeError("Live-Übertragung nur durch GitHub Actions auf social-assets/main.")
    github_token = os.environ.get("GITHUB_TOKEN", "")
    buffer_key = os.environ.get("BUFFER_API_KEY", "")
    if not all((github_token, buffer_key)):
        raise RuntimeError("GitHub-Token oder BUFFER_API_KEY fehlt.")

    record = json.loads(raw.decode("utf-8"))
    target = record["target"]
    picturefix = record.get("format_version") == 3
    if picturefix:
        buffer_key = normalize_picturefix_api_key(buffer_key)
    caller_brand = os.environ.get("BUFFER_BRAND", "ai-agent-builder")
    if picturefix:
        if (caller_brand != "picturefix" or os.environ.get("GITHUB_EVENT_NAME") != "issue_comment"
                or os.environ.get("GITHUB_ACTOR") != "derJosef-agents"):
            raise RuntimeError("PictureFix can only use authorized brand draft-only event.")
    elif caller_brand != "ai-agent-builder":
        raise RuntimeError("Another brand cannot use PictureFix Buffer credentials.")
    due_at = planned_due_at(draft_path, target)
    if picturefix and due_at is not None:
        raise RuntimeError("PictureFix preview cannot carry dueAt.")
    quality = authorize_auto_dated_draft(draft_path) if due_at is not None else None
    if picturefix:
        channel_id = discover_picturefix_channels(buffer_key, channel_cache=channel_cache)[target]
    else:
        channel_id = resolve_channel(buffer_key, target, channel_preference(target),
                                     channel_cache=channel_cache)
    pinterest_board_id = ""
    if picturefix and target == "pinterest":
        pinterest_board_id = discover_picturefix_board(buffer_key, channel_id)
    assets = parse_assets(raw)
    verify_media_access(assets)
    verify_auto_image_bytes(draft_path, assets)
    verify_picturefix_image_bytes(record, assets)
    receipt = receipt_path(draft_path)
    if fetch_receipt(github_token, receipt) is not None:
        raise RuntimeError(
            f"Für {draft_path} existiert bereits {receipt}. Kein erneuter API-Aufruf. "
            "Status in Buffer manuell prüfen."
        )
    pending = {
        "draft_file": draft_path,
        "target": target,
        "draft_sha256": hashlib.sha256(raw).hexdigest(),
        "state": "pending_manual_reconciliation_on_failure",
        "github_run_id": os.environ.get("GITHUB_RUN_ID", "unknown"),
    }
    if due_at is not None:
        pending.update({"due_at_utc": due_at, "channel_id": channel_id, "campaign_quality": quality})
    receipt_sha = put_receipt(
        github_token, receipt, pending, f"buffer: reserve draft transfer for {draft_path}"
    )
    # After the reservation, do not automatically retry on failure:
    # Buffer may have created a post even if the network response was lost.
    variables = {
        "text": text, "channelId": channel_id, "assets": assets,
        "metadata": platform_metadata(
            target, video=any("video" in a for a in assets),
            pinterest_board_id=pinterest_board_id,
            pinterest_title=record.get("pinterest_title", ""),
            pinterest_url=record.get("pinterest_url", ""),
        ),
    }
    if due_at is not None:
        variables["dueAt"] = due_at
    result = buffer_graphql(buffer_key, CREATE_DATED_DRAFT if due_at is not None else CREATE_DRAFT, variables)
    post_result = result.get("createPost") or {}
    post = post_result.get("post") if isinstance(post_result, dict) else None
    if not isinstance(post, dict) or not post.get("id"):
        # Buffer's MutationError.message may include tokens, URLs, personal
        # data, or post text. Never print it or persist it to public receipts.
        # A closed-vocabulary topic is a *hint*, not a verified root cause.
        error_type, category = safe_mutation_diagnosis(post_result)
        raise RuntimeError(
            f"Buffer-Draft nicht bestätigt ({error_type}; Diagnosekategorie={category}). "
            "Pending-Beleg bleibt; manuell prüfen. Kein automatischer Wiederholungsversuch."
        )
    post_id = str(post["id"])
    if due_at is not None:
        pending.update({"state": "created_requires_independent_check", "buffer_post_id": post_id})
        receipt_sha = put_receipt(
            github_token, receipt, pending,
            f"buffer: identify dated draft for {draft_path}", sha=receipt_sha,
        )
        if not verified_dated_post(post, post_id=post_id, channel_id=channel_id, due_at=due_at):
            raise RuntimeError("ALARM: Buffer-Anlage war kein datierter Draft; nur manuell abgleichen")
        independent = buffer_graphql(buffer_key, READ_DATED_DRAFT, {"id": post_id}).get("post")
        if not verified_dated_post(independent, post_id=post_id, channel_id=channel_id, due_at=due_at):
            raise RuntimeError("ALARM: Buffer-Readback bestätigt keinen datierten Draft")
        pending["state"] = "verified_prescheduled_draft_not_queued"
    else:
        pending.update({"state": "draft_created", "buffer_post_id": post_id})
        if picturefix:
            # Never retry an uncertain Buffer create; record ID BEFORE readback.
            pending["state"] = "created_requires_independent_check"
            receipt_sha = put_receipt(
                github_token, receipt, pending,
                f"buffer: identify PictureFix preview {draft_path}", sha=receipt_sha,
            )
            checked = buffer_graphql(buffer_key, READ_PICTUREFIX_DRAFT, {"id": post_id}).get("post")
            verified_image = verified_picturefix_post(
                checked, post_id=post_id, channel_id=channel_id,
                target=target, original_text=text,
            )
            if verified_image is None:
                raise RuntimeError("ALARM: Buffer failed PictureFix image/draft/dueAt readback.")
            pending.update({
                "state": "verified_unpublished_draft_with_image",
                "channel_id": channel_id, "original_image_sha256": record["image_sha256"],
                "buffer_asset_url": verified_image, "buffer_due_at": None,
                "buffer_status": "draft",
            })
    try:
        put_receipt(
            github_token,
            receipt,
            pending,
            f"buffer: confirm draft transfer for {draft_path}",
            sha=receipt_sha,
        )
    except RuntimeError as exc:
        raise RuntimeError(
            "Entwurf laut Buffer erstellt, aber GitHub-Beleg nicht aktualisiert. "
            f"{receipt} steht weiterhin auf pending. Manuell abgleichen."
        ) from exc
    if due_at is not None:
        print(f"Erfolg: verifizierter Buffer-Draft (Post-ID: {post_id}, dueAt={due_at}). Keine Queue/Publikation.")
    elif picturefix:
        print(f"PICTUREFIX_BUFFER_READBACK_PASS Post-ID={post_id}, target={target}, "
              "status=draft, dueAt=null, image=attached; no queue/publish.")
    else:
        print(f"Erfolg: Buffer-Entwurf angelegt (Post-ID: {post_id}). Keine Planung/Veröffentlichung.")
    print(f"GitHub-Beleg: {receipt}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Buffer: geprüfte Entwürfe für drei Kanäle übertragen.")
    parser.add_argument("--draft", action="append",
                        help="JSON unter drafts/ oder ready-for-buffer/ (mehrfach für einen Batch)")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="Nur lokal prüfen; keine API-Aufrufe.")
    mode.add_argument("--check-connection", action="store_true", help="Buffer-Kanäle nur lesend prüfen.")
    mode.add_argument("--check-picturefix-connection", action="store_true",
                      help="Drei PictureFix-Kanäle und Pinterest-Board nur lesend prüfen.")
    mode.add_argument("--send", action="store_true", help="Explizit als Buffer-Entwurf übertragen.")
    args = parser.parse_args()

    try:
        if args.check_picturefix_connection:
            if args.draft:
                raise ValueError("PictureFix preflight does not accept draft paths.")
            check_picturefix_connection()
        elif args.check_connection:
            if not args.draft:
                raise ValueError("An existing draft path is required.")
            check_connection()
        else:
            if not args.draft:
                raise ValueError("At least one draft path is required.")
            # Validate the full batch before sending the first draft.
            prepared = [read_draft(path) for path in args.draft]
            if len({path for path, _, _ in prepared}) != len(prepared):
                raise ValueError("Doppelte Draft-Datei innerhalb eines Batches.")
            if args.dry_run:
                for draft_path, text, raw in prepared:
                    assets = parse_assets(raw)
                    print(f"DRY-RUN OK: {draft_path}, Ziel {json.loads(raw.decode('utf-8'))['target']}, {len(text)} Zeichen, {len(assets)} Medien.")
                print("Keine API-Aufrufe, keine Buffer-Aktion.")
            else:
                # Only one process: organizations and all channel IDs read once.
                # Fail closed after any uncertain createPost: no retry or further posts.
                channel_cache = {}
                for draft_path, text, raw in prepared:
                    send_draft(draft_path, text, raw, channel_cache=channel_cache)
    except (ValueError, OSError, RuntimeError, json.JSONDecodeError) as exc:
        print(f"FEHLER: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
