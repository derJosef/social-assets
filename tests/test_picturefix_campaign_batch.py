"""PictureFix generic campaign runner: offline, zero external side effects."""

from datetime import datetime, timezone
import base64
import copy
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest import mock
from PIL import Image

from scripts.picturefix import campaign_batch_drafts as p
from scripts.picturefix import brand_artwork as branding


CLOCK = datetime(2026, 11, 20, 12, tzinfo=timezone.utc)
COMMIT = "d" * 40
DISCLOSURE = "KI-generierte Werbeillustration – kein tatsächliches Restaurierungsergebnis."
ALT = "KI-generierte Werbeillustration: historische Familie, die aus ihrem Foto tritt; kein Restaurierungsergebnis."


class CampaignTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        (self.root / "picturefix/campaigns").mkdir(parents=True)
        (self.root / "picturefix/quality").mkdir(parents=True)
        (self.root / "media/images").mkdir(parents=True)
        (self.root / "media/brand").mkdir(parents=True)
        canonical = Path(__file__).resolve().parents[1] / "media/brand/PictureFixLogo_Web.png"
        shutil.copyfile(canonical, self.root / "media/brand/PictureFixLogo_Web.png")
        self.env = {
            "GITHUB_REPOSITORY": "derJosef/social-assets", "GITHUB_REF": "refs/heads/main",
            "GITHUB_EVENT_NAME": "push", "GITHUB_RUN_ATTEMPT": "1",
            "GITHUB_ACTOR": "derJosef-agents", "GITHUB_ACTOR_ID": p.AGENT_ID,
            "GITHUB_SHA": COMMIT, "BUFFER_BRAND": "picturefix",
            "BUFFER_API_KEY": "test-buffer", "GITHUB_TOKEN": "test-github",
        }
        self.campaign_path = "picturefix/campaigns/PF-04.json"
        self.images = {}
        for kind, fname in (
            ("facebook_instagram", "PictureFix_PF04_Facebook_Instagram_1080x1350.png"),
            ("pinterest", "PictureFix_PF04_Pinterest_1000x1500.png"),
        ):
            file = self.root / "media/images" / fname
            source = self.root / ("source-" + kind + ".png")
            Image.new("RGB", (1000, 1500), "#827766").save(source)
            branding.compose(source, file, kind,
                             logo=self.root / "media/brand/PictureFixLogo_Web.png")
            self.images[kind] = {"path": "media/images/" + fname,
                                 "sha": hashlib.sha256(file.read_bytes()).hexdigest()}
        posts = {}
        for target, utc, local in (
            ("facebook", "2026-12-01T11:00:00Z", "2026-12-01T12:00:00+01:00"),
            ("instagram", "2026-12-01T17:00:00Z", "2026-12-01T18:00:00+01:00"),
            ("pinterest", "2026-12-03T09:00:00Z", "2026-12-03T10:00:00+01:00"),
        ):
            kind = "pinterest" if target == "pinterest" else "facebook_instagram"
            posts[target] = {
                "text": f"Eine Familiengeschichte aus alten Bildern. {DISCLOSURE} {target}",
                "alt_text": ALT,
                "image_path": self.images[kind]["path"],
                "image_sha256": self.images[kind]["sha"],
                "due_at_utc": utc,
                "due_at_local": local,
            }
            if target == "pinterest":
                posts[target].update({"pinterest_title": "Erinnerungen digital bewahren",
                                      "pinterest_url": "https://picturefix.de"})
        self.manifest = {
            "version": 1, "campaign_id": "PF-04", "brand": "picturefix",
            "topic_key": "familienfotos-archivieren-beispiel-2026",
            "topic": "Historische Erinnerungen und Familienbilder für nächste Generationen",
            "sources": [{"title": "Verifizierte fachliche Quelle", "url": "https://example.org/facts",
                         "accessed_at": "2026-11-20"}],
            "logo_git_blob_sha1": p.LOGO_BLOB,
            "creative_qa": "picturefix/quality/PF-04.json",
            "posts": posts,
        }
        self.qa = {
            "campaign_id": "PF-04", "real_picturefix_logo_blob_sha1": p.LOGO_BLOB,
            "historical_scene_pops_out": True,
            "period_accurate_faces_and_clothing": True,
            "ai_ad_illustration_not_a_restoration": True,
            "artwork_sha256": {
                "facebook_instagram": self.images["facebook_instagram"]["sha"],
                "pinterest": self.images["pinterest"]["sha"],
            },
        }
        self._write()

    def _write(self):
        (self.root / self.campaign_path).write_text(json.dumps(self.manifest), encoding="utf-8")
        (self.root / "picturefix/quality/PF-04.json").write_text(json.dumps(self.qa), encoding="utf-8")

    def test_valid_manifest_is_data_driven_for_three_platforms(self):
        record, items = p.load_campaign(self.campaign_path, COMMIT, now=CLOCK, root=self.root)
        self.assertEqual(record["campaign_id"], "PF-04")
        self.assertEqual([i["target"] for i in items], list(p.TARGETS))
        for item in items:
            self.assertEqual(item["assets"][0]["image"]["url"],
                             item["record"]["media"]["images"][0]["url"])
            self.assertIn("/" + COMMIT + "/", item["assets"][0]["image"]["url"])

    def test_only_original_agent_main_push_allowed(self):
        for key, value in (
            ("GITHUB_ACTOR", "derJosef"), ("GITHUB_ACTOR_ID", "350757945"),
            ("GITHUB_REF", "refs/heads/new-campaign"),
            ("GITHUB_EVENT_NAME", "pull_request"), ("GITHUB_RUN_ATTEMPT", "2"),
            ("GITHUB_SHA", "main"),
        ):
            with self.subTest(key=key), self.assertRaises(p.CampaignBlocked):
                p.authenticate_push({**self.env, key: value})

    def test_only_one_added_manifest_two_images_one_qa_allowed(self):
        files = [self.campaign_path, *[v["path"] for v in self.images.values()],
                 "picturefix/quality/PF-04.json"]
        diff = "".join(f"A\t{file}\n" for file in files)
        self.assertEqual(p.select_new_manifest(diff), self.campaign_path)
        for bad in (
            diff.replace("A\t", "M\t", 1),
            diff + "A\t.github/workflows/other.yml\n",
            diff + "A\tpicturefix/campaigns/PF-05.json\n",
            diff.replace("A\tmedia/images/PictureFix_PF04_Pinterest_1000x1500.png\n", ""),
        ):
            with self.subTest(bad=bad), self.assertRaises(p.CampaignBlocked):
                p.select_new_manifest(bad)

    def test_no_disclosure_provenance_or_corrupt_image(self):
        cases = [
            ("text", lambda: self.manifest["posts"]["facebook"].update(text="Ein alter Familientag – ohne Hinweis auf die Werbung.")),
            ("alt", lambda: self.manifest["posts"]["pinterest"].update(alt_text="Ein schönes Bild")),
            ("logo", lambda: self.qa.update(real_picturefix_logo_blob_sha1="f" * 40)),
            ("sha", lambda: self.manifest["posts"]["facebook"].update(image_sha256="0" * 64)),
            ("date", lambda: self.manifest["posts"]["facebook"].update(due_at_local="2026-12-01T12:00:00Z")),
            ("expired", lambda: self.manifest["posts"]["instagram"].update(due_at_utc="2026-11-20T12:10:00Z")),
            ("insecure", lambda: self.manifest["posts"]["pinterest"].update(pinterest_url="https://evil.example")),
            ("style", lambda: self.qa.update(period_accurate_faces_and_clothing=False)),
        ]
        for name, change in cases:
            with self.subTest(name=name):
                original, qa_original = copy.deepcopy(self.manifest), copy.deepcopy(self.qa)
                try:
                    change()
                    self._write()
                    with self.assertRaises(p.CampaignBlocked):
                        p.load_campaign(self.campaign_path, COMMIT, now=CLOCK, root=self.root)
                finally:
                    self.manifest, self.qa = original, qa_original
                    self._write()

    def test_authentic_logo_pixel_integrity_is_required(self):
        output = self.root / self.images["pinterest"]["path"]
        with Image.open(output) as image:
            image = image.convert("RGBA")
            image.putpixel((38, 55), (255, 1, 1, 255))
            image.save(output)
        # Even if an attacker adjusts the hash in the manifest and QA,
        # the approved real-logo imprint will still fail.
        new_sha = hashlib.sha256(output.read_bytes()).hexdigest()
        self.manifest["posts"]["pinterest"]["image_sha256"] = new_sha
        self.qa["artwork_sha256"]["pinterest"] = new_sha
        self._write()
        with self.assertRaises(ValueError):
            p.load_campaign(self.campaign_path, COMMIT, now=CLOCK, root=self.root)

    def test_text_transport_restores_exact_approved_logo_bytes(self):
        canonical = Path(__file__).resolve().parents[1] / "media/brand/PictureFixLogo_Web.png"
        transport = Path(__file__).resolve().parents[1] / "media/brand/PictureFixLogo_Web.b64"
        from scripts.picturefix.brand_artwork import load_canonical_logo
        self.assertEqual(load_canonical_logo(canonical).tobytes(),
                         load_canonical_logo(transport).tobytes())
        source = self.root / "source-facebook_instagram.png"
        output = self.root / "media/images/test-branded-from-text.png"
        branding.compose(source, output, "facebook_instagram", logo=transport)
        branding.verify_imprint(output, "facebook_instagram", logo=canonical)
        invalid = self.root / "corrupted-logo.b64"
        invalid.write_text("AAAA", encoding="ascii")
        with self.assertRaises(ValueError):
            load_canonical_logo(invalid)

    def _simulate(self, *, existing=None, fail_on_target=None, bad_read=False):
        _, prepared = p.load_campaign(self.campaign_path, COMMIT, now=CLOCK, root=self.root)
        expected = {i["target"]: i["record"] for i in prepared}
        channels = {x: "channel-" + x for x in p.TARGETS}
        queries, writes, ledger, by_id = [], [], {}, {}
        if existing:
            for target, state in existing.items():
                item = next(i for i in prepared if i["target"] == target)
                path = p.bridge.receipt_path(item["receipt_key"])
                receipt = {
                    "state": state, "campaign": "PF-04", "target": target,
                    "manifest_path": self.campaign_path,
                    "media_sha256": item["record"]["image_sha256"],
                    "buffer_post_id": "a" * 24,
                }
                ledger[path] = {"content": base64.b64encode(json.dumps(receipt).encode()).decode()}
                by_id["a" * 24] = (target, expected[target])

        def query(_token, operation, vars):
            queries.append((operation, vars))
            if "mutation CreateDatedDraft" in operation:
                target = vars["channelId"].removeprefix("channel-")
                if target == fail_on_target:
                    return {"createPost": {"message": "timeout"}}
                post_id = ("0123456789abcdef0000000" + str(len(by_id) + 1))[-24:]
                by_id[post_id] = (target, expected[target])
                return {"createPost": {"post": {
                    "id": post_id, "channelId": channels[target], "status": "draft",
                    "dueAt": expected[target]["due_at_utc"],
                }}}
            target, record = by_id[vars["id"]]
            return {"post": {
                "id": vars["id"], "channelId": channels[target],
                "channelService": target, "status": "queued" if bad_read else "draft",
                "dueAt": record["due_at_utc"], "text": record["text"],
                "shareMode": "customScheduled", "schedulingType": "automatic",
                "assets": [{"type": "image", "source": record["media"]["images"][0]["url"]}],
            }}

        def fetch(_token, path):
            return ledger.get(path)

        def put(_token, path, data, _message, sha=None):
            writes.append((path, copy.deepcopy(data)))
            ledger[path] = {"content": base64.b64encode(json.dumps(data).encode()).decode()}
            return "receipt-sha"

        with mock.patch.object(p.bridge, "normalize_picturefix_api_key", side_effect=lambda t: t), \
             mock.patch.object(p.bridge, "discover_picturefix_channels", return_value=channels), \
             mock.patch.object(p.bridge, "discover_picturefix_board", return_value="pinterest-board"), \
             mock.patch.object(p.bridge, "verify_media_access") as access, \
             mock.patch.object(p.bridge, "verify_picturefix_image_bytes") as check:
            def run():
                return p.send_batch(self.campaign_path, env=self.env, now=CLOCK, root=self.root,
                                    query=query, get_receipt=fetch, put_receipt=put)
            if fail_on_target or bad_read or (existing and "pending_manual_reconciliation_on_failure" in existing.values()):
                with self.assertRaises(p.CampaignBlocked):
                    run()
                ids = None
            else:
                ids = run()
            self.assertEqual(access.call_count, 3)
            self.assertEqual(check.call_count, 3)
        return ids, queries, writes

    def test_three_drafts_are_reserved_then_independently_verified(self):
        ids, queries, writes = self._simulate()
        self.assertEqual(len(ids), 3)
        self.assertEqual(len(set(ids)), 3)
        self.assertEqual(len(queries), 6)
        self.assertEqual(len(writes), 9)
        for index in (0, 3, 6):
            self.assertEqual(writes[index][1]["state"], "pending_manual_reconciliation_on_failure")
            self.assertEqual(writes[index + 2][1]["state"],
                             "verified_prescheduled_draft_not_queued_with_image")
        for operation, vars in queries[::2]:
            self.assertIn("saveToDraft: true", operation)
            self.assertIn("mode: customScheduled", operation)
            self.assertNotIn("shareNow", operation)
            self.assertEqual(vars["metadata"] is None, False)

    def test_verified_receipt_skips_buffer_creation_after_independent_read(self):
        ids, queries, writes = self._simulate(existing={"facebook": "verified_prescheduled_draft_not_queued_with_image"})
        self.assertEqual(len(ids), 3)
        self.assertEqual(sum("mutation CreateDatedDraft" in op for op, _ in queries), 2)
        self.assertEqual(len(writes), 6)

    def test_pending_receipt_stops_before_all_mutations(self):
        _, queries, writes = self._simulate(existing={"facebook": "pending_manual_reconciliation_on_failure"})
        self.assertEqual(queries, [])
        self.assertEqual(writes, [])

    def test_failure_is_not_retried_and_keeps_reservation(self):
        _, queries, writes = self._simulate(fail_on_target="instagram")
        self.assertEqual(sum("mutation CreateDatedDraft" in op for op, _ in queries), 2)
        self.assertEqual(writes[-1][1]["state"], "pending_manual_reconciliation_on_failure")

    def test_bad_independent_read_fails_closed(self):
        _, queries, writes = self._simulate(bad_read=True)
        self.assertEqual(len(queries), 2)
        self.assertEqual(writes[-1][1]["state"], "created_requires_independent_check")


if __name__ == "__main__":
    unittest.main()
