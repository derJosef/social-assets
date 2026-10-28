"""Fail-closed, offline tests for Facebook + Instagram interview video drafts."""
from __future__ import annotations
import base64
import hashlib
import json
from pathlib import Path
import sys
import unittest
from unittest import mock

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import buffer_draft as draft
import paf_tv_two_draft_readback as readback

class SocialClipDrafts(unittest.TestCase):
    def test_exactly_two_distinct_drafts(self):
        self.assertEqual(len(readback.DRAFTS),2)
        self.assertEqual(len(set(readback.DRAFTS)),2)
        self.assertTrue(all(x.startswith("drafts/paf-tv-interview-clip01-")
                            for x in readback.DRAFTS))

    def test_draft_media_text_and_target(self):
        for filename,target in zip(readback.DRAFTS,("facebook","instagram")):
            p,text,raw=draft.read_draft(filename)
            rec=json.loads(raw)
            self.assertEqual(p,filename)
            self.assertEqual(rec["target"],target)
            self.assertEqual(rec["format_version"],2)
            self.assertIn("PAF-TV",text)
            self.assertIn("Rolf Berger",text)
            self.assertEqual(rec["media"],{
                "type":"video",
                "url":"https://pauderer.de/assets/videos/social/PAF-TV_01_ki-agenten_9x16.mp4"})
            self.assertEqual(draft.parse_assets(raw),[{"video":{"url":rec["media"]["url"]}}])
            self.assertLessEqual(len(text),2200 if target=="instagram" else 3000)

    def test_channel_specific_metadata(self):
        self.assertEqual(draft.platform_metadata("facebook",video=True),{
            "facebook":{"type":"post"}})
        self.assertEqual(draft.platform_metadata("instagram",video=True),{
            "instagram":{"type":"reel","shouldShareToFeed":True}})
        self.assertIn("saveToDraft: true",draft.CREATE_DRAFT)
        self.assertNotIn("saveToDraft: false",draft.CREATE_DRAFT)
        self.assertNotIn("createPost",readback.READ_POST)
        self.assertNotIn("editPost",readback.READ_POST)

    def test_receipt_decoding_fails_closed(self):
        with self.assertRaises(RuntimeError):
            readback.decode_receipt(None)
        with self.assertRaises(RuntimeError):
            readback.decode_receipt({"content":"bad"})
        self.assertEqual(
            readback.decode_receipt({"content":base64.b64encode(b'{"state":"draft_created"}').decode()}),
            {"state":"draft_created"})

    def test_readback_matches_current_text_and_channel(self):
        for path,target in zip(readback.DRAFTS,("facebook","instagram")):
            _,text,raw=draft.read_draft(path)
            receipt={
                "state":"draft_created","draft_file":path,"target":target,
                "draft_sha256":hashlib.sha256(raw).hexdigest(),
                "buffer_post_id":"test-fake-"+target}
            file={"content":base64.b64encode(json.dumps(receipt).encode()).decode()}
            post={"id":receipt["buffer_post_id"],"channelId":"channel-"+target,
                  "status":"draft","text":text}
            with (mock.patch.object(readback,"fetch_receipt",return_value=file),
                  mock.patch.object(readback,"resolve_channel",return_value="channel-"+target),
                  mock.patch.object(readback,"buffer_graphql",return_value={"post":post})):
                self.assertEqual(readback.verify_draft(path,"testtoken","testtoken"),
                                 receipt["buffer_post_id"])
                for variant in ("buffer","scheduled","sent"):
                    with mock.patch.object(readback,"buffer_graphql",return_value={
                        "post":{**post,"status":variant}}):
                        with self.assertRaises(RuntimeError):
                            readback.verify_draft(path,"testtoken","testtoken")

if __name__=="__main__":
    unittest.main()
