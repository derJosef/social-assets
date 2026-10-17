#!/usr/bin/env python3
"""One-shot, six EXACT existing Buffer draft media replacements. Never creates/queues/publishes."""
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
        buffer_graphql, channel_preference, resolve_channel, fetch_receipt, put_receipt,
        REPOSITORY,
    )
except ImportError:
    from buffer_draft import (
        buffer_graphql, channel_preference, resolve_channel, fetch_receipt, put_receipt,
        REPOSITORY,
    )

IMAGE_COMMIT = "ac03f948b5ed24dd49c3363dfdef7c82de01810b"
IMAGE_ROOT = "https://raw.githubusercontent.com/derJosef/social-assets/" + IMAGE_COMMIT + "/media/images/"
RECEIPT_PREFIX = "delivery-receipts/legacy-six-image-edit-20261017-"
EXPECTED = (
    ("wer-liest-mit", "2026-10-16-legacy-wer-liest-mit-4x5-branded.png",
     "27229315d6fd2135b1c0cdc4be20eb94023e25818c7c7fe34c93fe9b715ada55",
     {"linkedin":"6ac8d5a926e224ee545ee6b5",
      "facebook":"6ac8d5ab26e224ee545ee761",
      "instagram":"6ac8d5ae26e224ee545ee809"},
     "KI-Chat mit zentraler Datenverarbeitung und vernetzten Datenwegen"),
    ("drei-tests", "2026-10-16-legacy-ein-agent-drei-tests-4x5-branded.png",
     "adf8f0dff10489bc482d1f11aed8c55a8f3a37c1395c57b376d39517a2ddc73a",
     {"linkedin":"6ac8961e7d9f9f33012bc9cd",
      "facebook":"6ac89617f07e682de6a98b36",
      "instagram":"6ac8961b7d9f9f33012bc803"},
     "Drei technische Prüfschritte für einen KI-Agenten"),
)
ORDER = ("linkedin", "facebook", "instagram")
POST_QUERY = """
query LegacyImageOnlyGetPost($id: PostId!) {
  post(input:{id:$id}) {
    id channelId channelService status dueAt text shareMode schedulingType
    tags { id }
    assets { type source mimeType }
    metadata {
      __typename
      ... on LinkedInPostMetadata { type firstComment linkAttachment { url } }
      ... on FacebookPostMetadata { type firstComment linkAttachment { url } }
      ... on InstagramPostMetadata {
        type firstComment link shouldShareToFeed isAiGenerated
        geolocation { id text }
      }
    }
  }
}
"""
EDIT = """
mutation LegacyReplaceImage($id: PostId!, $text: String!, $assets: [AssetInput!],
                           $metadata: PostInputMetaData, $tagIds: [TagId!]) {
  editPost(input: {
    id: $id
    text: $text
    assets: $assets
    metadata: $metadata
    tagIds: $tagIds
    saveToDraft: true
  }) {
    __typename
    ... on PostActionSuccess {
      post { id channelId channelService status dueAt text shareMode schedulingType
             assets { type source mimeType } tags { id } }
    }
  }
}
"""
# Deliberately no mode, dueAt, schedulingType, createPost, shareNow or publish.
class ImageRepairBlocked(RuntimeError):
    pass

def require(ok: bool, reason: str):
    if not ok:
        raise ImageRepairBlocked(reason)

def signature(post: dict) -> str:
    stable = {k:post.get(k) for k in (
        "id","channelId","channelService","status","dueAt","text",
        "shareMode","schedulingType","tags","assets","metadata",
    )}
    return hashlib.sha256(json.dumps(stable, sort_keys=True,
                                      ensure_ascii=False).encode()).hexdigest()

def media_url(filename: str) -> str:
    require(bool(re.fullmatch(r"2026-10-16-legacy-[a-z0-9-]+-4x5-branded\.png",filename)),
            "Unbekannte Bilddatei")
    return IMAGE_ROOT+filename

def verify_media(fetch=None) -> dict:
    fetch = fetch or fetch_exact_image
    result={}
    for key,filename,sha,_,_ in EXPECTED:
        url=media_url(filename)
        blob=fetch(url)
        require(isinstance(blob,bytes) and hashlib.sha256(blob).hexdigest()==sha,
                "Markenbild im unveränderlichen Git-Commit nicht SHA-identisch: "+key)
        try:
            with Image.open(io.BytesIO(blob)) as img:
                require(img.format=="PNG" and img.size==(1080,1350),
                        "Falsches PNG/Seitenverhältnis")
                img.verify()
        except (OSError,ValueError) as e:
            raise ImageRepairBlocked("PNG-Prüfung fehlgeschlagen") from e
        result[key]=url
    return result

def fetch_exact_image(url: str) -> bytes:
    require(url.startswith(IMAGE_ROOT),"Fremde Medienquelle gesperrt")
    with urllib.request.urlopen(url,timeout=35) as response:
        return response.read(16_000_001)

