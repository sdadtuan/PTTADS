"""Tests for Phase 2 gate prerequisites."""
from __future__ import annotations

import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from ptt_crm.dual_run import diff_lead_v1


class TestPhase2Prereqs(unittest.TestCase):
    @patch("ptt_crm.phase2_prereqs.ensure_shadow_sync_repair")
    @patch("ptt_crm.phase2_prereqs.ensure_domain_events_idempotency")
    def test_ensure_phase2_write_gates(self, mock_idem, mock_repair) -> None:
        from ptt_crm.phase2_prereqs import ensure_phase2_write_gates

        mock_idem.return_value = {"ok": True}
        mock_repair.return_value = {"ok": True, "repaired": 2}
        out = ensure_phase2_write_gates()
        self.assertTrue(out["ok"])
        mock_idem.assert_called_once()
        mock_repair.assert_called_once()

    @patch("ptt_crm.lead_shadow_sync.pg_shadow_ready", return_value=True)
    @patch("ptt_crm.lead_shadow_sync._fetch_pg_rows")
    @patch("ptt_crm.lead_shadow_sync._get_shadow_watermark", return_value=999)
    @patch("ptt_crm.lead_shadow_sync._apply_rows")
    @patch("ptt_crm.lead_shadow_sync.pg_connection")
    def test_shadow_repair_gaps(
        self,
        mock_pg_conn,
        mock_apply,
        _wm,
        mock_fetch,
        _ready,
    ) -> None:
        from ptt_crm.lead_shadow_sync import sync_shadow_repair_gaps

        class FakeCursor:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def execute(self, *_args, **_kwargs):
                return None

            def fetchall(self):
                return [(900000001,)]

        class FakeConn:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def cursor(self):
                return FakeCursor()

        mock_pg_conn.return_value = FakeConn()
        mock_fetch.return_value = [{"sqlite_lead_id": 900000001, "sync_version": 1}]
        mock_apply.return_value = {"synced": 1, "inserted": 1, "updated": 0}

        with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
            conn = sqlite3.connect(tmp.name)
            conn.execute(
                """
                CREATE TABLE crm_leads (
                    id INTEGER PRIMARY KEY, is_duplicate INTEGER DEFAULT 0
                )
                """
            )
            conn.commit()
            conn.close()
            with patch("ptt_crm.lead_shadow_sync.sqlite_db_path", return_value=tmp.name):
                out = sync_shadow_repair_gaps(limit=10)
        self.assertTrue(out["ok"])
        self.assertEqual(out["repaired"], 1)


class TestDualRunTimestamp(unittest.TestCase):
    def test_iso_vs_sqlite_timestamp(self) -> None:
        pg = {"id": 55, "created_at": "2026-06-23T11:16:04Z", "received_at": "2026-06-23T11:16:04Z"}
        nest = {"id": 55, "created_at": "2026-06-23 11:16:04", "received_at": "2026-06-23 11:16:04"}
        self.assertEqual(diff_lead_v1(pg, nest), [])


if __name__ == "__main__":
    unittest.main()
