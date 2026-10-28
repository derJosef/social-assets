"""Offline tests: only two existing Buffer IDs, dates, and no content edits."""
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch, Mock

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
spec=importlib.util.spec_from_file_location("reschedule_test",ROOT/"scripts/paf_tv_move_two_existing_schedules.py")
app=importlib.util.module_from_spec(spec);spec.loader.exec_module(app)

class ScheduledPostTests(unittest.TestCase):
    def test_locked_targets(self):
        app.check_fixture()
        self.assertEqual([x["channel"] for x in app.POSTS],["instagram","linkedin"])
        self.assertEqual(app.POSTS[0]["new_local"],"2026-10-30T18:00:00+01:00")
        self.assertEqual(app.POSTS[1]["new_local"],"2026-11-12T13:00:00+01:00")
    def post(self,p,old=True):
        return {"id":p["id"],"channelId":p["channel_id"],
                "channelService":p["channel"],"status":"scheduled",
                "dueAt":p["old"] if old else p["new"],
                "text":p["text_prefix"]+" Zusätzliche vorhandene Erläuterungen.",
                "shareMode":"addToQueue" if old else "customScheduled",
                "schedulingType":"automatic",
                "tags":[{"id":"tag-1"}],
                "assets":[{"type":"image","source":"https://example.com/a.png","mimeType":"image/png"}],
                "metadata":None if p["channel"]=="linkedin" else {
                    "__typename":"InstagramPostMetadata","type":"post",
                    "shouldShareToFeed":True,"isAiGenerated":False}}
    def test_old_and_new_status(self):
        for p in app.POSTS:
            post=self.post(p,True)
            sig=app.verify_post(post,p,before=True)
            fresh=self.post(p,False)
            self.assertEqual(sig,app.verify_post(fresh,p,before=False))
            with self.assertRaises(app.Block):
                app.verify_post(fresh,p,before=True)
            with self.assertRaises(app.Block):
                app.verify_post(post,p,before=False)
    def test_fail_closed_wrong_id_media_text_status(self):
        p=app.POSTS[0]
        original=self.post(p)
        for key,bad in [("id","fake"),("channelId","fake"),("text","other post"),
                         ("status","sent"),("status","draft"),("assets",[]),
                         ("shareMode","shareNow")]:
            v={**original,key:bad}
            with self.subTest(key=key,bad=bad), self.assertRaises(app.Block):
                app.verify_post(v,p,before=True)
    def test_live_owner_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"event.json"
            event={"action":"created","issue":{"number":19},"comment":{
                "body":app.TRIGGER,"user":{"id":45994004}}}
            path.write_text(json.dumps(event),encoding="utf-8")
            env={"GITHUB_REPOSITORY":"derJosef/social-assets","GITHUB_REF":"refs/heads/main",
                 "GITHUB_EVENT_NAME":"issue_comment","GITHUB_RUN_ATTEMPT":"1",
                 "GITHUB_ACTOR_ID":"45994004","GITHUB_EVENT_PATH":str(path)}
            with patch.dict(os.environ,env,clear=True):
                app.valid_event()
            for key,bad in [("GITHUB_REF","refs/heads/other"),
                            ("GITHUB_RUN_ATTEMPT","2"),
                            ("GITHUB_ACTOR_ID","1234")]:
                with patch.dict(os.environ,{**env,key:bad},clear=True):
                    with self.assertRaises(app.Block):
                        app.valid_event()
    def test_preflight_checks_both_without_mutation(self):
        posts={p["id"]:self.post(p) for p in app.POSTS}
        def get(key,query,vars):
            self.assertEqual(query,app.QUERY)
            return {"post":posts[vars["id"]]}
        data=app.preflight("fake-token",get=get)
        self.assertEqual(len(data),2)
        self.assertEqual([x["post"]["channel"] for x in data],["instagram","linkedin"])
    def test_only_edit_fields(self):
        src=app.EDIT
        for forbidden in ["createPost","saveToDraft","shareNow","text:","metadata:","assets:","tagIds:","schedulingType:"]:
            self.assertNotIn(forbidden,src)
        self.assertIn("mode: customScheduled",src)
        self.assertIn("dueAt: $dueAt",src)
if __name__=="__main__":
    unittest.main()
