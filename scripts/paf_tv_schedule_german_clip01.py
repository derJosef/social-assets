#!/usr/bin/env python3
"""One-time scheduling of the THREE existing German PAF-TV Clip-01 video drafts.

No createPost, no publication on invocation, no English clips, no other posts.
Preflight all three in Buffer + immutable GitHub receipts before the first edit;
reserve a separate one-time receipt for each existing post before editing it.
A missing/ambiguous response halts the batch without retrying any mutation.
"""
from __future__ import annotations
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import sys
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from buffer_draft import (
    REPOSITORY, buffer_graphql, channel_preference, fetch_receipt,
    parse_assets, platform_metadata, put_receipt, read_draft, receipt_path,
    resolve_channel, verify_media_access,
)

TRIGGER = "PAF-TV-SCHEDULE-THREE-GERMAN-CLIP01-20261029"
TZ = ZoneInfo("Europe/Berlin")
ITEMS = (
    {"target":"linkedin", "id":"6ae1a4cbf94c111d6ec0cc7c",
     "path":"drafts/paf-tv-interview-clip01-linkedin.json",
     "media":"PAF-TV_01_ki-agenten_4x5.mp4",
     "utc":"2026-10-29T09:00:00Z", "local":"2026-10-29T10:00:00+01:00"},
    {"target":"facebook", "id":"6ae1c8745719a3c4c80fbbcf",
     "path":"drafts/paf-tv-interview-clip01-facebook.json",
     "media":"PAF-TV_01_ki-agenten_9x16.mp4",
     "utc":"2026-10-29T16:00:00Z", "local":"2026-10-29T17:00:00+01:00"},
    {"target":"instagram", "id":"6ae1c87b26cf140c4c8554f5",
     "path":"drafts/paf-tv-interview-clip01-instagram.json",
     "media":"PAF-TV_01_ki-agenten_9x16.mp4",
     "utc":"2026-10-29T18:00:00Z", "local":"2026-10-29T19:00:00+01:00"},
)
BASE = "https://pauderer.de/assets/videos/social/"
RECEIPT_PREFIX = "schedule-receipts/paf-tv-german-clip01-20261029-"

GET = """
query CheckExistingInterviewVideo($id: PostId!) {
  post(input: {id:$id}) {
    id channelId channelService status dueAt text shareMode schedulingType
    tags { id }
    assets { type source mimeType }
    metadata {
      __typename
      ... on LinkedInPostMetadata { type firstComment linkAttachment {url} }
      ... on FacebookPostMetadata { type firstComment linkAttachment {url} }
      ... on InstagramPostMetadata {
        type firstComment link shouldShareToFeed isAiGenerated geolocation {id text}
      }
    }
  }
}
"""
EDIT = """
mutation ScheduleExistingInterviewVideo($id:PostId!, $dueAt:DateTime!,
  $text:String!, $assets:[AssetInput!], $metadata:PostInputMetaData,
  $tagIds:[TagId!]) {
  editPost(input:{
    id:$id, dueAt:$dueAt, mode:customScheduled, schedulingType:automatic,
    text:$text, assets:$assets, metadata:$metadata, tagIds:$tagIds,
    saveToDraft:false
  }) {
    __typename
    ... on PostActionSuccess {post {id channelId status dueAt}}
    ... on MutationError {message}
  }
}
"""

class ScheduleBlocked(RuntimeError):
    pass

def require(ok, message):
    if not ok:raise ScheduleBlocked(message)

def stamp(s):
    require(isinstance(s,str),"Timestamp is not a string")
    try:
        t=datetime.fromisoformat(s.replace("Z","+00:00"))
        require(t.tzinfo is not None,"Timezone not defined")
        return t.astimezone(timezone.utc)
    except ValueError as exc:raise ScheduleBlocked("Invalid timestamp") from exc

def receipt_name(item):
    return RECEIPT_PREFIX+item["target"]+"-"+item["id"]+".json"

def static_checks():
    require(len(ITEMS)==3 and {i["target"] for i in ITEMS}==
            {"linkedin","facebook","instagram"},"Exactly 3 platforms")
    require(len({i["id"] for i in ITEMS})==3,"Duplicated post IDs")
    for i in ITEMS:
        require(re.fullmatch(r"[0-9a-f]{24}",i["id"]),"Bad post ID")
        require(stamp(i["utc"]).astimezone(TZ).isoformat(timespec="seconds")==i["local"],
                "Wrong local-to-UTC conversion")
        require(i["path"]==f'drafts/paf-tv-interview-clip01-{i["target"]}.json',
                "Wrong draft path")
        require(i["media"]=="PAF-TV_01_ki-agenten_"+("4x5" if i["target"]=="linkedin"
                else "9x16")+".mp4","Unexpected video")
    for forbidden in ("createPost","shareNow"):
        require(forbidden not in EDIT,"Unsafe mutation")
    require("saveToDraft:false" in EDIT,"Scheduling must leave draft mode")
    print("PAF_TV_SCHEDULE_STATIC_THREE_TIMES_VERIFIED",flush=True)

