#!/usr/bin/env python3
"""One-time image-only correction for 3 existing, dated Buffer DRAFTS.

No createPost, no publish, no queue activation. The live Buffer copies are the
source of truth: any unexpected media/date/status/channel change stops the run.
The image and its checksum are pinned to a completed GitHub commit.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image

try:
    from scripts.buffer_draft import (
        REPOSITORY, buffer_graphql, fetch_receipt, put_receipt,
    )
    from scripts.legacy_six_buffer_image_edit import (
        POST_QUERY, safe_metadata, signature,
    )
except ImportError:
    from buffer_draft import REPOSITORY, buffer_graphql, fetch_receipt, put_receipt
    from legacy_six_buffer_image_edit import POST_QUERY, safe_metadata, signature


CAMPAIGN = "2026-11-20-telekom-mistral-europa-v6-cyan-t"
IMAGE_SHA256 = "f46f3412a1f787b17b531b508e6777c9e7e6a1ad2a1fb34112287c65faf54cfa"
IMAGE_COMMIT = "21cb4d7b9bc1f60450d17cfe952cab5ebba4e604"
NEW_IMAGE_URL = (
    "https://raw.githubusercontent.com/derJosef/social-assets/" + IMAGE_COMMIT
    + "/media/images/2026-11-20-telekom-mistral-europa-v6-cyan-t-flow-branded.png"
)
OLD_IMAGE_URL = (
    "https://raw.githubusercontent.com/derJosef/social-assets/"
    "12075b51ca2372c1d134290f58f842412f32b4bc/"
    "media/images/2026-11-20-telekom-mistral-europa-v2-branded.png"
)
POSTS = {
    "linkedin": {
        "id": "6afff0a57b0a126cebb56f34",
        "channel_id": "6aac167eea19ca0bde6ada5b",
        "due_at": "2026-12-09T15:00:00Z",
    },
    "facebook": {
        "id": "6afff0ab738ce4635f93ac57",
        "channel_id": "6ac781e46a5c39ccb64fe01c",
        "due_at": "2026-12-03T08:00:00Z",
    },
    "instagram": {
        "id": "6afff0b14c1afd05defcc931",
        "channel_id": "6ac79a686a5c39ccb650f94b",
        "due_at": "2026-12-02T17:00:00Z",
    },
}
TRIGGER = "AAB_TELEKOM_MISTRAL_APPROVED_CYAN_T_REPLACE_THREE_DRAFT_IMAGES_ONCE_20261120"
TRIGGER_PR = 82
AGENT_ID = 350701981
BATCH_RECEIPT = "delivery-receipts/2026-11-20-telekom-mistral-v6-image-refresh-batch.json"
ALT = (
    "Redaktionelle KI-Visualisierung: Ein cyanblaues, in Rechentechnik integriertes "
    "Telekom-T sendet einen Datenstrom an ein abstraktes KI-Netzwerk; "
    "originales Pauderer-Logo unten rechts."
)

EDIT = """
mutation ExistingDatedDraftImageOnly($id: PostId!, $text: String!,
  $dueAt: DateTime!, $assets: [AssetInput!],
  $metadata: PostInputMetaData, $tagIds: [TagId!]) {
  editPost(input: {
    id: $id, text: $text, dueAt: $dueAt,
    mode: customScheduled, schedulingType: automatic,
    assets: $assets, metadata: $metadata, tagIds: $tagIds,
    saveToDraft: true
  }) {
    __typename
    ... on PostActionSuccess {
      post { id channelId channelService status dueAt text assets { type source mimeType } }
    }
    ... on MutationError { message }
  }
}
"""


class DraftImageBlocked(RuntimeError):
    pass


def require(condition: bool, reason: str) -> None:
    if not condition:
        raise DraftImageBlocked(reason)


def same_instant(actual: object, expected: str) -> bool:
    """Buffer returns RFC3339 .000Z; compare UTC instants, not formatting."""
    if not isinstance(actual, str):
        return False
    try:
        def utc(value: str) -> datetime:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                raise ValueError("Entwurfstermin ohne Zeitzone")
            return parsed.astimezone(timezone.utc)
        return utc(actual) == utc(expected)
    except ValueError:
        return False


def verify_image(fetch=None) -> None:
    fetch = fetch or fetch_image
    binary = fetch(NEW_IMAGE_URL)
    require(isinstance(binary, bytes) and len(binary) < 5_000_000,
            "Unzulässige Bildbytes")
    require(hashlib.sha256(binary).hexdigest() == IMAGE_SHA256,
            "SHA-256 des gepinnten redaktionellen Bildes stimmt nicht")
    try:
        with Image.open(io.BytesIO(binary)) as im:
            require(im.format == "PNG" and im.size == (1080, 1350),
                    "Falsches Bildformat oder Seitenverhältnis")
            im.verify()
    except (ValueError, OSError) as exc:
        raise DraftImageBlocked("PNG-Validierung fehlgeschlagen") from exc


def fetch_image(url: str) -> bytes:
    require(url == NEW_IMAGE_URL, "Nur der gepinnte Bild-Commit ist zulässig")
    with urllib.request.urlopen(url, timeout=35) as response:
        return response.read(5_000_001)


def validate_event(path: Path, env: dict[str, str]) -> None:
    require(env.get("GITHUB_REPOSITORY") == REPOSITORY and
            env.get("GITHUB_REF") == "refs/heads/main" and
            env.get("GITHUB_EVENT_NAME") == "issue_comment" and
            env.get("GITHUB_RUN_ATTEMPT") == "1" and
            env.get("GITHUB_ACTOR") == "derJosef-agents" and
            env.get("GITHUB_ACTOR_ID") == str(AGENT_ID),
            "Der freigegebene einmalige Agentenlauf auf main fehlt")
    require(path.is_file() and path.stat().st_size < 100_000,
            "GitHub-Ereignis fehlt oder ist zu groß")
    event = json.loads(path.read_text(encoding="utf-8"))
    issue, comment = event.get("issue") or {}, event.get("comment") or {}
    require(event.get("action") == "created" and
            issue.get("number") == TRIGGER_PR and issue.get("pull_request") and
            (issue.get("user") or {}).get("id") == AGENT_ID and
            (comment.get("user") or {}).get("id") == AGENT_ID and
            comment.get("body") == TRIGGER,
            "Genaue autorisierte PR-Kommentar-Freigabe fehlt")


def check_post(raw: object, channel: str, *, expect_new: bool = False) -> dict:
    expected = POSTS[channel]
    require(isinstance(raw, dict) and raw.get("id") == expected["id"],
            f"Post-ID nicht bestätigt: {channel}")
    require(raw.get("channelId") == expected["channel_id"] and
            str(raw.get("channelService", "")).lower() == channel,
            f"Buffer-Kanal nicht bestätigt: {channel}")
    schedule_matches = (
        raw.get("status") == "draft" and
        same_instant(raw.get("dueAt"), expected["due_at"]) and
        raw.get("shareMode") == "customScheduled" and
        raw.get("schedulingType") == "automatic"
    )
    # Only non-sensitive scheduling fields; no post text, tags, media or credentials.
    # Diagnostic is deliberately read-only and still fails closed.
    require(schedule_matches,
            f"Status, geplanter Entwurfstermin oder Planungsmodus abgewichen: {channel} "
            f"status={raw.get('status')!r} dueAt={raw.get('dueAt')!r} "
            f"shareMode={raw.get('shareMode')!r} "
            f"schedulingType={raw.get('schedulingType')!r}")
    require(isinstance(raw.get("text"), str) and len(raw["text"].strip()) > 100,
            f"Text fehlt oder ist zu kurz: {channel}")
    tags = raw.get("tags")
    require(isinstance(tags, list) and all(isinstance(t, dict) and
            isinstance(t.get("id"), str) for t in tags),
            f"Buffer-Tags nicht eindeutig: {channel}")
    assets = raw.get("assets")
    image = NEW_IMAGE_URL if expect_new else OLD_IMAGE_URL
    require(isinstance(assets, list) and len(assets) == 1 and
            assets[0].get("type") == "image" and assets[0].get("source") == image,
            f"Aktuelles Buffer-Bild ist nicht das erwartete: {channel}")
    if expect_new:
        require(assets[0].get("mimeType") == "image/png", "Buffer-PNG-Typ fehlt")
    meta = safe_metadata(raw, channel)
    return {
        "id": expected["id"], "channel": channel,
        "text": raw["text"], "due_at": raw["dueAt"],
        "tags": [t["id"] for t in tags], "metadata": meta,
        "signature": signature(raw),
    }


def receipt_path(channel: str) -> str:
    return f"delivery-receipts/2026-11-20-telekom-mistral-v6-image-refresh-{channel}.json"


def live_edit(*, get=buffer_graphql, fetch=None,
              get_receipt=fetch_receipt, write_receipt=put_receipt,
              env: dict[str, str] | None = None) -> None:
    env = dict(os.environ if env is None else env)
    event_file = env.get("GITHUB_EVENT_PATH", "")
    require(bool(event_file), "GitHub-Ereignispfad fehlt")
    validate_event(Path(event_file), env)
    buffer_key, gh_token = env.get("BUFFER_API_KEY"), env.get("GITHUB_TOKEN")
    require(bool(buffer_key and gh_token), "Buffer/GitHub-Schnittstelle fehlt")
    verify_image(fetch)
    require(len(POSTS) == 3 and len(set(p["id"] for p in POSTS.values())) == 3 and
            all(re.fullmatch(r"[0-9a-f]{24}", p["id"]) for p in POSTS.values()),
            "Genau drei feste Post-IDs benötigt")
    require("createPost" not in EDIT and "shareNow" not in EDIT and
            "saveToDraft: true" in EDIT and "dueAt: $dueAt" in EDIT,
            "Mutation darf niemals anlegen, teilen oder Veröffentlichungsstatus aktivieren")

    snapshots = {}
    for channel, post in POSTS.items():
        raw = get(buffer_key, POST_QUERY, {"id": post["id"]}).get("post")
        snapshots[channel] = check_post(raw, channel)

    require(get_receipt(gh_token, BATCH_RECEIPT) is None,
            "Einmalige Gesamtreservation existiert bereits – kein Retry")
    for channel in POSTS:
        require(get_receipt(gh_token, receipt_path(channel)) is None,
                f"Einzelreservation existiert bereits: {channel}")

    batch = {"campaign": CAMPAIGN, "run_id": env.get("GITHUB_RUN_ID"),
             "state": "pending_manual_reconciliation_on_failure",
             "post_ids": [p["id"] for p in POSTS.values()],
             "image": NEW_IMAGE_URL, "image_sha256": IMAGE_SHA256}
    batch_sha = write_receipt(gh_token, BATCH_RECEIPT, batch,
                              "reserve one Telekom Mistral three-image edit")

    for channel, snap in snapshots.items():
        current = get(buffer_key, POST_QUERY, {"id": snap["id"]}).get("post")
        require(check_post(current, channel)["signature"] == snap["signature"],
                f"Buffer-Drift vor Bildtausch: {channel}")
        receipt = {"state": "pending_manual_reconciliation_on_failure",
                   "run_id": env.get("GITHUB_RUN_ID"), "post_id": snap["id"],
                   "channel": channel, "image": NEW_IMAGE_URL,
                   "preserved_text_sha256": hashlib.sha256(snap["text"].encode()).hexdigest(),
                   "preserved_due_at": snap["due_at"]}
        receipt_name = receipt_path(channel)
        record_sha = write_receipt(gh_token, receipt_name, receipt,
                                   "reserve one existing Buffer image edit")
        response = get(buffer_key, EDIT, {
            "id": snap["id"], "text": snap["text"],
            "dueAt": snap["due_at"],
            "assets": [{"image": {"url": NEW_IMAGE_URL,
                                   "metadata": {"altText": ALT}}}],
            "metadata": snap["metadata"], "tagIds": snap["tags"],
        }).get("editPost")
        changed = response.get("post") if isinstance(response, dict) else None
        require(isinstance(changed, dict) and changed.get("id") == snap["id"],
                f"Buffer-Mutation nicht bestätigt; nicht erneut ausführen: {channel}")
        verified = get(buffer_key, POST_QUERY, {"id": snap["id"]}).get("post")
        new = check_post(verified, channel, expect_new=True)
        require(new["text"] == snap["text"] and new["tags"] == snap["tags"] and
                new["metadata"] == snap["metadata"],
                f"Buffer-Text/Tags/Metadaten verändert; manuelle Prüfung: {channel}")
        receipt["state"] = "verified_existing_draft_image_only"
        receipt["verified_at_utc"] = datetime.now(timezone.utc).isoformat()
        write_receipt(gh_token, receipt_name, receipt,
                      "verified unchanged Buffer draft except image", sha=record_sha)
        print("TELEKOM_MISTRAL_DRAFT_IMAGE_PASS", channel, snap["id"],
              "draft unchanged, dueAt preserved, new image verified", flush=True)

    batch["state"] = "verified_three_existing_drafts_image_only"
    batch["verified_at_utc"] = datetime.now(timezone.utc).isoformat()
    write_receipt(gh_token, BATCH_RECEIPT, batch,
                  "verified all three unchanged Buffer drafts except image", sha=batch_sha)
    print("TELEKOM_MISTRAL_ALL_THREE_VERIFIED_NO_PUBLISH", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args()
    if not args.live:
        parser.error("Kein impliziter Buffer-Aufruf")
    try:
        live_edit()
        return 0
    except (DraftImageBlocked, ValueError, RuntimeError, OSError, json.JSONDecodeError) as exc:
        print("TELEKOM_MISTRAL_IMAGE_REFRESH_BLOCKED", type(exc).__name__,
              str(exc)[:220], file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
