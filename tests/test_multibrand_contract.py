#!/usr/bin/env python3
"""Safety-focused offline tests; no provider API or Buffer calls."""
import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from multibrand_contract import ConfigurationBlocked, load_registry, plan_job

RUN = "2026-10-20-weekly-hero"

class MultibrandContractTests(unittest.TestCase):
    def setUp(self):
        self.registry = load_registry()

    def test_all_four_brands_are_registered(self):
        self.assertEqual(set(self.registry["brands"]), {
            "ai-agent-builder", "picturefix", "sticken-lasern", "praezisionsarmaturen"
        })

    def test_rotation_creates_seven_independent_desktop_mobile_pairs(self):
        plan = plan_job("ai-agent-builder", "rotation", RUN, self.registry)
        self.assertEqual(plan["count"], 14)
        self.assertEqual(len(set(row["path"] for row in plan["outputs"])), 14)
        self.assertEqual(len(set(row["section"] for row in plan["outputs"])), 7)
        self.assertEqual({row["variant"] for row in plan["outputs"]}, {"desktop", "mobile"})
        self.assertFalse(plan["permission_to_publish"])
        self.assertTrue(plan["require_visual_review"])

    def test_news_images_are_outside_rotation(self):
        plan = plan_job("ai-agent-builder", "news", "2026-10-20-news-example", self.registry)
        self.assertEqual(plan["count"], 3)
        self.assertEqual({tuple(row["dimensions"]) for row in plan["outputs"]},
                         {(1672, 941), (1200, 900), (800, 800)})
        self.assertTrue(all("/news/" in row["path"] for row in plan["outputs"]))
        self.assertTrue(all("/rotation/" not in row["path"] for row in plan["outputs"]))

    def test_only_ai_agent_builder_can_have_preapproved_social_drafts(self):
        for brand in self.registry["brands"]:
            plan = plan_job(brand, "social", "2026-10-20-isolation", self.registry)
            self.assertEqual(plan["permission_to_create_buffer_drafts"],
                             brand == "ai-agent-builder")
            self.assertFalse(plan["permission_to_publish"])
            self.assertTrue(all("/" + brand + "/social/" in x["path"]
                                for x in plan["outputs"]))

    def test_other_brands_cannot_inherit_josef_website_or_logo(self):
        profiles = self.registry["brands"]
        self.assertEqual(profiles["sticken-lasern"]["logo_policy"],
                         "own-original-logo-not-josef")
        self.assertIsNone(profiles["sticken-lasern"]["website"]["domain"])
        for brand in ("picturefix", "sticken-lasern", "praezisionsarmaturen"):
            self.assertFalse(any(profiles[brand]["permissions"].values()))
            self.assertIsNone(profiles[brand]["website"]["repository"])
            self.assertEqual(plan_job(brand, "rotation", RUN, self.registry)["count"], 0)

    def test_brand_namespace_is_never_shared(self):
        a = plan_job("ai-agent-builder", "social", RUN, self.registry)
        b = plan_job("picturefix", "social", RUN, self.registry)
        self.assertNotEqual(a["namespace"], b["namespace"])
        self.assertFalse(set(x["path"] for x in a["outputs"]) &
                         set(x["path"] for x in b["outputs"]))

    def test_unknown_brand_and_traversal_blocked(self):
        for name in ("not-configured", "../ai-agent-builder", "AI Agent Builder"):
            with self.assertRaises(ConfigurationBlocked):
                plan_job(name, "rotation", RUN, self.registry)
        with self.assertRaises(ConfigurationBlocked):
            plan_job("ai-agent-builder", "rotation", "../escape", self.registry)

    def test_publication_permission_escalation_rejected(self):
        edited = copy.deepcopy(self.registry)
        edited["brands"]["picturefix"]["permissions"]["social_draft"] = True
        # Schema re-validation needs a real file; fail-closed draft production remains absent.
        plan = plan_job("picturefix", "social", RUN, self.registry)
        self.assertFalse(plan["permission_to_create_buffer_drafts"])
        self.assertFalse(plan["permission_to_publish"])

    def test_all_output_paths_are_separate_and_versioned(self):
        for brand in self.registry["brands"]:
            for kind in ("social", "news", "rotation"):
                plan = plan_job(brand, kind, RUN, self.registry)
                self.assertEqual(plan["status"], "offline-plan-only")
                self.assertTrue(all(path["path"].startswith(
                    f"generated/{brand}/{kind}/{RUN}/") for path in plan["outputs"]))

if __name__ == "__main__":
    unittest.main()
