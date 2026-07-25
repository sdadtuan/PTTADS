"""QA wiring for SEO/AEO P1 UX parity (S-03, S-06, S-12, E1)."""
from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class SeoP1QaTests(unittest.TestCase):
    def test_p1_ops_web_surfaces_exist(self) -> None:
        for rel in (
            "services/ops-web/src/components/SeoClientWorkspaceNav.tsx",
            "services/ops-web/src/app/seo/research/page.tsx",
            "services/ops-web/src/app/seo/reports/page.tsx",
            "services/ops-web/src/app/seo/strategy/page.tsx",
        ):
            self.assertTrue((ROOT / rel).is_file(), rel)

    def test_workspace_nav_links_modules(self) -> None:
        nav = (ROOT / "services/ops-web/src/components/SeoClientWorkspaceNav.tsx").read_text(
            encoding="utf-8",
        )
        for fragment in (
            "/seo/strategy",
            "/seo/research",
            "/seo/content",
            "/seo/reports",
            "customer_id=",
        ):
            self.assertIn(fragment, nav)

    def test_research_serp_pages_wired(self) -> None:
        research = (ROOT / "services/ops-web/src/app/seo/research/page.tsx").read_text(encoding="utf-8")
        self.assertIn("serpSnapshots", research)
        self.assertIn("filteredPages", research)
        self.assertNotIn("Phase 3", research)

    def test_reports_attribution_panel(self) -> None:
        reports = (ROOT / "services/ops-web/src/app/seo/reports/page.tsx").read_text(encoding="utf-8")
        self.assertIn("fetchSeoAttribution", reports)
        self.assertIn("Organic attribution", reports)

    def test_strategy_kpi_editor(self) -> None:
        strategy = (ROOT / "services/ops-web/src/app/seo/strategy/page.tsx").read_text(encoding="utf-8")
        self.assertIn("createSeoStrategyKpi", strategy)
        self.assertIn("updateSeoStrategyKpi", strategy)

    def test_nest_research_serp_pages_api(self) -> None:
        service = (ROOT / "services/ptt-crm-api/src/seo-content/seo-content.service.ts").read_text(
            encoding="utf-8",
        )
        self.assertIn("listSerpSnapshots", service)
        self.assertIn("listPages", service)

    def test_nest_kpi_patch_endpoint(self) -> None:
        controller = (
            ROOT / "services/ptt-crm-api/src/seo-strategy/seo-strategy.controller.ts"
        ).read_text(encoding="utf-8")
        self.assertIn("@Patch('clients/:id/strategy/kpis/:kpiId')", controller)


if __name__ == "__main__":
    unittest.main()
