#!/usr/bin/env python3
"""One-time recovery after failed date-only edit. No automatic retries.

October 28 first attempt: Buffer returned a MutationError for editing ONLY
dueAt; fresh independent audit shows BOTH posts unchanged. Recovery includes
original current content in the mutation as required by Buffer's whole-post
validation; independently verifies every persisted field afterwards.
"""
from __future__ import annotations
import base64
import hashlib
import json
import os
from datetime import datetime,timezone,timedelta
from pathlib import Path
import sys

import paf_tv_move_two_existing_schedules as old
from buffer_draft import buffer_graphql,fetch_receipt,put_receipt

TRIGGER="PAF-TV-MOVE-TWO-POSTS-RECOVER-WHOLE-VALIDATION-20261028"
FIRST_RUN="40673207492"
FIRST_ONLY=old.RECEIPTS+old.POSTS[0]["id"]+".json"
RECOVERY="delivery-receipts/paf-tv-two-existing-posts-shift-recovery-20261028-"

QUERY=old.QUERY.replace("assets { type source mimeType }",
    "assets { type source mimeType ... on ImageAsset { image { altText userTags { __typename } } } }")
EDIT="""
mutation RecoverOriginalScheduled($id: PostId!, $dueAt: DateTime!,
    $text: String!, $assets: [AssetInput!], $metadata: PostInputMetaData,
    $tagIds: [TagId!]) {
  editPost(input:{
    id:$id, dueAt:$dueAt, mode:customScheduled,
    text:$text, assets:$assets, metadata:$metadata, tagIds:$tagIds
  }) {
    __typename
    ... on PostActionSuccess {post {id channelId status dueAt}}
    ... on MutationError {message}
  }
}
"""

def require(cond,msg):
    if not cond:raise old.Block(msg)

def decode(file):
    require(isinstance(file,dict) and isinstance(file.get("content"),str),
            "Expected existing Github receipt not found")
    try:
        return json.loads(base64.b64decode(file["content"].replace("\n","")).decode("utf-8"))
    except (ValueError, UnicodeError) as exc:raise old.Block("Invalid old receipt") from exc

def owner_event():
    env=os.environ
    require(env.get("GITHUB_REPOSITORY")=="derJosef/social-assets"
            and env.get("GITHUB_REF")=="refs/heads/main"
            and env.get("GITHUB_EVENT_NAME")=="issue_comment"
            and env.get("GITHUB_ACTOR_ID")=="45994004"
            and env.get("GITHUB_RUN_ATTEMPT")=="1",
            "Only exact one-time owner action on main")
    event=json.loads(Path(env["GITHUB_EVENT_PATH"]).read_text("utf-8"))
    require(event.get("action")=="created"
            and (event.get("issue") or {}).get("number")==19
            and not (event.get("issue") or {}).get("pull_request")
            and (event.get("comment") or {}).get("body")==TRIGGER
            and (event.get("comment") or {}).get("user",{}).get("id")==45994004,
            "Invalid one-time owner consent")

def content_input(raw,p):
    # Validate original content + ensure no unsupported image metadata will be lost.
    fingerprint=old.verify_post(raw,p,before=True)
    asset=raw["assets"][0]
    image=asset.get("image")
    require(isinstance(image,dict)
            and isinstance(image.get("altText"),str)
            and not image.get("userTags"),
            "Existing image accessibility/tags cannot be preserved safely")
    metadata=raw.get("metadata")
    if p["channel"]=="instagram":
        require(isinstance(metadata,dict)
                and metadata.get("__typename")=="InstagramPostMetadata"
                and metadata.get("type")=="post"
                and metadata.get("shouldShareToFeed") is True
                and not metadata.get("link")
                and not metadata.get("geolocation"),
                "Instagram metadata requires custom handling")
        value={"instagram":{"type":"post","shouldShareToFeed":True}}
        if metadata.get("isAiGenerated") is not None:
            require(isinstance(metadata["isAiGenerated"],bool),"Unknown disclosure")
            value["instagram"]["isAiGenerated"]=metadata["isAiGenerated"]
        if metadata.get("firstComment"):
            require(isinstance(metadata["firstComment"],str),"Invalid comment")
            value["instagram"]["firstComment"]=metadata["firstComment"]
    else:
        require(metadata is None or metadata.get("__typename")=="LinkedInPostMetadata",
                "LinkedIn unexpected metadata")
        require(not metadata or not metadata.get("linkAttachment"),
                "Existing LinkedIn link attachment cannot be reconstructed")
        first=(metadata or {}).get("firstComment")
        require(first is None or isinstance(first,str),"Invalid LinkedIn comment")
        value={"linkedin":{"firstComment":first}} if first else None
    return {
        "id":p["id"],"dueAt":p["new"],"text":raw["text"],
        "assets":[{"image":{"url":asset["source"],
                            "metadata":{"altText":image["altText"]}}}],
        "metadata":value,
        "tagIds":[t["id"] for t in raw["tags"]],
    },fingerprint

