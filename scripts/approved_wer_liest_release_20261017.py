#!/usr/bin/env python3
"""One-time, owner-approved release of exactly three EXISTING 'Wer liest mit?' Buffer drafts.
No createPost, no replay on uncertainty, no other campaigns, no edits to PersonalOS.
Approval: Josef, ChatGPT 2026-10-17. FB+IG now; LI 2026-10-19T11:00:00Z.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from buffer_draft import (
    REPOSITORY, buffer_graphql, channel_preference, fetch_receipt,
    put_receipt, resolve_channel,
)
from legacy_six_buffer_image_edit import POST_QUERY, safe_metadata, signature

TRIGGER = "RELEASE_WER_LIEST_MIT_FB_IG_NOW_LI_20261019_1300_ONCE_20261017"
IMAGE = ("https://raw.githubusercontent.com/derJosef/social-assets/"
         "ac03f948b5ed24dd49c3363dfdef7c82de01810b/media/images/"
         "2026-10-16-legacy-wer-liest-mit-4x5-branded.png")
ALT = "KI-Chat mit zentraler Datenverarbeitung und vernetzten Datenwegen"
DUE_LI = "2026-10-19T11:00:00Z"
BATCH = "delivery-receipts/approved-wer-liest-20261017-release-batch.json"
RECOVERY_PREFIX = "delivery-receipts/legacy-six-image-edit-recovery-20261017-"
POSTS = (
    ("facebook", "6ac8d5ab26e224ee545ee761",
     "710f6011cf218cbebf77802c21fa0df4118fd1a75396a77dc5bca92728d44344"),
    ("instagram", "6ac8d5ae26e224ee545ee809",
     "7659889feaf9f6c7ce32ffc8c87a0ca803b3cae7e3e8078e2116344df2568338"),
    ("linkedin", "6ac8d5a926e224ee545ee6b5",
     "769759595c3f0f535f3d234f0f4fe65ff8d1e187898ce593a8c91e9d7436182b"),
)
SHARE_NOW = """
mutation ReleaseNow($id: PostId!, $text: String!, $assets: [AssetInput!],
                    $metadata: PostInputMetaData, $tagIds: [TagId!]) {
  editPost(input: {id:$id text:$text assets:$assets metadata:$metadata tagIds:$tagIds
                   schedulingType:automatic mode:shareNow saveToDraft:false}) {
    __typename
    ... on PostActionSuccess {post {id channelId status dueAt text}}
    ... on MutationError {message}
  }
}
"""
SCHEDULE_LI = """
mutation ReleaseMonday($id: PostId!, $dueAt: DateTime!, $text: String!,
                       $assets: [AssetInput!], $metadata: PostInputMetaData,
                       $tagIds: [TagId!]) {
  editPost(input: {id:$id text:$text assets:$assets metadata:$metadata tagIds:$tagIds
                   schedulingType:automatic mode:customScheduled dueAt:$dueAt
                   saveToDraft:false}) {
    __typename
    ... on PostActionSuccess {post {id channelId status dueAt text}}
    ... on MutationError {message}
  }
}
"""

class ReleaseBlocked(RuntimeError):
    pass


def need(condition, message):
    if not condition:
        raise ReleaseBlocked(message)


def owner_event(path):
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        issue, comment = data.get("issue", {}), data.get("comment", {})
        return bool(
            data.get("action") == "created"
            and issue.get("number") == 19
            and "pull_request" not in issue
            and (issue.get("user") or {}).get("login") == "derJosef"
            and issue.get("title") == "AIAGENT_BRIEF:2026-10-13-lieferanten-pdf-prueftor-e2e-003"
            and (comment.get("user") or {}).get("login") == "derJosef"
            and comment.get("body") == TRIGGER
        )
    except (OSError, TypeError, ValueError, AttributeError):
        return False


def check_post(record, *, target, pid, text_sha, channel):
    need(isinstance(record, dict) and record.get("id") == pid, "Falsche Post-ID")
    need(record.get("channelId") == channel and
         str(record.get("channelService", "")).lower() == target, "Falscher Buffer-Kanal")
    need(record.get("status") == "draft" and record.get("dueAt") is None,
         "Post ist nicht mehr ein unplanter Draft; KEIN Retry")
    need(record.get("shareMode") != "shareNow", "Post wurde bereits für sofortigen Versand angefragt")
    current_text = record.get("text")
    need(isinstance(current_text, str) and
         hashlib.sha256(current_text.encode("utf-8")).hexdigest() == text_sha,
         "Der von Josef geprüfte Text hat sich seit dem unabhängigen Audit geändert")
    images = record.get("assets")
    need(isinstance(images, list) and len(images) == 1 and
         images[0].get("source") == IMAGE and
         images[0].get("type", "").lower() == "image" and
         images[0].get("mimeType") == "image/png",
         "Originalbild fehlt oder wurde geändert")
    tags = record.get("tags")
    need(isinstance(tags, list) and all(isinstance(t, dict) and isinstance(t.get("id"), str)
                                        for t in tags), "Ungültige Tags")
    metadata = safe_metadata(record, target)
    return {"target":target, "id":pid, "channel":channel, "text":current_text,
            "text_sha":text_sha, "tags":[t["id"] for t in tags], "metadata":metadata,
            "fingerprint":signature(record)}


def verify_recovery(token, target, pid, text_sha):
    receipt = fetch_receipt(token, RECOVERY_PREFIX + pid + ".json")
    need(isinstance(receipt, dict), "Original-Recovery-Receipt nicht lesbar")
    import base64
    try:
        data = json.loads(base64.b64decode(receipt["content"]).decode("utf-8"))
    except (TypeError, KeyError, ValueError) as exc:
        raise ReleaseBlocked("Original-Recovery-Receipt ungültig") from exc
    need(data.get("state") == "verified_existing_draft_image_only_no_schedule"
         and data.get("post_id") == pid and data.get("target") == target
         and data.get("old_text_sha256") == text_sha and data.get("image") == IMAGE,
         "Buffer-Originalreceipts weichen ab")


def run():
    env = os.environ
    need(env.get("GITHUB_REPOSITORY") == REPOSITORY
         and env.get("GITHUB_REF") == "refs/heads/main"
         and env.get("GITHUB_EVENT_NAME") == "issue_comment"
         and env.get("GITHUB_ACTOR") == "derJosef"
         and env.get("GITHUB_RUN_ATTEMPT") == "1"
         and owner_event(env.get("GITHUB_EVENT_PATH", "")),
         "Nur eigentümergeprüfter exakt einmaliger Freigabebefehl")
    buffer_key, github_key = env.get("BUFFER_API_KEY"), env.get("GITHUB_TOKEN")
    need(bool(buffer_key and github_key), "API-Verbindung fehlt")
    need(datetime.now(timezone.utc) < datetime(2026,10,19,10,55,tzinfo=timezone.utc),
         "Freigabe-Workflow zu spät für LinkedIn-Montagstermin")

    # Live preflight of all three posts BEFORE reserving any mutation receipt.
    tasks = []
    for target, pid, text_sha in POSTS:
        channel = resolve_channel(buffer_key, target, channel_preference(target))
        raw = buffer_graphql(buffer_key, POST_QUERY, {"id":pid}).get("post")
        task = check_post(raw, target=target, pid=pid, text_sha=text_sha, channel=channel)
        verify_recovery(github_key, target, pid, text_sha)
        tasks.append(task)
    need(len(tasks) == 3 and len({t["id"] for t in tasks}) == 3, "Falsche Anzahl IDs")
    need(fetch_receipt(github_key, BATCH) is None,
         "Batch bereits reserviert; nur manuelle Abstimmung möglich")
    individual = [f"delivery-receipts/approved-wer-liest-20261017-release-{t['id']}.json"
                  for t in tasks]
    for path in individual:
        need(fetch_receipt(github_key, path) is None,
             "Ein Einzel-Receipt besteht bereits; kein Wiederanlauf")

    base = {"state":"pending_manual_reconciliation_on_failure",
            "post_ids":[t["id"] for t in tasks],
            "approved_scope":"fb_ig_shareNow_li_20261019T110000Z",
            "github_run_id":env.get("GITHUB_RUN_ID")}
    batch_sha = put_receipt(github_key, BATCH, base, "reserve once-approved Wer-liest release")
    completed = []
    for task, receipt_path in zip(tasks, individual):
        target, pid = task["target"], task["id"]
        # Recheck in case Josef or Buffer changed anything while this workflow waited.
        current = buffer_graphql(buffer_key, POST_QUERY, {"id":pid}).get("post")
        check = check_post(current, target=target, pid=pid,
                           text_sha=task["text_sha"], channel=task["channel"])
        need(check["fingerprint"] == task["fingerprint"], "Buffer-Zustand seit Vorprüfung geändert")
        reservation = {"state":"pending_manual_reconciliation_on_failure",
                       "post_id":pid, "target":target,
                       "action":"shareNow" if target != "linkedin" else "customScheduled",
                       "due_at":DUE_LI if target == "linkedin" else None,
                       "text_sha256":task["text_sha"], "image":IMAGE,
                       "github_run_id":env.get("GITHUB_RUN_ID")}
        sha = put_receipt(github_key, receipt_path, reservation,
                          "reserve approved existing Buffer post release")
        variables = {"id":pid, "text":task["text"], "metadata":task["metadata"],
                     "tagIds":task["tags"], "assets":[{"image":{"url":IMAGE,
                                                  "metadata":{"altText":ALT}}}]}
        if target == "linkedin":
            variables["dueAt"] = DUE_LI
        reply = buffer_graphql(buffer_key, SCHEDULE_LI if target == "linkedin" else SHARE_NOW,
                               variables).get("editPost")
        post = reply.get("post") if isinstance(reply, dict) else None
        need(isinstance(post, dict) and post.get("id") == pid,
             "Buffer-Veröffentlichungsmutation nicht bestätigt; Receipt bleibt pending")
        live = buffer_graphql(buffer_key, POST_QUERY, {"id":pid}).get("post")
        need(isinstance(live, dict) and live.get("id") == pid and
             live.get("channelId") == task["channel"] and
             live.get("text") == task["text"] and
             live.get("status") != "draft" and
             live.get("assets") and len(live["assets"]) == 1 and
             live["assets"][0].get("source") == IMAGE,
             "Buffer Readback widerspricht dem freigegebenen Post; kein Retry")
        if target == "linkedin":
            due = live.get("dueAt")
            need(isinstance(due, str) and
                 datetime.fromisoformat(due.replace("Z","+00:00")) ==
                 datetime.fromisoformat(DUE_LI.replace("Z","+00:00")) and
                 live.get("status") in ("buffer", "scheduled"),
                 "LinkedIn-Termin nicht unabhängig bestätigt")
            state = "linkedin_scheduled_verified"
        else:
            need(live.get("shareMode") == "shareNow" and
                 live.get("status") in ("sent", "buffer", "scheduled"),
                 "Sofort-Publikationsauftrag nicht unabhängig nachweisbar")
            state = ("published_sent_verified" if live.get("status") == "sent"
                     else "share_now_accepted_publication_not_yet_verified")
        reservation.update(state=state, verified_at_utc=datetime.now(timezone.utc).isoformat(),
                           buffer_status=live["status"])
        put_receipt(github_key, receipt_path, reservation, "verify approved Buffer release", sha=sha)
        completed.append({"target":target,"post_id":pid,"state":state,
                          "buffer_status":live["status"],"due_at":live.get("dueAt")})
        print("APPROVED_RELEASE_RESULT", json.dumps(completed[-1],ensure_ascii=False))
    base.update(state="release_commands_completed", results=completed,
                verified_at_utc=datetime.now(timezone.utc).isoformat())
    put_receipt(github_key, BATCH, base,"verify approved three-post release",sha=batch_sha)
    print("APPROVED_RELEASE_ALL_THREE_COMMANDS_ACCEPTED")


if __name__ == "__main__":
    try:
        run()
    except (RuntimeError, ValueError, OSError, KeyError, TypeError) as error:
        print("APPROVED_RELEASE_BLOCKED",type(error).__name__,str(error)[:220],file=sys.stderr)
        sys.exit(1)
