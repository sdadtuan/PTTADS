"""Tests for write dual-run check (Phase 2 W7)."""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch


class TestWriteDualRun(unittest.TestCase):
    @patch("ptt_crm.phase2_prereqs.ensure_phase2_write_gates")
    @patch("ptt_crm.dual_run_write._nest_get_lead")
    @patch("ptt_crm.dual_run_write._sqlite_write_snapshot")
    @patch("ptt_crm.dual_run_write.get_pg_lead_v1")
    @patch("ptt_crm.dual_run_write.reconcile_leads_pg_primary")
    @patch("ptt_crm.dual_run_write.sqlite3.connect")
    def test_matching_writes(
        self,
        mock_connect: MagicMock,
        mock_reconcile: MagicMock,
        mock_pg: MagicMock,
        mock_sql: MagicMock,
        mock_nest: MagicMock,
        mock_prereq: MagicMock,
    ) -> None:
        from ptt_crm.dual_run_write import run_write_dual_run_check

        mock_prereq.return_value = {"ok": True, "steps": {}}
        mock_reconcile.return_value = {"ok": True, "mismatches": []}
        conn = MagicMock()
        mock_connect.return_value = conn
        conn.execute.return_value.fetchall.return_value = [(1,)]
        mock_pg.return_value = {"id": 1, "owner_id": 5, "status": "assigned", "full_name": "A", "phone": ""}
        mock_sql.return_value = {"id": 1, "owner_id": 5, "status": "assigned"}
        mock_nest.return_value = {"id": 1, "owner_id": 5, "status": "assigned", "full_name": "A", "phone": ""}

        report = run_write_dual_run_check(sample_size=1, include_nest=True)
        self.assertTrue(report["ok"])
        self.assertEqual(report["pg_sqlite_mismatch_count"], 0)


if __name__ == "__main__":
    unittest.main()
