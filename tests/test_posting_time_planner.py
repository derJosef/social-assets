"""Deterministic, network-free posting-time proposal checks."""

import importlib.util
import json
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo


SOURCE = Path(__file__).resolve().parents[1] / "scripts" / "posting_time_planner.py"
spec = importlib.util.spec_from_file_location("posting_time_planner_tested", SOURCE)
planner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(planner)


class PostingTimePlannerTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        (self.root / "campaign-manifests").mkdir()
        (self.root / "ready-to-schedule").mkdir()
        self.today = date(2026, 10, 11)

    def propose(self, today=None):
        return planner.propose_times(today or self.today, self.root)

    def book(self, target, utc, filename="existing-request.json"):
        request = {"target": target, "publish_at_utc": utc,
                   "draft_file": "ready-for-buffer/previous.json",
                   "approved_for_scheduling": True}
        (self.root / "ready-to-schedule" / filename).write_text(json.dumps(request))

    def reserve_manifest(self, target, utc, filename="prior.json"):
        manifest = {"posting_times": {target: {"local": "unused-by-reservation-reader", "utc": utc}}}
        (self.root / "campaign-manifests" / filename).write_text(json.dumps(manifest))

    def test_research_backed_slots_without_bookings(self):
        result = self.propose()
        self.assertEqual(result["linkedin"]["local"], "2026-10-21T16:00:00+02:00")
        self.assertEqual(result["facebook"]["local"], "2026-10-22T09:00:00+02:00")
        self.assertEqual(result["instagram"]["local"], "2026-10-21T18:00:00+02:00")
        self.assertEqual(result["instagram"]["utc"], "2026-10-21T16:00:00Z")

    def test_approved_schedule_is_not_overwritten_or_clashed(self):
        before = json.dumps({"target": "linkedin", "publish_at_utc": "2026-10-21T14:00:00Z",
                             "approved_for_scheduling": True})
        file = self.root / "ready-to-schedule/prior.json"
        file.write_text(before)
        result = self.propose()
        # A nearby, research-supported Friday slot avoids the booked Wednesday.
        self.assertEqual(result["linkedin"]["local"], "2026-10-16T15:00:00+02:00")
        self.assertEqual(file.read_text(), before)

    def test_manifest_proposals_also_reserve_times(self):
        self.reserve_manifest("facebook", "2026-10-22T07:00:00Z")
        result = self.propose()
        self.assertNotEqual(result["facebook"]["utc"], "2026-10-22T07:00:00Z")
        self.assertEqual(result["linkedin"]["utc"], "2026-10-21T14:00:00Z")

    def test_channels_do_not_delay_each_other_by_weeks(self):
        self.reserve_manifest("linkedin", "2026-12-02T15:00:00Z")
        result = self.propose()
        self.assertEqual(result["facebook"]["utc"], "2026-10-22T07:00:00Z")
        self.assertLess(datetime.fromisoformat(result["linkedin"]["local"]).date(), date(2026, 11, 1))

    def test_daylight_saving_switch_to_winter(self):
        result = self.propose(date(2026, 10, 20))
        self.assertEqual(result["linkedin"], {
            "local": "2026-10-28T16:00:00+01:00", "utc": "2026-10-28T15:00:00Z"})
        for item in result.values():
            local = datetime.fromisoformat(item["local"])
            utc = datetime.fromisoformat(item["utc"].replace("Z", "+00:00"))
            self.assertEqual(utc, local.astimezone(timezone.utc))
            self.assertEqual(utc.astimezone(ZoneInfo("Europe/Berlin")), local)

    def test_daylight_saving_summer(self):
        result = self.propose(date(2027, 3, 23))
        self.assertTrue(all("+02:00" in item["local"] for item in result.values()))

    def test_every_slot_has_five_day_review_lead_and_max_35_days(self):
        result = self.propose()
        for item in result.values():
            local = datetime.fromisoformat(item["local"])
            self.assertGreaterEqual(local.date(), self.today + timedelta(days=5))
            self.assertLessEqual(local.date(), self.today + timedelta(days=35))

    def test_three_days_channel_spacing(self):
        self.reserve_manifest("instagram", "2026-10-23T16:00:00Z")
        result = self.propose()
        selected = datetime.fromisoformat(result["instagram"]["utc"].replace("Z", "+00:00"))
        previous = datetime(2026, 10, 23, 16, tzinfo=timezone.utc)
        self.assertGreaterEqual(abs(selected - previous), timedelta(days=3))

    def test_duplicate_manifest_json_keys_fail_closed(self):
        (self.root / "campaign-manifests/prior.json").write_text(
            '{"posting_times":{},"posting_times":{}}')
        with self.assertRaisesRegex(planner.TimePlanningBlocked, "Doppelter"):
            self.propose()

    def test_invalid_scheduling_request_time_fails_closed(self):
        self.book("facebook", "2026-10-22T07:00:00+00:00")
        with self.assertRaisesRegex(planner.TimePlanningBlocked, "ISO-8601"):
            self.propose()

    def test_unparseable_manifest_time_fails_closed(self):
        self.reserve_manifest("linkedin", "unleserlich")
        with self.assertRaisesRegex(planner.TimePlanningBlocked, "ISO-8601"):
            self.propose()

    def test_cannot_accept_datetime_as_today(self):
        with self.assertRaisesRegex(planner.TimePlanningBlocked, "Datum"):
            planner.propose_times(datetime(2026, 10, 11, tzinfo=timezone.utc), self.root)

    def test_no_writes_or_network_imports(self):
        before = sorted(p.relative_to(self.root) for p in self.root.rglob("*") if p.is_file())
        self.propose()
        after = sorted(p.relative_to(self.root) for p in self.root.rglob("*") if p.is_file())
        self.assertEqual(before, after)
        text = SOURCE.read_text()
        for prohibited in ("urllib.request", "requests.post(", "createPost(", "editPost("):
            self.assertNotIn(prohibited, text)


if __name__ == "__main__":
    unittest.main()
