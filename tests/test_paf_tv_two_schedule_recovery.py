"""Offline one-time schedule recovery tests; no API requests."""
from __future__ import annotations
import base64
import importlib.util
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import os,json,tempfile
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import paf_tv_move_two_existing_schedules as old
import paf_tv_two_schedule_recovery as app

class Tests(unittest.TestCase):
    def example(self,p):
        return {
           "id":p["id"],"channelId":p["channel_id"],"channelService":p["channel"],
           "status":"scheduled","dueAt":p["old"],
           "text":p["text_prefix"]+" Dies ist ein bestehender Beitrag.",
           "shareMode":"addToQueue","schedulingType":"automatic",
           "tags":[{"id":"tag"}],"assets":[{"type":"image",
             "source":"https://raw.githubusercontent.com/derJosef/social-assets/main/media/images/test.png",
             "mimeType":"image/png","image":{"altText":"Bestehende Beschreibung","userTags":[]}}],
           "metadata":None if p["channel"]=="linkedin" else {
                "__typename":"InstagramPostMetadata","type":"post",
                "firstComment":None,"link":None,"shouldShareToFeed":True,
                "isAiGenerated":False,"geolocation":None}
        }
    def test_date_contract(self):
        app.old.check_fixture()
        self.assertEqual(len(app.old.POSTS),2)
    def test_all_current_media_and_metadata_carried_over(self):
        for p in app.old.POSTS:
            original=self.example(p)
            payload,sig=app.content_input(original,p)
            self.assertEqual(payload["text"],original["text"])
            self.assertEqual(payload["assets"][0]["image"]["url"],original["assets"][0]["source"])
            self.assertEqual(payload["assets"][0]["image"]["metadata"]["altText"],"Bestehende Beschreibung")
            self.assertEqual(payload["tagIds"],["tag"])
            self.assertEqual(payload["id"],p["id"])
            self.assertEqual(payload["dueAt"],p["new"])
            if p["channel"]=="instagram":
                self.assertEqual(payload["metadata"],{"instagram":{"type":"post",
                    "shouldShareToFeed":True,"isAiGenerated":False}})
            else:self.assertIsNone(payload["metadata"])
            self.assertEqual(sig,old.fingerprint(original))
    def test_unknown_existing_metadata_fails_closed(self):
        p=app.old.POSTS[0]
        for mutate in ("user-tags","missing-alt","wrong-original-time","not-scheduled","story"):
            item=self.example(p)
            if mutate=="user-tags":item["assets"][0]["image"]["userTags"]=[{"__typename":"UserTag"}]
            elif mutate=="missing-alt":item["assets"][0]["image"].pop("altText")
            elif mutate=="wrong-original-time":item["dueAt"]=p["new"]
            elif mutate=="not-scheduled":item["status"]="sent"
            elif mutate=="story":item["metadata"]["type"]="story"
            with self.subTest(case=mutate),self.assertRaises(old.Block):
                app.content_input(item,p)
    def test_preflight_two_current_unmodified_posts(self):
        lookup={p["id"]:self.example(p) for p in old.POSTS}
        def mock_get(key,query,variables):
            self.assertEqual(query,app.QUERY)
            return {"post":lookup[variables["id"]]}
        self.assertEqual(len(app.preflight("fake",get=mock_get)),2)
    def test_old_receipt_path_is_explicit(self):
        self.assertIn("40673207492",app.FIRST_RUN)
        self.assertTrue(app.FIRST_ONLY.endswith(app.old.POSTS[0]["id"]+".json"))
    def test_pinned_event_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            file=Path(tmp)/"event.json"
            file.write_text(json.dumps({"action":"created","issue":{"number":19},
                  "comment":{"body":app.TRIGGER,"user":{"id":45994004}}}))
            base={"GITHUB_REPOSITORY":"derJosef/social-assets","GITHUB_REF":"refs/heads/main",
                  "GITHUB_EVENT_NAME":"issue_comment","GITHUB_RUN_ATTEMPT":"1",
                  "GITHUB_ACTOR_ID":"45994004","GITHUB_EVENT_PATH":str(file)}
            with patch.dict(os.environ,base,clear=True):app.owner_event()
            with patch.dict(os.environ,{**base,"GITHUB_RUN_ATTEMPT":"2"},clear=True):
                with self.assertRaises(old.Block):app.owner_event()
    def test_no_new_post_or_draft_or_immediate_publishing(self):
        self.assertNotIn("createPost",app.EDIT)
        self.assertNotIn("shareNow",app.EDIT)
        self.assertNotIn("saveToDraft",app.EDIT)
        self.assertIn("mode:customScheduled",app.EDIT)
        self.assertIn("tagIds:$tagIds",app.EDIT)
        self.assertIn("assets:$assets",app.EDIT)
if __name__=="__main__":unittest.main()
