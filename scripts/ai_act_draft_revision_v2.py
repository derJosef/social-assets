#!/usr/bin/env python3
"""One-shot correction of THREE EXISTING AI Agent Builder Buffer drafts.

Josef chose Europe-map image option 2 on 2026-11-20 and limited Instagram
to five hashtags. Never create, queue, schedule or publish a Buffer post.
Requires two separate authenticated issue comments: read-only preflight,
then the exact one-shot apply command. No retry after a reserved mutation.
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

from scripts import buffer_draft as bridge
from scripts.legacy_six_buffer_image_edit import POST_QUERY, signature

CAMPAIGN = "2026-11-20-eu-ai-act-kmu-2026"
ISSUE = 19
ISSUE_TITLE = "AIAGENT_BRIEF:2026-10-13-lieferanten-pdf-prueftor-e2e-003"
ACTOR = "derJosef-agents"
ACTOR_ID = 350701981
COMMANDS = {
    "preflight": "AIAGENT_AI_ACT_EUROPE_V2_EXISTING_DRAFT_PREFLIGHT",
    "apply": "AIAGENT_AI_ACT_EUROPE_V2_EXISTING_DRAFT_APPLY_ONCE",
}
IMAGE_COMMIT = "83873228dcfc26895975368f4edf9fc10945a881"
NEW_IMAGE = ("https://raw.githubusercontent.com/derJosef/social-assets/"
             + IMAGE_COMMIT + "/media/images/" + CAMPAIGN + "-v2-branded.png")
NEW_IMAGE_SHA256 = "aa0f2369ec251048810dcdbc1c4c636350d2232ea7fc2da1e22b4b6ab24cc159"
OLD_IMAGE = ("https://raw.githubusercontent.com/derJosef/social-assets/"
             "5bc4c8f49fd7ea032aaacf52936941e488e268f1/media/images/"
             + CAMPAIGN + "-branded.png")
BRIEF = "orchestration/briefs/" + CAMPAIGN + ".json"
ALT = ("Stilisierte Europa-Karte aus türkisfarbenen digitalen Leiterbahnen mit "
       "drei Prüfstationen; Überschrift AI ACT 2026; originales Pauderer-Logo.")
TARGETS = {
    "linkedin": {
        "id": "6b002be239116a845dd02cca",
        "channel": "6aac167eea19ca0bde6ada5b",
        "due_at": "2026-12-16T15:00:00Z",
    },
    "facebook": {
        "id": "6b002be79dd03fda0b064a26",
        "channel": "6ac781e46a5c39ccb64fe01c",
        "due_at": "2026-12-17T08:00:00Z",
    },
    "instagram": {
        "id": "6b002bebc0a7142f84b4bff1",
        # Taken from the independently verified 2026-11-20 Buffer receipt.
        "channel": "6ac79a686a5c39ccb650f94b",
        "due_at": "2026-12-16T17:00:00Z",
    },
}
RECEIPT_PREFIX = "delivery-receipts/2026-11-20-ai-act-europe-v2-"
BATCH_RECEIPT = RECEIPT_PREFIX + "batch.json"

EDIT = """
mutation ReviseExistingAIActDraft(
  $id: PostId!, $text: String!, $dueAt: DateTime!,
  $assets: [AssetInput!]!
) {
  editPost(input: {
    id: $id
    text: $text
    assets: $assets
    mode: customScheduled
    dueAt: $dueAt
    schedulingType: automatic
    saveToDraft: true
  }) {
    __typename
    ... on PostActionSuccess {
      post { id channelId channelService status dueAt text
             shareMode schedulingType assets { type source mimeType } }
    }
    ... on MutationError { message }
  }
}
"""


class RevisionBlocked(RuntimeError):
    pass


def require(ok: bool, reason: str) -> None:
    if not ok:
        raise RevisionBlocked(reason)


def expected_texts(root: Path) -> dict[str, str]:
    payload = json.loads((root / BRIEF).read_text(encoding="utf-8"))
    require(payload["campaign_id"] == CAMPAIGN, "Brief-Kampagne verändert")
    posts = payload["prepared_content"]["posts"]
    require(set(posts) == set(TARGETS), "Nicht exakt drei Originaltexte")
    require(posts["instagram"].endswith(" #Digitalisierung"),
            "Instagram-Ende ist nicht der bekannte 6-Hashtag-Stand")
    new = dict(posts)
    new["instagram"] = posts["instagram"].removesuffix(" #Digitalisierung")
    require(len(re.findall(r"(?<!\w)#[^\s#]+", new["instagram"])) == 5,
            "Instagram muss genau fünf Hashtags enthalten")
    require(new["linkedin"] == posts["linkedin"] and new["facebook"] == posts["facebook"],
            "Andere Texte dürfen nicht geändert werden")
    return posts, new


def same_instant(actual: object, expected: str) -> bool:
    if not isinstance(actual, str):
        return False
    try:
        return datetime.fromisoformat(actual.replace("Z", "+00:00")) == datetime.fromisoformat(
            expected.replace("Z", "+00:00")
        )
    except ValueError:
        return False


def verify_event(mode: str, env: dict[str, str]) -> None:
    require(mode in COMMANDS, "Unbekannter Modus")
    require(
        env.get("GITHUB_REPOSITORY") == bridge.REPOSITORY
        and env.get("GITHUB_REF") == "refs/heads/main"
        and env.get("GITHUB_EVENT_NAME") == "issue_comment"
        and env.get("GITHUB_RUN_ATTEMPT") == "1"
        and env.get("GITHUB_ACTOR") == ACTOR
        and env.get("GITHUB_ACTOR_ID") == str(ACTOR_ID),
        "Nur authentifizierter erster GitHub-Lauf durch derJosef-agents",
    )
    event = Path(env.get("GITHUB_EVENT_PATH", ""))
    require(event.is_file() and event.stat().st_size < 100_000,
            "Authentifizierte Issue-Ereignisdatei fehlt")
    data = json.loads(event.read_text(encoding="utf-8"))
    issue, comment = data.get("issue") or {}, data.get("comment") or {}
    require(
        data.get("action") == "created"
        and issue.get("number") == ISSUE
        and issue.get("title") == ISSUE_TITLE
        and not issue.get("pull_request")
        and (issue.get("user") or {}).get("login") == "derJosef"
        and (comment.get("user") or {}).get("id") == ACTOR_ID
        and comment.get("body") == COMMANDS[mode],
        "Exakter, einmaliger Revisions-Auftrag fehlt",
    )


def verify_image(fetch=None) -> str:
    if fetch is None:
        def fetch(url: str) -> bytes:
            with urllib.request.urlopen(url, timeout=35) as response:
                return response.read(15_000_001)
    require(NEW_IMAGE.startswith(
        "https://raw.githubusercontent.com/derJosef/social-assets/" + IMAGE_COMMIT + "/"
    ), "Bild-Commit nicht festgeschrieben")
    blob = fetch(NEW_IMAGE)
    require(isinstance(blob, bytes) and
            hashlib.sha256(blob).hexdigest() == NEW_IMAGE_SHA256,
            "Neues Bild nicht SHA-identisch")
    with Image.open(io.BytesIO(blob)) as im:
        require(im.format == "PNG" and im.size == (1080, 1350),
                "Neues Motiv muss verifiziertes 1080x1350-PNG sein")
        im.verify()
    return NEW_IMAGE


def check_current(post: object, target: str, old_text: str) -> dict:
    expected = TARGETS[target]
    require(isinstance(post, dict) and post.get("id") == expected["id"] and
            post.get("channelId") == expected["channel"] and
            str(post.get("channelService", "")).lower() == target,
            "Falsche Buffer-Post-/Channel-ID: " + target)
    require(post.get("status") == "draft" and
            same_instant(post.get("dueAt"), expected["due_at"]),
            "Status oder ursprünglicher dueAt verändert: " + target)
    require(post.get("text") == old_text,
            "Text seit ursprünglichem Receipt verändert: " + target)
    require(post.get("shareMode") == "customScheduled" and
            post.get("schedulingType") == "automatic",
            "Bestehender Entwurfs-Zeitmodus unklar: " + target)
    require(post.get("assets") == [{
        "type": "image", "source": OLD_IMAGE, "mimeType": "image/png"
    }], "Bild seit Erstproduktion geändert: " + target)
    require(isinstance(post.get("tags"), list) and
            isinstance(post.get("metadata"), (dict, type(None))),
            "Tags oder Metadaten unklar")
    return {"id": expected["id"], "target": target,
            "dueAt": expected["due_at"], "signature": signature(post),
            "metadata": post.get("metadata"), "tags": post.get("tags")}


def check_revised(post: object, target: str, new_text: str,
                  original: dict) -> None:
    require(isinstance(post, dict) and
            post.get("id") == original["id"] and
            post.get("channelId") == TARGETS[target]["channel"] and
            str(post.get("channelService", "")).lower() == target and
            post.get("status") == "draft" and
            same_instant(post.get("dueAt"), original["dueAt"]) and
            post.get("text") == new_text and
            post.get("shareMode") == "customScheduled" and
            post.get("schedulingType") == "automatic" and
            post.get("tags") == original["tags"] and
            post.get("metadata") == original["metadata"],
            "Unabhängiger Buffer-Readback weicht ab: " + target)
    require(post.get("assets") == [{
        "type": "image", "source": NEW_IMAGE, "mimeType": "image/png"
    }], "Neues Bild nicht im unveränderten Draft: " + target)


def receipt_path(target: str) -> str:
    return RECEIPT_PREFIX + target + ".json"


def run(mode: str, *, root: Path, env: dict[str, str] | None = None,
        query=None, fetch_image=None, get_receipt=None,
        put_receipt=None) -> dict:
    env = dict(os.environ if env is None else env)
    verify_event(mode, env)
    require("createPost" not in EDIT and "shareNow" not in EDIT and
            "saveToDraft: true" in EDIT and "mode: customScheduled" in EDIT,
            "Mutation ist nicht eindeutig draft-only")
    token, gh = env.get("BUFFER_API_KEY", ""), env.get("GITHUB_TOKEN", "")
    require(bool(token), "Buffer-Token fehlt")
    if mode == "apply":
        require(bool(gh), "GitHub-Receipt-Token fehlt")
    query = query or bridge.buffer_graphql
    get_receipt = get_receipt or bridge.fetch_receipt
    put_receipt = put_receipt or bridge.put_receipt
    old, new = expected_texts(root)
    verify_image(fetch_image)
    require(len(set(t["id"] for t in TARGETS.values())) == 3,
            "Post-IDs nicht eindeutig")
    # Entire batch is read and validated BEFORE the first irreversible edit.
    preflight = {}
    for target in ("linkedin", "facebook", "instagram"):
        post = query(token, POST_QUERY, {"id": TARGETS[target]["id"]}).get("post")
        preflight[target] = check_current(post, target, old[target])
    if mode == "preflight":
        return {"state": "read_only_preflight_pass", "posts": list(preflight),
                "existing_ids": [v["id"] for v in preflight.values()],
                "new_image_sha256": NEW_IMAGE_SHA256}

    require(get_receipt(gh, BATCH_RECEIPT) is None,
            "Einmaliger Batch bereits reserviert; kein Replay")
    for target in preflight:
        require(get_receipt(gh, receipt_path(target)) is None,
                "Frühere Mutation reserviert; kein Replay")
    batch = {"state": "pending_manual_reconciliation_on_failure",
             "campaign": CAMPAIGN, "image": NEW_IMAGE,
             "post_ids": [v["id"] for v in preflight.values()],
             "github_run_id": env.get("GITHUB_RUN_ID", "unknown")}
    batch_sha = put_receipt(gh, BATCH_RECEIPT, batch,
                            "reserve one-shot AI Act existing draft revision")
    verified_ids = []
    for target, original in preflight.items():
        # Guard again after previous edits; user may have changed this draft.
        current = query(token, POST_QUERY, {"id": original["id"]}).get("post")
        require(signature(current) == original["signature"],
                "Post seit Preflight verändert; STOP vor Mutation")
        path = receipt_path(target)
        receipt = {
            "state": "pending_manual_reconciliation_on_failure",
            "campaign": CAMPAIGN, "target": target, "post_id": original["id"],
            "expected_due_at": original["dueAt"],
            "new_image_sha256": NEW_IMAGE_SHA256,
            "new_text_sha256": hashlib.sha256(new[target].encode()).hexdigest(),
            "github_run_id": env.get("GITHUB_RUN_ID", "unknown"),
        }
        sha = put_receipt(gh, path, receipt,
                          "reserve exactly one existing draft edit")
        # One and only one Buffer mutation per ID; never retry after ambiguity.
        payload = query(token, EDIT, {
            "id": original["id"], "text": new[target],
            "dueAt": original["dueAt"],
            "assets": [{"image": {"url": NEW_IMAGE,
                                   "metadata": {"altText": ALT}}}],
        })
        result = payload.get("editPost") if isinstance(payload, dict) else None
        changed = result.get("post") if isinstance(result, dict) else None
        require(isinstance(changed, dict) and changed.get("id") == original["id"] and
                changed.get("status") == "draft" and
                same_instant(changed.get("dueAt"), original["dueAt"]),
                "Buffer-Edit nicht eindeutig bestätigt; KEIN RETRY")
        readback = query(token, POST_QUERY, {"id": original["id"]}).get("post")
        check_revised(readback, target, new[target], original)
        receipt["state"] = "verified_existing_draft_revised_unpublished"
        receipt["verified_at"] = datetime.now(timezone.utc).isoformat()
        put_receipt(gh, path, receipt,
                    "confirm unchanged-ID Buffer draft revision", sha=sha)
        verified_ids.append(original["id"])
        print("EXISTING_DRAFT_REVISION_PASS", target, original["id"],
              "status=draft unchanged_dueAt image_attached no_publish", flush=True)
    batch["state"] = "verified_three_existing_drafts_revised_unpublished"
    batch["verified_at"] = datetime.now(timezone.utc).isoformat()
    put_receipt(gh, BATCH_RECEIPT, batch, "verify one-shot AI Act revision",
                sha=batch_sha)
    return {"state": batch["state"], "existing_ids": verified_ids}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("preflight", "apply"), required=True)
    args = parser.parse_args()
    try:
        report = run(args.mode, root=Path(__file__).resolve().parents[1])
        print(json.dumps(report, ensure_ascii=False))
        return 0
    except (RuntimeError, ValueError, OSError, KeyError, json.JSONDecodeError) as exc:
        print("EXISTING_DRAFT_REVISION_BLOCKED", type(exc).__name__,
              str(exc)[:240], file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
