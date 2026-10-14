"""All checks offline and synthetic; no image generation or services involved."""
import json
import tempfile
import unittest
from pathlib import Path
from PIL import Image
from scripts import cleanroom_image_probe as probe
from scripts import cleanroom_image_brief as brief

SPEC = {"version":1,"scene":"document-review","steps":["receive","inspect","release"],"composition":"connected-three","figure":"none"}
REVIEW = {"visual_review": {k: True for k in probe.REVIEW_KEYS}, "review_evidence": "ChatGPT inspected the actual PNG image and its visual details; NOT a human review."}

class ProbeTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.p=Path(temporary.name)/'test.png'
        self.job=brief.compiled_job(SPEC)

    def create_png(self, size=(1080,1350)):
        Image.new('RGB',size,'#07111f').save(self.p)

    def test_correct_image_never_claims_context_isolation_or_authorizes_transfer(self):
        self.create_png()
        outcome=probe.assess(SPEC,self.job,self.p,REVIEW)
        self.assertEqual(outcome['state'],'PROVISIONAL_ONLY_UNVERIFIED_CONTEXT')
        self.assertFalse(outcome['actual_generator_context_verified'])
        self.assertFalse(outcome['transfer_permitted'])
        self.assertFalse(outcome['publication_permitted'])

    def test_wrong_size_blocks(self):
        self.create_png((1122,1402))
        outcome=probe.assess(SPEC,self.job,self.p,REVIEW)
        self.assertEqual(outcome['state'],'BLOCKED')
        self.assertIn('wrong_pixel_dimensions',outcome['hard_failures'])

    def test_detected_person_blocks_even_when_marks_are_clean(self):
        self.create_png()
        review=json.loads(json.dumps(REVIEW));review['visual_review']['no_people']=False
        result=probe.assess(SPEC,self.job,self.p,review)
        self.assertIn('visual_no_people',result['hard_failures'])

    def test_unclear_mark_not_translated_into_hard_failure(self):
        self.create_png()
        review=json.loads(json.dumps(REVIEW));review['visual_review']['no_foreign_logo']=None
        review['review_evidence']+=' A tiny area is unklar/unscharf.'
        result=probe.assess(SPEC,self.job,self.p,review)
        self.assertEqual(result['state'],'PROVISIONAL_ONLY_UNVERIFIED_CONTEXT')
        self.assertEqual(result['unresolved_marks'],['no_foreign_logo'])

    def test_unknown_mark_needs_explanation(self):
        self.create_png()
        review=json.loads(json.dumps(REVIEW));review['visual_review']['no_foreign_logo']=None
        with self.assertRaises(probe.InvalidProbe):probe.assess(SPEC,self.job,self.p,review)

    def test_fake_branded_prompt_is_rejected_even_with_correct_own_sha(self):
        self.create_png()
        job=json.loads(json.dumps(self.job)); job['generator_prompt']='Create a brand poster'
        import hashlib
        job['generator_prompt_sha256']=hashlib.sha256(job['generator_prompt'].encode()).hexdigest()
        with self.assertRaises(probe.InvalidProbe):probe.assess(SPEC,job,self.p,REVIEW)

    def test_reference_injection_rejected(self):
        self.create_png()
        job=json.loads(json.dumps(self.job));job['reference_images']=['hidden-brand.png']
        with self.assertRaises(probe.InvalidProbe):probe.assess(SPEC,job,self.p,REVIEW)

    def test_no_review_stays_pending(self):
        self.create_png()
        self.assertEqual(probe.assess(SPEC,self.job,self.p)['state'],'AWAITING_VISUAL_REVIEW')

    def test_invalid_visual_review_rejected(self):
        self.create_png()
        review=json.loads(json.dumps(REVIEW));review['visual_review']['no_people']='yes'
        with self.assertRaises(probe.InvalidProbe):probe.assess(SPEC,self.job,self.p,review)

    def test_corrupted_image_rejected(self):
        self.p.write_bytes(b'not png')
        with self.assertRaises(probe.InvalidProbe):probe.assess(SPEC,self.job,self.p)

    def test_jpeg_rejected(self):
        Image.new('RGB',(1080,1350),'#07111f').save(self.p,format='JPEG')
        self.assertIn('not_png',probe.assess(SPEC,self.job,self.p,REVIEW)['hard_failures'])

if __name__ == '__main__':unittest.main()
