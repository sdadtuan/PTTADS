"""Google insights sync unit tests (Phase 3 G2)."""
from __future__ import annotations

import os
import unittest
from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock, patch

from ptt_google.insights_sync import sync_account_insights, sync_google_insights


class GoogleInsightsSyncTest(unittest.TestCase):
    def setUp(self) -> None:
        os.environ["PTT_GOOGLE_INSIGHTS_STUB"] = "1"
        os.environ["PTT_GOOGLE_INSIGHTS_SYNC"] = "1"

    @patch("ptt_google.insights_sync.upsert_daily_performance")
    @patch("ptt_google.insights_sync.count_crm_leads", return_value=3)
    @patch("ptt_google.insights_sync._hub_map_lookup")
    def test_sync_account_stub(self, hub_lookup: MagicMock, _leads: MagicMock, upsert: MagicMock) -> None:
        hub_lookup.return_value = {
            "id": "11111111-1111-1111-1111-111111111111",
            "external_campaign_name": "Google Demo",
            "target_cpl_vnd": Decimal("500000"),
        }
        account = {
            "client_id": "550e8400-e29b-41d4-a716-446655440000",
            "external_account_id": "1234567890",
        }
        out = sync_account_insights(account, target_date=date(2026, 7, 16), stub=True)
        self.assertTrue(out.get("ok"))
        self.assertGreaterEqual(out.get("upserted", 0), 1)
        upsert.assert_called()
        call_kw = upsert.call_args[0][0]
        self.assertEqual(call_kw["channel"], "google")

    @patch("ptt_google.insights_sync._update_sync_state")
    @patch("ptt_google.insights_sync.sync_account_insights")
    @patch("ptt_google.insights_sync._load_google_accounts")
    @patch("ptt_google.insights_sync.pg_google_insights_ready", return_value=True)
    def test_sync_no_accounts_skipped(
        self,
        _ready: MagicMock,
        load_accounts: MagicMock,
        _sync_acct: MagicMock,
        _state: MagicMock,
    ) -> None:
        load_accounts.return_value = []
        out = sync_google_insights(target_date=date(2026, 7, 16))
        self.assertTrue(out.get("skipped"))
        self.assertEqual(out.get("reason"), "no_google_accounts")


if __name__ == "__main__":
    unittest.main()
