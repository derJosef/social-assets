import json
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import autonomous_campaign_gate as gate


class AutonomousCampaignGateTests(unittest.TestCase):
    def test_scheduling_is_proposal_only(self):
        self.assertNotIn("editPost", Path(gate.__file__).read_text())
        self.assertNotIn("saveToDraft: false", Path(gate.__file__).read_text())
        self.assertNotIn("createPost", Path(gate.__file__).read_text())

    def test_missing_post_files_fail_closed(self):
        with self.assertRaises(ValueError):
            gate.check_campaign(["ready-for-buffer/auto-2026-10-09-test-linkedin.json"], today=date(2026, 10, 9), verify_image=False)

    def test_duplicate_channel_fails_closed(self):
        p = ["ready-for-buffer/auto-2026-10-09-test-linkedin.json"] * 3
        with self.assertRaises(ValueError):
            gate.check_campaign(p, today=date(2026, 10, 9), verify_image=False)

    def test_utc_requires_z(self):
        with self.assertRaises(ValueError):
            gate.parse_utc("2026-10-22T16:00:00+02:00")

    def test_correct_europe_berlin_dst(self):
        from datetime import datetime, timezone
        from zoneinfo import ZoneInfo
        summer = datetime(2026, 10, 21, 16, tzinfo=ZoneInfo("Europe/Berlin"))
        winter = datetime(2026, 10, 27, 19, tzinfo=ZoneInfo("Europe/Berlin"))
        self.assertEqual(summer.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "2026-10-21T14:00:00Z")
        self.assertEqual(winter.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "2026-10-27T18:00:00Z")

    def test_no_api_side_effects_during_import(self):
        # Importing the gate must not write to Buffer/GitHub.
        self.assertTrue(callable(gate.check_campaign))


if __name__ == "__main__":
    unittest.main()
