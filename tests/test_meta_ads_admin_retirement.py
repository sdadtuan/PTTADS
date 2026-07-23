#!/usr/bin/env python3
"""Unit tests — Meta Ads Flask admin retirement (B3.3 / M1-G09)."""
from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from ptt_crm.config import meta_ads_admin_retired, meta_ads_ops_web_hub_url
from ptt_crm.flask_guard import deny_flask_meta_ads_admin
from ptt_crm.meta_ads_admin_retirement import flask_meta_ads_admin_redirect, migration_status


class MetaAdsAdminRetirementTests(unittest.TestCase):
    def test_not_retired_by_default(self) -> None:
        with patch.dict(os.environ, {"PTT_FLASK_META_ADS_ADMIN_RETIRED": "0"}, clear=False):
            self.assertFalse(meta_ads_admin_retired())
            self.assertIsNone(flask_meta_ads_admin_redirect())
            self.assertIsNone(deny_flask_meta_ads_admin())

    def test_retired_redirect(self) -> None:
        with patch.dict(
            os.environ,
            {
                "PTT_FLASK_META_ADS_ADMIN_RETIRED": "1",
                "PTT_OPS_WEB_URL": "https://ops.pttads.vn",
            },
            clear=False,
        ):
            self.assertTrue(meta_ads_admin_retired())
            url, code = flask_meta_ads_admin_redirect() or ("", 0)
            self.assertEqual(code, 302)
            self.assertEqual(url, "https://ops.pttads.vn/meta/facebook-ads")
            body, status = deny_flask_meta_ads_admin() or ({}, 0)
            self.assertEqual(status, 302)
            self.assertEqual(body.get("redirect"), url)

    def test_migration_status_gate(self) -> None:
        with patch.dict(os.environ, {"PTT_FLASK_META_ADS_ADMIN_RETIRED": "1"}, clear=False):
            status = migration_status()
            self.assertTrue(status["flask_meta_ads_admin_retired"])
            self.assertTrue(status["gate_m1_g09"])
            self.assertIn("/meta/facebook-ads", status["ops_web_hub_url"])

    def test_migration_status_includes_dry_run_fields(self) -> None:
        with patch.dict(os.environ, {"PTT_FLASK_META_ADS_ADMIN_RETIRED": "1"}, clear=False):
            status = migration_status()
            self.assertIn("gate_m1_g11", status)
            self.assertIn("retirement_env_pending_changes", status)

    def test_horizon1_gate_m1_g09(self) -> None:
        from ptt_crm.horizon1_meta_ads_gates import _check_meta_admin_retired_flag

        with patch.dict(
            os.environ,
            {
                "HORIZON1_EXPECT_META_HUB_RETIRED": "1",
                "PTT_FLASK_META_ADS_ADMIN_RETIRED": "1",
            },
            clear=False,
        ):
            check = _check_meta_admin_retired_flag()
            self.assertTrue(check["ok"])
            self.assertEqual(check["id"], "M1-G09")


if __name__ == "__main__":
    unittest.main()
