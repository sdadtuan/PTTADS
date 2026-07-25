"""QA wiring for SEO/AEO P2 hardening (Nest POSTs, hub drill-down, a11y, infra)."""
from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class SeoP2QaTests(unittest.TestCase):
    def test_p2_nest_research_post_endpoints(self) -> None:
        controller = (
            ROOT / "services/ptt-crm-api/src/seo-content/seo-content.controller.ts"
        ).read_text(encoding="utf-8")
        for fragment in (
            "@Post('clients/:id/research/serp')",
            "@Post('clients/:id/research/pages/sync-gsc')",
            "@Post('clients/:id/entities/autolink')",
        ):
            self.assertIn(fragment, controller)

    def test_p2_ops_web_actions_wired(self) -> None:
        research = (ROOT / "services/ops-web/src/app/seo/research/page.tsx").read_text(
            encoding="utf-8",
        )
        self.assertIn("captureSeoSerpSnapshot", research)
        self.assertIn("syncSeoPagesFromGsc", research)
        self.assertIn("autolinkSeoEntities", research)

    def test_p2_hub_drill_down(self) -> None:
        hub = (ROOT / "services/ops-web/src/app/seo/hub/page.tsx").read_text(encoding="utf-8")
        self.assertIn("SeoScoreMeter", hub)
        self.assertIn("/seo/aeo?customer_id=", hub)
        self.assertIn("/seo/content?view=review", hub)

    def test_p2_content_pipeline_views(self) -> None:
        content = (ROOT / "services/ops-web/src/app/seo/content/page.tsx").read_text(encoding="utf-8")
        self.assertIn("Cần refresh", content)
        self.assertIn("Review only", content)

    def test_p2_a11y_score_meter_and_chart_fallback(self) -> None:
        self.assertTrue((ROOT / "services/ops-web/src/components/SeoScoreMeter.tsx").is_file())
        charts = (ROOT / "services/ops-web/src/lib/seo/charts.tsx").read_text(encoding="utf-8")
        self.assertIn("a11y fallback", charts)
        aeo = (ROOT / "services/ops-web/src/app/seo/aeo/page.tsx").read_text(encoding="utf-8")
        self.assertIn('aria-live="polite"', aeo)

    def test_p2_grafana_link_ops_web(self) -> None:
        rules = (ROOT / "deploy/grafana/seo-ops-alert-rules.json").read_text(encoding="utf-8")
        self.assertIn("/seo/technical", rules)
        self.assertNotIn("/crm/seo/technical", rules)

    def test_p2_seed_uses_crm_seo_aeo_not_legacy(self) -> None:
        seed = (ROOT / "scripts/seed_super_admin_full_access.py").read_text(encoding="utf-8")
        self.assertNotIn('("crm_seo",', seed)
        self.assertIn("ADMIN_CRM_SECTIONS", seed)

    def test_flask_blueprint_tests_retired_message(self) -> None:
        phase1 = (ROOT / "tests/test_seo_aeo_phase1.py").read_text(encoding="utf-8")
        self.assertIn("Flask HTTP removed", phase1)


if __name__ == "__main__":
    unittest.main()
