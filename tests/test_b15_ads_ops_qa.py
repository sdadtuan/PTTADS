"""QA helpers for Wave B15 Meta Ads Ops UI."""
from __future__ import annotations

import unittest


class TestB15AdsOpsQa(unittest.TestCase):
    def test_nest_ads_ops_module_wired(self) -> None:
        app = open("services/ptt-crm-api/src/app.module.ts", encoding="utf-8").read()
        module = open("services/ptt-crm-api/src/meta-ads-ops/meta-ads-ops.module.ts", encoding="utf-8").read()
        controller = open("services/ptt-crm-api/src/meta-ads-ops/meta-ads-ops.controller.ts", encoding="utf-8").read()
        self.assertIn("MetaAdsOpsModule", app)
        self.assertIn("MetaAdsOpsController", module)
        self.assertIn("@Post('launch')", controller)
        self.assertIn("edit/submit", controller)

    def test_ops_web_ads_ops_route_and_wizard(self) -> None:
        page = open("services/ops-web/src/app/meta/ads-ops/page.tsx", encoding="utf-8").read()
        content = open("services/ops-web/src/app/meta/ads-ops/MetaAdsOpsContent.tsx", encoding="utf-8").read()
        nav = open("services/ops-web/src/components/OpsNav.tsx", encoding="utf-8").read()
        self.assertIn("MetaAdsOpsContent", page)
        self.assertIn("MetaWizardStepper", content)
        self.assertIn("MetaCreativePicker", content)
        self.assertIn("/meta/ads-ops", nav)

    def test_hub_edit_ad_entry(self) -> None:
        alerts = open("services/ops-web/src/components/meta/MetaAlertsTable.tsx", encoding="utf-8").read()
        edit_link = open("services/ops-web/src/components/meta/MetaEditAdLink.tsx", encoding="utf-8").read()
        self.assertIn("MetaEditAdLink", alerts)
        self.assertIn("Edit ad", edit_link)
        self.assertIn("mode: 'edit'", open("services/ops-web/src/lib/meta/ads-ops-url.ts", encoding="utf-8").read())

    def test_config_flag_helper(self) -> None:
        config = open("ptt_crm/config.py", encoding="utf-8").read()
        self.assertIn("def meta_ads_ops_enabled", config)
        self.assertIn("PTT_META_ADS_OPS_ENABLED", config)

    def test_campaign_writes_extended(self) -> None:
        types = open("services/ptt-crm-api/src/campaign-writes/campaign-writes.types.ts", encoding="utf-8").read()
        self.assertIn("update_ad_creative", types)
        self.assertIn("create_campaign", types)


if __name__ == "__main__":
    unittest.main()
