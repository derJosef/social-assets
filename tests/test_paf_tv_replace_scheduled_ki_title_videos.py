"""Existing-scheduled-post only: fade KI title image label; never switch platform AI flags."""
from __future__ import annotations
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import paf_tv_replace_scheduled_ki_title_videos as app

class Tests(unittest.TestCase):
    def post(self,i):
        p=app.ITEMS[i]
        meta=None if i==0 else (
             {"__typename":"FacebookPostMetadata","type":"post",
              "firstComment":None,"linkAttachment":None} if i==1 else
             {"__typename":"InstagramPostMetadata","type":"reel",
              "shouldShareToFeed":True,"isAiGenerated":False,
              "link":None,"geolocation":None,"firstComment":None})
        return {"id":p["id"],"channelId":p["channel_id"],
             "channelService":p["channel"],"status":"scheduled",
             "dueAt":p["due"],"text":"Test interview post with original untouched caption and tags",
             "shareMode":"customScheduled","schedulingType":"automatic",
             "tags":[{"id":"tag1"}],
             "assets":[{"type":"video","source":app.files(p)[0],"mimeType":"video/mp4"}],
             "metadata":meta}
    def test_exact_post_times_and_filenames(self):
        app.static_test()
        self.assertEqual([x["due"] for x in app.ITEMS],[
            "2026-10-29T09:00:00Z","2026-10-29T16:00:00Z","2026-10-29T18:00:00Z"])
        self.assertEqual({app.files(x)[1] for x in app.ITEMS},{
            app.BASE+"PAF-TV_01_ki-agenten_4x5_cover20261028_kihinweis20261028.mp4",
            app.BASE+"PAF-TV_01_ki-agenten_9x16_cover20261028_kihinweis20261028.mp4"})
    def test_media_only_change_retains_metadata(self):
        for i,p in enumerate(app.ITEMS):
            raw=self.post(i)
            old,meta,tags=app.check_post(raw,p,new=False)
            raw["assets"][0]["source"]=app.files(p)[1]
            new,meta2,tags2=app.check_post(raw,p,new=True)
            self.assertEqual(old,new)
            self.assertEqual(meta,meta2)
            self.assertEqual(tags,tags2)
            with self.assertRaises(app.Block):
                app.check_post(raw,p,new=False)
    def test_wrong_date_status_text_and_origin_fails(self):
        raw=self.post(1);p=app.ITEMS[1]
        for field,val in (("status","sent"),("dueAt","2026-10-30T16:00:00Z"),
                          ("channelId","wrong"),("text",""),("assets",[])):
            with self.subTest(field=field),self.assertRaises(app.Block):
                app.check_post({**raw,field:val},p,new=False)
    def test_disclosure_preserved(self):
        raw=self.post(2)
        self.assertEqual(app.metadata_input(raw["metadata"],"instagram"),
            {"instagram":{"type":"reel","shouldShareToFeed":True,"isAiGenerated":False}})
    def test_no_create_now_or_new_schedule(self):
        self.assertNotIn("createPost",app.EDIT)
        self.assertNotIn("shareNow",app.EDIT)
        self.assertIn("mode:customScheduled",app.EDIT)
        self.assertIn("saveToDraft:false",app.EDIT)
if __name__=="__main__":unittest.main()
