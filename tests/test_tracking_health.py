"""Tests for B9 tracking_health aggregates."""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from ptt_meta.tracking_health import tracking_health


class TestTrackingHealth(unittest.TestCase):
    @patch("ptt_meta.tracking_health.list_tracking_accounts")
    @patch("ptt_meta.tracking_health.capi_stats")
    @patch("ptt_meta.tracking_health.pg_capi_ready", return_value=True)
    def test_tracking_health_shape(
        self,
        _ready: MagicMock,
        mock_stats: MagicMock,
        mock_accounts: MagicMock,
    ) -> None:
        mock_stats.return_value = {
            "ok": True,
            "sent": 10,
            "failed": 2,
            "skipped": 1,
            "pending": 0,
            "fail_rate_pct": 16.7,
            "match_hint_pct": 83.3,
            "avg_latency_ms": 120.5,
            "by_status": {"sent": 10, "failed": 2},
        }
        mock_accounts.return_value = [
            {
                "client_id": "c1",
                "channel_account_id": "a1",
                "pixel_id": "px",
                "page_id": None,
                "capi_enabled": True,
                "last_sent_at": None,
                "pixel_test_ok": None,
            }
        ]
        out = tracking_health(client_id="c1", window_days=7)
        self.assertTrue(out.get("ok"))
        self.assertEqual(out.get("window_days"), 7)
        self.assertEqual(out["global"]["sent"], 10)
        self.assertEqual(len(out["accounts"]), 1)
        self.assertEqual(out.get("attribution_model"), "last_touch_crm")


if __name__ == "__main__":
    unittest.main()
