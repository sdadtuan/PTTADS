"""Phase 2 — PG-primary worker ingest + agency readonly config."""
from __future__ import annotations

import os
import unittest
from unittest.mock import MagicMock, patch

from ptt_crm.config import agency_flask_readonly, agency_ops_on_ops_web


class TestAgencyOpsConfig(unittest.TestCase):
    def test_default_ops_web_primary(self) -> None:
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("PTT_AGENCY_OPS_UPSTREAM", None)
            self.assertTrue(agency_ops_on_ops_web())
            self.assertTrue(agency_flask_readonly())

    def test_flask_upstream(self) -> None:
        with patch.dict(os.environ, {"PTT_AGENCY_OPS_UPSTREAM": "flask"}, clear=False):
            self.assertFalse(agency_ops_on_ops_web())


class TestLeadIngestPgRouting(unittest.TestCase):
    @patch("ptt_crm.lead_ingest_pg.process_ingest_lead_payload_pg")
    @patch("ptt_crm.config.leads_write_source_pg", return_value=True)
    def test_routes_to_pg_module(self, _pg: MagicMock, mock_pg_ingest: MagicMock) -> None:
        mock_pg_ingest.return_value = {"ok": True, "created_ids": [1], "write_path": "pg_primary"}
        from ptt_jobs.handlers.ingest_lead import process_ingest_lead_payload

        out = process_ingest_lead_payload({"channel": "meta", "lead": {"phone": "0901111222"}})
        self.assertTrue(out.get("ok"))
        mock_pg_ingest.assert_called_once()


class TestFlaskAgencyGuard(unittest.TestCase):
    @patch.dict(os.environ, {"PTT_AGENCY_OPS_UPSTREAM": "ops-web"}, clear=False)
    def test_agency_write_blocked(self) -> None:
        from flask import Flask

        from ptt_crm.flask_guard import deny_flask_agency_write

        app = Flask(__name__)
        with app.app_context():
            resp, status = deny_flask_agency_write()
        self.assertEqual(status, 503)
        data = resp.get_json()
        self.assertEqual(data["error"], "agency_ops_web_primary")


if __name__ == "__main__":
    unittest.main()
