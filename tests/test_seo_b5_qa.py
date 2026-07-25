"""QA wiring for SEO Phase 5 (B5) — client portal prod."""
from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class SeoB5QaTests(unittest.TestCase):
    def test_portal_seo_controller_routes(self) -> None:
        text = (ROOT / "services/ptt-crm-api/src/portal-seo/portal-seo.controller.ts").read_text(
            encoding="utf-8"
        )
        for fragment in (
            "portal/seo",
            "summary",
            "status",
            "widgets",
            "reports/executive",
            "content/pending",
            "content/:id/review",
        ):
            self.assertIn(fragment, text)

    def test_portal_web_seo_pages(self) -> None:
        for rel in (
            "services/portal-web/src/app/seo/page.tsx",
            "services/portal-web/src/app/seo/reports/page.tsx",
            "services/portal-web/src/app/seo/content/page.tsx",
            "services/portal-web/src/app/seo/content/[id]/page.tsx",
        ):
            self.assertTrue((ROOT / rel).is_file(), rel)

    def test_portal_seo_nav_hook(self) -> None:
        hook = (ROOT / "services/portal-web/src/hooks/usePortalSeoNav.ts").read_text(encoding="utf-8")
        self.assertIn("portalSeoStatus", hook)

    def test_portal_repository_aeo_mentions(self) -> None:
        repo = (ROOT / "services/ptt-crm-api/src/portal-seo/portal-seo.repository.ts").read_text(
            encoding="utf-8"
        )
        self.assertIn("seo_ai_mentions", repo)
        self.assertIn("open_alerts", repo)

    def test_seed_scripts(self) -> None:
        self.assertTrue((ROOT / "scripts/seed_portal_seo_pilot_map.py").is_file())
        self.assertTrue((ROOT / "scripts/seed_portal_seo_e2e_content.py").is_file())
        self.assertTrue((ROOT / "scripts/phase5_portal_seo_e2e_gate.sh").is_file())

    def test_e2e_spec_present(self) -> None:
        spec = (ROOT / "services/portal-web/e2e/portal-seo.spec.ts").read_text(encoding="utf-8")
        self.assertIn("client_review approve flow", spec)

    def test_env_portal_pilot_example(self) -> None:
        env = (ROOT / "deploy/env.seo-portal-pilot.example").read_text(encoding="utf-8")
        self.assertIn("PTT_PORTAL_SEO_ENABLED=1", env)


if __name__ == "__main__":
    unittest.main()