def safe_metadata(raw: dict, target: str):
    meta=raw.get("metadata")
    if meta is None and target=="linkedin":
        return None
    require(isinstance(meta,dict),"Plattformmetadaten fehlen; kein Edit")
    require(meta.get("type")=="post","Nur einzelne Feed-Posts")
    require(not meta.get("linkAttachment"),"Linkvorschau darf nicht überschrieben werden")
    first=meta.get("firstComment")
    require(first is None or isinstance(first,str),"Ungültiger erster Kommentar")
    if target=="linkedin":
        require(meta.get("__typename")=="LinkedInPostMetadata","Falscher LinkedIn-Metadatentyp")
        v={"type":"post"}
    elif target=="facebook":
        require(meta.get("__typename")=="FacebookPostMetadata","Falscher Facebook-Metadatentyp")
        v={"type":"post"}
    elif target=="instagram":
        require(meta.get("__typename")=="InstagramPostMetadata","Falscher Instagram-Metadatentyp")
        require(meta.get("shouldShareToFeed") is True,"Instagram muss ein Feed-Post bleiben")
        require(not meta.get("geolocation"),"Instagram-Geoposition gesondert prüfen")
        require(not meta.get("link"),"Instagram-Shoplink gesondert prüfen")
        require(meta.get("isAiGenerated") in (True,False),"AI-Kennzeichnung unklar")
        v={"type":"post","shouldShareToFeed":True,
           "isAiGenerated":meta["isAiGenerated"]}
    else:
        raise ImageRepairBlocked("Unbekanntes Netzwerk")
    if first: v["firstComment"]=first
    return {target:v}

def check_post(raw: object, *, id: str, target: str, expected_image: str) -> dict:
    require(isinstance(raw,dict) and raw.get("id")==id,"Post-Identität fehlt")
    require(str(raw.get("channelService","")).lower()==target,"Falsche Plattform")
    require(raw.get("status")=="draft" and raw.get("dueAt") is None,
            "Post ist nicht undatierter draft; keine Mutation")
    require(isinstance(raw.get("text"),str) and bool(raw["text"].strip()),
            "Aktueller Text fehlt")
    require(raw.get("shareMode")!="shareNow","Share-now-Modus gesperrt")
    tags=raw.get("tags")
    require(isinstance(tags,list) and all(isinstance(x,dict) and
            isinstance(x.get("id"),str) for x in tags),"Unbekannte Tags")
    assets=raw.get("assets")
    require(isinstance(assets,list) and len(assets)==1 and
            isinstance(assets[0],dict) and
            str(assets[0].get("type","")).lower()=="image",
            "Erwarteter bestehender Einzelbild-Entwurf fehlt")
    require(assets[0].get("source")!=expected_image,"Bild bereits ersetzt; kein Retry")
    meta=safe_metadata(raw,target)
    return {"id":id,"target":target,"channel_id":raw.get("channelId"),
            "text":raw["text"],"meta":meta,"tag_ids":[x["id"] for x in tags],
            "old_sig":signature(raw),"share_mode":raw.get("shareMode"),
            "scheduling_type":raw.get("schedulingType")}

def build_preflight(buffer_key: str, *, get=buffer_graphql, fetch=None):
    sources=verify_media(fetch)
    channels={target:resolve_channel(buffer_key,target,channel_preference(target)) for target in ORDER}
    tasks=[]
    for topic,_,_,ids,alt in EXPECTED:
        for target in ORDER:
            pid=ids[target]
            url=sources[topic]
            raw=get(buffer_key,POST_QUERY,{"id":pid}).get("post")
            info=check_post(raw,id=pid,target=target,expected_image=url)
            require(info["channel_id"]==channels[target],"Nicht zugeordneter Buffer-Kanal")
            info.update(topic=topic,image=url,alt=alt)
            tasks.append(info)
    require(len(tasks)==6 and len({x["id"] for x in tasks})==6,
            "Sechs eindeutige unveränderte Post-IDs erforderlich")
    return tasks

def receipt_path(pid: str) -> str:
    require(bool(re.fullmatch(r"[a-f0-9]{24}",pid)),"Ungültige feste Post-ID")
    return RECEIPT_PREFIX+pid+".json"

def valid_owner_event(path: Path) -> bool:
    try:
        if not path.is_file() or path.stat().st_size > 100_000:
            return False
        event=json.loads(path.read_text(encoding="utf-8"))
        issue=event.get("issue") or {}
        comment=event.get("comment") or {}
        return (
            event.get("action")=="created"
            and issue.get("number")==19
            and not issue.get("pull_request")
            and (issue.get("user") or {}).get("login")=="derJosef"
            and (comment.get("user") or {}).get("login")=="derJosef"
            and comment.get("body")=="LEGACY_SIX_DRAFTS_REPLACE_IMAGE_ONLY_ONCE_20261017"
        )
    except (OSError,ValueError,TypeError,AttributeError):
        return False


