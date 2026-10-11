"""Offline tests for bot-write isolation; never call Buffer or GitHub."""
import hashlib
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import buffer_draft as sender
from scripts import immutable_campaign_assets as assets
from scripts import campaign_reservations as reservations

CAMPAIGN = "2026-10-12-isolated"
TARGETS = ("linkedin", "facebook", "instagram")


class LedgerTests(unittest.TestCase):
    def test_main_reservation_cannot_be_reused_after_ledger_migration(self):
        calls = []
        def get(url, **kwargs):
            calls.append(url)
            return {"sha": "historic"}
        with mock.patch.object(sender, "json_http", side_effect=get):
            self.assertEqual(sender.fetch_receipt("token", "delivery-receipts/old.json"), {"sha": "historic"})
        self.assertEqual(len(calls), 1)
        self.assertIn("?ref=main", calls[0])

    def test_ledger_branch_must_exist_before_a_new_receipt_can_be_reserved(self):
        calls = []
        def get(url, **kwargs):
            calls.append(url)
            raise RuntimeError("HTTP 404 bei api.github.com")
        with mock.patch.object(sender, "json_http", side_effect=get):
            with self.assertRaisesRegex(RuntimeError, "404"):
                sender.fetch_receipt("token", "delivery-receipts/new.json")
        self.assertEqual(len(calls), 2)
        self.assertIn("/branches/automation-receipts", calls[1])

    def test_ledger_miss_and_hit(self):
        def get(url, **kwargs):
            if "?ref=main" in url:
                raise RuntimeError("HTTP 404 bei api.github.com")
            if "/branches/" in url:
                return {"name": "automation-receipts"}
            if "?ref=automation-receipts" in url:
                return {"sha": "new-reservation"}
            raise AssertionError(url)
        with mock.patch.object(sender, "json_http", side_effect=get):
            self.assertEqual(sender.fetch_receipt("token", "delivery-receipts/new.json"), {"sha": "new-reservation"})

    def test_new_receipts_can_never_write_to_main(self):
        calls = []
        def write(url, **kwargs):
            calls.append(kwargs["payload"])
            return {"content": {"sha": "receipt"}}
        with mock.patch.object(sender, "json_http", side_effect=write):
            sender.put_receipt("token", "delivery-receipts/new.json", {"state": "pending"}, "reserve")
        self.assertEqual(calls[0]["branch"], "automation-receipts")
        self.assertNotEqual(calls[0]["branch"], "main")


class ImmutableMediaTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        subprocess.run(["git", "init", "-q"], cwd=self.root, check=True)
        subprocess.run(["git", "config", "user.email", "tests@example.invalid"], cwd=self.root, check=True)
        subprocess.run(["git", "config", "user.name", "Offline Tests"], cwd=self.root, check=True)
        self.image_file = f"media/images/{CAMPAIGN}-branded.png"
        (self.root / "media/images").mkdir(parents=True)
        self.image = b"synthetic image bytes; no actual buffer call"
        (self.root / self.image_file).write_bytes(self.image)
        subprocess.run(["git", "add", self.image_file], cwd=self.root, check=True)
        subprocess.run(["git", "commit", "-qm", "immutable artwork"], cwd=self.root, check=True)
        self.commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=self.root, text=True).strip()
        (self.root / "campaign-manifests").mkdir()
        (self.root / "ready-for-buffer").mkdir()
        paths = {t: f"ready-for-buffer/auto-{CAMPAIGN}-{t}.json" for t in TARGETS}
        self.manifest = {"campaign_id": CAMPAIGN, "image": {
            "final": self.image_file, "sha256": hashlib.sha256(self.image).hexdigest()}, "posts": paths}
        (self.root / f"campaign-manifests/{CAMPAIGN}.json").write_text(json.dumps(self.manifest))
        self.posts = paths
        for target, file in paths.items():
            (self.root / file).write_text(json.dumps({"format_version": 2, "target": target,
                "text": "Synthetic", "media": {"type": "images", "images": [{
                    "url": assets.PREFIX + "main/" + self.image_file, "alt_text": "Synthetic"}]}}))

    def test_all_three_posts_pinned_to_committed_image_without_a_network_call(self):
        changed = assets.pin(CAMPAIGN, self.commit, self.root)
        self.assertEqual(set(changed), set(self.posts.values()))
        for file in changed:
            data = json.loads((self.root / file).read_text())
            url = data["media"]["images"][0]["url"]
            self.assertEqual(url, assets.PREFIX + self.commit + "/" + self.image_file)
            self.assertEqual(sender.validate_media_url(url, "images"), url)
        with self.assertRaisesRegex(ValueError, "bereits gepinnter"):
            assets.pin(CAMPAIGN, self.commit, self.root)

    def test_uncommitted_changed_image_is_rejected_without_partial_rewrite(self):
        (self.root / self.image_file).write_bytes(b"tampered image")
        before = [(self.root / p).read_bytes() for p in self.posts.values()]
        with self.assertRaisesRegex(ValueError, "nicht das geprüfte Bild"):
            assets.pin(CAMPAIGN, self.commit, self.root)
        self.assertEqual(before, [(self.root / p).read_bytes() for p in self.posts.values()])

    def test_bad_last_post_causes_no_partial_rewrite(self):
        instagram = self.root / self.posts["instagram"]
        obj = json.loads(instagram.read_text())
        obj["media"]["images"][0]["url"] = "https://attacker.invalid/image.png"
        instagram.write_text(json.dumps(obj))
        before = [(self.root / p).read_bytes() for p in self.posts.values()]
        with self.assertRaises(ValueError):
            assets.pin(CAMPAIGN, self.commit, self.root)
        self.assertEqual(before, [(self.root / p).read_bytes() for p in self.posts.values()])

    def test_ref_is_exact_sha_not_mutable_branch_or_truncated_hash(self):
        for bad in ("automation/campaign/abc", "deadbeef", "main/../../secret", "a"*39):
            with self.subTest(bad=bad):
                url = assets.PREFIX + bad + "/" + self.image_file
                with self.assertRaises(ValueError):
                    sender.validate_media_url(url, "images")

    def test_unverified_remote_bytes_fail_before_receipt(self):
        with mock.patch.object(sender, "ROOT", self.root):
            good = assets.PREFIX + self.commit + "/" + self.image_file
            fake_response = mock.MagicMock()
            fake_response.__enter__.return_value.read.return_value = b"wrong image"
            with mock.patch.object(sender.urllib.request, "urlopen", return_value=fake_response):
                with self.assertRaisesRegex(RuntimeError, "stimmt nicht"):
                    sender.verify_auto_image_bytes(self.posts["linkedin"], [{"image": {"url": good}}])

    def test_verified_remote_bytes_accept_only_same_fingerprint(self):
        with mock.patch.object(sender, "ROOT", self.root):
            good = assets.PREFIX + self.commit + "/" + self.image_file
            response = mock.MagicMock()
            response.__enter__.return_value.read.return_value = self.image
            with mock.patch.object(sender.urllib.request, "urlopen", return_value=response):
                sender.verify_auto_image_bytes(self.posts["linkedin"], [{"image": {"url": good}}])


