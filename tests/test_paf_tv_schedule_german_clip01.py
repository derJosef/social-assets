"""Offline regression: exact three PAF-TV interview video scheduling requests."""
from __future__ import annotations
import base64
import hashlib
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import paf_tv_schedule_german_clip01 as app

class TestInterviewSchedule(unittest.TestCase):
    def setup_info(self,i):
        p=app.ITEMS[i]
        target=p["target"]
        path,text,raw=app.read_draft(p["path"])
        self.assertEqual(path,p["path"])
        return {"item":p,"text":text,"channel_id":"c-"+target,
                "assets":app.parse_assets(raw),
                "metadata":app.platform_metadata(target,video=True)}

    def example(self,info,scheduled=False):
        p=info["item"]
        m=None
        if p["target"]=="facebook":
            m={"__typename":"FacebookPostMetadata","type":"post",
               "firstComment":None,"linkAttachment":None}
        elif p["target"]=="instagram":
            m={"__typename":"InstagramPostMetadata","type":"reel",
               "shouldShareToFeed":True,"isAiGenerated":False,"firstComment":None,
               "link":None,"geolocation":None}
        return {"id":p["id"],"channelId":info["channel_id"],
                "channelService":p["target"],
                "text":info["text"],"status":"scheduled" if scheduled else "draft",
                "dueAt":p["utc"] if scheduled else None,
                "shareMode":"customScheduled" if scheduled else "addToQueue",
                "schedulingType":"automatic","tags":[],
                "assets":[{"type":"video","source":app.BASE+p["media"],
                          "mimeType":"video/mp4"}],"metadata":m}

    def test_utc_dates_and_exact_platforms(self):
        app.static_checks()
        self.assertEqual([v["target"] for v in app.ITEMS],
                         ["linkedin","facebook","instagram"])
        self.assertEqual([i["local"] for i in app.ITEMS],
                         ["2026-10-29T10:00:00+01:00",
                          "2026-10-29T17:00:00+01:00",
                          "2026-10-29T19:00:00+01:00"])

    def test_original_sources_and_unmodified_media(self):
        for i in range(3):
            info=self.setup_info(i)
            original=self.example(info)
            current=self.example(info,True)
            self.assertEqual(app.post_check(original,info,scheduled=False),
                             app.post_check(current,info,scheduled=True))
            with self.assertRaises(app.ScheduleBlocked):
                app.post_check(current,info,scheduled=False)

    def test_change_in_text_asset_status_fails_closed(self):
        info=self.setup_info(2)
        raw=self.example(info)
        for key,value in (("status","sent"),("dueAt","2026-10-28T19:00:00Z"),
                          ("text","Different"),("channelId","other"),
                          ("assets",[])):
            with self.subTest(key=key),self.assertRaises(app.ScheduleBlocked):
                app.post_check({**raw,key:value},info,scheduled=False)

    def test_only_exact_existing_posts_no_create(self):
        self.assertNotIn("createPost",app.EDIT)
        self.assertNotIn("shareNow",app.EDIT)
        self.assertIn("mode:customScheduled",app.EDIT)
        self.assertIn("saveToDraft:false",app.EDIT)
        self.assertIn("tagIds: $tagIds",app.EDIT)
        self.assertIn("assets:$assets",app.EDIT)

    def test_receipt_rejects_missing_and_malformed_data(self):
        for record in (None,{},{"content":"bad"}):
            with self.assertRaises(Exception):
                app.decode_receipt(record)

    def test_english_not_in_any_source(self):
        self.assertTrue(all("english" not in i["path"] for i in app.ITEMS))

if __name__=="__main__":
    unittest.main()
