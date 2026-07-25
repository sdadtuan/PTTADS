"""QA wiring for SEO Phase 4 (B4) — AEO, authority, ranks, automations, freshness, experiments."""
from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class SeoB4QaTests(unittest.TestCase):
    def test_nest_b4_modules(self) -> None:
        for rel in (
            "services/ptt-crm-api/src/seo-aeo/seo-aeo.controller.ts",
            "services/ptt-crm-api/src/seo-authority/seo-authority.controller.ts",
            "services/ptt-crm-api/src/seo-ranks/seo-ranks.controller.ts",
            "services/ptt-crm-api/src/seo-automations/seo-automations.controller.ts",
            "services/ptt-crm-api/src/seo-freshness/seo-freshness.controller.ts",
            "services/ptt-crm-api/src/seo-experiments/seo-experiments.controller.ts",
        ):
            self.assertTrue((ROOT / rel).is_file(), rel)

    def test_aeo_routes(self) -> None:
        text = (ROOT / "services/ptt-crm-api/src/seo-aeo/seo-aeo.controller.ts").read_text(encoding="utf-8")
        for fragment in ("aeo/queries", "aeo/coverage", "aeo/scan"):
            self.assertIn(fragment, text)

    def test_authority_routes(self) -> None:
        text = (ROOT / "services/ptt-crm-api/src/seo-authority/seo-authority.controller.ts").read_text(
            encoding="utf-8"
        )
        for fragment in ("authority/signals", "authority/import", "authority/summary"):
            self.assertIn(fragment, text)

    def test_ranks_routes(self) -> None:
        text = (ROOT / "services/ptt-crm-api/src/seo-ranks/seo-ranks.controller.ts").read_text(encoding="utf-8")
        for fragment in ("ranks/keywords", "ranks/capture", "ranks/sov", "ranks/import"):
            self.assertIn(fragment, text)

    def test_automations_routes(self) -> None:
        text = (ROOT / "services/ptt-crm-api/src/seo-automations/seo-automations.controller.ts").read_text(
            encoding="utf-8"
        )
        for fragment in ("automations/status", "automations/sync-runs", "automations/run-alert-checks"):
            self.assertIn(fragment, text)

    def test_freshness_routes(self) -> None:
        text = (ROOT / "services/ptt-crm-api/src/seo-freshness/seo-freshness.controller.ts").read_text(
            encoding="utf-8"
        )
        for fragment in ("freshness/queue", "freshness/rescore"):
            self.assertIn(fragment, text)

    def test_experiments_routes(self) -> None:
        text = (ROOT / "services/ptt-crm-api/src/seo-experiments/seo-experiments.controller.ts").read_text(
            encoding="utf-8"
        )
        for fragment in ("experiments/status", "clients/:id/experiments", "experiments/:experimentId"):
            self.assertIn(fragment, text)

    def test_ops_web_b4_pages(self) -> None:
        for rel in (
            "services/ops-web/src/app/seo/aeo/page.tsx",
            "services/ops-web/src/app/seo/authority/page.tsx",
            "services/ops-web/src/app/seo/ranks/page.tsx",
            "services/ops-web/src/app/seo/automations/page.tsx",
            "services/ops-web/src/app/seo/freshness/page.tsx",
            "services/ops-web/src/app/seo/experiments/page.tsx",
        ):
            self.assertTrue((ROOT / rel).is_file(), rel)

    def test_ops_nav_b4_links(self) -> None:
        nav = (ROOT / "services/ops-web/src/components/OpsNav.tsx").read_text(encoding="utf-8")
        for path in ("/seo/aeo", "/seo/authority", "/seo/ranks", "/seo/automations", "/seo/freshness", "/seo/experiments"):
            self.assertIn(path, nav)

    def test_job_queue_aeo_scan(self) -> None:
        jq = (ROOT / "services/ptt-crm-api/src/webhooks/job-queue.repository.ts").read_text(encoding="utf-8")
        self.assertIn("enqueueSeoAeoScanJob", jq)
        self.assertIn("seo_aeo_scan", jq)

    def test_app_module_registers_b4(self) -> None:
        app = (ROOT / "services/ptt-crm-api/src/app.module.ts").read_text(encoding="utf-8")
        for mod in (
            "SeoAeoModule",
            "SeoAuthorityModule",
            "SeoRanksModule",
            "SeoAutomationsModule",
            "SeoFreshnessModule",
            "SeoExperimentsModule",
        ):
            self.assertIn(mod, app)

    def test_hub_aeo_mentions_join(self) -> None:
        repo = (ROOT / "services/ptt-crm-api/src/seo-admin/seo-admin.repository.ts").read_text(encoding="utf-8")
        self.assertIn("seo_ai_mentions", repo)


if __name__ == "__main__":
    unittest.main()
