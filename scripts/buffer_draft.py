#!/usr/bin/env python3
"""Transfer exactly one LinkedIn text post to Buffer as a draft, never schedule.

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

ROOT = Path(__file__).resolve().parents[1]
BUFFER_ENDPOINT = "https://api.buffer.com"
REPOSITORY = "derJosef/social-assets"

# The only Buffer mutation in this script. There is no scheduling or publish path.
CREATE_DRAFT = """
mutation CreateDraft($text: String!, $channelId: ChannelId!) {
  createPost(input: {
    text: $text
    channelId: $channelId
    schedulingType: automatic
    mode: addToQueue
    saveToDraft: true
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
    drafts_dir = (ROOT / "drafts").resolve(strict=True)
    path = (ROOT / given_path).resolve(strict=True)
    try:
        relative = path.relative_to(drafts_dir)
    except ValueError as exc:
        raise ValueError("Die Datei muss unter drafts/ liegen.") from exc
    if path.suffix.lower() != ".json" or not path.is_file():
        raise ValueError("Eine vorhandene JSON-Datei unter drafts/ ist erforderlich.")
    raw = path.read_bytes()
    if len(raw) > 100_000:
        raise ValueError("Entwurfsdatei ist zu groß.")
    record = json.loads(raw.decode("utf-8"))
    if not isinstance(record, dict) or set(record) != {"format_version", "target", "text"}:
        raise ValueError("Erlaubte Felder: format_version, target, text.")
    if record["format_version"] != 1 or record["target"] != "linkedin":
        raise ValueError("Vorerst ausschließlich LinkedIn-Textentwürfe (Format 1).")
    text = record["text"]
    if not isinstance(text, str) or not text.strip() or len(text) > 3000:
        raise ValueError("Text ist leer, ungültig oder länger als 3000 Zeichen.")
    return "drafts/" + relative.as_posix(), text, raw


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


def resolve_linkedin_channel(token: str, preferred_id: str = "") -> str:
    """Read Buffer account/channel metadata and select one LinkedIn channel.

    No mutation; auto-select only if there is exactly one suitable LinkedIn channel.
    An optional BUFFER_CHANNEL_ID is accepted for accounts with multiple channels.
    """
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
            if str(channel.get("service", "")).lower() == "linkedin" and channel.get("id"):
                candidates.add(str(channel["id"]))
    if preferred_id:
        if preferred_id not in candidates:
            raise RuntimeError("BUFFER_CHANNEL_ID verweist nicht auf einen verbundenen LinkedIn-Kanal.")
        return preferred_id
    if not candidates:
        raise RuntimeError("Kein LinkedIn-Kanal in Buffer verbunden oder für diesen Schlüssel sichtbar.")
    if len(candidates) != 1:
        raise RuntimeError(
            "Mehrere LinkedIn-Kanäle gefunden; BUFFER_CHANNEL_ID zur eindeutigen Auswahl hinterlegen."
        )
    return next(iter(candidates))


def check_connection() -> None:
    buffer_key = os.environ.get("BUFFER_API_KEY", "")
    if not buffer_key:
        raise RuntimeError("BUFFER_API_KEY fehlt als GitHub-Secret.")
    resolve_linkedin_channel(buffer_key, os.environ.get("BUFFER_CHANNEL_ID", "").strip())
    print("Verbindungstest erfolgreich: LinkedIn-Kanal eindeutig gefunden.")
    print("Nur Buffer-Daten gelesen. Kein Entwurf erstellt, nichts eingeplant oder veröffentlicht.")


def send_draft(draft_path: str, text: str, raw: bytes) -> None:
    if os.environ.get("GITHUB_REPOSITORY") != REPOSITORY or os.environ.get("GITHUB_REF") != "refs/heads/main":
        raise RuntimeError("Live-Übertragung nur durch GitHub Actions auf social-assets/main.")
    github_token = os.environ.get("GITHUB_TOKEN", "")
    buffer_key = os.environ.get("BUFFER_API_KEY", "")
    if not all((github_token, buffer_key)):
        raise RuntimeError("GitHub-Token oder BUFFER_API_KEY fehlt.")

    channel_id = resolve_linkedin_channel(
        buffer_key, os.environ.get("BUFFER_CHANNEL_ID", "").strip()
    )

    receipt = receipt_path(draft_path)
    if fetch_receipt(github_token, receipt) is not None:
        raise RuntimeError(
            f"Für {draft_path} existiert bereits {receipt}. Kein erneuter API-Aufruf. "
            "Status in Buffer manuell prüfen."
        )
    pending = {
        "draft_file": draft_path,
        "draft_sha256": hashlib.sha256(raw).hexdigest(),
        "state": "pending_manual_reconciliation_on_failure",
        "github_run_id": os.environ.get("GITHUB_RUN_ID", "unknown"),
    }
    receipt_sha = put_receipt(
        github_token, receipt, pending, f"buffer: reserve draft transfer for {draft_path}"
    )
    # After the reservation, do not automatically retry on failure:
    # Buffer may have created a post even if the network response was lost.
    result = buffer_graphql(buffer_key, CREATE_DRAFT, {"text": text, "channelId": channel_id})
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
    parser = argparse.ArgumentParser(description="Buffer: LinkedIn-Draft sicher übertragen.")
    parser.add_argument("--draft", required=True, help="JSON unter drafts/, z. B. drafts/beispiel-linkedin.json")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="Nur lokal prüfen; keine API-Aufrufe.")
    mode.add_argument("--check-connection", action="store_true", help="Buffer-Kanäle nur lesend prüfen.")
    mode.add_argument("--send", action="store_true", help="Explizit als Buffer-Entwurf übertragen.")
    args = parser.parse_args()

    try:
        draft_path, text, raw = read_draft(args.draft)
        if args.dry_run:
            print(f"DRY-RUN OK: {draft_path}, Ziel LinkedIn, {len(text)} Zeichen.")
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
