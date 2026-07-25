"""Zalo campaign write adapter tests (Prod-Z4)."""
from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from ptt_zalo.campaign_write import (
    apply_campaign_status,
    apply_daily_budget,
    campaign_write_allowed,
    create_campaign,
)


class TestZaloCampaignWritePilot(unittest.TestCase):
    def test_stub_mode_skips_pilot_gate(self) -> None:
        with patch.dict(os.environ, {"PTT_ZALO_CAMPAIGN_WRITE_STUB": "1"}, clear=False):
            ok, err = campaign_write_allowed(client_id="other", external_campaign_id="camp-x")
            self.assertTrue(ok)
            self.assertIsNone(err)

    def test_real_mode_requires_pilot_flag(self) -> None:
        env = {
            "PTT_ZALO_CAMPAIGN_WRITE_STUB": "0",
            "PTT_ZALO_CAMPAIGN_WRITE_PILOT": "0",
        }
        with patch.dict(os.environ, env, clear=False):
            ok, err = campaign_write_allowed(
                client_id="550e8400-e29b-41d4-a716-446655440000",
                external_campaign_id="zalo_camp_1",
            )
            self.assertFalse(ok)
            self.assertEqual(err, "pilot_mode_disabled")

    @patch.dict(os.environ, {"PTT_ZALO_CAMPAIGN_WRITE_STUB": "1"}, clear=False)
    def test_create_campaign_stub(self) -> None:
        out = create_campaign(
            account={"external_account_id": "acc_1", "client_id": "c1"},
            new_value={
                "external_account_id": "acc_1",
                "campaign_name": "Test Zalo",
                "daily_budget_vnd": 500000,
            },
            client_id="c1",
        )
        self.assertTrue(out["ok"])
        self.assertTrue(out.get("stub"))
        self.assertTrue(str(out.get("external_campaign_id", "")).startswith("stub_zalo_"))

    @patch.dict(os.environ, {"PTT_ZALO_CAMPAIGN_WRITE_STUB": "1"}, clear=False)
    def test_apply_status_stub(self) -> None:
        out = apply_campaign_status(
            account={"client_id": "c1"},
            external_campaign_id="zalo_camp_1",
            status="PAUSED",
            client_id="c1",
        )
        self.assertTrue(out["ok"])
        self.assertEqual(out.get("status"), "PAUSED")

    @patch.dict(os.environ, {"PTT_ZALO_CAMPAIGN_WRITE_STUB": "1"}, clear=False)
    def test_apply_daily_budget_stub(self) -> None:
        out = apply_daily_budget(
            account={"client_id": "c1"},
            external_campaign_id="zalo_camp_1",
            daily_budget_vnd=300000,
            client_id="c1",
        )
        self.assertTrue(out["ok"])
        self.assertEqual(out.get("daily_budget_vnd"), 300000)


if __name__ == "__main__":
    unittest.main()
