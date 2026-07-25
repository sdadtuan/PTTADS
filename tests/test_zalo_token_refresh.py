"""Tests for Zalo token refresh (Prod-S3)."""
from __future__ import annotations

import os
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from ptt_agency.channel_vault import compute_token_status


class TestZaloTokenRefresh(unittest.TestCase):
    def test_expiring_status_within_7_days(self) -> None:
        soon = datetime.now(timezone.utc) + timedelta(days=3)
        self.assertEqual(
            compute_token_status(has_token=True, token_status=None, token_expires_at=soon),
            "expiring",
        )

    @patch.dict(os.environ, {"PTT_ZALO_TOKEN_REFRESH": "0"}, clear=False)
    def test_sync_skipped_when_disabled(self) -> None:
        from ptt_zalo.token_refresh import sync_zalo_token_refresh

        out = sync_zalo_token_refresh()
        self.assertTrue(out.get("skipped"))

    @patch("ptt_zalo.token_refresh.list_zalo_accounts_for_maintenance")
    @patch("ptt_zalo.token_refresh.resolve_zalo_refresh_token", return_value="refresh-x")
    @patch("ptt_zalo.token_refresh.refresh_account_token")
    def test_refresh_due_skips_far_expiry(
        self,
        mock_refresh: MagicMock,
        _mock_resolve: MagicMock,
        mock_list: MagicMock,
    ) -> None:
        from ptt_zalo.token_refresh import refresh_due_tokens

        far = datetime.now(timezone.utc) + timedelta(days=30)
        mock_list.return_value = [
            {
                "id": "acc-1",
                "client_id": "c-1",
                "external_account_id": "oa_1",
                "token_expires_at": far,
                "token_status": "valid",
                "meta": {},
            }
        ]
        out = refresh_due_tokens()
        mock_refresh.assert_not_called()
        self.assertEqual(out["refresh_skipped"], 1)

    @patch.dict(os.environ, {"PTT_ZALO_TOKEN_REFRESH_STUB": "1", "PTT_ZALO_TOKEN_REFRESH": "1"}, clear=False)
    @patch("ptt_zalo.token_refresh.vault_columns_ready", return_value=True)
    @patch("ptt_zalo.token_refresh.list_zalo_accounts_for_maintenance")
    @patch("ptt_zalo.token_refresh.resolve_zalo_refresh_token", return_value="r1")
    @patch("ptt_zalo.token_refresh.resolve_zalo_access_token", return_value="access")
    @patch("ptt_zalo.token_refresh._persist_refresh_tokens")
    def test_stub_refresh(
        self,
        mock_persist: MagicMock,
        _a: MagicMock,
        _b: MagicMock,
        mock_list: MagicMock,
        _vault: MagicMock,
    ) -> None:
        from ptt_zalo.token_refresh import refresh_account_token

        soon = datetime.now(timezone.utc) + timedelta(days=5)
        row = {
            "id": "acc-1",
            "client_id": "c-1",
            "external_account_id": "oa_1",
            "token_expires_at": soon,
            "meta": {},
        }
        mock_list.return_value = [row]
        out = refresh_account_token(row, stub=True)
        self.assertTrue(out.get("ok"))
        mock_persist.assert_called_once()


class TestZaloOAuthTokens(unittest.TestCase):
    @patch.dict(os.environ, {}, clear=True)
    def test_missing_credentials(self) -> None:
        from ptt_zalo.oauth_tokens import exchange_zalo_refresh_token

        out = exchange_zalo_refresh_token("tok")
        self.assertIn("_zalo_error", out)


if __name__ == "__main__":
    unittest.main()
