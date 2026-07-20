"""Tests for Agency Ops blueprint."""
from __future__ import annotations


import os
import unittest

if os.environ.get("PTT_RUN_FLASK_TESTS") != "1":
    raise unittest.SkipTest(
        "Flask HTTP removed — set PTT_RUN_FLASK_TESTS=1 to run integration tests"
    )
import unittest
from unittest.mock import MagicMock, patch


class TestAgencyBlueprint(unittest.TestCase):
    def setUp(self) -> None:
        from app import app

        self.client = app.test_client()

    @patch("app._admin_logged_in", return_value=True)
    @patch("blueprints.agency._can", return_value=True)
    @patch("blueprints.agency.deps.ensure_crm_session_html", return_value=None)
    @patch("blueprints.agency.deps.admin_page_template_kwargs", return_value={})
    def test_agency_dashboard(self, _kw: MagicMock, _sess: MagicMock, _can: MagicMock, _auth: MagicMock) -> None:
        resp = self.client.get("/crm/agency")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Agency Ops", resp.data)

    @patch("blueprints.agency._can", return_value=True)
    def test_api_clients_requires_pg_or_503(self, _can: MagicMock) -> None:
        with patch("ptt_agency.clients.list_clients", side_effect=RuntimeError("no pg")):
            resp = self.client.get("/api/v1/clients")
        self.assertIn(resp.status_code, (503, 401))


if __name__ == "__main__":
    unittest.main()
