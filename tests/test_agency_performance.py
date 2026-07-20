"""Tests for Agency campaign performance API (M6)."""
from __future__ import annotations


import os
import unittest

if os.environ.get("PTT_RUN_FLASK_TESTS") != "1":
    raise unittest.SkipTest(
        "Flask HTTP removed — set PTT_RUN_FLASK_TESTS=1 to run integration tests"
    )
import unittest
from unittest.mock import MagicMock, patch

from ptt_agency.performance import compute_cpl, list_campaign_performance


class TestComputeCpl(unittest.TestCase):
    def test_cpl_basic(self) -> None:
        self.assertEqual(compute_cpl(150000, 3), 50000.0)

    def test_cpl_no_leads(self) -> None:
        self.assertIsNone(compute_cpl(1000, 0))

    def test_cpl_no_spend(self) -> None:
        self.assertIsNone(compute_cpl(0, 5))


class TestListCampaignPerformance(unittest.TestCase):
    @patch("ptt_agency.performance.pg_performance_ready", return_value=False)
    def test_not_ready(self, _mock: MagicMock) -> None:
        out = list_campaign_performance(client_id="550e8400-e29b-41d4-a716-446655440000")
        self.assertFalse(out.get("ok"))

    @patch("ptt_agency.performance.pg_connection")
    @patch("ptt_agency.performance.pg_performance_ready", return_value=True)
    def test_day_rows(self, _ready: MagicMock, mock_pg: MagicMock) -> None:
        from datetime import date, datetime, timezone

        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_pg.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cur

        perf_date = date(2026, 7, 15)
        mock_cur.description = [
            ("performance_date",),
            ("channel",),
            ("external_campaign_id",),
            ("external_campaign_name",),
            ("spend",),
            ("currency",),
            ("impressions",),
            ("clicks",),
            ("leads_crm",),
            ("leads_platform",),
            ("conversion_value",),
            ("hub_campaign_map_id",),
            ("hub_campaign_id",),
            ("target_cpl_vnd",),
            ("synced_at",),
            ("cpl_snapshot",),
            ("roas_snapshot",),
        ]
        mock_cur.fetchone.return_value = (perf_date, datetime(2026, 7, 16, tzinfo=timezone.utc), 1)
        mock_cur.fetchall.return_value = [
            (
                perf_date,
                "meta",
                "camp_1",
                "Demo Campaign",
                150000,
                "VND",
                1000,
                50,
                3,
                2,
                0,
                "550e8400-e29b-41d4-a716-446655440001",
                42,
                60000,
                datetime(2026, 7, 16, tzinfo=timezone.utc),
                50000,
                None,
            ),
        ]

        out = list_campaign_performance(
            client_id="550e8400-e29b-41d4-a716-446655440000",
            date_from="2026-07-15",
            date_to="2026-07-15",
            group_by="day",
        )
        self.assertTrue(out.get("ok"))
        self.assertEqual(len(out["rows"]), 1)
        row = out["rows"][0]
        self.assertEqual(row["cpl"], 50000.0)
        self.assertEqual(row["channel"], "meta")
        self.assertEqual(row["target_cpl_vnd"], 60000.0)
        self.assertTrue(row["hub_mapped"])
        self.assertEqual(row["hub_campaign_id"], 42)
        self.assertIn("/crm/hub?campaign_id=42", row["hub_url"])


class TestPerformanceBlueprint(unittest.TestCase):
    def setUp(self) -> None:
        from app import app

        self.client = app.test_client()

    @patch("app._admin_logged_in", return_value=True)
    @patch("blueprints.agency._can", return_value=True)
    @patch("ptt_agency.clients.fetch_client", return_value={"id": "c1"})
    @patch("ptt_agency.performance.list_campaign_performance")
    def test_api_performance(self, mock_list: MagicMock, _fetch: MagicMock, _can: MagicMock, _auth: MagicMock) -> None:
        mock_list.return_value = {"ok": True, "rows": [], "summary": {}}
        resp = self.client.get("/api/v1/clients/c1/performance?from=2026-07-01&to=2026-07-07")
        self.assertEqual(resp.status_code, 200)
        mock_list.assert_called_once()

    @patch("app._admin_logged_in", return_value=True)
    @patch("blueprints.agency._can", return_value=True)
    def test_api_performance_requires_client(self, _can: MagicMock, _auth: MagicMock) -> None:
        resp = self.client.get("/api/v1/performance")
        self.assertEqual(resp.status_code, 400)


if __name__ == "__main__":
    unittest.main()
