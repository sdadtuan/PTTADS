"""QA helpers for Wave B12 creative registry."""
from __future__ import annotations

import unittest


class TestB12CreativeRegistryQa(unittest.TestCase):
    def test_api_route_registered(self) -> None:
        text = open(
            "services/ptt-crm-api/src/meta-creative-registry/meta-creative-registry.controller.ts",
            encoding="utf-8",
        ).read()
        self.assertIn("creative-links", text)
        self.assertIn("resolve", text)

    def test_ops_creative_link_panel(self) -> None:
        panel = open("services/ops-web/src/components/meta/MetaCreativeLinkPanel.tsx", encoding="utf-8").read()
        creatives = open(
            "services/ops-web/src/app/crm/creatives/CrmCreativesContent.tsx",
            encoding="utf-8",
        ).read()
        self.assertIn("MetaCreativeLinkPanel", panel)
        self.assertIn("MetaCreativeLinkPanel", creatives)
        self.assertIn("external_ad_id", panel)

    def test_ddl_v9_table(self) -> None:
        ddl = open(
            "docs/specs/2026-07-25-postgresql-ddl-v9-meta-creative-registry.sql",
            encoding="utf-8",
        ).read()
        self.assertIn("meta_ad_creative_links", ddl)
        self.assertIn("creative_submission_id", ddl)


if __name__ == "__main__":
    unittest.main()
