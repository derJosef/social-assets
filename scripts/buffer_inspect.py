#!/usr/bin/env python3
"""Read-only Buffer post status diagnosis. No scheduling or publishing mutation."""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

from buffer_draft import buffer_graphql

ROOT = Path(__file__).resolve().parents[1]
QUERY = """
query InspectPost($id: PostId!) {
  post(input: { id: $id }) { id channelId status dueAt }
}
"""


def main() -> int:
    if len(sys.argv) != 2 or not re.fullmatch(r"diagnostics/[a-zA-Z0-9_.-]+\.json", sys.argv[1]):
        raise ValueError("Nur eine JSON-Datei unmittelbar unter diagnostics/ zulässig.")
    input_path = (ROOT / sys.argv[1]).resolve(strict=True)
    if not input_path.is_relative_to((ROOT / "diagnostics").resolve()):
        raise ValueError("Ungültiger Dateipfad.")
    data = json.loads(input_path.read_text(encoding="utf-8"))
    ids = data.get("post_ids") if isinstance(data, dict) else None
    if not isinstance(ids, list) or not 1 <= len(ids) <= 10 or any(not isinstance(i, str) or not re.fullmatch(r"[a-f0-9]{24}", i) for i in ids):
        raise ValueError("Nur 1 bis 10 vorhandene Buffer-Post-IDs zulässig.")
    token = os.environ.get("BUFFER_API_KEY", "")
    if not token:
        raise RuntimeError("Buffer-API-Zugang fehlt.")
    for post_id in ids:
        post = buffer_graphql(token, QUERY, {"id": post_id}).get("post")
        if not isinstance(post, dict) or post.get("id") != post_id:
            print(f"{post_id}: UNKLAR (bitte Buffer prüfen)")
        else:
            print(f"{post_id}: status={post.get('status')}, dueAt={post.get('dueAt')}, channelId={post.get('channelId')}")
    print("Nur gelesen; keine Änderungen an Beiträgen vorgenommen.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (RuntimeError, ValueError, OSError, json.JSONDecodeError) as exc:
        print(f"Diagnose fehlgeschlagen: {exc}", file=sys.stderr)
        sys.exit(1)
