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
        self.today = date(2026, 10, 12)

    def propose(self, today=None):
        return planner.propose_times(today or self.today, self.root,
                                     research_checked_at=date(2026, 10, 12))

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

    def test_old_approved_request_does_not_claim_live_occupancy(self):
        before = json.dumps({"target": "linkedin", "publish_at_utc": "2026-10-21T14:00:00Z",
                             "approved_for_scheduling": True})
        file = self.root / "ready-to-schedule/prior.json"
        file.write_text(before)
        result = self.propose()
        # A GitHub approval is not confirmation that a post is still in Buffer.
        self.assertEqual(result["linkedin"]["local"], "2026-10-21T16:00:00+02:00")
        self.assertEqual(file.read_text(), before)

    def test_unactivated_manifest_proposals_do_not_reserve_times(self):
        self.reserve_manifest("facebook", "2026-10-22T07:00:00Z")
        result = self.propose()
        self.assertEqual(result["facebook"]["utc"], "2026-10-22T07:00:00Z")
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
        result = planner.propose_times(date(2027, 3, 23), self.root,
                                       research_checked_at=date(2027, 3, 22))
        self.assertTrue(all("+02:00" in item["local"] for item in result.values()))

    def test_every_slot_has_five_day_review_lead_and_max_21_days(self):
        result = self.propose()
        for item in result.values():
            local = datetime.fromisoformat(item["local"])
            self.assertGreaterEqual(local.date(), self.today + timedelta(days=5))
            self.assertLessEqual(local.date(), self.today + timedelta(days=21))

    def test_verified_buffer_queue_enforces_gap_without_ghost_reservations(self):
        # Only dates independently confirmed as scheduled in Buffer may block.
        busy = (
            "2026-10-21T14:00:00Z",
            "2026-10-28T15:00:00Z",
            "2026-11-04T15:00:00Z",
        )
        for i, utc in enumerate(busy):
            self.reserve_manifest("linkedin", utc, filename=f"existing-{i}.json")
        today = date(2026, 10, 16)
        chosen = planner.propose_times(today, self.root,
                                        research_checked_at=date(2026, 10, 12),
                                        verified_buffer_slots={"linkedin": list(busy[:1])})
        self.assertEqual(chosen["linkedin"]["local"], "2026-10-28T16:00:00+01:00")
        expected = datetime(2026, 10, 28, 15, tzinfo=timezone.utc)
        for utc in busy[:1]:
            occupied = datetime.fromisoformat(utc.replace("Z", "+00:00"))
            self.assertGreaterEqual(abs(expected - occupied), timedelta(days=3))
        # No cross-channel delay: use normal, close-in Facebook/Instagram slots.
        self.assertLessEqual(datetime.fromisoformat(chosen["facebook"]["local"]).date(),
                             today + timedelta(days=21))
        self.assertLessEqual(datetime.fromisoformat(chosen["instagram"]["local"]).date(),
                             today + timedelta(days=21))

    def test_live_queue_filling_21_day_horizon_blocks_instead_of_waiting_months(self):
        today = date(2026, 10, 16)
        earliest = today + timedelta(days=planner.MIN_REVIEW_DAYS)
        cutoff = today + timedelta(days=planner.MAX_LOOKAHEAD_DAYS)
        slots = []
        for day_offset in range((cutoff - earliest).days + 1):
            day = earliest + timedelta(days=day_offset)
            if day.weekday() in {x[0] for x in planner.SLOTS["linkedin"]}:
                when = datetime.combine(day, datetime.min.time().replace(hour=16),
                                        tzinfo=ZoneInfo("Europe/Berlin"))
                utc = when.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                slots.append(utc)
        with self.assertRaisesRegex(planner.TimePlanningBlocked, "21 Tagen"):
            planner.propose_times(today, self.root,
                                  research_checked_at=date(2026, 10, 12),
                                  verified_buffer_slots={"linkedin": slots})

    def test_three_days_channel_spacing(self):
        self.reserve_manifest("instagram", "2026-10-23T16:00:00Z")
        result = planner.propose_times(self.today, self.root,
                     research_checked_at=date(2026, 10, 12),
                     verified_buffer_slots={"instagram": ["2026-10-23T16:00:00Z"]})
        selected = datetime.fromisoformat(result["instagram"]["utc"].replace("Z", "+00:00"))
        previous = datetime(2026, 10, 23, 16, tzinfo=timezone.utc)
        self.assertGreaterEqual(abs(selected - previous), timedelta(days=3))

    def test_live_december_schedule_moves_only_occupied_channel_slots(self):
        result = planner.propose_times(date(2026, 11, 24), self.root,
                     research_checked_at=date(2026, 11, 20),
                     verified_buffer_slots={"linkedin": ["2026-12-02T15:00:00Z"]})
        self.assertEqual(result["linkedin"]["local"], "2026-12-09T16:00:00+01:00")
        self.assertEqual(result["instagram"]["local"], "2026-12-02T18:00:00+01:00")
        self.assertEqual(result["facebook"]["local"], "2026-12-03T09:00:00+01:00")

    def test_invalid_live_buffer_channel_fails_closed(self):
        with self.assertRaisesRegex(planner.TimePlanningBlocked, "ungültige Kanäle"):
            planner.propose_times(self.today, self.root,
                    research_checked_at=date(2026, 10, 12),
                    verified_buffer_slots={"pinterest": ["2026-10-22T07:00:00Z"]})

    def test_explicit_blackout_moves_only_the_affected_date(self):
        result = planner.propose_times(date(2026, 11, 24), self.root,
                     research_checked_at=date(2026, 11, 20),
                     blackouts=frozenset({date(2026, 12, 2)}))
        self.assertNotEqual(result["linkedin"]["local"][:10], "2026-12-02")
        self.assertNotEqual(result["instagram"]["local"][:10], "2026-12-02")
        self.assertEqual(result["facebook"]["local"], "2026-12-03T09:00:00+01:00")

    def test_duplicate_unactivated_manifest_keys_are_irrelevant(self):
        (self.root / "campaign-manifests/prior.json").write_text(
            '{"posting_times":{},"posting_times":{}}')
        self.assertEqual(self.propose()["linkedin"]["local"], "2026-10-21T16:00:00+02:00")

    def test_stale_scheduling_request_is_not_live_queue(self):
        self.book("facebook", "2026-10-22T07:00:00+00:00")
        self.assertEqual(self.propose()["facebook"]["utc"], "2026-10-22T07:00:00Z")

    def test_invalid_confirmed_buffer_timestamp_fails_closed(self):
        self.reserve_manifest("linkedin", "unleserlich")
        with self.assertRaisesRegex(planner.TimePlanningBlocked, "ISO-8601"):
            planner.propose_times(self.today, self.root,
                    research_checked_at=date(2026, 10, 12),
                    verified_buffer_slots={"linkedin": ["unleserlich"]})

    def test_cannot_accept_datetime_as_today(self):
        with self.assertRaisesRegex(planner.TimePlanningBlocked, "Datum"):
            planner.propose_times(datetime(2026, 10, 11, tzinfo=timezone.utc), self.root)

    def test_two_independent_studies_are_recorded_per_channel(self):
        for target in planner.TARGETS:
            urls = planner.RESEARCH_URLS[target]
            self.assertEqual(len(urls), 2)
            self.assertTrue(any("buffer.com" in url for url in urls))
            self.assertTrue(any("sproutsocial.com" in url for url in urls))
        self.assertEqual(planner.RESEARCH_CHECKED_AT, date(2026, 11, 20))
        self.assertEqual(planner.SLOTS["linkedin"][0], (2, 16))
        self.assertEqual(planner.SLOTS["instagram"][0], (2, 18))

    def test_current_november_research_supports_upcoming_slots(self):
        result = planner.propose_times(date(2026, 11, 20), self.root)
        for item in result.values():
            self.assertIn("+01:00", item["local"])
            self.assertGreaterEqual(datetime.fromisoformat(item["local"]).date(),
                                    date(2026, 11, 25))

    def test_no_blanket_year_end_pause_without_explicit_blackout(self):
        self.assertTrue(planner.editorial_day_allowed(date(2026, 12, 23)))
        self.assertTrue(planner.editorial_day_allowed(date(2026, 12, 24)))
        self.assertTrue(planner.editorial_day_allowed(date(2026, 12, 31)))
        self.assertTrue(planner.editorial_day_allowed(date(2027, 1, 6)))
        self.assertTrue(planner.editorial_day_allowed(date(2027, 1, 10)))
        self.assertFalse(planner.editorial_day_allowed(
            date(2026, 12, 23), blackouts=frozenset({date(2026, 12, 23)})))
        self.assertTrue(planner.editorial_day_allowed(date(2027, 1, 11)))
        self.assertTrue(planner.editorial_day_allowed(date(2027, 1, 13)))
        self.assertTrue(planner.editorial_day_allowed(date(2027, 12, 20)))

    def test_november_ghost_reservations_no_longer_yield_january(self):
        # These were historical suggestions, not evidence of a live queue.
        reserved = {
            "linkedin": ["2026-11-18T15:00:00Z", "2026-11-25T15:00:00Z",
                         "2026-12-02T15:00:00Z", "2026-12-09T15:00:00Z",
                         "2026-12-16T15:00:00Z"],
            "facebook": ["2026-11-19T08:00:00Z", "2026-11-24T18:00:00Z",
                         "2026-12-03T08:00:00Z", "2026-12-08T18:00:00Z",
                         "2026-12-17T08:00:00Z"],
            "instagram": ["2026-11-18T17:00:00Z", "2026-11-25T17:00:00Z",
                          "2026-12-02T17:00:00Z", "2026-12-09T17:00:00Z",
                          "2026-12-16T17:00:00Z"],
        }
        for target, times in reserved.items():
            for i, utc in enumerate(times):
                self.reserve_manifest(target, utc, filename=f"{target}-{i}.json")
        result = planner.propose_times(date(2026, 11, 23), self.root,
                                       research_checked_at=date(2026, 11, 20))
        self.assertEqual(result["linkedin"]["local"], "2026-12-02T16:00:00+01:00")
        self.assertEqual(result["facebook"]["local"], "2026-12-03T09:00:00+01:00")
        self.assertEqual(result["instagram"]["local"], "2026-12-02T18:00:00+01:00")

    def test_research_older_than_thirty_days_blocks_before_planning(self):
        with self.assertRaisesRegex(planner.TimePlanningBlocked, "30 Tage"):
            planner.propose_times(date(2026, 12, 21), self.root)
        with self.assertRaisesRegex(planner.TimePlanningBlocked, "aus der Zukunft"):
            planner.propose_times(date(2026, 11, 19), self.root)

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
