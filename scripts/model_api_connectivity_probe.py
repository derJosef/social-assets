#!/usr/bin/env python3
"""Read-only, small GitHub Models connectivity probe. No Buffer and no user data.

No token, model text, headers containing credentials, or project prompts
are printed or persisted. Makes at most three HTTP requests.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

CATALOG = "https://models.github.ai/catalog/models"
INFERENCE = "https://models.github.ai/inference/chat/completions"
LIMIT = 8192


def check_response(response, label):
    raw = response.read(LIMIT + 1)
    ctype = response.headers.get("Content-Type", "").split(";")[0].strip().lower()
    info = {
        "probe": label,
        "http_status": response.status,
        "content_type": ctype,
        "bytes_read": len(raw),
        "truncated": len(raw) > LIMIT,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "request_id_present": bool(response.headers.get("x-github-request-id")),
    }
    if len(raw) <= LIMIT:
        try:
            decoded = json.loads(raw)
            info["json_valid"] = True
            if isinstance(decoded, dict):
                info["json_object_keys"] = sorted(decoded.keys())[:16]
                if isinstance(decoded.get("choices"), list):
                    info["choices_count"] = len(decoded["choices"])
                    if decoded["choices"]:
                        msg = decoded["choices"][0].get("message", {})
                        info["assistant_message_is_string"] = isinstance(msg.get("content"), str)
                if isinstance(decoded.get("message"), str):
                    info["error_message_type"] = "provider_message_present"
            elif isinstance(decoded, list):
                info["json_type"] = "array"
                info["array_length"] = len(decoded)
            else:
                info["json_type"] = type(decoded).__name__
        except (ValueError, UnicodeDecodeError):
            info["json_valid"] = False
            if len(raw) <= 16:
                info["short_body_ascii"] = raw.decode("ascii", errors="replace")
    return info


def request(label, method, url, token, payload=None):
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {
        "Authorization": "Bearer " + token,
        "User-Agent": "social-assets-model-readonly-probe",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2026-03-10",
    }
    if data is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=35) as response:
            return check_response(response, label)
    except urllib.error.HTTPError as exc:
        with exc:
            return check_response(exc, label)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return {"probe": label, "transport_error_type": type(exc).__name__}


def main():
    token = os.environ.get("GH_MODELS_PROBE_TOKEN", "")
    if not token:
        raise SystemExit("No GitHub Actions model token")
    if os.environ.get("GITHUB_REF") != "refs/heads/social-model-connectivity-20261010":
        raise SystemExit("Must run only on isolated branch")
    results = [
        request("authenticated_catalog", "GET", CATALOG, token),
        request("minimal_chat_json", "POST", INFERENCE, token, {
            "model": "openai/gpt-4o-mini",
            "messages": [{"role": "user", "content": "Return exactly OK."}],
            "temperature": 0,
            "max_tokens": 16,
            "stream": False,
        }),
        request("structured_chat_json", "POST", INFERENCE, token, {
            "model": "openai/gpt-4o-mini",
            "messages": [
                {"role": "system", "content": "Respond with a JSON object."},
                {"role": "user", "content": "Return JSON with one field status set to ok."}
            ],
            "temperature": 0,
            "max_tokens": 40,
            "response_format": {"type": "json_object"},
            "stream": False,
        }),
    ]
    report = {
        "diagnostic": "github_models_read_only_v1",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "github_ref": os.environ.get("GITHUB_REF"),
        "model": "openai/gpt-4o-mini",
        "buffer_calls": 0,
        "repository_writes": 0,
        "requests": results,
    }
    dest = Path("/tmp/github-model-connection-diagnostic.json")
    dest.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    for result in results:
        print(json.dumps(result, sort_keys=True))
    success = results[1].get("json_valid") is True and results[1].get("choices_count", 0) > 0
    print("MODEL_PROBE_RESULT:", "RESPONSE_OK" if success else "STILL_BLOCKED")
    # A blocked diagnosis is a successful diagnostic execution. It is not a
    # confirmation that the autonomous model pipeline works.
    return 0


if __name__ == "__main__":
    sys.exit(main())
