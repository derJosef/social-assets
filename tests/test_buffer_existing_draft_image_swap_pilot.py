"""No-network pilot tests: do not touch Buffer or existing posts."""
import hashlib
import json
import tempfile
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path

from scripts import buffer_existing_draft_image_swap_pilot as pilot

URL = ("https://raw.githubusercontent.com/derJosef/social-assets/"
       + "a" * 40 + "/media/images/2026-10-14-agent-drei-tests.png")

def png():
    # PNG signature/IHDR dimensions; the pilot only inspects header/hash.
    return (b"\x89PNG\r\n\x1a\n" + (13).to_bytes(4,"big") + b"IHDR" +
            (1080).to_bytes(4,"big") + (1350).to_bytes(4,"big") +
            bytes([8,6,0,0,0]) + b"0" * 180)

def post(asset="https://example.test/old.png", status="draft"):
    return {
        "id":pilot.POST_ID,
        "channelId":pilot.CHANNEL_ID,
        "channelService":"linkedin",
        "status":status, "dueAt":None,
        "createdAt":"2026-10-09T07:22:06.383Z",
        "text":"Bevor der KI-Agent arbeitet, sind drei Tests wichtig. " * 6,
        "assets":[{"type":"image", "source":asset}],
    }

class PilotTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.file=Path(self.tmp.name)/"private-snapshot.json"
        self.original=post()
        self.raw=png()
        self.sha=hashlib.sha256(self.raw).hexdigest()
        self.time=datetime.now(timezone.utc)
        self.snapshot=pilot.save_snapshot(self.original,self.file,now=self.time)

    def test_snapshot_roundtrip_and_no_overwrite(self):
        got=pilot.load_snapshot(self.file,now=self.time)
        self.assertEqual(got["post"],self.original)
        with self.assertRaisesRegex(pilot.PilotBlocked,"Never overwrite"):
            pilot.save_snapshot(self.original,self.file,now=self.time)
        with self.assertRaisesRegex(pilot.PilotBlocked,"stale"):
            pilot.load_snapshot(self.file,now=self.time+timedelta(minutes=21))

    def test_exact_pinned_image_hash_and_size(self):
        pilot.validate_image(URL,self.sha,download=lambda u:self.raw)
        with self.assertRaisesRegex(pilot.PilotBlocked,"SHA256"):
            pilot.validate_image(URL,"f"*64,download=lambda u:self.raw)
        with self.assertRaisesRegex(pilot.PilotBlocked,"commit-pinned"):
            pilot.validate_image(URL.replace("a"*40,"main"),self.sha,download=lambda u:self.raw)

    def test_edit_only_assets_once_with_two_reads(self):
        after=post(asset="https://buffer.example/new-image.png")
        calls=[]
        def fake_get(key, query, variables):
            calls.append((query,variables))
            if "mutation " in query:
                return {"editPost":{"__typename":"PostActionSuccess","post":after}}
            return {"post":self.original if len([q for q,_ in calls if "query " in q])==1 else after}
        result=pilot.edit_once(self.snapshot,URL,self.sha,get=fake_get,download=lambda u:self.raw,token="synthetic")
        self.assertEqual(result["status"],"PASS")
        self.assertEqual(len([q for q,_ in calls if "mutation " in q]),1)
        params=[vars for q,vars in calls if "mutation " in q][0]
        self.assertEqual(set(params),{"id","assets"})
        self.assertNotIn("text",params)
        self.assertNotIn("dueAt",params)
        self.assertNotIn("mode",params)
        self.assertNotIn("saveToDraft",params)
        self.assertEqual(result["post_id"],pilot.POST_ID)

    def test_manual_change_since_snapshot_blocks_before_edit(self):
        changed=post()
        changed["text"] += " User appended sentence."
        queries=[]
        def getter(key,query,variables):
            queries.append(query)
            if "mutation " in query:
                self.fail("MUST NOT MUTATE")
            return {"post":changed}
        with self.assertRaisesRegex(pilot.PilotBlocked,"changed after snapshot"):
            pilot.edit_once(self.snapshot,URL,self.sha,get=getter,download=lambda u:self.raw,token="synthetic")
        self.assertEqual(len(queries),1)

    def test_preapproved_post_becoming_scheduled_blocks(self):
        changed=post(status="scheduled")
        with self.assertRaisesRegex(pilot.PilotBlocked,"unscheduled"):
            pilot.verify_same_state(changed,self.original)

    def test_clear_image_swap_but_status_change_must_fail(self):
        after=post(asset="https://buffer.example/new-image.png",status="scheduled")
        with self.assertRaises(pilot.PilotBlocked):
            pilot._check_after(after,self.original)

    def test_mutation_error_never_retries(self):
        calls=[]
        def getter(key,query,variables):
            calls.append(query)
            if "mutation " in query:
                return {"editPost":{"__typename":"MutationError","message":"rejected"}}
            return {"post":self.original}
        with self.assertRaisesRegex(pilot.PilotBlocked,"failed"):
            pilot.edit_once(self.snapshot,URL,self.sha,get=getter,download=lambda u:self.raw,token="synthetic")
        self.assertEqual(len([q for q in calls if "mutation " in q]),1)

    def test_rejects_bad_pilot_identity_or_image_structure(self):
        wrong=dict(self.original,id="another_post")
        with self.assertRaises(pilot.PilotBlocked):pilot.validate_post(wrong)
        wrong=dict(self.original,assets=[])
        with self.assertRaises(pilot.PilotBlocked):pilot.validate_post(wrong)
        wrong=dict(self.original,dueAt="2026-11-01T10:00:00Z")
        with self.assertRaises(pilot.PilotBlocked):pilot.validate_post(wrong)


if __name__=="__main__":
    unittest.main()
