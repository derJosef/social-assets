#!/usr/bin/env python3
"""One-time, read-only full download of all six existing PAF-TV social MP4s.

No Buffer calls, no server writes. The separate protected draft sender only
runs after this completes successfully. Exact released sizes are pinned.
"""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from buffer_draft import PAF_VIDEO_BASE, PAF_VIDEO_SIZES, verify_media_access

def main():
    for name in sorted(PAF_VIDEO_SIZES):
        verify_media_access([{"video":{"url": PAF_VIDEO_BASE+name}}])
    print("PAF_TV_SIX_COMPLETE_PUBLIC_MP4_DOWNLOADS_VERIFIED", flush=True)

if __name__=="__main__":
    main()
