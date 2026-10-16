"""Fail-closed, non-sensitive summaries of Buffer GraphQL mutation errors.

Buffer may return freeform error messages containing URLs, account names,
user text or other private data. NEVER echo or persist those messages.
Only closed-vocabulary diagnostic identifiers may reach public GitHub logs.

Classification is advisory; it does not prove root cause, change retry
policy, authorize any Buffer operation, or clear a GitHub pending receipt.
"""
from __future__ import annotations

import re

KNOWN_TYPES = frozenset({
    "InvalidInputError", "LimitReachedError", "MutationError", "VoidMutationError",
})
MAX_INSPECTED_MESSAGE = 4096

# A limited, deliberately conservative allowlist: recognize known *topics*,
# not an arbitrary copy of Buffer's text or any embedded identifiers.
_CATEGORIES = (
    ("media_dimensions", re.compile(
        r"(?:image|media|photo|picture).{0,90}(?:dimensions?|width|height)"
        r"|(?:dimensions?|width|height).{0,90}(?:image|media|photo|picture)"
        r"|(?:could not|cannot|unable to|failed to).{0,60}determine.{0,40}dimensions?",
        re.IGNORECASE)),
    ("media_access", re.compile(
        r"(?:image|media|asset|photo|picture).{0,90}(?:download|fetch|access|retriev|reachable|url|host|load)"
        r"|(?:download|fetch|access|retriev|reachable|load).{0,90}(?:image|media|asset|photo|picture)",
        re.IGNORECASE)),
    ("media_format", re.compile(
        r"(?:unsupported|invalid|unrecognized).{0,50}(?:image|media|file|format|mime|content.type)"
        r"|(?:image|media|file).{0,50}(?:unsupported|format|mime.type)",
        re.IGNORECASE)),
    ("posting_time", re.compile(
        r"\bdueat\b|\bdue date\b|\bschedul(?:e|ing|ed)\b"
        r"|\bcustomscheduled\b|\bdate.?time\b",
        re.IGNORECASE)),
    ("post_text", re.compile(
        r"\btext (?:is )?required\b|\btext.{0,60}(?:empty|too long|length|characters?|limit)"
        r"|\bcharacter limit\b",
        re.IGNORECASE)),
    ("channel", re.compile(
        r"\bchannel(?:id)?\b|\bconnect(?:ion|ed|ing)?\b.{0,50}\b(?:account|profile)\b",
        re.IGNORECASE)),
    ("post_metadata", re.compile(
        r"\bmetadata\b|\blinkattachment\b|\bshouldsharetofeed\b",
        re.IGNORECASE)),
    ("permissions", re.compile(
        r"\b(?:forbidden|unauthori[sz]ed|permissions?|not allowed)\b",
        re.IGNORECASE)),
    ("limits", re.compile(
        r"\b(?:quota|rate limit|limit reached|subscription limit|plan limit)\b",
        re.IGNORECASE)),
    ("media_other", re.compile(
        r"\b(?:assets?|images?|media|photos?)\b", re.IGNORECASE)),
)


def safe_mutation_diagnosis(result: object) -> tuple[str, str]:
    """Return only static error class and topic. Never return untrusted text."""
    if not isinstance(result, dict):
        return ("UnexpectedResponse", "unknown")
    raw_type = result.get("__typename")
    typ = raw_type if isinstance(raw_type, str) and raw_type in KNOWN_TYPES else "OtherMutationError"
    raw_message = result.get("message")
    if not isinstance(raw_message, str) or len(raw_message) > MAX_INSPECTED_MESSAGE:
        return (typ, "unknown")
    for category, pattern in _CATEGORIES:
        if pattern.search(raw_message):
            return (typ, category)
    return (typ, "unknown")
