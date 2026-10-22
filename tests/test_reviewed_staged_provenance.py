"""Offline unit tests: no network or Buffer calls; fail closed before drafts."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.reviewed_staged_provenance import (
    ALLOWED_CAMPAIGNS, LOGO_ORIGINAL_SHA256, PREVIOUS_ASSET_QA_RUN,
    ReviewedProvenanceBlocked, load_verified_posts,
)


class ReviewedFingerprintStagingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.campaign = "2026-10-21-fingerabdruck-selfie-01"
        fixed = ALLOWED_CAMPAIGNS[self.campaign]
        self.proof = {
            "format_version":1, "brand":"ai-agent-builder",
            "campaign_id":self.campaign, "execution_mode":"drafts",
            "origin":"github_reviewed_existing_staged_artwork",
            "source_pr":46, "source_qa_run":PREVIOUS_ASSET_QA_RUN,
            "image_review":f"visual-reviews/{self.campaign}.json",
            "image_sha256":fixed["final_sha256"],
            "prepared_content":{"posts":{
                "linkedin":"Ein sorgfältig geprüfter LinkedIn-Text. "*12,
                "facebook":"Ein sorgfältig geprüfter Facebook-Text. "*12,
                "instagram":"Ein sorgfältig geprüfter Instagram-Text. "*12
            }}
        }
        self.review = {
            "source_sha256":fixed["source_sha256"],
            "visual_review":dict.fromkeys((
                "no_people","no_robot","no_foreign_logo","no_generated_text",
                "plausible_details","matches_topic","heading_and_logo_space"
            ),True)
        }
        self.receipt = {
            "source_png_sha256":fixed["source_sha256"],
            "final_sha256":fixed["final_sha256"],
            "logo_original_sha256":LOGO_ORIGINAL_SHA256,
            "size":[1080,1350],
            "status":"asset_technical_qa_passed_only_NOT_buffer_published",
            "logo_qa":{"logo_verified":True,"validator":"personalos_canonical"}
        }
        self.evidence = {"status":"eligible_for_draft_only",
                         "campaign":self.campaign,
                         "image_sha256":fixed["final_sha256"]}
        self.write_files()

    def write_files(self):
        entries = {
            f"reviewed-campaign-provenance/{self.campaign}.json":self.proof,
            f"visual-reviews/{self.campaign}.json":self.review,
            f"visual-reviews/{self.campaign}-build-receipt.json":self.receipt
        }
        for path,data in entries.items():
            target=self.root/path
            target.parent.mkdir(parents=True,exist_ok=True)
            target.write_text(json.dumps(data),encoding="utf-8")

    def verify(self):
        self.write_files()
        return load_verified_posts(self.root,self.campaign,self.evidence)

    def test_valid_github_qa_image_and_matching_three_texts(self):
        self.assertEqual(set(self.verify()),{"linkedin","facebook","instagram"})

    def test_unknown_campaign_not_allowed(self):
        with self.assertRaisesRegex(ReviewedProvenanceBlocked,"freigegebene"):
            load_verified_posts(self.root,"2026-10-22-unreviewed",self.evidence)

    def test_fake_image_digest_rejected(self):
        self.proof["image_sha256"]="0"*64
        with self.assertRaisesRegex(ReviewedProvenanceBlocked,"Finalbild"):
            self.verify()

    def test_fake_logo_digest_rejected(self):
        self.receipt["logo_original_sha256"]="0"*64
        with self.assertRaisesRegex(ReviewedProvenanceBlocked,"Logo"):
            self.verify()

    def test_unclear_visual_review_rejected(self):
        self.review["visual_review"]["no_generated_text"]=None
        with self.assertRaisesRegex(ReviewedProvenanceBlocked,"Visuelle"):
            self.verify()

    def test_wrong_qa_run_rejected(self):
        self.proof["source_qa_run"]="https://github.com/derJosef/social-assets/actions/runs/1"
        with self.assertRaisesRegex(ReviewedProvenanceBlocked,"Provenienz"):
            self.verify()

    def test_undated_or_incomplete_posts_rejected(self):
        self.proof["prepared_content"]["posts"].pop("instagram")
        with self.assertRaisesRegex(ReviewedProvenanceBlocked,"Post-Texte"):
            self.verify()

    def test_unknown_extra_key_rejected(self):
        self.proof["unexpected"]="yes"
        with self.assertRaisesRegex(ReviewedProvenanceBlocked,"Provenienzschema"):
            self.verify()

    def test_wrong_image_dimensions_rejected(self):
        self.receipt["size"]=[1024,1536]
        with self.assertRaisesRegex(ReviewedProvenanceBlocked,"Logo"):
            self.verify()

    def test_wrong_original_source_rejected(self):
        self.receipt["source_png_sha256"]="0"*64
        with self.assertRaisesRegex(ReviewedProvenanceBlocked,"Originalquellen"):
            self.verify()


if __name__ == "__main__":
    unittest.main()
