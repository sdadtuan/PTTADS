"""Tests for Meta granular RBAC (B8.1)."""
from __future__ import annotations

import unittest


class TestMetaRbacB81(unittest.TestCase):
    def test_tracking_configure_guard_requires_agency_configure(self) -> None:
        text = open(
            "services/ptt-crm-api/src/meta-tracking/guards/staff-meta-tracking.guard.ts",
            encoding="utf-8",
        ).read()
        self.assertIn("crm_agency', 'configure'", text)
        self.assertNotIn("crm_facebook_ads', 'view'", text.split("StaffMetaTrackingConfigureGuard")[1])

    def test_ops_caps_tracking_configure(self) -> None:
        caps = open("services/ops-web/src/lib/meta/caps.ts", encoding="utf-8").read()
        self.assertIn("canApproveMetaCampaignWrite", caps)
        self.assertIn("return hasCap(user, 'crm_agency', 'configure')", caps.split("canConfigureMetaTracking")[1])

    def test_buyer_seed_has_no_approve(self) -> None:
        seed = open("scripts/seed_staff_meta_rbac_b81.py", encoding="utf-8").read()
        self.assertIn("MKT-02", seed)
        self.assertIn("meta_campaign_write", seed)
        self.assertNotIn("'approve'", seed.split("MKT-02")[1].split("TECH")[0])


if __name__ == "__main__":
    unittest.main()
