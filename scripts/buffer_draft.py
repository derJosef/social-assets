#!/usr/bin/env python3
"""Transfer one LinkedIn/Facebook/Instagram post to Buffer as a draft, never schedule.

No external calls in dry-run mode. Live sending is only possible with --send,
configured GitHub Actions secrets and a reservation receipt in this repository.
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

ROOT = Path(__file__).resolve().parents[1]
BUFFER_ENDPOINT = "https://api.buffer.com"
REPOSITORY = "derJosef/social-assets"

# The only Buffer mutation in this script. There is no scheduling or publish path.
CREATE_DRAFT = """
mutation CreateDraft($text: String!, $channelId: ChannelId!, $assets: [AssetInput!]!) {
  createPost(input: {
    text: $text
    channelId: $channelId
    schedulingType: automatic
    mode: addToQueue
    saveToDraft: true
    assets: $assets
  }) {
    ... on PostActionSuccess { post { id text } }
    ... on MutationError { message }
  }
}
"""

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
            result = json.load(response)
            if not isinstance(result, dict):
                raise RuntimeError("Unerwartetes API-Antwortformat.")
            return result
    except urllib.error.HTTPError as exc:
        # Do not log credentials or potentially confidential API response bodies.
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
    if not isinstance(record, dict) or record.get("target") not in ("linkedin", "facebook", "instagram"):
        raise ValueError("Nur LinkedIn-, Facebook- und Instagram-Entwürfe werden akzeptiert.")
    fmt = record.get("format_version")
    if fmt == 1 and set(record) != {"format_version", "target", "text"}:
        raise ValueError("Format 1 erlaubt nur format_version, target und text.")
    if fmt == 2 and set(record) != {"format_version", "target", "text", "media"}:
        raise ValueError("Format 2 benötigt genau format_version, target, text und media.")
    if fmt not in (1, 2):
        raise ValueError("Unbekanntes Entwurfsformat.")
    target = record["target"]
    assets = parse_assets(raw)
    if target == "instagram" and not assets:
        raise ValueError("Instagram benötigt mindestens ein Bild, reiner Text ist nicht erlaubt.")
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
MEDIA_PREFIX = "https://raw.githubusercontent.com/derJosef/social-assets/main/media/"
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
        or not value.startswith(MEDIA_PREFIX)
    ):
        raise ValueError("Medien müssen direkt aus dem öffentlichen social-assets/media/ kommen.")
    suffix = value[len(MEDIA_PREFIX):]
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
    if record.get("format_version") != 2:
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
    raise ValueError("Medientyp nur images oder document.")


def verify_media_access(assets: list[dict]) -> None:
    """Preflight public media URLs before reserving a one-time transfer receipt."""
    urls = []
    for asset in assets:
        media = asset.get("image") or asset.get("document")
        urls.append((media["url"], "application/pdf" if "document" in asset else "image/"))
        if "document" in asset:
            urls.append((media["thumbnailUrl"], "image/"))
    for url, content_type_prefix in urls:
        try:
            request = urllib.request.Request(
                url, method="HEAD", headers={"User-Agent": "social-assets-buffer-draft/1.0"}
            )
            with urllib.request.urlopen(request, timeout=20) as response:
                typ = response.headers.get("Content-Type", "").lower()
                length = response.headers.get("Content-Length")
                size_limit = 100_000_000 if content_type_prefix == "application/pdf" else 10_000_000
                if typ and not (typ.startswith(content_type_prefix) or typ.startswith("application/octet-stream")):
                    raise RuntimeError("Medien-Link liefert keinen Bild-/PDF-Inhalt.")
                if length is not None and int(length) > size_limit:
                    raise RuntimeError("Mediendatei überschreitet die Größenbegrenzung.")
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f"Medien-Link nicht öffentlich abrufbar: HTTP {exc.code}.") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError("Öffentliche Medien-URL ist nicht erreichbar.") from exc


def receipt_path(draft_path: str) -> str:
    # One receipt per immutable draft filename; changing a sent file cannot resend it.
    digest = hashlib.sha256(draft_path.encode("utf-8")).hexdigest()[:24]
    return f"delivery-receipts/{digest}.json"


def github_contents_url(receipt: str) -> str:
    escaped = urllib.parse.quote(receipt, safe="/")
    return f"https://api.github.com/repos/{REPOSITORY}/contents/{escaped}"


def fetch_receipt(token: str, receipt: str) -> dict | None:
    url = github_contents_url(receipt) + "?ref=main"
    try:
        return json_http(url, token=token)
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
        "branch": "main",
    }
    if sha:
        payload["sha"] = sha
    response = json_http(github_contents_url(receipt), token=token, method="PUT", payload=payload)
    saved = response.get("content") or {}
    if not saved.get("sha"):
        raise RuntimeError("GitHub hat den Empfangsbeleg nicht bestätigt.")
    return saved["sha"]


def resolve_channel(token: str, target: str, preferred_id: str = "") -> str:
    """Select exactly one matching Buffer service. Never fall back to other networks."""
    if target not in ("linkedin", "facebook", "instagram"):
        raise ValueError("Unbekannter Buffer-Kanal.")
    account = buffer_graphql(token, GET_ORGANIZATIONS, {}).get("account")
    if not isinstance(account, dict) or not isinstance(account.get("organizations"), list):
        raise RuntimeError("Buffer-Organisationen konnten nicht gelesen werden.")
    candidates: set[str] = set()
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
            if str(channel.get("service", "")).lower() == target and channel.get("id"):
                candidates.add(str(channel["id"]))
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
    }[target]
    return os.environ.get(name, "").strip()


def check_connection() -> None:
    buffer_key = os.environ.get("BUFFER_API_KEY", "")
    if not buffer_key:
        raise RuntimeError("BUFFER_API_KEY fehlt als GitHub-Secret.")
    for target in ("linkedin", "facebook", "instagram"):
        resolve_channel(buffer_key, target, channel_preference(target))
    print("Verbindungstest erfolgreich: LinkedIn, Facebook und Instagram eindeutig gefunden.")
    print("Nur Buffer-Daten gelesen. Kein Entwurf erstellt, nichts eingeplant oder veröffentlicht.")


def send_draft(draft_path: str, text: str, raw: bytes) -> None:
    if os.environ.get("GITHUB_REPOSITORY") != REPOSITORY or os.environ.get("GITHUB_REF") != "refs/heads/main":
        raise RuntimeError("Live-Übertragung nur durch GitHub Actions auf social-assets/main.")
    github_token = os.environ.get("GITHUB_TOKEN", "")
    buffer_key = os.environ.get("BUFFER_API_KEY", "")
    if not all((github_token, buffer_key)):
        raise RuntimeError("GitHub-Token oder BUFFER_API_KEY fehlt.")

    target = json.loads(raw.decode("utf-8"))["target"]
    channel_id = resolve_channel(buffer_key, target, channel_preference(target))
    assets = parse_assets(raw)
    verify_media_access(assets)
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
    receipt_sha = put_receipt(
        github_token, receipt, pending, f"buffer: reserve draft transfer for {draft_path}"
    )
    # After the reservation, do not automatically retry on failure:
    # Buffer may have created a post even if the network response was lost.
    result = buffer_graphql(buffer_key, CREATE_DRAFT, {"text": text, "channelId": channel_id, "assets": assets})
    post_result = result.get("createPost") or {}
    post = post_result.get("post") if isinstance(post_result, dict) else None
    if not isinstance(post, dict) or not post.get("id"):
        raise RuntimeError("Buffer-Draft nicht bestätigt. Pending-Beleg bleibt; manuell prüfen.")
    pending.update({"state": "draft_created", "buffer_post_id": str(post["id"])})
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
    print(f"Erfolg: Buffer-Entwurf angelegt (Post-ID: {post['id']}). Keine Planung/Veröffentlichung.")
    print(f"GitHub-Beleg: {receipt}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Buffer: freigegebene Entwürfe für drei Kanäle übertragen.")
    parser.add_argument("--draft", required=True, help="JSON unter drafts/ oder ready-for-buffer/")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="Nur lokal prüfen; keine API-Aufrufe.")
    mode.add_argument("--check-connection", action="store_true", help="Buffer-Kanäle nur lesend prüfen.")
    mode.add_argument("--send", action="store_true", help="Explizit als Buffer-Entwurf übertragen.")
    args = parser.parse_args()

    try:
        draft_path, text, raw = read_draft(args.draft)
        if args.dry_run:
            assets = parse_assets(raw)
            print(f"DRY-RUN OK: {draft_path}, Ziel {json.loads(raw.decode('utf-8'))['target']}, {len(text)} Zeichen, {len(assets)} Medien.")

            print("Keine API-Aufrufe, keine Buffer-Aktion.")
        elif args.check_connection:
            check_connection()
        else:
            send_draft(draft_path, text, raw)
    except (ValueError, OSError, RuntimeError, json.JSONDecodeError) as exc:
        print(f"FEHLER: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
