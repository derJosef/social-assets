"""Safely report Buffer API quota headers (no API calls or secret logging).

Reference: https://developers.buffer.com/guides/api-limits.html
The three policies are identified by their documented window lengths, not plan names.
"""

from __future__ import annotations

import re


WINDOWS = {900: "15m", 86400: "24h", 2592000: "30d"}
_PARAM = re.compile(r"(?:^|;)\s*([a-z]+)\s*=\s*(\d+)\b")


def _entries(headers, name: str) -> list[str]:
    """Handle repeated HTTP fields and intermediary-combined field values."""
    if headers is None:
        return []
    if hasattr(headers, "get_all"):
        values = headers.get_all(name, [])
    else:
        value = headers.get(name)
        values = [value] if value is not None else []
    if isinstance(values, str):
        values = [values]
    return [entry.strip()
            for value in values for entry in re.split(r',\s*(?=")', str(value))
            if entry.strip()]


def _parts(entry: str) -> tuple[str | None, dict[str, int]]:
    name = re.match(r'^\s*"([^"]+)"', entry)
    fields = {key: int(value) for key, value in _PARAM.findall(entry)}
    return (name.group(1) if name else None), fields


def read_limits(headers) -> dict[str, dict[str, int]]:
    """Return only numeric quota data; never expose partition keys or raw headers."""
    policies = {}
    for raw in _entries(headers, "RateLimit-Policy"):
        name, fields = _parts(raw)
        if name and fields.get("w") in WINDOWS and fields.get("q", 0) > 0:
            policies[name] = fields
    result = {}
    for raw in _entries(headers, "RateLimit"):
        name, fields = _parts(raw)
        policy = policies.get(name)
        if policy is None or "r" not in fields or "t" not in fields:
            continue
        window = WINDOWS[policy["w"]]
        result[window] = {"remaining": fields["r"], "quota": policy["q"],
                          "reset_seconds": fields["t"]}
    return result


def report_limits(headers, *, output=print) -> dict[str, dict[str, int]]:
    """Log one secret-free summary per policy and warn at <=10% remaining."""
    limits = read_limits(headers)
    for window in ("15m", "24h", "30d"):
        item = limits.get(window)
        if item is None:
            continue
        low = item["remaining"] * 10 <= item["quota"]
        level = "WARN" if low else "OK"
        output(f"BUFFER_QUOTA {level} window={window} remaining={item['remaining']} "
               f"quota={item['quota']} reset_s={item['reset_seconds']}")
    return limits


def retry_after_seconds(headers) -> int | None:
    """Read Buffer's retry delay; never assume a missing/invalid header is zero."""
    if headers is None:
        return None
    raw = headers.get("Retry-After")
    if raw is None:
        return None
    value = str(raw).strip()
    if not value.isascii() or not value.isdecimal() or len(value) > 10:
        return None
    return int(value)
