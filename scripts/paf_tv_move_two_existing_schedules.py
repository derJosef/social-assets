#!/usr/bin/env python3
"""Move exactly two already scheduled Buffer posts, never create/publish another.

This is deliberately one-time. Both original post identities and times must
match before any edit. Change only mode + dueAt; Buffer retains text, media,
metadata, tags, scheduling type, channel and content on omitted fields.
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path
import re
import sys
from zoneinfo import ZoneInfo

from buffer_draft import REPOSITORY, buffer_graphql, fetch_receipt, put_receipt

TRIGGER = "PAF-TV-MOVE-EXISTING-LI-IG-20261028"
RECEIPTS = "delivery-receipts/paf-tv-two-existing-posts-shift-20261028-"
BERLIN = ZoneInfo("Europe/Berlin")
POSTS = (
    {
        "channel": "instagram",
        "id": "6ac7fa87c121d8911406c941",
        "channel_id": "6ac79a686a5c39ccb650f94b",
        "text_prefix": "DARF DER KI-AGENT DAS?",
        "old": "2026-10-28T17:00:00.000Z",
        "new": "2026-10-30T17:00:00Z",
        "new_local": "2026-10-30T18:00:00+01:00",
    },
    {
        "channel": "linkedin",
        "id": "6acdefc5ca68ebbd369b79a7",
        "channel_id": "6aac167eea19ca0bde6ada5b",
        "text_prefix": "Eine Lieferanten-PDF kann technische Daten enthalten.",
        "old": "2026-10-28T15:00:00.000Z",
        "new": "2026-11-12T12:00:00Z",
        "new_local": "2026-11-12T13:00:00+01:00",
    },
)

QUERY = """
query PafTvMoveGet($id: PostId!) {
  post(input: {id:$id}) {
    id channelId channelService status dueAt text shareMode schedulingType
    tags { id }
    assets { type source mimeType }
    metadata {
      __typename
      ... on LinkedInPostMetadata { type firstComment linkAttachment { url } }
      ... on InstagramPostMetadata { type firstComment link shouldShareToFeed isAiGenerated
        geolocation {id text} }
    }
  }
}
"""
# No text/asset/meta/tag/schedulingType/saveToDraft in input: ALL preserved.
EDIT = """
mutation PafTvMoveExisting($id: PostId!, $dueAt: DateTime!) {
  editPost(input: {
    id: $id
    mode: customScheduled
    dueAt: $dueAt
  }) {
    __typename
    ... on PostActionSuccess { post {id channelId status dueAt} }
    ... on MutationError { message }
  }
}
"""

class Block(RuntimeError):
    pass

def require(ok, msg):
    if not ok: raise Block(msg)

def dt(s):
    require(isinstance(s,str), "Non-string Buffer time")
    try: return datetime.fromisoformat(s.replace("Z","+00:00")).astimezone(timezone.utc)
    except ValueError as ex: raise Block("Invalid UTC timestamp") from ex

def current_equal(a,b):
    return dt(a)==dt(b)

def check_fixture():
    require(len(POSTS)==2 and len({p["id"] for p in POSTS})==2,
            "Exactly two unique posts")
    for p in POSTS:
        require(re.fullmatch(r"[a-f0-9]{24}",p["id"]), "Bad post ID")
        require(dt(p["new"]).astimezone(BERLIN).isoformat(timespec="seconds")==p["new_local"],
                "Wrong daylight savings conversion")
        require(dt(p["new"]) > dt(p["old"]), "Cannot shift backwards")
    require("createPost" not in EDIT and "shareNow" not in EDIT,
            "Unsafe mutation")
    require("saveToDraft" not in EDIT and "schedulingType:" not in EDIT,
            "Do not alter publishing mode")
    require("assets:" not in EDIT and "text:" not in EDIT and "metadata:" not in EDIT,
            "Do not touch content or assets")
    print("TWO_EXISTING_POST_TIME_CONTRACT_OK")

def valid_event():
    env=os.environ
    require(env.get("GITHUB_REPOSITORY")==REPOSITORY
            and env.get("GITHUB_REF")=="refs/heads/main"
            and env.get("GITHUB_EVENT_NAME")=="issue_comment"
            and env.get("GITHUB_RUN_ATTEMPT")=="1"
            and env.get("GITHUB_ACTOR_ID")=="45994004",
            "Only first owner-triggered run on main")
    event=json.loads(Path(env["GITHUB_EVENT_PATH"]).read_text("utf-8"))
    require(event.get("action")=="created", "Wrong event action")
    issue=event.get("issue") or {}
    comment=event.get("comment") or {}
    require(issue.get("number")==19
            and not issue.get("pull_request")
            and comment.get("body")==TRIGGER
            and comment.get("user",{}).get("id")==45994004,
            "Owner one-time approval missing")

def fingerprint(post):
    # Everything except schedule-related fields is immutable.
    immutable=("id","channelId","channelService","text","schedulingType",
               "tags","assets","metadata")
    stable={k:post.get(k) for k in immutable}
    return hashlib.sha256(json.dumps(stable,sort_keys=True,ensure_ascii=False).encode()).hexdigest()

def verify_post(post, expected, *, before):
    require(isinstance(post,dict) and post.get("id")==expected["id"],
            "Expected Buffer post missing")
    require(post.get("channelId")==expected["channel_id"] and
            post.get("channelService","").lower()==expected["channel"],
            "Wrong Buffer channel")
    require(str(post.get("status","")).lower() in ("scheduled","buffer"),
            "Post already sent/draft/unknown")
    require(isinstance(post.get("text"),str) and
            post["text"].startswith(expected["text_prefix"]),
            "Post content differs from approved topic")
    if before:
        require(current_equal(post.get("dueAt"),expected["old"]),
                "Original time changed since last audit")
    else:
        require(current_equal(post.get("dueAt"),expected["new"]),
                "New time not independently confirmed")
    assets=post.get("assets")
    require(isinstance(assets,list) and len(assets)==1
            and assets[0].get("type","").lower()=="image"
            and isinstance(assets[0].get("source"),str)
            and assets[0]["source"].startswith("https://"),
            "Original image missing/changed")
    tags=post.get("tags")
    require(isinstance(tags,list) and all(isinstance(t.get("id"),str) for t in tags),
            "Cannot preserve post tags")
    metadata=post.get("metadata")
    require(metadata is None or isinstance(metadata,dict),
            "Cannot preserve metadata")
    require(post.get("shareMode")!="shareNow", "Already publishing now")
    return fingerprint(post)

def preflight(key, *, get=buffer_graphql):
    check_fixture()
    seen=[]
    for p in POSTS:
        require(dt(p["new"])>datetime.now(timezone.utc)+timedelta(minutes=2),
                "Requested new date is no longer in the future")
        before=get(key,QUERY,{"id":p["id"]}).get("post")
        sig=verify_post(before,p,before=True)
        seen.append({"post":p,"before_sig":sig,"before_share_mode":before.get("shareMode")})
    print("PREFLIGHT_TWO_ORIGINAL_BUFFER_SCHEDULED_POSTS_IDENTIFIED",flush=True)
    return seen

def receipt_path(p):
    return RECEIPTS+p["id"]+".json"

def shift(key,github_key,*,get=buffer_graphql):
    require(key and github_key,"Buffer/GitHub credentials missing")
    valid_event()
    targets=preflight(key,get=get)
    # Validate *both* and absence of all receipts before first mutation.
    for item in targets:
        require(fetch_receipt(github_key,receipt_path(item["post"])) is None,
                "One-time schedule receipt already exists; cannot retry")
    for item in targets:
        p=item["post"]
        # Re-fetch directly before the change. No stale writes.
        before=get(key,QUERY,{"id":p["id"]}).get("post")
        require(verify_post(before,p,before=True)==item["before_sig"],
                "Post modified after preflight")
        receipt={
            "post_id":p["id"],"channel":p["channel"],
            "old_due_at_utc":p["old"],"new_due_at_utc":p["new"],
            "state":"pending_manual_reconciliation_on_failure",
            "original_content_sha256":item["before_sig"],
            "github_run_id":os.environ.get("GITHUB_RUN_ID","unknown")
        }
        rec_sha=put_receipt(github_key,receipt_path(p),receipt,
                            "reserve owner-approved Buffer schedule move")
        # Never retry an editPost mutation after the receipt is reserved.
        result=get(key,EDIT,{"id":p["id"],"dueAt":p["new"]})
        edit=result.get("editPost") if isinstance(result,dict) else None
        candidate=edit.get("post") if isinstance(edit,dict) else None
        require(isinstance(candidate,dict) and candidate.get("id")==p["id"],
                "Buffer editPost unconfirmed; pending receipt, DO NOT RETRY")
        require(candidate.get("channelId")==p["channel_id"]
                and str(candidate.get("status","")).lower() in ("scheduled","buffer")
                and current_equal(candidate.get("dueAt"),p["new"]),
                "Buffer mutation result did not confirm schedule")
        after=get(key,QUERY,{"id":p["id"]}).get("post")
        require(verify_post(after,p,before=False)==item["before_sig"],
                "Readback differs: some original post content/asset/metadata changed")
        require(after.get("shareMode")=="customScheduled",
                "Post is not in customScheduled mode after edit")
        receipt.update(state="verified_rescheduled_existing_post",verified_due_at_utc=p["new"])
        put_receipt(github_key,receipt_path(p),receipt,
                    "verify original Buffer post rescheduled, content intact",sha=rec_sha)
        print("BUFFER_ORIGINAL_POST_TIME_MOVED",
              p["channel"],p["id"],p["new_local"],"status=scheduled",flush=True)
    print("TWO_EXISTING_BUFFER_DATES_MOVED_INTERVIEW_DRAFTS_UNTOUCHED",flush=True)

def main():
    if "--self-test" in sys.argv:
        check_fixture()
        return
    if "--live" not in sys.argv or len(sys.argv)!=2:
        raise Block("Only --live after protected owner event")
    shift(os.environ.get("BUFFER_API_KEY",""),os.environ.get("GITHUB_TOKEN",""))

if __name__=="__main__":
    try:main()
    except Exception as ex:
        print("BUFFER_SCHEDULE_MOVE_STOP",type(ex).__name__,str(ex)[:170],file=sys.stderr)
        raise SystemExit(1)
