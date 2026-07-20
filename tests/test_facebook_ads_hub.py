"""Tests for Facebook Ads hub module."""
from __future__ import annotations


import os
import unittest

if os.environ.get("PTT_RUN_FLASK_TESTS") != "1":
    raise unittest.SkipTest(
        "Flask HTTP removed — set PTT_RUN_FLASK_TESTS=1 to run integration tests"
    )
import unittest
from unittest.mock import MagicMock, patch


class TestFacebookAdsHub(unittest.TestCase):
    @patch("ptt_agency.facebook_ads_hub.pg_facebook_hub_ready", return_value=False)
    def test_not_ready(self, _ready: MagicMock) -> None:
        from ptt_agency.facebook_ads_hub import facebook_ads_hub_summary

        out = facebook_ads_hub_summary()
        self.assertFalse(out["ok"])
        self.assertEqual(out["error"], "facebook_hub_not_ready")

    @patch("ptt_agency.facebook_ads_hub._meta_job_counts", return_value={"dead": 0, "failed": 0, "pending": 0})
    @patch("ptt_agency.facebook_ads_hub.pg_connection")
    @patch("ptt_agency.channel_vault.vault_columns_ready", return_value=False)
    @patch("ptt_agency.facebook_ads_hub.pg_facebook_hub_ready", return_value=True)
    def test_summary_empty(
        self,
        _hub_ready: MagicMock,
        _vault: MagicMock,
        mock_pg: MagicMock,
        _jobs: MagicMock,
    ) -> None:
        from ptt_agency.facebook_ads_hub import facebook_ads_hub_summary

        cur = MagicMock()
        cur.description = [("id",)]
        cur.fetchall.return_value = []
        conn = MagicMock()
        conn.cursor.return_value.__enter__.return_value = cur
        mock_pg.return_value.__enter__.return_value = conn

        out = facebook_ads_hub_summary(window_days=7)
        self.assertTrue(out["ok"])
        self.assertEqual(out["summary"]["meta_clients"], 0)
        self.assertEqual(out["clients"], [])


class TestFacebookAdsHubBlueprint(unittest.TestCase):
    def setUp(self) -> None:
        from app import app

        self.client = app.test_client()

    @patch("app._admin_logged_in", return_value=True)
    @patch("blueprints.agency._can_facebook_ads", return_value=True)
    @patch("blueprints.agency.deps.ensure_crm_session_html", return_value=None)
    @patch("blueprints.agency.deps.admin_page_template_kwargs", return_value={})
    def test_facebook_ads_hub_page(self, _kw: MagicMock, _sess: MagicMock, _can: MagicMock, _auth: MagicMock) -> None:
        resp = self.client.get("/crm/facebook-ads")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Facebook Ads", resp.data)

    @patch("blueprints.agency._can_facebook_ads", return_value=True)
    @patch("ptt_agency.facebook_ads_hub.facebook_ads_hub_summary", return_value={"ok": True, "summary": {}, "clients": [], "alerts": []})
    def test_api_facebook_ads_hub(self, _summary: MagicMock, _can: MagicMock) -> None:
        resp = self.client.get("/api/v1/facebook-ads/hub?days=7")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data["ok"])


if __name__ == "__main__":
    unittest.main()
