"""QA checks for Wave B8.1 breakdown + RBAC."""
from __future__ import annotations

import unittest


class TestB81BreakdownQa(unittest.TestCase):
    def test_breakdown_api_route(self) -> None:
        text = open(
            "services/ptt-crm-api/src/meta-intelligence/meta-intelligence.controller.ts",
            encoding="utf-8",
        ).read()
        self.assertIn("insights/breakdown", text)

    def test_ops_breakdown_ui(self) -> None:
        table = open("services/ops-web/src/components/meta/MetaCampaignTable.tsx", encoding="utf-8").read()
        panel = open("services/ops-web/src/components/meta/MetaBreakdownPanel.tsx", encoding="utf-8").read()
        self.assertIn("MetaBreakdownPanel", table)
        self.assertIn("publisher_platform", panel)


if __name__ == "__main__":
    unittest.main()
