"""QA wiring for SEO Phase 6 (B6) — BI + Gate D/E."""
from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class SeoB6QaTests(unittest.TestCase):
    def test_bi_controller_routes(self) -> None:
        text = (ROOT / "services/ptt-crm-api/src/seo-bi/seo-bi.controller.ts").read_text(encoding="utf-8")
        for fragment in ("bi/status", "bi/dashboard", "bi/parity", "bi/export-clickhouse", "attribution"):
            self.assertIn(fragment, text)

    def test_cron_controller_routes(self) -> None:
        text = (ROOT / "services/ptt-crm-api/src/seo-cron/seo-cron.controller.ts").read_text(encoding="utf-8")
        for fragment in ("gate-d", "gate-e", "status"):
            self.assertIn(fragment, text)

    def test_cms_and_crawl_routes(self) -> None:
        cms = (ROOT / "services/ptt-crm-api/src/seo-cms/seo-cms.controller.ts").read_text(encoding="utf-8")
        crawl = (ROOT / "services/ptt-crm-api/src/seo-technical/seo-crawl-internal.controller.ts").read_text(
            encoding="utf-8"
        )
        tech = (ROOT / "services/ptt-crm-api/src/seo-technical/seo-technical.controller.ts").read_text(encoding="utf-8")
        self.assertIn("cms-target", cms)
        self.assertIn("cms/test", cms)
        self.assertIn("crawl-ingest", crawl)
        self.assertIn("crawl-schedule", tech)

    def test_clickhouse_job_handler(self) -> None:
        worker = (ROOT / "ptt_worker/__main__.py").read_text(encoding="utf-8")
        handler = (ROOT / "ptt_jobs/handlers/seo_clickhouse_export.py").read_text(encoding="utf-8")
        self.assertIn("seo_clickhouse_export", worker)
        self.assertIn("export_seo_facts_to_clickhouse", handler)

    def test_ops_web_bi_cms_pages(self) -> None:
        self.assertTrue((ROOT / "services/ops-web/src/app/seo/bi/page.tsx").is_file())
        self.assertTrue((ROOT / "services/ops-web/src/app/seo/cms/page.tsx").is_file())
        bi = (ROOT / "services/ops-web/src/app/seo/bi/page.tsx").read_text(encoding="utf-8")
        self.assertIn("fetchSeoBiStatus", bi)
        self.assertIn("exportSeoClickhouse", bi)

    def test_env_b6_example(self) -> None:
        env = (ROOT / "deploy/env.seo-bi-gate-de.example").read_text(encoding="utf-8")
        self.assertIn("PTT_SEO_BI_EXPORT_ENABLED=1", env)
        self.assertIn("PTT_SEO_CMS_AUTO_PUBLISH=1", env)
        self.assertIn("PTT_CWV_STUB=1", env)

    def test_job_queue_enqueue(self) -> None:
        repo = (ROOT / "services/ptt-crm-api/src/webhooks/job-queue.repository.ts").read_text(encoding="utf-8")
        self.assertIn("enqueueSeoClickhouseExportJob", repo)
        self.assertIn("seo_clickhouse_export", repo)


if __name__ == "__main__":
    unittest.main()
