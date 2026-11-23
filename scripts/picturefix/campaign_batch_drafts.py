#!/usr/bin/env python3
"""PictureFix manifest-to-Buffer: exactly three unpublished, dated, checked drafts.

The creative campaign is data.  Only delivery safety is deterministic.  The
legacy PF-01/02/03 runners and the AI Agent Builder remain completely separate.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sys
from zoneinfo import ZoneInfo

from scripts import buffer_draft as bridge
from scripts.picturefix.brand_artwork import verify_imprint


ROOT = Path(__file__).resolve().parents[2]
AGENT_LOGIN = "derJosef-agents"
AGENT_ID = "350701981"
LOGO_BLOB = "0cd926e6631209dd4e5c8029dfb72c29bbf89ea8"
TARGETS = ("facebook", "instagram", "pinterest")
ID_RE = re.compile(r"PF-[0-9]{2,4}")
SHA_RE = re.compile(r"[0-9a-f]{64}")
COMMIT_RE = re.compile(r"[0-9a-f]{40}")
POST_ID_RE = re.compile(r"[a-f0-9]{24}")
READ = """
query VerifyPictureFixCampaignDraft($id: PostId!) {
  post(input: { id: $id }) {
    id channelId channelService status dueAt text shareMode schedulingType
    assets { type source }
  }
}
"""
POSTS_QUERY = """
query AuditPictureFixPosts($organizationId: OrganizationId!, $channelIds: [ChannelId!], $after: String) {
  posts(first: 100, after: $after, input: {
    organizationId: $organizationId,
    filter: {channelIds: $channelIds},
    sort: [{field: createdAt, direction: desc}]
  }) {
    edges { node { id channelId status text dueAt assets { source } } }
    pageInfo { hasNextPage endCursor }
  }
}
"""


class CampaignBlocked(RuntimeError):
    """Ambiguous authority, media, schedule or Buffer state: fail closed."""


def require(ok: bool, why: str) -> None:
    if not ok:
        raise CampaignBlocked(why)


def timestamp(value: object) -> datetime:
    require(isinstance(value, str) and len(value) < 60, "Time must be ISO-8601")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise CampaignBlocked("Invalid scheduled time") from exc
    require(parsed.tzinfo is not None, "Scheduled time requires zone")
    return parsed.astimezone(timezone.utc)


def authenticate_push(env: dict[str, str]) -> str:
    """An authenticated first-attempt, owner-agent main push, not a PR build."""
    require(env.get("GITHUB_REPOSITORY") == bridge.REPOSITORY and
            env.get("GITHUB_REF") == "refs/heads/main" and
            env.get("GITHUB_EVENT_NAME") == "push" and
            env.get("GITHUB_RUN_ATTEMPT") == "1" and
            env.get("GITHUB_ACTOR") == AGENT_LOGIN and
            env.get("GITHUB_ACTOR_ID") == AGENT_ID,
            "Only an authorized derJosef-agents push to main can deliver")
    commit = env.get("GITHUB_SHA", "")
    require(bool(COMMIT_RE.fullmatch(commit)), "Immutable main commit required")
    return commit


def select_new_manifest(diff: str) -> str:
    """Accept exactly one added manifest plus up to two new campaign PNGs.

    The action supplies git diff --name-status for before..after; no argument
    from an issue comment, PR file or workflow_dispatch is trusted.
    """
    require(isinstance(diff, str) and 0 < len(diff) < 8_000, "Invalid push diff")
    added = []
    for line in diff.splitlines():
        bits = line.split("\t")
        require(len(bits) == 2 and bits[0] == "A", "Only new campaign files allowed")
        added.append(bits[1])
    manifests = [p for p in added if re.fullmatch(r"picturefix/campaigns/PF-[0-9]{2,4}\.json", p)]
    require(len(manifests) == 1 and len(added) == 4,
            "Exactly one new campaign, two images and creative QA required")
    campaign_id = Path(manifests[0]).stem
    require(int(campaign_id[3:]) >= 4, "PF-01 to PF-03 are immutable legacy campaigns")
    expected_prefix = f"media/images/PictureFix_{campaign_id.replace('-', '')}_"
    images = [p for p in added if p.startswith(expected_prefix) and p.endswith(".png")]
    qa = f"picturefix/quality/{campaign_id}.json"
    require(len(images) == 2 and len(set(images)) == 2 and
            set(added) == {manifests[0], *images, qa},
            "Push must contain only one campaign manifest, exactly two PNGs and QA")
    return manifests[0]


def load_campaign(manifest_path: str, commit: str, *, now: datetime | None = None,
                  root: Path | None = None) -> tuple[dict, list[dict]]:
    """Offline manifest, logo metadata, dates, URLs, copy and image hash checks."""
    require(bool(COMMIT_RE.fullmatch(commit)), "Media requires immutable commit")
    require(bool(re.fullmatch(r"picturefix/campaigns/PF-[0-9]{2,4}\.json", manifest_path)),
            "Manifest is outside approved PictureFix namespace")
    root = root or ROOT
    file = root / manifest_path
    require(file.is_file() and file.stat().st_size <= 40_000, "Missing/oversized manifest")
    record = json.loads(file.read_text(encoding="utf-8"))
    require(isinstance(record, dict) and set(record) == {
        "version", "campaign_id", "brand", "topic_key", "topic", "sources",
        "logo_git_blob_sha1", "creative_qa", "posts",
    }, "Manifest fields must match approved schema")
    campaign_id = Path(manifest_path).stem
    require(int(campaign_id[3:]) >= 4, "Cannot recreate legacy PictureFix campaigns")
    require(record.get("version") == 1 and record.get("brand") == "picturefix" and
            record.get("campaign_id") == campaign_id and
            record.get("logo_git_blob_sha1") == LOGO_BLOB,
            "Campaign identity, real logo or version mismatch")
    require(isinstance(record.get("topic_key"), str) and
            re.fullmatch(r"[a-z0-9][a-z0-9-]{8,99}", record["topic_key"]) and
            isinstance(record.get("topic"), str) and 20 <= len(record["topic"]) <= 200,
            "Topic and unique topic key required")
    for peer in (root / "picturefix/campaigns").glob("PF-*.json"):
        if peer != file:
            require(peer.stat().st_size <= 40_000, "Peer campaign oversized")
            previous = json.loads(peer.read_text(encoding="utf-8"))
            require(isinstance(previous, dict) and
                    previous.get("topic_key") != record["topic_key"],
                    "Topic key already used by another PictureFix campaign")
    sources = record["sources"]
    require(isinstance(sources, list) and 1 <= len(sources) <= 8 and
            all(isinstance(x, dict) and set(x) == {"title", "url", "accessed_at"} and
                isinstance(x["title"], str) and 10 <= len(x["title"]) <= 200 and
                isinstance(x["url"], str) and x["url"].startswith("https://") and
                15 <= len(x["url"]) <= 400 and
                isinstance(x["accessed_at"], str) and
                re.fullmatch(r"20[0-9]{2}-[0-9]{2}-[0-9]{2}", x["accessed_at"])
                for x in sources), "Traceable research sources required")
    qa_path = f"picturefix/quality/{campaign_id}.json"
    require(record["creative_qa"] == qa_path, "Campaign QA path mismatch")
    qa_file = root / qa_path
    require(qa_file.is_file() and qa_file.stat().st_size < 30_000, "Missing creative QA")
    qa = json.loads(qa_file.read_text(encoding="utf-8"))
    require(isinstance(qa, dict) and qa.get("campaign_id") == campaign_id and
            qa.get("real_picturefix_logo_blob_sha1") == LOGO_BLOB and
            qa.get("historical_scene_pops_out") is True and
            qa.get("period_accurate_faces_and_clothing") is True and
            qa.get("ai_ad_illustration_not_a_restoration") is True,
            "PictureFix concept/style/provenance QA missing")

    posts = record["posts"]
    require(isinstance(posts, dict) and set(posts) == set(TARGETS),
            "Exactly Facebook, Instagram and Pinterest required")
    clock = now or datetime.now(timezone.utc)
    clock = clock.astimezone(timezone.utc)
    seen_dates = set()
    seen_paths = set()
    prepared = []
    for target in TARGETS:
        post = posts[target]
        required = {"text", "alt_text", "image_path", "image_sha256", "due_at_utc", "due_at_local"}
        if target == "pinterest":
            required |= {"pinterest_title", "pinterest_url"}
        require(isinstance(post, dict) and set(post) == required,
                f"Invalid post fields: {target}")
        text = post["text"]
        alt = post["alt_text"]
        require(isinstance(text, str) and 40 <= len(text) <= 2200 and
                "KI-generierte Werbeillustration" in text and
                "kein tatsächliches Restaurierungsergebnis" in text and
                isinstance(alt, str) and 25 <= len(alt) <= 1000 and
                "KI-generierte Werbeillustration" in alt and
                "kein Restaurierungsergebnis" in alt,
                f"KI advertising disclosure missing: {target}")
        due = timestamp(post["due_at_utc"])
        require(due > clock + timedelta(minutes=30) and
                due < clock + timedelta(days=90), "Date must be 30 min to 90 days ahead")
        local = timestamp(post["due_at_local"])
        parsed_local = datetime.fromisoformat(post["due_at_local"])
        require(local == due and parsed_local.utcoffset() ==
                due.astimezone(ZoneInfo("Europe/Berlin")).utcoffset(),
                "Berlin time zone/DST and UTC date mismatch")
        require(post["due_at_utc"] not in seen_dates, "Dates must be distinct")
        seen_dates.add(post["due_at_utc"])

        image_path = post["image_path"]
        expected_suffix = ("Facebook_Instagram_1080x1350.png" if target != "pinterest"
                           else "Pinterest_1000x1500.png")
        require(image_path == f"media/images/PictureFix_{campaign_id.replace('-', '')}_{expected_suffix}",
                "Image name/target/campaign mismatch")
        image_sha = post["image_sha256"]
        require(isinstance(image_sha, str) and bool(SHA_RE.fullmatch(image_sha)),
                "Image SHA-256 missing")
        image = root / image_path
        require(image.is_file() and image.stat().st_size < 10_000_000 and
                hashlib.sha256(image.read_bytes()).hexdigest() == image_sha,
                "Checked campaign PNG not present or altered")
        seen_paths.add(image_path)
        if target == "pinterest":
            require(isinstance(post["pinterest_title"], str) and
                    10 <= len(post["pinterest_title"]) <= 100 and
                    post["pinterest_url"] == "https://picturefix.de",
                    "Pinterest title/destination invalid")
        source = f"https://raw.githubusercontent.com/{bridge.REPOSITORY}/{commit}/{image_path}"
        asset_record = {
            "format_version": 3, "target": target, "text": text,
            "image_sha256": image_sha,
            "media": {"type": "images", "images": [{"url": source, "alt_text": alt}]},
            "due_at_utc": post["due_at_utc"],
            "pinterest_title": post.get("pinterest_title", ""),
            "pinterest_url": post.get("pinterest_url", ""),
        }
        prepared.append({"target": target, "record": asset_record,
                         "assets": bridge.parse_assets(json.dumps(asset_record).encode("utf-8")),
                         "receipt_key": f"picturefix/campaigns/{campaign_id}/{target}"})
    require(len(seen_paths) == 2 and
            posts["facebook"]["image_sha256"] == posts["instagram"]["image_sha256"],
            "Facebook/Instagram must share one artwork; Pinterest needs another")
    require(isinstance(qa.get("artwork_sha256"), dict) and
            qa["artwork_sha256"] == {
                "facebook_instagram": posts["facebook"]["image_sha256"],
                "pinterest": posts["pinterest"]["image_sha256"],
            }, "Artwork SHA must match independent QA")
    logo_path = root / "media/brand/PictureFixLogo_Web.png"
    require(logo_path.is_file(), "Missing pinned canonical PictureFix logo")
    verify_imprint(root / posts["facebook"]["image_path"],
                   "facebook_instagram", logo=logo_path)
    verify_imprint(root / posts["pinterest"]["image_path"],
                   "pinterest", logo=logo_path)
    return record, prepared


def check_post(post: object, expected: dict, channel: str, post_id: str) -> None:
    require(isinstance(post, dict) and post.get("id") == post_id and
            post.get("channelId") == channel and
            str(post.get("channelService", "")).lower() == expected["target"] and
            post.get("status") == "draft" and post.get("text") == expected["text"] and
            timestamp(post.get("dueAt")) == timestamp(expected["due_at_utc"]) and
            post.get("shareMode") == "customScheduled" and
            post.get("schedulingType") == "automatic" and
            isinstance(post.get("assets"), list) and len(post["assets"]) == 1 and
            post["assets"][0].get("type") == "image" and
            post["assets"][0].get("source") == expected["media"]["images"][0]["url"],
            "Independent Buffer GET did not confirm exact dated, image-bearing DRAFT")


def audit_live_picturefix(token: str, channels: dict[str, str], items: list[dict],
                          verified_ids: dict[str, str], *, query) -> None:
    """Fail closed on a live same-channel slot or duplicate before any mutation.

    Old GitHub campaign dates are not reservations. The actual Buffer account
    is queried in full, including drafts, to avoid recreating orphaned posts.
    Verified receipts are exempted only by their exact Buffer post ID; they are
    independently checked again in ``send_batch`` before any other send.
    """
    account = query(token, bridge.GET_PICTUREFIX_ORGANIZATIONS, {}).get("account")
    orgs = account.get("organizations") if isinstance(account, dict) else None
    require(isinstance(orgs, list) and len(orgs) == 1 and
            isinstance(orgs[0], dict) and orgs[0].get("name") == "PictureFix" and
            orgs[0].get("channelCount") == 3 and
            isinstance(orgs[0].get("id"), str) and bool(orgs[0]["id"]),
            "Live PictureFix organization audit unavailable")
    require(set(channels) == set(TARGETS) and len(set(channels.values())) == 3,
            "PictureFix channel audit mismatch")
    expected = {channels[item["target"]]: item for item in items}
    seen_ids: set[str] = set()
    cursor = None
    for _ in range(5):
        response = query(token, POSTS_QUERY, {
            "organizationId": orgs[0]["id"],
            "channelIds": list(channels.values()),
            "after": cursor,
        }).get("posts")
        require(isinstance(response, dict) and isinstance(response.get("edges"), list),
                "Live PictureFix Buffer posts page unavailable")
        for edge in response["edges"]:
            post = edge.get("node") if isinstance(edge, dict) else None
            require(isinstance(post, dict) and
                    isinstance(post.get("id"), str) and bool(POST_ID_RE.fullmatch(post["id"])) and
                    post["id"] not in seen_ids and post.get("channelId") in expected,
                    "Live PictureFix post data is incomplete or repeated")
            seen_ids.add(post["id"])
            item = expected[post["channelId"]]
            target = item["target"]
            if post["id"] == verified_ids.get(target):
                continue
            record = item["record"]
            if post.get("text") == record["text"]:
                raise CampaignBlocked(f"Existing PictureFix {target} text in Buffer; reconcile before creation")
            assets = post.get("assets")
            require(isinstance(assets, list), "Live PictureFix post assets unavailable")
            if any(isinstance(a, dict) and a.get("source") ==
                   record["media"]["images"][0]["url"] for a in assets):
                raise CampaignBlocked(f"Existing PictureFix {target} image in Buffer; reconcile before creation")
            if post.get("dueAt") is not None and timestamp(post["dueAt"]) == timestamp(record["due_at_utc"]):
                raise CampaignBlocked(f"Existing PictureFix {target} Buffer time is occupied")
        page = response.get("pageInfo")
        require(isinstance(page, dict) and isinstance(page.get("hasNextPage"), bool),
                "Live PictureFix Buffer pagination unavailable")
        if not page["hasNextPage"]:
            return
        cursor = page.get("endCursor")
        require(isinstance(cursor, str) and bool(cursor),
                "Live PictureFix Buffer pagination cursor missing")
    raise CampaignBlocked("PictureFix Buffer audit exceeds 500 posts; no mutation")


def send_batch(manifest_path: str, *, env: dict[str, str] | None = None,
               now: datetime | None = None, root: Path | None = None,
               query=None, get_receipt=None, put_receipt=None) -> list[str]:
    """Preflight the whole batch before ANY mutation; reserve each send first."""
    env = dict(os.environ if env is None else env)
    commit = authenticate_push(env)
    require(env.get("BUFFER_BRAND") == "picturefix" and
            bool(env.get("BUFFER_API_KEY")) and bool(env.get("GITHUB_TOKEN")),
            "Dedicated PictureFix/receipt credentials required")
    require("saveToDraft: true" in bridge.CREATE_DATED_DRAFT and
            "mode: customScheduled" in bridge.CREATE_DATED_DRAFT and
            "shareNow" not in bridge.CREATE_DATED_DRAFT,
            "Buffer mutation must never publish or enqueue")
    campaign, items = load_campaign(manifest_path, commit, now=now, root=root)
    token = bridge.normalize_picturefix_api_key(env["BUFFER_API_KEY"])
    github_token = env["GITHUB_TOKEN"]
    query = query or bridge.buffer_graphql
    get_receipt = get_receipt or bridge.fetch_receipt
    put_receipt = put_receipt or bridge.put_receipt
    channels = bridge.discover_picturefix_channels(token)
    require(isinstance(channels, dict) and all(channels.get(t) for t in TARGETS),
            "All three PictureFix channels must be unambiguous")
    board_id = bridge.discover_picturefix_board(token, channels["pinterest"])
    require(bool(board_id), "Pinterest board required")

    # Authenticate ALL assets and ALL receipts BEFORE any createPost.
    for item in items:
        bridge.verify_media_access(item["assets"])
        bridge.verify_picturefix_image_bytes(item["record"], item["assets"])
    states = {}
    for item in items:
        receipt = bridge.receipt_path(item["receipt_key"])
        existing = get_receipt(github_token, receipt)
        if existing is not None:
            # A previously verified send can be reused, never created again.
            # The bridge returns GitHub's content object, base64 encoded.
            import base64
            try:
                prior = json.loads(base64.b64decode(existing["content"]).decode("utf-8"))
            except (KeyError, ValueError, TypeError) as exc:
                raise CampaignBlocked("Existing receipt cannot be trusted") from exc
            require(prior.get("state") == "verified_prescheduled_draft_not_queued_with_image" and
                    prior.get("campaign") == campaign["campaign_id"] and
                    prior.get("target") == item["target"] and
                    prior.get("manifest_path") == manifest_path and
                    prior.get("media_sha256") == item["record"]["image_sha256"] and
                    bool(POST_ID_RE.fullmatch(str(prior.get("buffer_post_id", "")))),
                    "Pending/mismatched receipt: manual reconciliation needed; no retry")
            states[item["target"]] = {"receipt": receipt, "prior": prior}
        else:
            states[item["target"]] = {"receipt": receipt}

    audit_live_picturefix(token, channels, items, {
        target: state["prior"]["buffer_post_id"]
        for target, state in states.items() if "prior" in state
    }, query=query)

    result_ids = []
    for item in items:
        target, expected = item["target"], item["record"]
        channel_id = channels[target]
        receipt = states[target]["receipt"]
        prior = states[target].get("prior")
        if prior:
            post_id = prior["buffer_post_id"]
            independent = query(token, READ, {"id": post_id}).get("post")
            check_post(independent, expected, channel_id, post_id)
            result_ids.append(post_id)
            print(f"PICTUREFIX_ALREADY_VERIFIED {campaign['campaign_id']} {target} {post_id}", flush=True)
            continue

        reserved = {
            "state": "pending_manual_reconciliation_on_failure",
            "campaign": campaign["campaign_id"], "target": target,
            "manifest_path": manifest_path,
            "media_sha256": expected["image_sha256"],
            "scheduled_utc": expected["due_at_utc"],
            "channel_id": channel_id,
            "github_run_id": env.get("GITHUB_RUN_ID", ""),
            "media_commit": commit,
        }
        receipt_sha = put_receipt(github_token, receipt, reserved,
                                  f"picturefix {campaign['campaign_id']} reserve {target}")
        variables = {
            "text": expected["text"], "channelId": channel_id,
            "assets": item["assets"], "dueAt": expected["due_at_utc"],
            "metadata": bridge.platform_metadata(
                target, pinterest_board_id=board_id,
                pinterest_title=expected["pinterest_title"],
                pinterest_url=expected["pinterest_url"]),
        }
        returned = query(token, bridge.CREATE_DATED_DRAFT, variables)
        action = returned.get("createPost") if isinstance(returned, dict) else None
        post = action.get("post") if isinstance(action, dict) else None
        require(isinstance(post, dict) and bool(POST_ID_RE.fullmatch(str(post.get("id", "")))),
                "Unclear createPost; reservation stays pending, NEVER retry blindly")
        post_id = post["id"]
        reserved.update({"state": "created_requires_independent_check", "buffer_post_id": post_id})
        receipt_sha = put_receipt(github_token, receipt, reserved,
                                  f"picturefix {campaign['campaign_id']} captured {target}", sha=receipt_sha)
        require(post.get("channelId") == channel_id and post.get("status") == "draft" and
                timestamp(post.get("dueAt")) == timestamp(expected["due_at_utc"]),
                "Buffer creation response is not a dated draft")
        independently_read = query(token, READ, {"id": post_id}).get("post")
        check_post(independently_read, expected, channel_id, post_id)
        reserved.update({
            "state": "verified_prescheduled_draft_not_queued_with_image",
            "buffer_status": "draft", "buffer_post_id": post_id,
            "buffer_due_at": expected["due_at_utc"],
            "buffer_asset_url": expected["media"]["images"][0]["url"],
            "verified_at_utc": datetime.now(timezone.utc).isoformat(),
        })
        put_receipt(github_token, receipt, reserved,
                    f"picturefix {campaign['campaign_id']} verified {target}", sha=receipt_sha)
        result_ids.append(post_id)
        print(f"PICTUREFIX_VERIFIED_DRAFT {campaign['campaign_id']} {target} "
              f"{post_id} {expected['due_at_utc']} image=verified draft_only", flush=True)
    require(len(result_ids) == 3 and len(set(result_ids)) == 3,
            "Exactly three independent Buffer draft IDs required")
    print(f"PICTUREFIX_CAMPAIGN_PASS {campaign['campaign_id']} three verified dated drafts", flush=True)
    return result_ids


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--send", action="store_true")
    args = parser.parse_args()
    if not args.send:
        parser.error("Explicit --send required; no implicit Buffer mutation")
    try:
        send_batch(args.manifest)
    except (CampaignBlocked, RuntimeError, ValueError, OSError, json.JSONDecodeError) as exc:
        print("PICTUREFIX_CAMPAIGN_BLOCKED", type(exc).__name__, str(exc)[:200], file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