def live_edit(*, get=buffer_graphql, fetch=None):
    require(os.environ.get("GITHUB_REPOSITORY")==REPOSITORY and
            os.environ.get("GITHUB_REF")=="refs/heads/main" and
            os.environ.get("GITHUB_EVENT_NAME")=="issue_comment" and
            os.environ.get("GITHUB_RUN_ATTEMPT")=="1" and
            os.environ.get("GITHUB_ACTOR")=="derJosef",
            "Nur erster eigentümergeprüfter GitHub-Lauf auf main")
    event_file=os.environ.get("GITHUB_EVENT_PATH","")
    require(bool(event_file) and valid_owner_event(Path(event_file)),
            "Expliziter eigentümergeprüfter Einmalauftrag fehlt")
    token=os.environ.get("BUFFER_API_KEY","")
    gh=os.environ.get("GITHUB_TOKEN","")
    require(bool(token and gh),"API-Zugriff fehlt")
    tasks=build_preflight(token,get=get,fetch=fetch)
    # One additional immutable batch reservation: even a failure before the
    # first individual edit cannot silently start a second campaign attempt.
    batch="delivery-receipts/legacy-six-image-edit-batch-20261017.json"
    require(fetch_receipt(gh,batch) is None,
            "Einmaliger Gesamtlauf wurde bereits reserviert; kein Retry")
    for t in tasks:
        require(fetch_receipt(gh,receipt_path(t["id"])) is None,
                "Mindestens ein Buffer-Reparaturbeleg besteht bereits; nicht wiederholen")
    put_receipt(gh,batch,{
        "state":"pending_manual_reconciliation_on_failure",
        "post_ids":[t["id"] for t in tasks],
        "github_run_id":os.environ.get("GITHUB_RUN_ID","unknown")
    },"reserve once-only six existing draft image edits")
    for t in tasks:
        current=get(token,POST_QUERY,{"id":t["id"]}).get("post")
        check=check_post(current,id=t["id"],target=t["target"],expected_image=t["image"])
        require(check["old_sig"]==t["old_sig"],"Buffer-Änderung seit Preflight, Abbruch")
        # Permanent reservation BEFORE the only edit call for this post
        path=receipt_path(t["id"])
        receipt={"post_id":t["id"],"target":t["target"],
                 "topic":t["topic"],"image":t["image"],"old_text_sha256":
                 hashlib.sha256(t["text"].encode()).hexdigest(),
                 "state":"pending_manual_reconciliation_on_failure",
                 "github_run_id":os.environ.get("GITHUB_RUN_ID","unknown")}
        sha=put_receipt(gh,path,receipt,"reserve single existing Buffer draft image edit")
        response=get(token,EDIT,{"id":t["id"],"text":t["text"],
                                  "assets":[{"image":{"url":t["image"],
                                      "metadata":{"altText":t["alt"]}}}],
                                  "metadata":t["meta"],"tagIds":t["tag_ids"]})
        action=response.get("editPost")
        changed=action.get("post") if isinstance(action,dict) else None
        require(isinstance(changed,dict) and changed.get("id")==t["id"],
                "Buffer edit unconfirmed; receipt pending; DO NOT RETRY")
        # Independent GET, not the mutation response, determines success
        verify=get(token,POST_QUERY,{"id":t["id"]}).get("post")
        require(isinstance(verify,dict) and verify.get("id")==t["id"] and
                verify.get("text")==t["text"] and verify.get("status")=="draft" and
                verify.get("dueAt") is None and
                verify.get("channelId")==t["channel_id"] and
                verify.get("shareMode")==t["share_mode"] and
                verify.get("schedulingType")==t["scheduling_type"] and
                isinstance(verify.get("assets"),list) and
                len(verify["assets"])==1 and
                verify["assets"][0].get("source")==t["image"] and
                verify["assets"][0].get("mimeType")=="image/png" and
                [v.get("id") for v in verify.get("tags",[])]==t["tag_ids"],
                "Post edit did not independently verify as unchanged draft; DO NOT RETRY")
        receipt["state"]="verified_existing_draft_image_only_no_schedule"
        receipt["verified_at_utc"]=datetime.now(timezone.utc).isoformat()
        put_receipt(gh,path,receipt,"verify existing Buffer draft image edit",sha=sha)
        print("LEGACY_DRAFT_IMAGE_EDIT_PASS",t["topic"],t["target"],t["id"],
              "status=draft due_at=null, no publish or schedule")

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--live",action="store_true")
    args=parser.parse_args()
    if not args.live: parser.error("No implicit Buffer mutation")
    try:
        live_edit()
        print("LEGACY_DRAFT_IMAGE_EDIT_PASS all six verified")
    except (RuntimeError,ValueError,OSError) as exc:
        print("LEGACY_DRAFT_IMAGE_EDIT_BLOCKED",type(exc).__name__,
              str(exc)[:180],file=sys.stderr)
        return 1
    return 0
if __name__=="__main__":
    raise SystemExit(main())
