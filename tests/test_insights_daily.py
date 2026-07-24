"""Tests for B10 daily insights helpers."""
from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from ptt_meta.insights_daily import VALID_LEVELS, fetch_daily_insights, insights_level_enabled


class TestInsightsDailyConfig(unittest.TestCase):
    def test_default_level_campaign(self) -> None:
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("PTT_META_INSIGHTS_LEVEL", None)
            self.assertEqual(insights_level_enabled(), "campaign")

    def test_valid_levels(self) -> None:
        self.assertIn("adset", VALID_LEVELS)


class TestInsightsDailyFetch(unittest.TestCase):
    @patch("ptt_meta.insights_daily.pg_insight_level_column_ready", return_value=False)
    def test_adset_disabled_without_ddl(self, _ready: unittest.mock.MagicMock) -> None:
        with patch.dict(os.environ, {"PTT_META_INSIGHTS_LEVEL": "adset"}, clear=False):
            out = fetch_daily_insights(level="adset")
        self.assertTrue(out.get("disabled"))
        self.assertEqual(out.get("reason"), "insight_level_column_not_ready")

    @patch("ptt_meta.insights_daily.pg_connection")
    @patch("ptt_meta.insights_daily.pg_insight_level_column_ready", return_value=True)
    def test_campaign_fetch(self, _ready: unittest.mock.MagicMock, mock_pg: unittest.mock.MagicMock) -> None:
        cur = unittest.mock.MagicMock()
        cur.description = [
            ("client_id",),
            ("client_code",),
            ("client_name",),
            ("external_campaign_id",),
            ("external_campaign_name",),
            ("performance_date",),
            ("spend",),
            ("impressions",),
            ("clicks",),
            ("leads_crm",),
            ("conversion_value",),
            ("external_adset_id",),
            ("external_adset_name",),
            ("insight_level",),
        ]
        cur.fetchall.return_value = [
            (
                "550e8400-e29b-41d4-a716-446655440000",
                "DEMO",
                "Demo",
                "camp_1",
                "Camp 1",
                "2026-07-21",
                100000,
                1000,
                50,
                2,
                200000,
                None,
                None,
                "campaign",
            )
        ]
        conn = unittest.mock.MagicMock()
        conn.cursor.return_value.__enter__.return_value = cur
        mock_pg.return_value.__enter__.return_value = conn

        out = fetch_daily_insights(level="campaign", default_days=7)
        self.assertTrue(out["ok"])
        self.assertEqual(out["count"], 1)
        self.assertEqual(out["rows"][0]["external_campaign_id"], "camp_1")
