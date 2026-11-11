#!/usr/bin/env python3
"""Read-only diagnosis: actual Buffer draft video metadata and HTTPS headers.

No createPost, editPost, schedule or publishing operations. No tokens logged.
"""
from __future__ import annotations
import json
import os
import sys
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

BASE = "https://pauderer.de/assets/videos/social/"
POSTS = {
    "linkedin": ("6ae1a4cbf94c111d6ec0cc7c", "PAF-TV_01_ki-agenten_4x5.mp4"),
    "facebook": ("6ae1c8745719a3c4c80fbbcf", "PAF-TV_01_ki-agenten_9x16.mp4"),
    "instagram": ("6ae1c87b26cf140c4c8554f5", "PAF-TV_01_ki-agenten_9x16.mp4"),
}
QUERY = """
query PafTvPlayerDiagnostic($id: PostId!) {
  post(input: {id: $id}) {
    id status channelService
    assets {
      __typename type mimeType source thumbnail
      ... on VideoAsset {
        video { durationMs containerFormat videoCodec frameRate
                audioCodec isTranscodingRequired isVideoProcessing
                width height fileSize }
      }
    }
  }
}
"""
HEADER_KEYS = ("Content-Type", "Content-Length", "Accept-Ranges",
               "Content-Range", "Access-Control-Allow-Origin",
               "Access-Control-Allow-Credentials",
               "Cross-Origin-Resource-Policy", "Cross-Origin-Embedder-Policy",
               "Content-Security-Policy", "X-Frame-Options",
               "Cache-Control", "Vary", "Access-Control-Allow-Headers")

def require(cond, message):
    if not cond:
        raise RuntimeError(message)

def buffer_read(token, post_id):
    body = json.dumps({"query":QUERY, "variables":{"id":post_id}}).encode()
    req=Request("https://api.buffer.com",data=body,method="POST",
                headers={"Authorization":"Bearer "+token,
                         "Content-Type":"application/json",
                         "Accept":"application/json",
                         "User-Agent":"paftv-buffer-readonly-diagnostic/1.0"})
    with urlopen(req,timeout=30) as response:
        return json.load(response)

def extract_status(record, target, expected_id, expected_video):
    require(not record.get("errors"),"Buffer GraphQL returned an error (not printed)")
    data = record.get("data") or {}
    post = data.get("post")
    require(isinstance(post,dict) and post.get("id")==expected_id,
            "Unexpected or missing Buffer post")
    service=str(post.get("channelService","")).lower()
    require(service==target,"Buffer channel mismatch")
    assets=post.get("assets")
    require(isinstance(assets,list),"Buffer assets missing")
    safe=[]
    for asset in assets:
        source=asset.get("source") or ""
        host=urlsplit(source).hostname or ""
        video=asset.get("video")
        safe.append({"type":asset.get("type"),"mimeType":asset.get("mimeType"),
                     "source_host":host,"expected_source":source==BASE+expected_video,
                     "thumbnail_host":urlsplit(asset.get("thumbnail") or "").hostname,
                     "video":video})
    return {"target":target,"status":post.get("status"),"asset_count":len(assets),
            "assets":safe}

def http_probe(label,url,method,range_header=False):
    headers={"Origin":"https://publish.buffer.com",
             "User-Agent":"Mozilla/5.0 (diagnostic of cross-origin media playback)",
             "Accept-Encoding":"identity"}
    if range_header:
        headers["Range"]="bytes=1048576-1048639"
    req=Request(url,method=method,headers=headers)
    with urlopen(req,timeout=45) as response:
        out={"name":label,"method":method,
             "status":response.status,
             "redirected":response.geturl()!=url}
        out.update({k:response.headers.get(k) for k in HEADER_KEYS
                    if response.headers.get(k) is not None})
        if method=="GET":
            chunk=response.read(128)
            out["read_bytes"]=len(chunk)
        return out

def main():
    require(os.environ.get("GITHUB_REPOSITORY")=="derJosef/social-assets",
            "Invalid repository")
    require(os.environ.get("GITHUB_REF")=="refs/heads/main",
            "Invalid Git reference")
    require(os.environ.get("GITHUB_EVENT_NAME")=="issue_comment",
            "Invalid GitHub event")
    require(os.environ.get("GITHUB_ACTOR_ID")=="45994004",
            "Invalid trigger identity")
    token=os.environ.get("BUFFER_API_KEY","")
    require(bool(token),"Missing Buffer API secret")
    for target,(post_id,filename) in POSTS.items():
        result=extract_status(buffer_read(token,post_id),target,post_id,filename)
        print("BUFFER_VIDEO_READBACK "+json.dumps(result,ensure_ascii=False,sort_keys=True),flush=True)
    targets = {
        "Social 9x16": BASE+"PAF-TV_01_ki-agenten_9x16.mp4",
        "Social 4x5": BASE+"PAF-TV_01_ki-agenten_4x5.mp4",
        "Master": "https://pauderer.de/assets/videos/interview-paf-tv-2026-95.mp4",
    }
    for label,url in targets.items():
        for method,ranged in (("HEAD",False),("GET",True)):
            try:
                info=http_probe(label,url,method,ranged)
                print("HTTP_MEDIA_PROBE "+json.dumps(info,ensure_ascii=False,sort_keys=True),flush=True)
            except (HTTPError,URLError,RuntimeError) as exc:
                print("HTTP_MEDIA_PROBE_ERROR "+label+" "+method+": "
                      +str(type(exc).__name__),flush=True)
    print("READ_ONLY_PLAYBACK_DIAGNOSTIC_DONE_NO_POST_MUTATION",flush=True)

if __name__=="__main__":
    try:
        main()
    except (RuntimeError,ValueError,HTTPError,URLError) as exc:
        print("READONLY_DIAG_STOP "+str(exc),file=sys.stderr)
        sys.exit(1)
