#!/usr/bin/env python3
"""Render the immutable GitHub receipt as a ChatGPT-readable weekly draft report.

Never creates a Buffer post. The confirmed Buffer snapshot comes exclusively
from orchestrator_verify_buffer.py, not from local plans. On partial failure
show BLOCKED and NEVER present unverified posts as ready for approval.
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path

TARGETS = ("linkedin", "facebook", "instagram")
TITLES = {"linkedin": "LinkedIn", "facebook": "Facebook", "instagram": "Instagram"}
BUFFER_DASHBOARD = "https://publish.buffer.com"
ID_RE = re.compile(r"[a-f0-9]{24}\Z")
CAMPAIGN_RE = re.compile(r"20\d{2}-\d{2}-\d{2}-[a-z0-9]+(?:-[a-z0-9]+)*\Z")
IMAGE_RE = re.compile(
    r"https://raw\.githubusercontent\.com/derJosef/social-assets/"
    r"[0-9a-f]{40}/media/images/20[0-9]{2}-[0-9]{2}-[0-9]{2}-"
    r"[a-z0-9-]+-branded\.png\Z"
)


class InvalidReviewReceipt(ValueError):
    pass


def validate(report: dict) -> tuple[str, dict]:
    if not isinstance(report, dict):
        raise InvalidReviewReceipt("Invalid orchestration receipt")
    campaign = report.get("campaign")
    if not isinstance(campaign, str) or not CAMPAIGN_RE.fullmatch(campaign):
        raise InvalidReviewReceipt("Invalid campaign identity")
    verification = report.get("buffer_verification")
    if report.get("job_status") != "success":
        raise InvalidReviewReceipt("GitHub orchestrator did not complete successfully")
    if (report.get("state") != "buffer_drafts_verified"
            or not isinstance(verification, dict)
            or verification.get("status") != "PASS"):
        raise InvalidReviewReceipt("Campaign has no complete Buffer confirmation")
    posts = verification.get("posts")
    if not isinstance(posts, dict) or set(posts) != set(TARGETS):
        raise InvalidReviewReceipt("All three independently verified channels required")
    ids, channels = set(), set()
    for target in TARGETS:
        post = posts[target]
        if not isinstance(post, dict) or post.get("service") != target:
            raise InvalidReviewReceipt(f"Wrong platform in {target} review")
        pid, channel = post.get("post_id"), post.get("channel_id")
        if not isinstance(pid, str) or not ID_RE.fullmatch(pid):
            raise InvalidReviewReceipt(f"Missing trustworthy Buffer post ID: {target}")
        if not isinstance(channel, str) or not channel or len(channel) > 200:
            raise InvalidReviewReceipt(f"Missing trustworthy channel ID: {target}")
        if pid in ids or channel in channels:
            raise InvalidReviewReceipt("Duplicate Buffer posts or channels")
        ids.add(pid)
        channels.add(channel)
        if (post.get("status") != "draft" or post.get("published") is not False
                or post.get("editorial_approval") != "pending_after_draft"):
            raise InvalidReviewReceipt("Not an unpublished draft awaiting human approval")
        if (post.get("buffer_link_kind") != "official_dashboard_not_direct_post"
                or post.get("buffer_dashboard_url") != BUFFER_DASHBOARD
                or post.get("buffer_direct_post_url") is not None):
            raise InvalidReviewReceipt("Unverified Buffer deep link may not be rendered")
        due, local = post.get("dueAt"), post.get("scheduled_local")
        if not isinstance(due, str) or not isinstance(local, str):
            raise InvalidReviewReceipt("Missing concrete publication proposal")
        try:
            utc = datetime.fromisoformat(due.replace("Z", "+00:00"))
            berlin = datetime.fromisoformat(local)
        except ValueError as exc:
            raise InvalidReviewReceipt("Invalid posting date") from exc
        if (due[-1:] != "Z" or utc.tzinfo is None or berlin.tzinfo is None
                or berlin.astimezone(utc.tzinfo) != utc):
            raise InvalidReviewReceipt("Berlin and UTC times disagree")
        if (not isinstance(post.get("text"), str) or not post["text"].strip()
                or post.get("image_attached_in_buffer") is not True):
            raise InvalidReviewReceipt("Missing actual Buffer copy or image")
        img = post.get("review_image_url")
        if not isinstance(img, str) or not IMAGE_RE.fullmatch(img) or campaign not in img:
            raise InvalidReviewReceipt("Review image is not an immutable campaign PNG")
        asset = post.get("buffer_asset_url")
        if not isinstance(asset, str) or not asset.startswith("https://"):
            raise InvalidReviewReceipt("Buffer image asset unverified")
    return campaign, posts


def text_fence(value: str) -> str:
    """Literal post text, unable to inject headings or Markdown links."""
    longest = max((len(m.group()) for m in re.finditer(r"~+", value)), default=0)
    fence = "~" * max(4, longest + 1)
    return fence + "text\n" + value + "\n" + fence


def render(report: dict) -> str:
    if not isinstance(report, dict):
        report = {}
    campaign = report.get("campaign", "unknown")
    title = f"# AI Agent Builder – Wochenkampagne {campaign}\n\n"
    try:
        _, posts = validate(report)
    except InvalidReviewReceipt as exc:
        status = str(report.get("job_status", "unknown"))
        return (title + "**Status: BLOCKED – keine vollständige, bestätigte Dreiergruppe.**\n\n"
                + "Die ChatGPT-Wochenkampagne darf diese Beiträge nicht als fertige "
                + "Buffer-Drafts zur Freigabe anbieten.\n\n"
                + f"Technischer Grund: {str(exc)}. Jobstatus: {status}.\n\n"
                + "Bereits möglicherweise angelegte Einzelposts **nicht** automatisch erneut "
                + "übertragen; vorhandene Receipt-IDs manuell abgleichen.\n")
    out = [title, "**Status: drei geprüfte, vordatierte Buffer-Drafts. Keine Veröffentlichung.**\n"]
    checked_at = report.get("buffer_verification", {}).get("checked_at", "unknown")
    out.append(f"Unabhängiger Buffer-Rücklesezeitpunkt (UTC): {checked_at}\n")
    out.append("Dies ist ein **Snapshot**. Spätere Bearbeitungen direkt in Buffer sind maßgeblich "
               "und dürfen bei Freigabe nicht durch diese Fassung überschrieben werden.\n")
    out.append("Der Buffer-Link führt zum offiziellen Dashboard, **nicht** direkt in den "
               "einzelnen Post. Buffer dokumentiert derzeit keinen verlässlichen "
               "API-Deep-Link zu unveröffentlichten Entwürfen.\n")
    for target in TARGETS:
        item = posts[target]
        out.extend([
            f"## {TITLES[target]}\n",
            f"**Vorgesehener Zeitpunkt:** {item['scheduled_local']} (Europe/Berlin) / {item['dueAt']} (UTC)  ",
            "**Status:** draft, nicht in der Veröffentlichungswarteschlange  ",
            f"**Buffer-Post-ID:** {item['post_id']}  ",
            f"**Kanal-ID:** {item['channel_id']}\n",
            f"[Buffer öffnen – Kanal {TITLES[target]} → Drafts]({BUFFER_DASHBOARD}) "
            "(Dashboard-Einstieg, kein individueller Post-Link)\n",
            f"![Vorschau des geprüften Markenbildes]({item['review_image_url']})\n",
            "**Tatsächlich von Buffer zurückgelesener Beitragstext:**\n",
            text_fence(item["text"]) + "\n",
        ])
    out.append("**Deine Entscheidung:** „freigegeben“, direkt in Buffer ändern, oder "
               "hier Änderungen beauftragen. „Freigegeben“ allein ist **noch keine** "
               "technische Live-Queue-Aktion: Vor einem späteren Scheduling müssen "
               "die drei bestehenden Post-IDs und die dann aktuellen Texte/Bilder/"
               "Termine erneut direkt in Buffer geprüft werden. Keine Duplikate.\n")
    return "\n".join(out)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", required=True)
    parser.add_argument("--markdown", required=True)
    args = parser.parse_args()
    try:
        value = json.loads(Path(args.report).read_text(encoding="utf-8"))
        markdown = render(value)
        path = Path(args.markdown)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(markdown, encoding="utf-8")
        print("REVIEW_REPORT", "PASS" if "**Status: drei geprüfte" in markdown
              else "BLOCKED", str(path))
        return 0
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        print("REVIEW_REPORT_BLOCKED", type(exc).__name__, str(exc)[:220])
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
