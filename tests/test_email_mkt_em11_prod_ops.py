#!/usr/bin/env python3
"""Unit tests — EM-11 prod ops (cron enqueue, journey helpers, RBAC seed)."""
from __future__ import annotations

import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from ptt_email.campaign_schedule import enqueue_due_scheduled_campaigns
from ptt_email.eligibility import in_quiet_hours
from ptt_email.journey_engine import _next_step_key, enqueue_journey_cron_jobs


class CampaignScheduleCronTests(unittest.TestCase):
    @patch("ptt_jobs.enqueue.enqueue_job")
    def test_enqueue_due_scheduled_campaigns(self, mock_enqueue) -> None:
        mock_enqueue.return_value = {"id": "job-1"}
        out = enqueue_due_scheduled_campaigns()
        self.assertTrue(out["ok"])
        self.assertEqual(out["mode"], "queue")
        mock_enqueue.assert_called_once()
        args = mock_enqueue.call_args[0]
        self.assertEqual(args[0], "email_campaign_schedule_due")


class JourneyGraphTests(unittest.TestCase):
    def test_next_step_via_edges(self) -> None:
        graph = {
            "nodes": [
                {"id": "t1", "type": "trigger"},
                {"id": "s1", "type": "send"},
                {"id": "x1", "type": "exit"},
            ],
            "edges": [
                {"from": "t1", "to": "s1"},
                {"from": "s1", "to": "x1"},
            ],
        }
        self.assertEqual(_next_step_key(graph, None), "s1")
        self.assertEqual(_next_step_key(graph, "s1"), "x1")

    @patch("ptt_jobs.enqueue.enqueue_job")
    def test_enqueue_journey_cron(self, mock_enqueue) -> None:
        mock_enqueue.return_value = {"id": "j1"}
        out = enqueue_journey_cron_jobs()
        self.assertTrue(out["ok"])
        self.assertEqual(mock_enqueue.call_count, 3)
        job_types = [call.args[0] for call in mock_enqueue.call_args_list]
        self.assertIn("email_journey_enroll_scan", job_types)
        self.assertIn("email_journey_tick", job_types)
        self.assertIn("email_journey_trigger_events", job_types)


class EspConfigTests(unittest.TestCase):
    def test_esp_dry_run_off_when_env_zero(self) -> None:
        import os
        from ptt_email.config import email_esp_dry_run

        with patch.dict(os.environ, {"PTT_EMAIL_ESP_DRY_RUN": "0", "PTT_EMAIL_SEND_ENABLED": "1"}):
            self.assertFalse(email_esp_dry_run())


if __name__ == "__main__":
    unittest.main()