def owner_event():
    e=os.environ
    require(e.get("GITHUB_REPOSITORY")==REPOSITORY and
            e.get("GITHUB_REF")=="refs/heads/main" and
            e.get("GITHUB_EVENT_NAME")=="issue_comment" and
            e.get("GITHUB_RUN_ATTEMPT")=="1" and
            e.get("GITHUB_ACTOR_ID")=="45994004",
            "Only one exact owner comment on protected main")
    event=json.loads(Path(e["GITHUB_EVENT_PATH"]).read_text("utf-8"))
    issue=event.get("issue") or {}
    comment=event.get("comment") or {}
    require(event.get("action")=="created" and issue.get("number")==19
            and not issue.get("pull_request")
            and comment.get("body")==TRIGGER
            and (comment.get("user") or {}).get("id")==45994004,
            "Owner approval not present")

def decode_receipt(raw):
    require(isinstance(raw,dict) and isinstance(raw.get("content"),str),
            "Original GitHub Buffer receipt missing")
    try:
        record=json.loads(base64.b64decode(raw["content"].replace("\n","")).decode())
    except (ValueError,UnicodeError) as exc:
        raise ScheduleBlocked("Invalid Buffer delivery receipt") from exc
    require(isinstance(record,dict),"Invalid receipt shape")
    return record

def immutable_fingerprint(post):
    keys=("id","channelId","channelService","text","tags","assets","metadata","schedulingType")
    return hashlib.sha256(json.dumps({k:post.get(k) for k in keys},
              sort_keys=True,ensure_ascii=False).encode()).hexdigest()

def post_check(post, info, *, scheduled):
    item=info["item"]
    require(isinstance(post,dict) and post.get("id")==item["id"],
            "Buffer post ID mismatch")
    require(post.get("channelId")==info["channel_id"] and
            str(post.get("channelService","")).lower()==item["target"],
            "Wrong Buffer channel")
    require(post.get("text")==info["text"],"Post text was changed")
    assert_date=stamp(item["utc"])
    if scheduled:
        require(post.get("status") in ("scheduled","buffer") and
                stamp(post.get("dueAt"))==assert_date,
                "Buffer did not independently confirm custom-scheduled post")
        require(post.get("shareMode")=="customScheduled",
                "Buffer did not set customScheduled shareMode")
    else:
        require(str(post.get("status","")).lower()=="draft" and
                post.get("dueAt") is None,"Post already scheduled or has changed")
        require(post.get("shareMode")!="shareNow","Post is publishing immediately")
    assets=post.get("assets")
    require(isinstance(assets,list) and len(assets)==1 and
            str(assets[0].get("type","")).lower()=="video" and
            assets[0].get("source")==BASE+item["media"],
            "Original German video was changed in Buffer")
    require(isinstance(post.get("tags"),list) and
            all(isinstance(t,dict) and isinstance(t.get("id"),str)
                for t in post["tags"]),"Tags cannot be preserved")
    metadata=post.get("metadata")
    if item["target"]=="instagram":
        require(isinstance(metadata,dict) and
                metadata.get("__typename")=="InstagramPostMetadata" and
                metadata.get("type")=="reel" and
                metadata.get("shouldShareToFeed") is True and
                not metadata.get("link") and not metadata.get("geolocation") and
                not metadata.get("firstComment"),
                "Instagram original reel metadata must be unmodified")
    elif item["target"]=="facebook":
        require(isinstance(metadata,dict) and
                metadata.get("__typename")=="FacebookPostMetadata" and
                metadata.get("type")=="post" and
                not metadata.get("linkAttachment") and
                not metadata.get("firstComment"),
                "Facebook original post metadata must be unmodified")
    else:
        require(metadata is None or (
                metadata.get("__typename")=="LinkedInPostMetadata" and
                not metadata.get("firstComment") and
                not metadata.get("linkAttachment")),
                "LinkedIn metadata must be original")
    return immutable_fingerprint(post)

