"""Meta campaign write pilot gate tests (Phase 4)."""
from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from ptt_meta.campaign_write import apply_daily_budget, campaign_write_allowed


class TestMetaCampaignWritePilot(unittest.TestCase):
    def test_stub_mode_skips_pilot_gate(self) -> None:
        with patch.dict(os.environ, {"PTT_META_CAMPAIGN_WRITE_STUB": "1"}, clear=False):
            ok, err = campaign_write_allowed(
                client_id="other",
                external_campaign_id="camp-x",
            )
            self.assertTrue(ok)
            self.assertIsNone(err)

    def test_real_mode_requires_pilot_flag(self) -> None:
        env = {
            "PTT_META_CAMPAIGN_WRITE_STUB": "0",
            "PTT_META_CAMPAIGN_WRITE_PILOT": "0",
        }
        with patch.dict(os.environ, env, clear=False):
            ok, err = campaign_write_allowed(
                client_id="550e8400-e29b-41d4-a716-446655440000",
                external_campaign_id="120210123456789",
            )
            self.assertFalse(ok)
            self.assertEqual(err, "pilot_mode_disabled")

    def test_pilot_lists_enforced(self) -> None:
        env = {
            "PTT_META_CAMPAIGN_WRITE_STUB": "0",
            "PTT_META_CAMPAIGN_WRITE_PILOT": "1",
            "PTT_META_CAMPAIGN_WRITE_PILOT_CLIENTS": "550e8400-e29b-41d4-a716-446655440000",
            "PTT_META_CAMPAIGN_WRITE_PILOT_CAMPAIGNS": "120210123456789",
        }
        with patch.dict(os.environ, env, clear=False):
            ok, _ = campaign_write_allowed(
                client_id="550e8400-e29b-41d4-a716-446655440000",
                external_campaign_id="120210123456789",
            )
            self.assertTrue(ok)
            ok2, err2 = campaign_write_allowed(
                client_id="660e8400-e29b-41d4-a716-446655440001",
                external_campaign_id="120210123456789",
            )
            self.assertFalse(ok2)
            self.assertEqual(err2, "client_not_in_pilot")

    @patch("ptt_meta.campaign_write.resolve_meta_access_token", return_value="tok")
    @patch("ptt_meta.campaign_write.normalize_ad_account_id", return_value="act_1")
    def test_apply_daily_budget_blocked_without_pilot(self, _acct, _tok) -> None:
        env = {
            "PTT_META_CAMPAIGN_WRITE_STUB": "0",
            "PTT_META_CAMPAIGN_WRITE_PILOT": "0",
        }
        account = {"external_account_id": "act_1", "client_id": "c1"}
        with patch.dict(os.environ, env, clear=False):
            out = apply_daily_budget(
                account=account,
                external_campaign_id="camp-1",
                daily_budget_vnd=100000,
                client_id="c1",
            )
            self.assertFalse(out["ok"])
            self.assertEqual(out["error"], "pilot_mode_disabled")


if __name__ == "__main__":
    unittest.main()
