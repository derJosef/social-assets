#!/usr/bin/env python3
"""Independent read-only reconciliation after autonomous Buffer draft creation."""
import argparse
import json
import os
import re
import sys
from pathlib import Path
from buffer_draft import buffer_graphql, fetch_receipt, receipt_path

POST_QUERY = """
query InspectOrchestratedPost($id: PostId!) {
  post(input: { id: $id }) { id channelId status dueAt }
}
"""
TARGETS = ("linkedin","facebook","instagram")
def verify(campaign: str) -> dict:
    if not re.fullmatch(r"20\d{2}-\d{2}-\d{2}-[a-z0-9]+(?:-[a-z0-9]+)*",campaign):
        raise ValueError("Ungültige Kampagnenkennung")
    token=os.environ.get("GITHUB_TOKEN","")
    buffer_token=os.environ.get("BUFFER_API_KEY","")
    if not token or not buffer_token:
        raise RuntimeError("Missing API credentials for independent Buffer verification")
    outputs={}
    for t in TARGETS:
        file=f"ready-for-buffer/auto-{campaign}-{t}.json"
        receipt=fetch_receipt(token,receipt_path(file))
        if not isinstance(receipt,dict) or not receipt.get("content"):
            raise RuntimeError(f"Missing GitHub receipt for {t}")
        import base64
        record=json.loads(base64.b64decode(receipt["content"]))
        if record.get("state")!="draft_created" or record.get("draft_file")!=file:
            raise RuntimeError(f"Receipt not a confirmed draft: {t}")
        post_id=record.get("buffer_post_id","")
        if not re.fullmatch(r"[0-9a-f]{24}",post_id):
            raise RuntimeError(f"Buffer post ID missing for {t}")
        p=buffer_graphql(buffer_token,POST_QUERY,{"id":post_id}).get("post")
        if not isinstance(p,dict) or p.get("id")!=post_id or p.get("status")!="draft" or p.get("dueAt") is not None:
            raise RuntimeError(f"Buffer status unclear/not draft for {t}")
        outputs[t]={"post_id":post_id,"status":"draft","dueAt":None}
    return outputs

if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--campaign",required=True)
    ap.add_argument("--report",required=True)
    args=ap.parse_args()
    try:
        found=verify(args.campaign)
        path=Path(args.report)
        info=json.loads(path.read_text(encoding="utf-8"))
        info["buffer_verification"]={"status":"PASS","posts":found}
        info["state"]="buffer_drafts_verified"
        path.write_text(json.dumps(info,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        print("BUFFER_VERIFICATION_PASS",json.dumps(found))
    except Exception as err:
        print("BUFFER_VERIFICATION_BLOCKED",type(err).__name__,str(err)[:260],file=sys.stderr)
        sys.exit(1)
