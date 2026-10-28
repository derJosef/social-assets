#!/usr/bin/env python3
"""Replace ONLY video URLs on three already scheduled PAF-TV interview posts.

Never create posts, never change dueAt, text, platform tags or caption metadata.
Every write has its own one-time GitHub receipt and independent Buffer readback.
Only run after six user-original cover MP4s pass remote HTTP SHA verification.
"""
from __future__ import annotations
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import sys
from datetime import datetime,timezone
from urllib.request import Request,urlopen

from buffer_draft import (
    REPOSITORY,buffer_graphql,fetch_receipt,put_receipt,resolve_channel,
    channel_preference
)

TRIGGER="PAF-TV-REPLACE-3-SCHEDULED-COVER-VIDEOS-20261028"
BASE="https://pauderer.de/assets/videos/social/"
RECEIPT_PREFIX="delivery-receipts/paf-tv-existing-scheduled-cover-replace-20261028-"
ITEMS=(
    {"channel":"linkedin","id":"6ae1a4cbf94c111d6ec0cc7c",
     "file":"PAF-TV_01_ki-agenten_4x5",
     "due":"2026-10-29T09:00:00Z",
     "channel_id":"6aac167eea19ca0bde6ada5b"},
    {"channel":"facebook","id":"6ae1c8745719a3c4c80fbbcf",
     "file":"PAF-TV_01_ki-agenten_9x16",
     "due":"2026-10-29T16:00:00Z",
     "channel_id":"6ac781e46a5c39ccb64fe01c"},
    {"channel":"instagram","id":"6ae1c87b26cf140c4c8554f5",
     "file":"PAF-TV_01_ki-agenten_9x16",
     "due":"2026-10-29T18:00:00Z",
     "channel_id":"6ac79a686a5c39ccb650f94b"},
)
POST_QUERY="""
query ReadPAFTVCoverPost($id:PostId!) {
 post(input:{id:$id}) {
   id channelId channelService status dueAt text shareMode schedulingType
   tags {id}
   assets {type source mimeType}
   metadata {
     __typename
     ... on LinkedInPostMetadata {type firstComment linkAttachment {url}}
     ... on FacebookPostMetadata {type firstComment linkAttachment {url}}
     ... on InstagramPostMetadata {
       type firstComment shouldShareToFeed isAiGenerated link geolocation {id text}
     }
   }
 }
}
"""
EDIT="""
mutation ReplaceScheduledPAFTVVideo($id:PostId!,$dueAt:DateTime!,
  $text:String!,$assets:[AssetInput!],$metadata:PostInputMetaData,
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
class Block(RuntimeError):pass
def require(ok,msg):
    if not ok:raise Block(msg)
def timestamp(value):
    require(isinstance(value,str),"Missing Buffer timestamp")
    try:return datetime.fromisoformat(value.replace("Z","+00:00")).astimezone(timezone.utc)
    except ValueError as exc:raise Block("Invalid Buffer timestamp") from exc
def files(item):
    return (BASE+item["file"]+".mp4",
            BASE+item["file"]+"_cover20261028.mp4")
def receipt(item):
    return RECEIPT_PREFIX+item["channel"]+"-"+item["id"]+".json"

def static_test():
    require(len(ITEMS)==3 and {a["channel"] for a in ITEMS}=={
        "linkedin","facebook","instagram"},"Three posts only")
    require(len({x["id"] for x in ITEMS})==3,"Duplicate post IDs")
    require(all(re.fullmatch("[0-9a-f]{24}",x["id"]) for x in ITEMS),
            "Bad Buffer post ID")
    require("createPost" not in EDIT and "shareNow" not in EDIT and
            "saveToDraft:false" in EDIT,"Unsafe Buffer mutation")
    require("mode:customScheduled" in EDIT and "dueAt:$dueAt" in EDIT,
            "Custom time not preserved")
    print("COVER_BUFFER_THREE_EXISTING_POSTS_STATIC_PASS",flush=True)

def owner_event():
    e=os.environ
    require(e.get("GITHUB_REPOSITORY")==REPOSITORY and
            e.get("GITHUB_REF")=="refs/heads/main" and
            e.get("GITHUB_EVENT_NAME")=="issue_comment" and
            e.get("GITHUB_RUN_ATTEMPT")=="1" and
            e.get("GITHUB_ACTOR_ID")=="45994004",
            "Not approved owner-run main event")
    event=json.loads(Path(e["GITHUB_EVENT_PATH"]).read_text("utf-8"))
    i,c=event.get("issue") or {},event.get("comment") or {}
    require(event.get("action")=="created" and i.get("number")==19
            and not i.get("pull_request") and
            c.get("body")==TRIGGER and
            (c.get("user") or {}).get("id")==45994004,
            "Expected single exact approval missing")

def metadata_input(raw,platform):
    if platform=="linkedin":
        require(raw is None or (isinstance(raw,dict) and
                raw.get("__typename")=="LinkedInPostMetadata" and
                not raw.get("linkAttachment")),"Unexpected LinkedIn metadata")
        comment=(raw or {}).get("firstComment")
        require(comment is None or isinstance(comment,str),"Unexpected comment")
        return {"linkedin":{"firstComment":comment}} if comment else None
    require(isinstance(raw,dict),"Missing platform metadata")
    if platform=="facebook":
        require(raw.get("__typename")=="FacebookPostMetadata" and
                raw.get("type")=="post" and not raw.get("linkAttachment"),
                "Facebook post metadata changed")
        m={"type":"post"}
    else:
        require(raw.get("__typename")=="InstagramPostMetadata" and
                raw.get("type")=="reel" and raw.get("shouldShareToFeed") is True and
                not raw.get("link") and not raw.get("geolocation"),
                "Instagram Reel metadata changed")
        m={"type":"reel","shouldShareToFeed":True}
        v=raw.get("isAiGenerated")
        require(v is None or isinstance(v,bool),"Unrecognized AI disclosure")
        if v is not None:m["isAiGenerated"]=v
    comment=raw.get("firstComment")
    require(comment is None or isinstance(comment,str),"Unexpected comment")
    if comment:m["firstComment"]=comment
    return {platform:m}

def content_fingerprint(post):
    fields=("id","channelId","channelService","text","tags","metadata","schedulingType")
    return hashlib.sha256(json.dumps({x:post.get(x) for x in fields},
      sort_keys=True,ensure_ascii=False).encode()).hexdigest()

def check_post(post,item,*,new):
    require(isinstance(post,dict) and post.get("id")==item["id"],
            "Buffer post ID differs")
    require(post.get("channelId")==item["channel_id"] and
            str(post.get("channelService","")).lower()==item["channel"],
            "Wrong Buffer social channel")
    require(post.get("status") in ("scheduled","buffer") and
            timestamp(post.get("dueAt"))==timestamp(item["due"]) and
            post.get("shareMode")=="customScheduled" and
            post.get("schedulingType")=="automatic",
            "Original scheduled time or post mode altered")
    require(isinstance(post.get("text"),str) and
            len(post["text"])>20,
            "Original text not present")
    tags=post.get("tags")
    require(isinstance(tags,list) and all(isinstance(x,dict) and
            isinstance(x.get("id"),str) for x in tags),
            "Cannot preserve tags")
    meta=metadata_input(post.get("metadata"),item["channel"])
    asset=post.get("assets")
    wanted=(files(item)[1] if new else files(item)[0])
    require(isinstance(asset,list) and len(asset)==1 and
            asset[0].get("type")=="video" and
            asset[0].get("source")==wanted,
            "Wrong existing video URL or wrong cover version")
    return content_fingerprint(post),meta,[a["id"] for a in tags]

def verify_cover_video_url(url):
    # HEAD only, initial FULL GET SHA checked in Website GH Actions.
    require(url.startswith(BASE) and url.endswith("_cover20261028.mp4"),
            "Wrong media host or path")
    with urlopen(Request(url,method="HEAD",
                   headers={"Cache-Control":"no-cache"}),timeout=55) as r:
        require(r.status==200 and r.geturl()==url and
                "video/mp4" in r.headers.get("Content-Type","").lower() and
                500_000<int(r.headers.get("Content-Length","0"))<100_000_000,
                "New MP4 not publicly available")

def preflight(key,gh,get=buffer_graphql):
    static_test()
    require(all(timestamp(i["due"])>datetime.now(timezone.utc) for i in ITEMS),
            "PAF-TV post may already have been sent")
    urls=sorted({files(i)[1] for i in ITEMS})
    for url in urls:
        verify_cover_video_url(url)
        print("NEW_COVER_VIDEO_HTTP_PASS",url,flush=True)
    entries=[];cache={}
    for item in ITEMS:
        require(fetch_receipt(gh,receipt(item)) is None,
                "A previous cover media edit already reserved; no retry")
        channel=resolve_channel(key,item["channel"],channel_preference(item["channel"]),
                                channel_cache=cache)
        require(channel==item["channel_id"],"Unexpected account channel")
        current=get(key,POST_QUERY,{"id":item["id"]}).get("post")
        sig,meta,tags=check_post(current,item,new=False)
        entries.append({"item":item,"sig":sig,"metadata":meta,
                        "tags":tags,"text":current["text"]})
    print("THREE_EXISTING_SCHEDULED_CLIP01_READBACK_PRECHECK_PASS",flush=True)
    return entries

def live(key,gh,get=buffer_graphql):
    owner_event()
    require(bool(key and gh),"Missing connected Buffer/GitHub token")
    prepared=preflight(key,gh,get=get)
    for entry in prepared:
        item=entry["item"]
        current=get(key,POST_QUERY,{"id":item["id"]}).get("post")
        sig,meta,tags=check_post(current,item,new=False)
        require(sig==entry["sig"] and meta==entry["metadata"] and
                tags==entry["tags"] and current["text"]==entry["text"],
                "Post changed since preflight")
        path=receipt(item)
        state={"state":"pending_manual_reconciliation_on_failure",
               "post_id":item["id"],"target":item["channel"],
               "date_utc":item["due"],
               "original_media":files(item)[0],
               "new_media":files(item)[1],
               "original_content_sha256":sig,
               "github_run_id":os.environ.get("GITHUB_RUN_ID","unknown")}
        sha=put_receipt(gh,path,state,"reserve one PAF-TV scheduled video cover edit")
        result=get(key,EDIT,{"id":item["id"],"dueAt":item["due"],
                             "text":entry["text"],
                             "assets":[{"video":{"url":files(item)[1]}}],
                             "metadata":entry["metadata"],"tagIds":entry["tags"]})
        act=result.get("editPost") if isinstance(result,dict) else None
        changed=act.get("post") if isinstance(act,dict) else None
        require(isinstance(changed,dict) and changed.get("id")==item["id"],
                "Buffer media edit unconfirmed, immutable receipt pending; NO RETRY")
        require(changed.get("channelId")==item["channel_id"] and
                changed.get("status") in ("scheduled","buffer") and
                timestamp(changed.get("dueAt"))==timestamp(item["due"]),
                "Mutation changed Buffer post scheduling")
        checked=get(key,POST_QUERY,{"id":item["id"]}).get("post")
        sig2,meta2,tags2=check_post(checked,item,new=True)
        require(sig2==sig and meta2==meta and tags2==tags and
                checked.get("text")==entry["text"],
                "Independent readback failed: original metadata/text/time changed")
        state["state"]="verified_scheduled_post_cover_video_replaced"
        put_receipt(gh,path,state,"verify existing scheduled PAF-TV media replacement",sha=sha)
        print("PAF_TV_SCHEDULED_COVER_VIDEO_REPLACED_VERIFIED",item["channel"],item["id"],
              item["due"],flush=True)
    print("PAF_TV_THREE_COVER_VIDEOS_UPDATED_EXISTING_TIMES_UNCHANGED",flush=True)

if __name__=="__main__":
    try:
        if sys.argv[1:]==["--self-test"]:static_test()
        elif sys.argv[1:]==["--live"]:
            live(os.environ.get("BUFFER_API_KEY",""),os.environ.get("GITHUB_TOKEN",""))
        else:raise Block("Explicit --self-test/--live required")
    except Exception as exc:
        print("PAF_TV_BUFFER_COVER_UPDATE_STOP",type(exc).__name__,str(exc)[:210],file=sys.stderr)
        sys.exit(1)
