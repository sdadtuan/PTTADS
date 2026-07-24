"""Tests for Meta insights breakdown (B8.1)."""
from __future__ import annotations

import os
import unittest
from datetime import date
from unittest.mock import patch

from ptt_meta.graph_insights import stub_campaign_breakdown_insights
from ptt_meta.insights_breakdown import (
    meta_insights_breakdown_enabled,
    normalize_breakdown_row,
    query_breakdown_summary,
)


class TestBreakdownConfig(unittest.TestCase):
    def test_disabled_by_default(self) -> None:
        with patch.dict(os.environ, {"PTT_META_INSIGHTS_BREAKDOWN": "0"}, clear=False):
            self.assertFalse(meta_insights_breakdown_enabled())


class TestBreakdownMath(unittest.TestCase):
    def test_stub_platform_rows(self) -> None:
        rows = stub_campaign_breakdown_insights(
            since="2026-07-20",
            until="2026-07-20",
            ad_account_id="act_123",
            breakdown_type="publisher_platform",
        )
        self.assertEqual(len(rows), 2)
        spend = sum(float(r["spend"]) for r in rows)
        self.assertAlmostEqual(spend, 150_000, delta=1)

    def test_normalize_breakdown_row(self) -> None:
        row = normalize_breakdown_row(
            {
                "external_campaign_id": "camp_1",
                "performance_date": "2026-07-20",
                "publisher_platform": "facebook",
                "spend": 100_000,
                "impressions": 1000,
                "clicks": 20,
                "leads_platform": 2,
            },
            breakdown_type="publisher_platform",
        )
        assert row is not None
        self.assertEqual(row["breakdown_value"], "facebook")

    @patch("ptt_meta.insights_breakdown.list_breakdown_rows")
    @patch("ptt_meta.insights_breakdown.campaign_spend_total")
    @patch("ptt_meta.insights_breakdown.pg_daily_performance_breakdown_ready", return_value=True)
    def test_spend_delta_within_tolerance(self, _ready, mock_total, mock_rows) -> None:
        mock_rows.return_value = [
            {
                "client_id": "c1",
                "external_campaign_id": "camp_1",
                "performance_date": "2026-07-20",
                "breakdown_type": "publisher_platform",
                "breakdown_value": "facebook",
                "spend": 100_000,
                "impressions": 0,
                "clicks": 0,
                "leads_platform": 0,
            },
            {
                "client_id": "c1",
                "external_campaign_id": "camp_1",
                "performance_date": "2026-07-20",
                "breakdown_type": "publisher_platform",
                "breakdown_value": "instagram",
                "spend": 50_000,
                "impressions": 0,
                "clicks": 0,
                "leads_platform": 0,
            },
        ]
        mock_total.return_value = 150_000
        out = query_breakdown_summary(
            client_id="c1",
            external_campaign_id="camp_1",
            breakdown_type="publisher_platform",
            date_from=date(2026, 7, 20),
            date_to=date(2026, 7, 20),
        )
        self.assertEqual(out["breakdown_spend"], 150_000)
        self.assertEqual(out["total_spend"], 150_000)
        self.assertEqual(out["spend_delta_pct"], 0.0)


if __name__ == "__main__":
    unittest.main()
