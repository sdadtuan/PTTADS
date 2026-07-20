"""Tests for leads read upstream cutover (Phase 1b Bước 8)."""
from __future__ import annotations


import os
import unittest

if os.environ.get("PTT_RUN_FLASK_TESTS") != "1":
    raise unittest.SkipTest(
        "Flask HTTP removed — set PTT_RUN_FLASK_TESTS=1 to run integration tests"
    )
import os
import unittest
from unittest.mock import MagicMock, patch


class TestLeadsReadUpstreamConfig(unittest.TestCase):
    def test_default_flask(self) -> None:
        from ptt_crm.config import leads_read_upstream

        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("PTT_LEADS_READ_UPSTREAM", None)
            self.assertEqual(leads_read_upstream(), "flask")

    def test_nest_mode(self) -> None:
        from ptt_crm.config import leads_read_upstream

        with patch.dict(os.environ, {"PTT_LEADS_READ_UPSTREAM": "nest"}):
            self.assertEqual(leads_read_upstream(), "nest")

    def test_invalid_falls_back_flask(self) -> None:
        from ptt_crm.config import leads_read_upstream

        with patch.dict(os.environ, {"PTT_LEADS_READ_UPSTREAM": "invalid"}):
            self.assertEqual(leads_read_upstream(), "flask")


class TestLeadsUpstreamProxy(unittest.TestCase):
    @patch("ptt_crm.leads_upstream.fetch_nest_json")
    def test_proxy_list_success(self, mock_fetch: MagicMock) -> None:
        from ptt_crm.leads_upstream import proxy_list_leads

        mock_fetch.return_value = (200, {"leads": [], "total": 0, "limit": 50, "offset": 0}, None)
        body, status = proxy_list_leads("limit=50")
        self.assertEqual(status, 200)
        self.assertEqual(body["total"], 0)

    @patch("ptt_crm.leads_upstream.fetch_nest_json")
    def test_proxy_list_error_502(self, mock_fetch: MagicMock) -> None:
        from ptt_crm.leads_upstream import proxy_list_leads

        mock_fetch.return_value = (0, None, "connection refused")
        body, status = proxy_list_leads()
        self.assertEqual(status, 502)
        self.assertEqual(body["upstream"], "nest")

    @patch("ptt_crm.leads_upstream.fetch_nest_json")
    def test_proxy_get_404(self, mock_fetch: MagicMock) -> None:
        from ptt_crm.leads_upstream import proxy_get_lead

        mock_fetch.return_value = (404, {"error": "Not found"}, None)
        body, status = proxy_get_lead(999)
        self.assertEqual(status, 404)
        self.assertEqual(body["error"], "Not found")


class TestBlueprintUpstreamRouting(unittest.TestCase):
    @patch("app._admin_logged_in", return_value=True)
    @patch("blueprints.crm_leads_v1._can", return_value=True)
    @patch("ptt_crm.leads_upstream.proxy_list_leads")
    @patch("ptt_crm.leads_upstream.nest_upstream_enabled", return_value=True)
    def test_list_proxies_when_nest(
        self,
        _enabled: MagicMock,
        mock_proxy: MagicMock,
        _can: MagicMock,
        _auth: MagicMock,
    ) -> None:
        from app import app

        mock_proxy.return_value = ({"leads": [], "total": 0, "limit": 50, "offset": 0}, 200)
        client = app.test_client()
        resp = client.get("/api/v1/leads?limit=50")
        self.assertEqual(resp.status_code, 200)
        mock_proxy.assert_called_once()
        self.assertEqual(resp.get_json()["total"], 0)

    @patch("app._admin_logged_in", return_value=True)
    @patch("blueprints.crm_leads_v1._can", return_value=True)
    @patch("ptt_crm.leads_read.list_leads_v1", return_value=([{"id": 1}], 1))
    @patch("ptt_crm.dual_run.maybe_dual_run_list")
    @patch("ptt_crm.leads_upstream.nest_upstream_enabled", return_value=False)
    def test_list_local_when_flask(
        self,
        _enabled: MagicMock,
        _dual: MagicMock,
        mock_list: MagicMock,
        _can: MagicMock,
        _auth: MagicMock,
    ) -> None:
        from app import app

        client = app.test_client()
        resp = client.get("/api/v1/leads?limit=10")
        self.assertEqual(resp.status_code, 200)
        mock_list.assert_called_once()
        self.assertEqual(resp.get_json()["total"], 1)


if __name__ == "__main__":
    unittest.main()