def preflight(buffer_key, github_key, *, get=buffer_graphql):
    static_checks()
    now=datetime.now(timezone.utc)
    cache={}
    prepared=[]
    for item in ITEMS:
        require(stamp(item["utc"])>now+timedelta(minutes=20),
                "Scheduled time is too close or past")
        path,text,raw=read_draft(item["path"])
        require(path==item["path"],"Source draft moved")
        record=json.loads(raw)
        require(record["target"]==item["target"] and
                record["media"]=={"type":"video","url":BASE+item["media"]},
                "Wrong original media")
        receipt=decode_receipt(fetch_receipt(github_key,receipt_path(path)))
        require(receipt.get("state")=="draft_created" and
                receipt.get("draft_file")==path and
                receipt.get("target")==item["target"] and
                receipt.get("buffer_post_id")==item["id"] and
                receipt.get("draft_sha256")==hashlib.sha256(raw).hexdigest(),
                "Original delivery receipt differs from draft")
        require(fetch_receipt(github_key,receipt_name(item)) is None,
                "Scheduling already attempted; do not retry")
        channel=resolve_channel(buffer_key,item["target"],
                  channel_preference(item["target"]),channel_cache=cache)
        info={"item":item,"channel_id":channel,"text":text,
              "assets":parse_assets(raw),"metadata":platform_metadata(
                  item["target"],video=True)}
        post=get(buffer_key,GET,{"id":item["id"]}).get("post")
        sig=post_check(post,info,scheduled=False)
        info.update({"fingerprint":sig,"tags":[t["id"] for t in post["tags"]]})
        prepared.append(info)
    print("PAF_TV_ALL_THREE_EXISTING_DRAFTS_READ_ONLY_CONFIRMED",flush=True)
    return prepared

def schedule(buffer_key,github_key,*,get=buffer_graphql):
    owner_event()
    require(bool(buffer_key and github_key),"Credentials absent")
    prepared=preflight(buffer_key,github_key,get=get)
    for info in prepared:
        item=info["item"]
        latest=get(buffer_key,GET,{"id":item["id"]}).get("post")
        require(post_check(latest,info,scheduled=False)==info["fingerprint"],
                "Post modified since preflight; no mutation")
        receipt={"state":"pending_manual_reconciliation_on_failure",
            "target":item["target"],"buffer_post_id":item["id"],
            "due_at_utc":item["utc"],
            "draft_file":item["path"],"original_fingerprint":info["fingerprint"],
            "github_run_id":os.environ.get("GITHUB_RUN_ID","unknown")}
        path=receipt_name(item)
        sha=put_receipt(github_key,path,receipt,
                        "reserve one-time PAF-TV German video scheduling")
        payload={"id":item["id"],"dueAt":item["utc"],"text":info["text"],
                 "assets":info["assets"],"metadata":info["metadata"],
                 "tagIds":info["tags"]}
        result=get(buffer_key,EDIT,payload)
        act=result.get("editPost") if isinstance(result,dict) else None
        post=act.get("post") if isinstance(act,dict) else None
        require(isinstance(post,dict) and post.get("id")==item["id"],
                "Buffer video editPost not confirmed; receipt pending, NO RETRY")
        require(post.get("channelId")==info["channel_id"] and
                post.get("status") in ("scheduled","buffer") and
                stamp(post.get("dueAt"))==stamp(item["utc"]),
                "Buffer mutation did not confirm requested custom date")
        readback=get(buffer_key,GET,{"id":item["id"]}).get("post")
        require(post_check(readback,info,scheduled=True)==info["fingerprint"],
                "Independent readback differs; receipt pending, NO RETRY")
        receipt.update(state="verified_scheduled_video",verified_due_at_utc=item["utc"])
        put_receipt(github_key,path,receipt,"confirm scheduled German PAF-TV video",
                    sha=sha)
        print("PAF_TV_SCHEDULED_AND_READBACK_OK",item["target"],item["id"],
              item["local"],flush=True)
    print("PAF_TV_THREE_GERMAN_VIDEO_POSTS_SCHEDULED_ENGLISH_VERSIONS_UNTOUCHED",flush=True)

if __name__=="__main__":
    try:
        if sys.argv[1:]==["--self-test"]:static_checks()
        elif sys.argv[1:]==["--live"]:
            schedule(os.environ.get("BUFFER_API_KEY",""),os.environ.get("GITHUB_TOKEN",""))
        else:raise ScheduleBlocked("Only explicit --self-test or --live")
    except Exception as exc:
        print("PAF_TV_SCHEDULE_STOP",type(exc).__name__,str(exc)[:190],file=sys.stderr)
        sys.exit(1)