class WorkflowBoundaryTests(unittest.TestCase):
    def test_bots_never_push_or_write_main_in_changed_workflows(self):
        root = Path(__file__).resolve().parents[1]
        for file in ("social-campaign-orchestrator.yml", "social-visual-brand-test.yml"):
            content = (root / ".github/workflows" / file).read_text()
            self.assertNotIn("git push origin HEAD:main", content)
        orchestrator = (root / ".github/workflows/social-campaign-orchestrator.yml").read_text()
        self.assertIn("git push origin \"HEAD:refs/heads/$branch\"", orchestrator)
        self.assertIn("-f content=\"$content\" -f branch=automation-receipts", orchestrator)
        self.assertIn("'orchestration/approvals/*.json'", orchestrator)
        self.assertIn('BRIEF="orchestration/briefs/$(basename "$changed_file")"', orchestrator)
        self.assertLess(orchestrator.index("--dated-draft"), orchestrator.index("scripts/campaign_reservations.py"))
        self.assertLess(orchestrator.index("scripts/campaign_reservations.py"), orchestrator.index("scripts/social_orchestrator.py --brief"))
        self.assertLess(orchestrator.index("git push origin \"HEAD:refs/heads/$branch\""),
                        orchestrator.index("python3 scripts/buffer_draft.py --draft"))


class PreviousReservationsTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.ref = reservations.REF_PREFIX + CAMPAIGN
        self.manifest = {"brand": "ai-agent-builder", "campaign_id": CAMPAIGN,
                         "posting_times": {t: {"utc": "2026-10-22T10:00:00Z",
                             "local": "2026-10-22T12:00:00+02:00"} for t in TARGETS}}
        self.raw = json.dumps(self.manifest).encode()

    def test_imports_old_campaign_slots_from_read_only_remote_ref(self):
        def git(root, *args):
            if args[0] == "for-each-ref":
                return (self.ref + "\n").encode()
            if args[0] == "show":
                return self.raw
            raise AssertionError(args)
        with mock.patch.object(reservations, "git_bytes", side_effect=git):
            files = reservations.import_manifests(self.root)
        self.assertEqual(files, [f"campaign-manifests/{CAMPAIGN}.json"])
        self.assertEqual((self.root / files[0]).read_bytes(), self.raw)

    def test_new_repo_with_zero_prior_campaigns_stays_empty(self):
        with mock.patch.object(reservations, "git_bytes", return_value=b""):
            self.assertEqual(reservations.import_manifests(self.root), [])

    def test_bad_branch_stops_without_creating_files(self):
        with mock.patch.object(reservations, "git_bytes", return_value=b"refs/remotes/origin/automation/campaign/invalid\n"):
            with self.assertRaisesRegex(ValueError, "Branch-ID"):
                reservations.import_manifests(self.root)
        self.assertFalse((self.root / "campaign-manifests").exists())

    def test_malformed_existing_slot_stops_before_write(self):
        bad = json.loads(self.raw)
        bad["posting_times"]["linkedin"]["local"] = "2026-10-22T12:00:00+01:00"
        with mock.patch.object(reservations, "git_bytes", side_effect=[
            (self.ref + "\n").encode(), json.dumps(bad).encode(),
        ]):
            with self.assertRaisesRegex(ValueError, "Zeitzone"):
                reservations.import_manifests(self.root)
        self.assertFalse((self.root / "campaign-manifests").exists())

    def test_correct_utc_but_wrong_berlin_wall_time_is_rejected(self):
        bad = json.loads(self.raw)
        bad["posting_times"]["facebook"]["local"] = "2026-10-22T11:00:00+01:00"
        with mock.patch.object(reservations, "git_bytes", side_effect=[
            (self.ref + "\n").encode(), json.dumps(bad).encode(),
        ]):
            with self.assertRaisesRegex(ValueError, "Zeitzone"):
                reservations.import_manifests(self.root)


if __name__ == "__main__":
    unittest.main()
