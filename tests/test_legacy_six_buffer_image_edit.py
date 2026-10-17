"""Synthetic, network-free guards for six existing draft image edits."""
import hashlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from PIL import Image
from scripts import legacy_six_buffer_image_edit as m


def fixture_image():
    buf=io.BytesIO()
    Image.new("RGB",(1080,1350),"navy").save(buf,format="PNG")
    return buf.getvalue()


def fake_post(pid,target,image="https://example.com/old.png"):
    metadata={
        "linkedin":{"__typename":"LinkedInPostMetadata","type":"post","firstComment":None,"linkAttachment":None},
        "facebook":{"__typename":"FacebookPostMetadata","type":"post","firstComment":None,"linkAttachment":None},
        "instagram":{"__typename":"InstagramPostMetadata","type":"post","firstComment":None,
                     "link":None,"shouldShareToFeed":True,"isAiGenerated":False,"geolocation":None},
    }
    return {"id":pid,"channelId":"channel-"+target,"channelService":target,
            "status":"draft","dueAt":None,"text":"The live Buffer text / user edits are authoritative.",
            "shareMode":"addToQueue","schedulingType":"automatic","tags":[],
            "assets":[{"type":"image","source":image,"mimeType":"image/png"}],
            "metadata":metadata[target]}


class LegacyImageDraftTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.image=fixture_image()
        sha=hashlib.sha256(self.image).hexdigest()
        self.expected=tuple((topic,fn,sha,ids,alt) for topic,fn,_,ids,alt in m.EXPECTED)
        self.posts={pid:fake_post(pid,target) for _,_,_,ids,_ in self.expected
                    for target,pid in ids.items()}
        self.events={"action":"created",
                     "issue":{"number":19,"user":{"login":"derJosef"}},
                     "comment":{"user":{"login":"derJosef"},
                         "body":"LEGACY_SIX_DRAFTS_REPLACE_IMAGE_ONLY_ONCE_20261017"}}
        self.eventfile=self.root/"event.json"
        self.eventfile.write_text(json.dumps(self.events))
        self.receipts={}
        self.calls=[]
        self.env={
            "GITHUB_REPOSITORY":"derJosef/social-assets",
            "GITHUB_REF":"refs/heads/main",
            "GITHUB_EVENT_NAME":"issue_comment",
            "GITHUB_RUN_ATTEMPT":"1",
            "GITHUB_ACTOR":"derJosef",
            "GITHUB_EVENT_PATH":str(self.eventfile),
            "BUFFER_API_KEY":"synthetic-buffer-token",
            "GITHUB_TOKEN":"synthetic-github-token",
            "GITHUB_RUN_ID":"123",
        }

    def mock_get(self,key,query,variables):
        if "editPost(" in query:
            self.calls.append(("edit",variables))
            current=self.posts[variables["id"]]
            current["assets"]=[{"type":"image","source":variables["assets"][0]["image"]["url"],
                                "mimeType":"image/png"}]
            return {"editPost":{"__typename":"PostActionSuccess","post":{"id":variables["id"]}}}
        self.calls.append(("read",variables))
        return {"post":json.loads(json.dumps(self.posts[variables["id"]]))}

    def fetch_receipt(self,token,path):
        return self.receipts.get(path)
    def put_receipt(self,token,path,value,msg,sha=None):
        self.receipts[path]=dict(value)
        return "fake-receipt-blob"

    def patch(self):
        return mock.patch.multiple(m,EXPECTED=self.expected,
                                  resolve_channel=lambda _,ch,__: "channel-"+ch,
                                  channel_preference=lambda _: "",
                                  fetch_receipt=self.fetch_receipt,
                                  put_receipt=self.put_receipt)

    def test_strict_event_guard(self):
        self.assertTrue(m.valid_owner_event(self.eventfile))
        for bad in (
            {"comment":{"user":{"login":"other"},"body":self.events["comment"]["body"]}},
            {"comment":{"user":{"login":"derJosef"},"body":"LEGACY_SIX_DRAFTS_REPLACE_IMAGE_ONLY_ONCE_20261017\npublish"}},
            {"issue":{"number":20,"user":{"login":"derJosef"}}},
            {"issue":{"number":19,"user":{"login":"derJosef"},"pull_request":{"url":"not-a-real-pr"}}},
        ):
            x={**self.events,**bad}
            self.eventfile.write_text(json.dumps(x))
            self.assertFalse(m.valid_owner_event(self.eventfile))
        self.assertFalse(m.valid_owner_event(self.root/"missing"))

    def test_source_sha_and_dimensions_are_enforced(self):
        with self.patch():
            verified=m.verify_media(fetch=lambda _:self.image)
            self.assertEqual(set(verified),{"wer-liest-mit","drei-tests"})
            with self.assertRaisesRegex(m.ImageRepairBlocked,"SHA-identisch"):
                m.verify_media(fetch=lambda _:self.image+b"x")

    def test_reject_non_draft_wrong_channel_missing_asset_or_meta(self):
        pid="6ac8d5a926e224ee545ee6b5"
        post=fake_post(pid,"linkedin")
        self.assertEqual(m.check_post(post,id=pid,target="linkedin",expected_image="new")["text"],post["text"])
        for change in ({"status":"scheduled"},{"dueAt":"2026-10-19T12:00:00Z"},
                       {"assets":[]},{"channelService":"instagram"},
                       {"text":""},{"shareMode":"shareNow"}):
            broken={**post,**change}
            with self.assertRaises(m.ImageRepairBlocked):
                m.check_post(broken,id=pid,target="linkedin",expected_image="new")
        ig=fake_post("6ac8d5ae26e224ee545ee809","instagram")
        ig["metadata"]["geolocation"]={"id":"extra"}
        with self.assertRaises(m.ImageRepairBlocked):
            m.check_post(ig,id=ig["id"],target="instagram",expected_image="new")

    def test_live_six_edits_are_existing_drafts_only_and_receipted_once(self):
        with self.patch(),mock.patch.dict(os.environ,self.env,clear=True):
            m.live_edit(get=self.mock_get,fetch=lambda _:self.image)
        edits=[v for name,v in self.calls if name=="edit"]
        self.assertEqual(len(edits),6)
        self.assertEqual(len(self.receipts),7) # batch plus six original-ID receipts
        self.assertEqual(self.receipts["delivery-receipts/legacy-six-image-edit-batch-20261017.json"]["state"],
                         "verified_six_existing_draft_images_not_queued")
        self.assertTrue(all(v["state"]=="verified_existing_draft_image_only_no_schedule"
                            for k,v in self.receipts.items() if "batch" not in k))
        for e in edits:
            self.assertEqual(e["text"],"The live Buffer text / user edits are authoritative.")
            self.assertEqual(len(e["assets"]),1)
            self.assertTrue(e["assets"][0]["image"]["url"].startswith(m.IMAGE_ROOT))
        self.assertIn("saveToDraft: true",m.EDIT)
        self.assertNotIn("createPost(",m.EDIT)
        self.assertNotIn("mode:",m.EDIT)
        self.assertNotIn("dueAt:",m.EDIT)
        self.assertNotIn("schedulingType:",m.EDIT)
        edits_before=len(edits)
        with self.patch(),mock.patch.dict(os.environ,self.env,clear=True):
            with self.assertRaises(m.ImageRepairBlocked):
                m.live_edit(get=self.mock_get,fetch=lambda _:self.image)
        self.assertEqual(len([x for x in self.calls if x[0]=="edit"]),edits_before)

    def test_failing_any_preflight_blocks_all_edits(self):
        self.posts["6ac8d5a926e224ee545ee6b5"]["status"]="scheduled"
        with self.patch(),mock.patch.dict(os.environ,self.env,clear=True):
            with self.assertRaises(m.ImageRepairBlocked):
                m.live_edit(get=self.mock_get,fetch=lambda _:self.image)
        self.assertFalse(self.receipts)
        self.assertFalse([x for x in self.calls if x[0]=="edit"])

    def test_workflow_is_owner_only_no_pr_or_push_mutation_trigger(self):
        from pathlib import Path
        p=(Path(__file__).resolve().parents[1]/
           ".github/workflows/legacy-six-buffer-inplace-image-update.yml")
        source=p.read_text()
        for gate in ["github.actor == 'derJosef'","github.event.issue.number == 19",
                     "github.run_attempt == 1","LEGACY_SIX_DRAFTS_REPLACE_IMAGE_ONLY_ONCE_20261017"]:
            self.assertIn(gate,source)
        self.assertNotIn("  push:",source)
        self.assertNotIn("  pull_request:",source)


if __name__=="__main__":
    unittest.main()
