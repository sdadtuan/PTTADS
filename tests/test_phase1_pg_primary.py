"""Phase 1 — PostgreSQL primary for leads (no ptt.db OLTP)."""
from __future__ import annotations

import json
import os
import unittest
from unittest.mock import MagicMock, patch

from flask import Flask

from ptt_crm.config import (
    lead_replica_sync_enabled,
    leads_pg_primary,
    leads_read_source_pg,
    leads_write_source,
    leads_write_source_pg,
)
from ptt_crm.flask_guard import deny_flask_lead_write


class TestPhase1PgPrimaryConfig(unittest.TestCase):
    def test_default_write_source_pg(self) -> None:
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("PTT_LEADS_WRITE_SOURCE", None)
            self.assertEqual(leads_write_source(), "pg")
            self.assertTrue(leads_write_source_pg())
            self.assertTrue(leads_pg_primary())

    def test_read_source_follows_write_when_unset(self) -> None:
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("PTT_LEADS_WRITE_SOURCE", None)
            os.environ.pop("PTT_LEADS_READ_SOURCE", None)
            self.assertTrue(leads_read_source_pg())

    def test_read_source_sqlite_override(self) -> None:
        with patch.dict(
            os.environ,
            {"PTT_LEADS_WRITE_SOURCE": "pg", "PTT_LEADS_READ_SOURCE": "sqlite"},
            clear=False,
        ):
            self.assertFalse(leads_read_source_pg())

    def test_replica_sync_off_when_pg_primary(self) -> None:
        with patch.dict(os.environ, {"PTT_LEADS_WRITE_SOURCE": "pg"}, clear=False):
            os.environ.pop("PTT_LEAD_REPLICA_SYNC", None)
            self.assertFalse(lead_replica_sync_enabled())

    def test_replica_sync_on_when_sqlite_write(self) -> None:
        with patch.dict(os.environ, {"PTT_LEADS_WRITE_SOURCE": "sqlite"}, clear=False):
            os.environ.pop("PTT_LEAD_REPLICA_SYNC", None)
            self.assertTrue(lead_replica_sync_enabled())

    def test_sqlite_rollback(self) -> None:
        with patch.dict(os.environ, {"PTT_LEADS_WRITE_SOURCE": "sqlite"}, clear=False):
            self.assertEqual(leads_write_source(), "sqlite")
            self.assertFalse(leads_pg_primary())


app = Flask(__name__)


class TestFlaskLeadWriteGuardPhase1(unittest.TestCase):
    @patch.dict(os.environ, {"PTT_LEADS_WRITE_SOURCE": "pg"}, clear=False)
    def test_pg_primary_blocks_flask_lead_write(self) -> None:
        with app.app_context():
            resp, status = deny_flask_lead_write("crm_leads_mutate")
        self.assertEqual(status, 503)
        data = json.loads(resp.get_data(as_text=True))
        self.assertEqual(data["error"], "leads_pg_primary")

    @patch.dict(os.environ, {"PTT_LEADS_WRITE_SOURCE": "sqlite"}, clear=False)
    def test_sqlite_mode_allows_when_monolith_active(self) -> None:
        with patch.dict(os.environ, {"PTT_FLASK_MONOLITH_MODE": "active"}, clear=False):
            with app.app_context():
                self.assertIsNone(deny_flask_lead_write())


class TestLeadsReadPgPath(unittest.TestCase):
    @patch("ptt_crm.leads_read._list_leads_v1_pg")
    @patch("ptt_crm.config.leads_read_source_pg", return_value=True)
    def test_list_routes_to_pg(self, _cfg: MagicMock, mock_pg: MagicMock) -> None:
        mock_pg.return_value = ([{"id": 1}], 1)
        from ptt_crm.leads_read import list_leads_v1

        leads, total = list_leads_v1(limit=10, offset=0)
        self.assertEqual(total, 1)
        self.assertEqual(leads[0]["id"], 1)
        mock_pg.assert_called_once()

    @patch("ptt_crm.leads_read._get_lead_v1_pg")
    @patch("ptt_crm.config.leads_read_source_pg", return_value=True)
    def test_get_routes_to_pg(self, _cfg: MagicMock, mock_pg: MagicMock) -> None:
        mock_pg.return_value = {"id": 42, "full_name": "PG Lead"}
        from ptt_crm.leads_read import get_lead_v1

        lead = get_lead_v1(42)
        self.assertEqual(lead["id"], 42)
        mock_pg.assert_called_once_with(42)


if __name__ == "__main__":
    unittest.main()
