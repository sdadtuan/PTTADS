"""Tests for staging write cutover pilot gates (P0 #3)."""
from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from ptt_crm.staging_write_pilot import (
    build_pilot_report,
    check_lead_assigned_event,
    check_staging_env_flags,
    get_sync_mode,
    run_preflight_gates,
    set_sync_mode,
)


class TestStagingWritePilot(unittest.TestCase):
    @patch.dict(
        "os.environ",
        {
            "PTT_LEADS_WRITE_ENABLED": "1",
            "PTT_LEADS_WRITE_UPSTREAM": "nest",
            "PTT_LEAD_SHADOW_SYNC": "1",
            "PTT_LEADS_READ_UPSTREAM": "nest",
        },
        clear=False,
    )
    @patch("ptt_crm.staging_write_pilot.get_sync_mode", return_value={"ok": True, "sync_mode": "pg_primary"})
    def test_check_staging_env_flags_ok(self, _sync: MagicMock) -> None:
        out = check_staging_env_flags(expect_pg_primary=True)
        self.assertTrue(out["ok"])
        self.assertEqual(out["checks"]["write_upstream"], "nest")

    @patch.dict("os.environ", {"PTT_LEADS_WRITE_ENABLED": "0"}, clear=False)
    @patch("ptt_crm.staging_write_pilot.get_sync_mode", return_value={"ok": True, "sync_mode": "sqlite_to_pg"})
    def test_check_staging_env_flags_fail(self, _sync: MagicMock) -> None:
        out = check_staging_env_flags()
        self.assertFalse(out["ok"])
        self.assertIn("PTT_LEADS_WRITE_ENABLED!=1", out["issues"])

    @patch("ptt_jobs.db.pg_connection")
    def test_set_sync_mode(self, mock_pg: MagicMock) -> None:
        conn = MagicMock()
        cur = MagicMock()
        cur.fetchone.return_value = ("pg_primary", datetime.now(timezone.utc))
        conn.cursor.return_value.__enter__.return_value = cur
        mock_pg.return_value.__enter__.return_value = conn
        out = set_sync_mode("pg_primary")
        self.assertTrue(out["ok"])
        self.assertEqual(out["sync_mode"], "pg_primary")

    @patch("ptt_jobs.db.pg_connection")
    def test_get_sync_mode(self, mock_pg: MagicMock) -> None:
        conn = MagicMock()
        cur = MagicMock()
        now = datetime.now(timezone.utc)
        cur.fetchone.return_value = ("sqlite_to_pg", now, now)
        conn.cursor.return_value.__enter__.return_value = cur
        mock_pg.return_value.__enter__.return_value = conn
        out = get_sync_mode()
        self.assertTrue(out["ok"])
        self.assertEqual(out["sync_mode"], "sqlite_to_pg")

    @patch("ptt_jobs.db.pg_connection")
    def test_check_lead_assigned_event(self, mock_pg: MagicMock) -> None:
        conn = MagicMock()
        cur = MagicMock()
        now = datetime.now(timezone.utc)
        cur.fetchall.return_value = [
            ("e1", "42", now, now - timedelta(seconds=5), {}),
        ]
        conn.cursor.return_value.__enter__.return_value = cur
        mock_pg.return_value.__enter__.return_value = conn
        out = check_lead_assigned_event(lead_id=42)
        self.assertTrue(out["ok"])

    @patch("ptt_crm.staging_write_pilot.check_pg_preflight")
    @patch("ptt_crm.staging_write_pilot.fetch_nest_health")
    def test_run_preflight_gates(self, mock_health: MagicMock, mock_pg: MagicMock) -> None:
        mock_health.return_value = {
            "ok": True,
            "body": {"leads_write_enabled": True},
        }
        mock_pg.return_value = {"ok": True, "issues": []}
        with patch.dict(
            "os.environ",
            {
                "PTT_LEADS_WRITE_ENABLED": "1",
                "PTT_LEADS_WRITE_UPSTREAM": "nest",
                "PTT_LEAD_SHADOW_SYNC": "1",
                "PTT_LEADS_READ_UPSTREAM": "nest",
            },
            clear=False,
        ):
            with patch("ptt_crm.staging_write_pilot.get_sync_mode", return_value={"sync_mode": "pg_primary"}):
                out = run_preflight_gates()
        self.assertTrue(out["ok"])

    def test_build_pilot_report(self) -> None:
        report = build_pilot_report(
            phase="test",
            steps={"preflight": {"ok": True}, "smoke": {"ok": False}},
        )
        self.assertFalse(report["ok"])
        self.assertEqual(report["failed_steps"], ["smoke"])


if __name__ == "__main__":
    unittest.main()
