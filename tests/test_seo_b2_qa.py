"""QA wiring for SEO Phase 2 (B2) — research + content pipeline (no Flask)."""
from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class SeoB2QaTests(unittest.TestCase):
    def test_nest_content_module_files(self) -> None:
        for rel in (
            "services/ptt-crm-api/src/seo-content/seo-content.controller.ts",
            "services/ptt-crm-api/src/seo-content/seo-content.service.ts",
            "services/ptt-crm-api/src/seo-content/seo-content.repository.ts",
            "services/ptt-crm-api/src/seo-content/seo-content.module.ts",
            "services/ptt-crm-api/src/seo-content/seo-content.constants.ts",
        ):
            self.assertTrue((ROOT / rel).is_file(), rel)

    def test_content_routes_declared(self) -> None:
        text = (ROOT / "services/ptt-crm-api/src/seo-content/seo-content.controller.ts").read_text(
            encoding="utf-8"
        )
        for fragment in (
            "clients/:id/research",
            "clients/:id/keywords",
            "research/brief-preview",
            "research/to-content",
            "content/pipeline",
            "content/:id/approve",
            "content/:id/aeo-checklist",
        ):
            self.assertIn(fragment, text)

    def test_write_and_approve_guards(self) -> None:
        guards = (ROOT / "services/ptt-crm-api/src/seo-admin/guards/staff-seo-view.guard.ts").read_text(
            encoding="utf-8"
        )
        self.assertIn("StaffSeoWriteGuard", guards)
        self.assertIn("StaffSeoApproveGuard", guards)
        self.assertIn("staffHasSeoApprove", guards)

    def test_ops_web_research_and_content_pages(self) -> None:
        self.assertTrue((ROOT / "services/ops-web/src/app/seo/research/page.tsx").is_file())
        self.assertTrue((ROOT / "services/ops-web/src/app/seo/content/page.tsx").is_file())
        self.assertTrue((ROOT / "services/ops-web/src/app/seo/content/[id]/page.tsx").is_file())

    def test_ops_nav_has_research_content_links(self) -> None:
        nav = (ROOT / "services/ops-web/src/components/OpsNav.tsx").read_text(encoding="utf-8")
        self.assertIn("/seo/research", nav)
        self.assertIn("/seo/content", nav)

    def test_ops_web_caps_write_approve(self) -> None:
        caps = (ROOT / "services/ops-web/src/lib/seo/caps.ts").read_text(encoding="utf-8")
        self.assertIn("canWriteSeo", caps)
        self.assertIn("canApproveSeo", caps)

    def test_app_module_registers_content_module(self) -> None:
        app = (ROOT / "services/ptt-crm-api/src/app.module.ts").read_text(encoding="utf-8")
        self.assertIn("SeoContentModule", app)


if __name__ == "__main__":
    unittest.main()
