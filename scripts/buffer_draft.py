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
except ImportError:
    from buffer_error_diagnostics import safe_mutation_diagnosis

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
MEDIA_HOST_PREFIX = "https://raw.githubusercontent.com/derJosef/social-assets/"
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



def platform_metadata(target: str) -> dict | None:
    """Mandatory channel-specific post input metadata, independent of publication mode."""
    if target == "facebook":
        return {"facebook": {"type": "post"}}
    if target == "instagram":
        return {"instagram": {"type": "post", "shouldShareToFeed": True}}
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
    due_at = planned_due_at(draft_path, target)
    quality = authorize_auto_dated_draft(draft_path) if due_at is not None else None
    channel_id = resolve_channel(buffer_key, target, channel_preference(target))
    assets = parse_assets(raw)
    verify_media_access(assets)
    verify_auto_image_bytes(draft_path, assets)
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
        "metadata": platform_metadata(target),
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
    else:
        print(f"Erfolg: Buffer-Entwurf angelegt (Post-ID: {post_id}). Keine Planung/Veröffentlichung.")
    print(f"GitHub-Beleg: {receipt}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Buffer: geprüfte Entwürfe für drei Kanäle übertragen.")
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
