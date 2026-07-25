"""QA wiring for SEO Phase 3 (B3) — technical, reports, governance, strategy."""
from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class SeoB3QaTests(unittest.TestCase):
    def test_nest_b3_modules(self) -> None:
        for rel in (
            "services/ptt-crm-api/src/seo-technical/seo-technical.controller.ts",
            "services/ptt-crm-api/src/seo-reports/seo-reports.controller.ts",
            "services/ptt-crm-api/src/seo-governance/seo-governance.controller.ts",
            "services/ptt-crm-api/src/seo-strategy/seo-strategy.controller.ts",
        ):
            self.assertTrue((ROOT / rel).is_file(), rel)

    def test_technical_routes(self) -> None:
        text = (ROOT / "services/ptt-crm-api/src/seo-technical/seo-technical.controller.ts").read_text(
            encoding="utf-8"
        )
        for fragment in ("clients/:id/issues", "issues/import", "clients/:id/cwv", "cwv/capture"):
            self.assertIn(fragment, text)

    def test_reports_routes(self) -> None:
        text = (ROOT / "services/ptt-crm-api/src/seo-reports/seo-reports.controller.ts").read_text(
            encoding="utf-8"
        )
        for fragment in ("dashboard/:type", "reports/export", "reports/schedules", "alerts"):
            self.assertIn(fragment, text)

    def test_governance_routes(self) -> None:
        text = (ROOT / "services/ptt-crm-api/src/seo-governance/seo-governance.controller.ts").read_text(
            encoding="utf-8"
        )
        for fragment in ("governance/policies", "governance/compliance", "governance/evaluate", "governance/overrides"):
            self.assertIn(fragment, text)

    def test_strategy_routes(self) -> None:
        text = (ROOT / "services/ptt-crm-api/src/seo-strategy/seo-strategy.controller.ts").read_text(
            encoding="utf-8"
        )
        for fragment in ("strategy/okr", "strategy/goals", "strategy/kpis/refresh"):
            self.assertIn(fragment, text)

    def test_ops_web_b3_pages(self) -> None:
        for rel in (
            "services/ops-web/src/app/seo/technical/page.tsx",
            "services/ops-web/src/app/seo/reports/page.tsx",
            "services/ops-web/src/app/seo/governance/page.tsx",
            "services/ops-web/src/app/seo/strategy/page.tsx",
        ):
            self.assertTrue((ROOT / rel).is_file(), rel)

    def test_ops_nav_b3_links(self) -> None:
        nav = (ROOT / "services/ops-web/src/components/OpsNav.tsx").read_text(encoding="utf-8")
        for path in ("/seo/technical", "/seo/reports", "/seo/governance", "/seo/strategy"):
            self.assertIn(path, nav)

    def test_technical_and_reports_guards(self) -> None:
        guards = (ROOT / "services/ptt-crm-api/src/seo-admin/guards/staff-seo-view.guard.ts").read_text(
            encoding="utf-8"
        )
        self.assertIn("StaffSeoTechnicalGuard", guards)
        self.assertIn("StaffSeoReportsGuard", guards)

    def test_app_module_registers_b3(self) -> None:
        app = (ROOT / "services/ptt-crm-api/src/app.module.ts").read_text(encoding="utf-8")
        for mod in ("SeoTechnicalModule", "SeoReportsModule", "SeoGovernanceModule", "SeoStrategyModule"):
            self.assertIn(mod, app)


if __name__ == "__main__":
    unittest.main()
