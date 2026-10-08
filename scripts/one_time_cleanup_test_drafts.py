#!/usr/bin/env python3
"""One-time Buffer test-draft cleanup; exact allowlist, receipts and live preflight."""
import base64
import json
import os
import sys

from scripts import buffer_draft as api

# Only the six explicit technical test drafts visible in Buffer on 2026-10-08.
ALLOWLIST = {
    "6ac75a585d76b00cd8321775": ("linkedin", "delivery-receipts/30af1273fda7d75693b17106.json"),
    "6ac7731af9e3728044fad9bc": ("linkedin", "delivery-receipts/73a2511d77a9acd301af50dd.json"),
    "6ac77566390a3385c92eda30": ("linkedin", "delivery-receipts/461745205279f9f606dc3ae1.json"),
    "6ac77582f9e3728044fb41d9": ("linkedin", "delivery-receipts/d2991b236d07b4a314b8300b.json"),
    "6ac79c7cd1ababbf88b1c607": ("facebook", "delivery-receipts/d4a745d637fb922f3cd89153.json"),
    "6ac79c9782db5af660c65919": ("instagram", "delivery-receipts/2b85199bff09bcfce284c209.json"),
}
GET_POST = """
query InspectDraft($id: PostId!) {
  post(input: { id: $id }) {
    id
    text
    status
    channelService
    createdAt
  }
}
"""
DELETE_POST = """
mutation DeleteConfirmedTestDraft($id: PostId!) {
  deletePost(input: { id: $id }) {
    __typename
    ... on DeletePostSuccess { id }
    ... on MutationError { message }
  }
}
"""
AUDIT_PATH = "cleanup-audit/2026-10-08-buffer-test-drafts.json"


def ensure_environment():
    if os.environ.get("GITHUB_REPOSITORY") != api.REPOSITORY:
        raise RuntimeError("GitHub repository mismatch")
    if os.environ.get("GITHUB_REF") != "refs/heads/main":
        raise RuntimeError("Cleanup may run only on main")
    key, token = os.environ.get("BUFFER_API_KEY"), os.environ.get("GITHUB_TOKEN")
    if not key or not token:
        raise RuntimeError("Missing Buffer or GitHub API key")
    return key, token


def inspect_post(key, post_id, service):
    response = api.buffer_graphql(key, GET_POST, {"id": post_id})
    post = response.get("post")
    if not isinstance(post, dict):
        raise RuntimeError(f"Buffer post not retrievable: {post_id}")
    if post.get("id") != post_id:
        raise RuntimeError(f"Post ID mismatch: {post_id}")
    if post.get("status") != "draft":
        raise RuntimeError(f"Post not a draft: {post_id}")
    if post.get("channelService") != service:
        raise RuntimeError(f"Service mismatch: {post_id}")
    if not isinstance(post.get("text"), str) or not post["text"].startswith("TESTENTWURF"):
        raise RuntimeError(f"Post does not have explicit TESTENTWURF prefix: {post_id}")
    if not str(post.get("createdAt", "")).startswith("2026-10-08"):
        raise RuntimeError(f"Post not created on test date: {post_id}")


def inspect_receipt(token, post_id, receipt_path, service):
    item = api.fetch_receipt(token, receipt_path)
    if not isinstance(item, dict):
        raise RuntimeError(f"Receipt missing: {receipt_path}")
    raw = base64.b64decode(item["content"].replace("\n", ""))
    receipt = json.loads(raw)
    if receipt.get("buffer_post_id") != post_id or receipt.get("state") != "draft_created":
        raise RuntimeError(f"Receipt does not prove successful creation: {post_id}")
    if receipt.get("target", service) != service:
        raise RuntimeError(f"Receipt target mismatch: {post_id}")


def main():
    key, token = ensure_environment()
    if len(ALLOWLIST) != 6:
        raise RuntimeError("Expected exactly six test drafts")
    if api.fetch_receipt(token, AUDIT_PATH) is not None:
        raise RuntimeError("One-time cleanup audit already exists; never rerun")
    # Phase 1: No deletion until every receipt AND Buffer draft are verified.
    for post_id, (service, receipt) in ALLOWLIST.items():
        inspect_receipt(token, post_id, receipt, service)
        inspect_post(key, post_id, service)
        print(f"Preflight OK: {service}, draft {post_id}")
    print("All six test drafts verified before first delete.")

    audit = {
        "test_date": "2026-10-08",
        "purpose": "Only six approved test drafts; regular content and receipts untouched",
        "github_run_id": os.environ.get("GITHUB_RUN_ID", ""),
        "results": [],
    }
    audit_sha = api.put_receipt(token, AUDIT_PATH, audit, "audit(buffer): reserve one-time six-draft cleanup")
    # Phase 2: Each mutation is by an exact post ID and requires Buffer confirmation.
    try:
        for post_id, (service, receipt) in ALLOWLIST.items():
            inspect_post(key, post_id, service)
            answer = api.buffer_graphql(key, DELETE_POST, {"id": post_id}).get("deletePost", {})
            if not isinstance(answer, dict) or answer.get("id") != post_id:
                raise RuntimeError(f"Buffer did not confirm deletion: {post_id}; type={answer.get('__typename') if isinstance(answer, dict) else 'unknown'}")
            audit["results"].append({"post_id": post_id, "target": service, "status": "deleted"})
            audit_sha = api.put_receipt(token, AUDIT_PATH, audit, f"audit(buffer): confirmed deletion {post_id}", sha=audit_sha)
            print(f"DELETED CONFIRMED: {service} {post_id}")
    except BaseException:
        print(f"Cleanup interrupted after {len(audit['results'])} confirmations; audit preserved", file=sys.stderr)
        raise
    print("COMPLETE: exactly six Buffer test drafts deleted, no other posts touched.")


if __name__ == "__main__":
    main()
