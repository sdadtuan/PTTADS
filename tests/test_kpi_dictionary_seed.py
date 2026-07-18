"""KPI dictionary seed tests (P0-10)."""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch


class TestKpiDictionarySeed(unittest.TestCase):
    @patch("ptt_jobs.db.pg_connection")
    @patch("ptt_jobs.db.pg_available", return_value=True)
    def test_pg_kpi_definitions_ready(self, _avail, mock_pg) -> None:
        conn = MagicMock()
        cur = MagicMock()
        cur.fetchone.side_effect = [(1,), (13,)]
        conn.cursor.return_value.__enter__.return_value = cur
        mock_pg.return_value.__enter__.return_value = conn

        from ptt_crm.pg_schema import pg_kpi_definitions_ready

        self.assertTrue(pg_kpi_definitions_ready())


if __name__ == "__main__":
    unittest.main()
