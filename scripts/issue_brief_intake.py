#!/usr/bin/env python3
"""Accept owner-authored, schema-bound weekly briefs from GitHub Issue events.

Trusted workflow code always executes from protected main. The public issue
is DATA only: never run its content as a command or workflow definition.
No GitHub or Buffer API writes; creates at most ONE ephemeral local brief.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = "derJosef/social-assets"
OWNER = "derJosef"
PREFIX = "AIAGENT_BRIEF:"
CAMPAIGN_RE = re.compile(r"20\d{2}-\d{2}-\d{2}-[a-z0-9]+(?:-[a-z0-9]+)*\Z")
MAX_BODY_BYTES = 65_536
EXPECTED_KEYS = {
    "format_version", "brand", "campaign_id", "execution_mode",
    "topic", "sources", "posting_sources", "image_review", "prepared_content",
}


class IssueBriefBlocked(ValueError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise IssueBriefBlocked(message)


def extract(event: dict) -> tuple[str, dict, int]:
    require(isinstance(event, dict), "Issue event is not JSON object")
    repo = event.get("repository")
    issue = event.get("issue")
    require(isinstance(repo, dict) and repo.get("full_name") == REPOSITORY,
            "Unexpected public repository")
    require(event.get("action") == "opened" and isinstance(issue, dict),
            "Only newly opened campaign issues permitted")
    creator = issue.get("user")
    require(isinstance(creator, dict) and creator.get("login") == OWNER
            and issue.get("author_association") == "OWNER",
            "Only confirmed repository owner may submit an automatic campaign")
    number = issue.get("number")
    require(type(number) is int and number > 0, "Invalid GitHub issue identity")
    title = issue.get("title")
    require(isinstance(title, str) and title.startswith(PREFIX),
            "Not an AI Agent Builder campaign issue")
    campaign = title[len(PREFIX):]
    require(CAMPAIGN_RE.fullmatch(campaign) is not None,
            "Campaign slug must be YYYY-MM-DD-topic")
    body = issue.get("body")
    require(isinstance(body, str) and 0 < len(body.encode("utf-8")) <= MAX_BODY_BYTES,
            "Campaign issue content missing or too large")
    try:
        obj = json.loads(body)
    except (ValueError, UnicodeError):
        raise IssueBriefBlocked("Issue body must be one JSON campaign brief, not Markdown") from None
    require(isinstance(obj, dict) and set(obj) == EXPECTED_KEYS | {"chatgpt_image"},
            "ChatGPT image transfer required; no paid image-API fallback")
    # Reuse the proven ChatGPT -> Adobe file transfer -> pinned GitHub import.
    # This validates the public owner issue BEFORE any network/Image/Buffer call.
    from chatgpt_image_import import inspect_brief, ChatImageBlocked
    try:
        inspect_brief(obj)
    except ChatImageBlocked as exc:
        raise IssueBriefBlocked(str(exc)) from None
    require(obj.get("format_version") == 1
            and obj.get("brand") == "ai-agent-builder"
            and obj.get("campaign_id") == campaign
            and obj.get("execution_mode") == "drafts"
            and obj.get("image_review") == f"visual-reviews/{campaign}.json",
            "Brief identity, brand, draft mode or review binding mismatch")
    prepared = obj.get("prepared_content")
    require(isinstance(prepared, dict) and set(prepared) ==
            {"posts", "visual", "six_hats", "risks"},
            "Full editorial package required; three posts, visual:null, six hats and risks")
    # Brand image comes independently from the verified topic and canonical
    # Original-Logo compositor. Never allow obsolete generated three-card art.
    require(prepared["visual"] is None, "Prepared visual must be null; no generated cards")
    posts = prepared["posts"]
    require(isinstance(posts, dict)
            and set(posts) == {"linkedin", "facebook", "instagram"}
            and all(isinstance(post, str) and
                    250 <= len(post) <= (2200 if target == "instagram" else 3000)
                    for target, post in posts.items()),
            "All three channel-length posts required for automatic draft-first creation")
    hats = prepared["six_hats"]
    require(isinstance(hats, dict) and set(hats) ==
            {"white", "red", "black", "yellow", "green", "blue"}
            and all(isinstance(v, str) and len(v) > 24 for v in hats.values()),
            "Six full thinking hats required")
    require(isinstance(prepared["risks"], list),
            "Editorial risks must be documented in an array")
    require(isinstance(obj.get("topic"), str) and 30 <= len(obj["topic"]) <= 550,
            "Missing concrete campaign topic")
    require(isinstance(obj.get("sources"), list) and 2 <= len(obj["sources"]) <= 6
            and isinstance(obj.get("posting_sources"), list)
            and len(obj["posting_sources"]) >= 6,
            "Independent article and posting-time sources required")
    return campaign, obj, number


def stage(event_path: Path, root: Path = ROOT) -> dict:
    root = root.resolve()
    try:
        data = json.loads(event_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise IssueBriefBlocked("Cannot read validated GitHub event JSON") from exc
    campaign, brief, number = extract(data)
    path = root / f"orchestration/briefs/{campaign}.json"
    require(path.parent.is_dir() and path.parent.is_relative_to(root),
            "Canonical brief directory not available")
    require(not path.exists(), "Campaign brief already exists. No overwrite or retry")
    content = json.dumps(brief, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    with path.open("x", encoding="utf-8") as stream:
        stream.write(content)
    return {"campaign": campaign, "issue_number": number,
            "brief": path.relative_to(root).as_posix(),
            "ephemeral_created": True,
            "main_changed": False, "buffer_posts_created": 0}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--event", required=True)
    parser.add_argument("--root", default=str(ROOT))
    args = parser.parse_args()
    try:
        result = stage(Path(args.event), Path(args.root))
        print("OWNER_ISSUE_BRIEF_ACCEPTED", json.dumps(result, ensure_ascii=False))
        return 0
    except IssueBriefBlocked as exc:
        print("OWNER_ISSUE_BRIEF_BLOCKED:", str(exc)[:180], file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
