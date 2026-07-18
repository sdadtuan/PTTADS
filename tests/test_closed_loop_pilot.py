"""Tests for closed-loop staging pilot (P0 #4)."""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from ptt_agency.closed_loop_pilot import (
    check_cpl_tab_data,
    check_hub_campaign_map,
    check_insights_sync_enabled,
    check_meta_token,
    check_pixel_configured,
    resolve_client,
    run_closed_loop_pilot,
)


class TestClosedLoopPilot(unittest.TestCase):
    @patch("ptt_agency.clients.fetch_client_by_code")
    def test_resolve_client_by_code(self, mock_fetch: MagicMock) -> None:
        mock_fetch.return_value = {"id": "c1", "code": "DEMO", "name": "Demo"}
        out = resolve_client(client_code="demo")
        self.assertTrue(out["ok"])
        self.assertEqual(out["client"]["code"], "DEMO")

    @patch("ptt_agency.clients.list_channel_accounts")
    def test_meta_token_ok(self, mock_list: MagicMock) -> None:
        mock_list.return_value = [
            {
                "channel": "meta",
                "id": "a1",
                "has_token": True,
                "token_status": "valid",
                "external_account_id": "act_1",
            }
        ]
        out = check_meta_token("c1")
        self.assertTrue(out["ok"])

    @patch("ptt_agency.clients.list_channel_accounts")
    def test_pixel_from_account(self, mock_list: MagicMock) -> None:
        mock_list.return_value = [
            {"channel": "meta", "pixel_configured": True, "pixel_id": "12345678901", "id": "a1"}
        ]
        out = check_pixel_configured("c1")
        self.assertTrue(out["ok"])
        self.assertEqual(out["pixel_id"], "12345678901")

    @patch("ptt_jobs.db.pg_connection")
    def test_hub_map(self, mock_pg: MagicMock) -> None:
        conn = MagicMock()
        cur = MagicMock()
        cur.fetchall.return_value = [
            (1, "120330123456789012", 80000, True),
        ]
        cur.description = [
            ("hub_campaign_id",),
            ("external_campaign_id",),
            ("target_cpl_vnd",),
            ("active",),
        ]
        conn.cursor.return_value.__enter__.return_value = cur
        mock_pg.return_value.__enter__.return_value = conn
        out = check_hub_campaign_map("c1")
        self.assertTrue(out["ok"])

    @patch("ptt_meta.insights_sync.pg_meta_insights_ready", return_value=True)
    @patch("ptt_meta.insights_sync.meta_insights_stub_mode", return_value=True)
    @patch("ptt_meta.insights_sync.meta_insights_sync_enabled", return_value=True)
    def test_insights_flag(self, *_m: MagicMock) -> None:
        out = check_insights_sync_enabled()
        self.assertTrue(out["ok"])

    @patch("ptt_agency.performance.list_campaign_performance")
    def test_cpl_tab(self, mock_perf: MagicMock) -> None:
        mock_perf.return_value = {
            "ok": True,
            "rows": [{"cpl": 50000, "spend": 100000, "leads_crm": 2}],
            "summary": {"row_count": 1},
            "date_from": "2026-07-10",
            "date_to": "2026-07-16",
        }
        out = check_cpl_tab_data("c1")
        self.assertTrue(out["ok"])

    @patch("ptt_agency.closed_loop_pilot.check_cpl_tab_data")
    @patch("ptt_agency.closed_loop_pilot.check_daily_performance")
    @patch("ptt_agency.closed_loop_pilot.check_insights_sync_enabled")
    @patch("ptt_agency.closed_loop_pilot.check_hub_campaign_map")
    @patch("ptt_agency.closed_loop_pilot.check_pixel_configured")
    @patch("ptt_agency.closed_loop_pilot.check_meta_token")
    @patch("ptt_agency.closed_loop_pilot.resolve_client")
    def test_run_pilot_all_ok(
        self,
        mock_resolve: MagicMock,
        mock_token: MagicMock,
        mock_pixel: MagicMock,
        mock_map: MagicMock,
        mock_flag: MagicMock,
        mock_dp: MagicMock,
        mock_cpl: MagicMock,
    ) -> None:
        mock_resolve.return_value = {"ok": True, "client": {"id": "c1", "code": "DEMO"}}
        mock_token.return_value = {"ok": True}
        mock_pixel.return_value = {"ok": True}
        mock_map.return_value = {"ok": True}
        mock_flag.return_value = {"ok": True}
        mock_dp.return_value = {"ok": True}
        mock_cpl.return_value = {"ok": True, "summary": {"row_count": 2}}
        out = run_closed_loop_pilot(client_code="DEMO")
        self.assertTrue(out["ok"])


class TestChannelAccountMeta(unittest.TestCase):
    @patch("ptt_agency.clients.fetch_channel_account")
    @patch("ptt_agency.clients.pg_connection")
    @patch("ptt_agency.channel_vault.vault_columns_ready", return_value=True)
    def test_update_pixel(self, _vault: MagicMock, mock_pg: MagicMock, mock_fetch: MagicMock) -> None:
        from ptt_agency.clients import update_channel_account_meta

        conn = MagicMock()
        cur = MagicMock()
        cur.fetchone.side_effect = [({},), ("id",)]
        conn.cursor.return_value.__enter__.return_value = cur
        mock_pg.return_value.__enter__.return_value = conn
        mock_fetch.return_value = {"id": "a1", "pixel_id": "999", "pixel_configured": True}
        out = update_channel_account_meta(
            "550e8400-e29b-41d4-a716-446655440000",
            "660e8400-e29b-41d4-a716-446655440001",
            pixel_id="999",
        )
        self.assertEqual(out["pixel_id"], "999")


if __name__ == "__main__":
    unittest.main()
