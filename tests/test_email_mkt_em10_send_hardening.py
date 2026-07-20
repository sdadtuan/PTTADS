#!/usr/bin/env python3
"""Unit tests — EM-10 Send hardening (eligibility + schedule)."""
from __future__ import annotations

import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from ptt_email.eligibility import in_quiet_hours, next_send_after_quiet_hours


class QuietHoursTests(unittest.TestCase):
    def test_in_quiet_hours_overnight_window(self) -> None:
        cfg = {"start": "22:00", "end": "07:00", "timezone": "Asia/Ho_Chi_Minh"}
        late = datetime(2026, 7, 20, 23, 0, tzinfo=timezone.utc)
        self.assertTrue(in_quiet_hours(now=late, quiet_config=cfg, workspace_tz="Asia/Ho_Chi_Minh"))

    def test_outside_quiet_hours(self) -> None:
        cfg = {"start": "22:00", "end": "07:00", "timezone": "Asia/Ho_Chi_Minh"}
        midday = datetime(2026, 7, 20, 4, 0, tzinfo=timezone.utc)
        self.assertFalse(in_quiet_hours(now=midday, quiet_config=cfg, workspace_tz="Asia/Ho_Chi_Minh"))

    def test_next_send_after_quiet_hours_future(self) -> None:
        cfg = {"start": "22:00", "end": "07:00", "timezone": "Asia/Ho_Chi_Minh"}
        late = datetime(2026, 7, 20, 16, 0, tzinfo=timezone.utc)
        nxt = next_send_after_quiet_hours(now=late, quiet_config=cfg, workspace_tz="Asia/Ho_Chi_Minh")
        self.assertGreater(nxt, late)


class FrequencyCapTests(unittest.TestCase):
    @patch("ptt_email.eligibility.SCHEMA", "email_mkt")
    def test_contact_over_frequency_cap(self) -> None:
        from ptt_email.eligibility import contact_over_frequency_cap

        cur = MagicMock()
        cur.fetchone.return_value = (5,)
        self.assertTrue(contact_over_frequency_cap(cur, "contact-1", 5))
        cur.fetchone.return_value = (2,)
        self.assertFalse(contact_over_frequency_cap(cur, "contact-1", 5))


class ScheduleDueTests(unittest.TestCase):
    @patch("ptt_email.campaign_schedule.pg_connection")
    def test_run_due_no_campaigns(self, mock_pg) -> None:
        from ptt_email.campaign_schedule import run_due_scheduled_campaigns

        conn = mock_pg.return_value.__enter__.return_value
        cur = conn.cursor.return_value.__enter__.return_value
        cur.fetchall.return_value = []
        out = run_due_scheduled_campaigns()
        self.assertTrue(out["ok"])
        self.assertEqual(out["processed"], 0)


if __name__ == "__main__":
    unittest.main()
