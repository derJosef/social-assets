#!/usr/bin/env python3
"""Offline regression for exact PAF-TV video URLs and complete MP4 validation."""
import importlib.util
import io
import json
from pathlib import Path
import sys
import unittest
from unittest import mock

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
spec=importlib.util.spec_from_file_location("paf_tv_buffer_draft",(ROOT/"scripts/buffer_draft.py"))
app=importlib.util.module_from_spec(spec)
spec.loader.exec_module(app)

class VideoTests(unittest.TestCase):
    URL="https://pauderer.de/assets/videos/social/PAF-TV_01_ki-agenten_4x5.mp4"
    def decode(self,url=URL):
        return app.parse_assets(json.dumps({
            "format_version":2,"target":"linkedin","text":"Nur ein Draft",
            "media":{"type":"video","url":url}
        }).encode("utf-8"))

    def test_video_accepted_exactly(self):
        self.assertEqual(self.decode(),[{"video":{"url":self.URL}}])
        self.assertEqual(len(app.PAF_VIDEO_FILENAMES),6)
        self.assertEqual(len(app.PAF_VIDEO_SIZES),6)

    def test_video_bad_hosts_and_paths_rejected(self):
        for url in [
            "http://pauderer.de/assets/videos/social/PAF-TV_01_ki-agenten_4x5.mp4",
            "https://www.pauderer.de/assets/videos/social/PAF-TV_01_ki-agenten_4x5.mp4",
            "https://pauderer.de.evil.net/assets/videos/social/PAF-TV_01_ki-agenten_4x5.mp4",
            "https://pauderer.de/assets/videos/social/PAF-TV_01_ki-agenten_4x5.mp4?key=secret",
            "https://pauderer.de/assets/videos/social/../secret.mp4",
            "https://pauderer.de/assets/videos/social/PAF-TV_01_datenschutz_4x5.mp4",
            "https://pauderer.de/assets/videos/social/PAF-TV_04_ki-agenten_4x5.mp4",
            "https://pauderer.de/assets/videos/social/PAF-TV_01_ki-agenten_4x5.mp4#fragment",
        ]:
            with self.subTest(url=url),self.assertRaises(ValueError):
                self.decode(url)

    def test_video_fields_are_strict(self):
        data={"format_version":2,"target":"linkedin","text":"Test",
              "media":{"type":"video","url":self.URL,"link":"foo"}}
        with self.assertRaises(ValueError):
            app.parse_assets(json.dumps(data).encode())

    def test_instagram_video_is_a_reel(self):
        self.assertEqual(
            app.platform_metadata("instagram", video=True),
            {"instagram":{"type":"reel","shouldShareToFeed":True}})
        self.assertEqual(
            app.platform_metadata("instagram"),
            {"instagram":{"type":"post","shouldShareToFeed":True}})
        self.assertIn("saveToDraft: true",app.CREATE_DRAFT)

    def test_streamed_get_requires_exact_bytes_and_ftyp(self):
        raw=b"\x00\x00\x00\x18ftypisom"+b"x"*50
        class Response:
            def __init__(self,method,truncated=False):
                self.status=200
                self.headers={"Content-Type":"video/mp4","Content-Length":str(len(raw))}
                self.data=io.BytesIO(raw[:-1] if truncated else raw)
            def __enter__(self):return self
            def __exit__(self,*args):return False
            def geturl(self):return VideoTests.URL
            def read(self,size):return self.data.read(size)
        with mock.patch.dict(app.PAF_VIDEO_SIZES,{"PAF-TV_01_ki-agenten_4x5.mp4":len(raw)}):
            with mock.patch.object(app.urllib.request,"urlopen",
                side_effect=lambda request,**kwargs: Response(request.get_method())) as calls:
                app.verify_media_access(self.decode())
                self.assertEqual(calls.call_count,2)
            with mock.patch.object(app.urllib.request,"urlopen",
                side_effect=lambda request,**kwargs: Response(request.get_method(),truncated=request.get_method()=="GET")):
                with self.assertRaisesRegex(RuntimeError,"vollständigen Herunterladen"):
                    app.verify_media_access(self.decode())

    def test_video_not_in_auto_image_pipeline(self):
        self.assertIn('verify_auto_image_bytes',app.send_draft.__code__.co_names)

if __name__=="__main__":
    unittest.main()