def preflight(key,get=buffer_graphql):
    old.check_fixture()
    tasks=[]
    for p in old.POSTS:
        require(old.dt(p["new"])>datetime.now(timezone.utc)+timedelta(minutes=2),
                "New schedule time must be in future")
        raw=get(key,QUERY,{"id":p["id"]}).get("post")
        payload,signature=content_input(raw,p)
        tasks.append((p,payload,signature))
    print("RECOVERY_READ_ONLY_VERIFIED_BOTH_UNCHANGED",flush=True)
    return tasks

def live(key,github_key,get=buffer_graphql):
    owner_event()
    require(bool(key and github_key),"Token missing")
    tasks=preflight(key,get=get)
    old_receipt=decode(fetch_receipt(github_key,FIRST_ONLY))
    require(old_receipt.get("state")=="pending_manual_reconciliation_on_failure"
            and old_receipt.get("github_run_id")==FIRST_RUN
            and old_receipt.get("post_id")==old.POSTS[0]["id"]
            and old_receipt.get("old_due_at_utc")==old.POSTS[0]["old"],
            "Unreconciled prior partial write; no recovery")
    # Check no other old or recovery reservation exists.
    require(fetch_receipt(github_key,old.RECEIPTS+old.POSTS[1]["id"]+".json") is None,
            "Earlier process may have edited second post")
    for p,_,_ in tasks:
        require(fetch_receipt(github_key,RECOVERY+p["id"]+".json") is None,
                "Recovery was already attempted; stop")
    for p,payload,signature in tasks:
        latest=get(key,QUERY,{"id":p["id"]}).get("post")
        _,current_sig=content_input(latest,p)
        require(current_sig==signature,"Post modified during recovery")
        path=RECOVERY+p["id"]+".json"
        receipt={"post_id":p["id"],"channel":p["channel"],"old":p["old"],
                 "new":p["new"],"state":"pending_manual_reconciliation_on_failure",
                 "github_run_id":os.environ.get("GITHUB_RUN_ID","unknown"),
                 "preflight_content_sha256":signature}
        sha=put_receipt(github_key,path,receipt,"reserve one-time Buffer full-content recovery")
        # One write per existing post, NO retry on lost/ambiguous response.
        result=get(key,EDIT,payload)
        mutation=result.get("editPost") if isinstance(result,dict) else None
        candidate=mutation.get("post") if isinstance(mutation,dict) else None
        if not isinstance(candidate,dict) or candidate.get("id")!=p["id"]:
            typename=mutation.get("__typename") if isinstance(mutation,dict) else "Unknown"
            # never display arbitrary Buffer error text in public Actions logs.
            raise old.Block("Buffer did not confirm recovery edit; API result "+str(typename)[:50]
                            +"; receipt pending, DO NOT RETRY")
        require(candidate.get("channelId")==p["channel_id"]
                and candidate.get("status") in ("scheduled","buffer")
                and old.current_equal(candidate.get("dueAt"),p["new"]),
                "Recovery edit response not exact")
        after=get(key,QUERY,{"id":p["id"]}).get("post")
        require(old.verify_post(after,p,before=False)==signature
                and after.get("shareMode")=="customScheduled",
                "Independent readback changed image/text/meta/tags or dueAt")
        receipt.update(state="verified_rescheduled_existing_post")
        put_receipt(github_key,path,receipt,"readback verified existing Buffer post moved",sha=sha)
        print("BUFFER_MOVED_AND_VERIFIED",p["channel"],p["id"],p["new_local"],flush=True)
    print("PAF_TV_TWO_EXISTING_POSTS_RESCHEDULED_NO_INTERVIEW_CHANGES",flush=True)

if __name__=="__main__":
    try:
        if len(sys.argv)==2 and sys.argv[1]=="--self-test":
            old.check_fixture()
            require("createPost" not in EDIT and "saveToDraft" not in EDIT
                    and "shareNow" not in EDIT,"unsafe mutation")
            print("RECOVERY_OFFLINE_PASS")
        elif len(sys.argv)==2 and sys.argv[1]=="--live":
            live(os.environ.get("BUFFER_API_KEY",""),os.environ.get("GITHUB_TOKEN",""))
        else: raise old.Block("Explicit --live or --self-test required")
    except Exception as exc:
        print("RECOVERY_SCHEDULE_MOVE_STOP",type(exc).__name__,str(exc)[:170],file=sys.stderr)
        sys.exit(1)
