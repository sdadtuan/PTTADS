"""Tests for Meta token refresh job M1-03."""
from __future__ import annotations

import os
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from ptt_agency.channel_vault import compute_token_status
from ptt_meta.graph_tokens import exchange_long_lived_token, meta_app_credentials


class TestGraphTokens(unittest.TestCase):
    def test_missing_app_credentials(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            out = exchange_long_lived_token("EAA-test")
            self.assertIn("_graph_error", out)

    @patch("ptt_meta.graph_tokens.urllib.request.urlopen")
    def test_exchange_success(self, mock_urlopen: MagicMock) -> None:
        mock_resp = MagicMock()
        mock_resp.read.return_value = b'{"access_token":"EAA-new","expires_in":5184000}'
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        with patch.dict(
            os.environ,
            {"META_APP_ID": "123", "META_APP_SECRET": "secret"},
            clear=False,
        ):
            out = exchange_long_lived_token("EAA-old")
        self.assertEqual(out.get("access_token"), "EAA-new")
        self.assertEqual(out.get("expires_in"), 5184000)

    def test_meta_app_credentials_fallback(self) -> None:
        with patch.dict(
            os.environ,
            {"CRM_FACEBOOK_APP_ID": "fb-id", "CRM_FACEBOOK_APP_SECRET": "fb-secret"},
            clear=True,
        ):
            app_id, secret = meta_app_credentials()
        self.assertEqual(app_id, "fb-id")
        self.assertEqual(secret, "fb-secret")


class TestTokenRefreshLogic(unittest.TestCase):
    def test_alert_status_expiring_within_7_days(self) -> None:
        soon = datetime.now(timezone.utc) + timedelta(days=3)
        self.assertEqual(
            compute_token_status(has_token=True, token_status=None, token_expires_at=soon),
            "expiring",
        )

    @patch("ptt_meta.token_refresh.list_meta_accounts_for_maintenance")
    @patch("ptt_meta.token_refresh.resolve_meta_access_token", return_value="EAA-x")
    @patch("ptt_meta.token_refresh.refresh_account_token")
    def test_refresh_due_tokens_skips_far_expiry(
        self,
        mock_refresh: MagicMock,
        _mock_resolve: MagicMock,
        mock_list: MagicMock,
    ) -> None:
        from ptt_meta.token_refresh import refresh_due_tokens

        far = datetime.now(timezone.utc) + timedelta(days=30)
        mock_list.return_value = [
            {
                "id": "acc-1",
                "client_id": "c-1",
                "external_account_id": "act_1",
                "token_expires_at": far,
                "token_status": "valid",
            }
        ]
        out = refresh_due_tokens()
        mock_refresh.assert_not_called()
        self.assertEqual(out["refresh_skipped"], 1)
        self.assertEqual(out["refreshed"], 0)

    @patch("ptt_meta.token_refresh.list_meta_accounts_for_maintenance")
    @patch("ptt_meta.token_refresh.resolve_meta_access_token", return_value="EAA-x")
    @patch("ptt_meta.token_refresh.refresh_account_token")
    def test_refresh_due_tokens_refreshes_soon_expiry(
        self,
        mock_refresh: MagicMock,
        _mock_resolve: MagicMock,
        mock_list: MagicMock,
    ) -> None:
        from ptt_meta.token_refresh import refresh_due_tokens

        soon = datetime.now(timezone.utc) + timedelta(days=5)
        mock_list.return_value = [
            {
                "id": "acc-1",
                "client_id": "c-1",
                "external_account_id": "act_1",
                "token_expires_at": soon,
                "token_status": "expiring",
            }
        ]
        mock_refresh.return_value = {"ok": True, "account_id": "acc-1"}
        out = refresh_due_tokens()
        mock_refresh.assert_called_once()
        self.assertEqual(out["refreshed"], 1)

    @patch("ptt_meta.token_refresh._dispatch_token_alert")
    @patch("ptt_meta.token_refresh.list_meta_accounts_for_maintenance")
    @patch("ptt_meta.token_refresh.resolve_meta_access_token", return_value="EAA-x")
    def test_alert_expiring_tokens(
        self,
        _mock_resolve: MagicMock,
        mock_list: MagicMock,
        mock_alert: MagicMock,
    ) -> None:
        from ptt_meta.token_refresh import alert_expiring_tokens

        soon = datetime.now(timezone.utc) + timedelta(days=2)
        mock_list.return_value = [
            {
                "id": "acc-1",
                "client_id": "c-1",
                "client_code": "DEMO",
                "external_account_id": "act_1",
                "token_expires_at": soon,
                "token_status": "expiring",
                "meta": {},
            }
        ]
        mock_alert.return_value = True
        out = alert_expiring_tokens()
        mock_alert.assert_called_once()
        self.assertEqual(out["alerts_sent"], 1)

    @patch("ptt_meta.token_refresh.alert_expiring_tokens", return_value={"alerts_sent": 0})
    @patch("ptt_meta.token_refresh.refresh_due_tokens", return_value={"refreshed": 0, "refresh_failed": 0})
    @patch("ptt_meta.token_refresh.vault_columns_ready", return_value=True)
    def test_sync_disabled_skips(
        self,
        _mock_vault: MagicMock,
        _mock_refresh: MagicMock,
        _mock_alert: MagicMock,
    ) -> None:
        from ptt_meta.token_refresh import sync_meta_token_refresh

        with patch.dict(os.environ, {"PTT_META_TOKEN_REFRESH": "0", "PTT_META_TOKEN_REFRESH_STUB": "0"}, clear=False):
            out = sync_meta_token_refresh()
        self.assertTrue(out.get("skipped"))

    @patch("ptt_agency.clients.set_channel_account_token")
    @patch("ptt_meta.token_refresh._clear_alert_marker")
    @patch("ptt_meta.token_refresh.resolve_meta_access_token", return_value="EAA-old")
    def test_refresh_account_token_stub(
        self,
        _mock_resolve: MagicMock,
        _mock_clear: MagicMock,
        mock_set: MagicMock,
    ) -> None:
        from ptt_meta.token_refresh import refresh_account_token

        mock_set.side_effect = lambda *a, **k: {"id": "acc-1", "token_status": "valid"}
        with patch.dict(os.environ, {"PTT_META_TOKEN_REFRESH_STUB": "1"}, clear=False):
            out = refresh_account_token(
                {"id": "acc-1", "client_id": "c-1", "external_account_id": "act_1"},
                stub=True,
            )
        self.assertTrue(out.get("ok"))
        self.assertTrue(out.get("stub"))
        mock_set.assert_called_once()


class TestMetaTokenRefreshHandler(unittest.TestCase):
    @patch("ptt_jobs.handlers.meta_token_refresh.sync_meta_token_refresh")
    @patch("ptt_jobs.handlers.meta_token_refresh.mark_job_done")
    def test_handler_marks_done(self, mock_done: MagicMock, mock_sync: MagicMock) -> None:
        from ptt_jobs.handlers.meta_token_refresh import run_meta_token_refresh_job

        mock_sync.return_value = {"ok": True, "refreshed": 1}
        run_meta_token_refresh_job({"id": "j1", "payload": {}, "attempts": 1, "max_attempts": 3})
        mock_done.assert_called_once_with("j1")


if __name__ == "__main__":
    unittest.main()
