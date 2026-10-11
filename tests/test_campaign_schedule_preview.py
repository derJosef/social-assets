"""No network, GitHub credentials, Buffer imports or publication side effects."""

import hashlib
import importlib.util
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path


SOURCE = Path(__file__).resolve().parents[1] / "scripts" / "campaign_schedule_preview.py"
spec = importlib.util.spec_from_file_location("campaign_schedule_preview_tested", SOURCE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class PreviewTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        for part in ("campaign-manifests", "ready-for-buffer", "ready-to-schedule", "media/images"):
            (self.root / part).mkdir(parents=True)
        self.campaign = "2026-10-11-sicherer-entwurf"
        self.manifest_path = f"campaign-manifests/{self.campaign}.json"
        self.now = datetime(2026, 10, 11, 12, 0, tzinfo=timezone.utc)
        self.image = f"media/images/{self.campaign}-branded.png"
        (self.root / self.image).write_bytes(b"synthetic image, no personal media")
        self.manifest = {
            "format_version": 1, "brand": "ai-agent-builder", "campaign_id": self.campaign,
            "image": {"final": self.image, "sha256": hashlib.sha256((self.root / self.image).read_bytes()).hexdigest()},
            "posts": {}, "posting_times": {
                "linkedin": {"local": "2026-10-14T16:00:00+02:00", "utc": "2026-10-14T14:00:00Z"},
                "facebook": {"local": "2026-10-15T09:00:00+02:00", "utc": "2026-10-15T07:00:00Z"},
                "instagram": {"local": "2026-10-14T18:00:00+02:00", "utc": "2026-10-14T16:00:00Z"},
            },
        }
        for target in module.TARGETS:
            path = f"ready-for-buffer/auto-{self.campaign}-{target}.json"
            self.manifest["posts"][target] = path
            (self.root / path).write_text(json.dumps({"format_version": 2, "target": target,
                "text": f"Kampagnentext für {target}", "media": {"type": "images", "images": [{
                    "url": f"https://raw.githubusercontent.com/derJosef/social-assets/main/{self.image}",
                    "alt_text": "Synthetische Vorschau"}]} }), encoding="utf-8")
        self.save()

    def save(self):
        (self.root / self.manifest_path).write_text(json.dumps(self.manifest), encoding="utf-8")

    def preview(self):
        return module.inspect(self.root, self.manifest_path, self.now)

    def test_valid_read_only_preview_contains_all_text_and_times(self):
        preview = self.preview()
        self.assertEqual(preview["review_state"], "PROPOSAL_ONLY")
        self.assertEqual(len(preview["posts"]), 3)
        result = module.render_markdown(preview)
        self.assertIn("14.10.2026 16:00 (MESZ)", result)
        self.assertIn("15.10.2026 09:00 (MESZ)", result)
        self.assertIn("Kampagnentext für instagram", result)
        self.assertIn("NICHT FREIGEGEBEN", result)
        self.assertIn("keine Terminierung", result)

    def test_winter_offset_is_converted_correctly(self):
        self.manifest["posting_times"]["linkedin"] = {
            "local": "2026-11-04T16:00:00+01:00", "utc": "2026-11-04T15:00:00Z"}
        self.save()
        self.assertIn("04.11.2026 16:00 (MEZ)", module.render_markdown(self.preview()))

    def test_winter_offset_in_october_is_rejected(self):
        self.manifest["posting_times"]["linkedin"] = {
            "local": "2026-10-14T16:00:00+01:00", "utc": "2026-10-14T15:00:00Z"}
        self.save()
        with self.assertRaisesRegex(module.PreviewBlocked, "Sommer"):
            self.preview()

    def test_utc_mismatch_fails_closed(self):
        self.manifest["posting_times"]["instagram"]["utc"] = "2026-10-14T15:00:00Z"
        self.save()
        with self.assertRaisesRegex(module.PreviewBlocked, "passen nicht"):
            self.preview()

    def test_expired_time_is_rejected(self):
        self.manifest["posting_times"]["linkedin"] = {
            "local": "2026-10-07T16:00:00+02:00", "utc": "2026-10-07T14:00:00Z"}
        self.save()
        with self.assertRaisesRegex(module.PreviewBlocked, "Vergangenheit"):
            self.preview()

    def test_changed_image_is_blocked(self):
        (self.root / self.image).write_bytes(b"image changed after manifest")
        with self.assertRaisesRegex(module.PreviewBlocked, "Bild wurde"):
            self.preview()

    def test_wrong_campaign_is_blocked(self):
        self.manifest["campaign_id"] = "2026-10-12-fremde-kampagne"
        self.save()
        with self.assertRaisesRegex(module.PreviewBlocked, "gehört nicht"):
            self.preview()

    def test_wrong_post_target_is_blocked(self):
        path = self.manifest["posts"]["facebook"]
        (self.root / path).write_text(json.dumps({"format_version": 1, "target": "linkedin", "text": "Falsch"}))
        with self.assertRaisesRegex(module.PreviewBlocked, "Entwurf für facebook"):
            self.preview()

    def test_draft_image_swap_is_blocked(self):
        path = self.manifest["posts"]["instagram"]
        draft = json.loads((self.root / path).read_text(encoding="utf-8"))
        draft["media"]["images"][0]["url"] = "https://example.com/fremdes.png"
        (self.root / path).write_text(json.dumps(draft))
        with self.assertRaisesRegex(module.PreviewBlocked, "Bild im instagram"):
            self.preview()

    def test_wrong_post_path_is_blocked(self):
        self.manifest["posts"]["linkedin"] = "ready-for-buffer/../ready-to-schedule/example.json"
        self.save()
        with self.assertRaisesRegex(module.PreviewBlocked, "falsch zugeordnet"):
            self.preview()

    def test_manifest_traversal_is_blocked(self):
        with self.assertRaisesRegex(module.PreviewBlocked, "Einzelmanifest"):
            module.inspect(self.root, "campaign-manifests/../ready-for-buffer/post.json", self.now)

    def test_duplicate_json_keys_are_blocked(self):
        raw = (self.root / self.manifest_path).read_text()
        (self.root / self.manifest_path).write_text(raw.replace('"format_version": 1,',
            '"format_version": 1, "format_version": 1,'), encoding="utf-8")
        with self.assertRaisesRegex(module.PreviewBlocked, "Doppelter"):
            self.preview()

    def test_missing_target_blocks_entire_preview(self):
        self.manifest["posting_times"].pop("instagram")
        self.save()
        with self.assertRaisesRegex(module.PreviewBlocked, "Alle drei"):
            self.preview()

    def test_existing_campaign_slot_collision_blocks_preview(self):
        prior = {"posting_times": {"linkedin": {
            "local": "2026-10-14T16:30:00+02:00", "utc": "2026-10-14T14:30:00Z"}}}
        (self.root / "campaign-manifests/2026-10-01-andere-kampagne.json").write_text(
            json.dumps(prior), encoding="utf-8")
        with self.assertRaisesRegex(module.PreviewBlocked, "Zeitkollision für linkedin"):
            self.preview()

    def test_existing_schedule_request_collision_blocks_preview(self):
        request = {"target": "facebook", "draft_file": "ready-for-buffer/fremder-entwurf.json",
                   "publish_at_utc": "2026-10-15T07:30:00Z", "approved_for_scheduling": True}
        (self.root / "ready-to-schedule/frueherer-auftrag.json").write_text(json.dumps(request))
        with self.assertRaisesRegex(module.PreviewBlocked, "Zeitkollision für facebook"):
            self.preview()

    def test_same_draft_has_prior_scheduling_request(self):
        request = {"target": "instagram", "draft_file": self.manifest["posts"]["instagram"],
                   "publish_at_utc": "2026-10-28T16:00:00Z", "approved_for_scheduling": True}
        (self.root / "ready-to-schedule/already-requested.json").write_text(json.dumps(request))
        with self.assertRaisesRegex(module.PreviewBlocked, "bereits ein Terminierungsauftrag"):
            self.preview()


if __name__ == "__main__":
    unittest.main()
