"""QA wiring for SEO Phase 0 + B1 (no Flask)."""
from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class SeoP0B1QaTests(unittest.TestCase):
    def test_env_example_exists(self) -> None:
        self.assertTrue((ROOT / "deploy/env.seo-aeo-pilot.example").is_file())

    def test_client_workspace_page_exists(self) -> None:
        self.assertTrue((ROOT / "services/ops-web/src/app/seo/clients/[id]/page.tsx").is_file())

    def test_nest_client_routes_declared(self) -> None:
        text = (ROOT / "services/ptt-crm-api/src/seo-admin/seo-admin.controller.ts").read_text(
            encoding="utf-8"
        )
        for fragment in (
            "clients/:id'",
            "clients/:id/tasks'",
            "clients/:id/settings'",
            "clients/:id/sync/:source'",
        ):
            self.assertIn(fragment, text)

    def test_python_hub_links_ops_web(self) -> None:
        hub = (ROOT / "ptt_seo/hub.py").read_text(encoding="utf-8")
        self.assertIn('"/seo/clients"', hub)
        self.assertNotIn('"/crm/seo/clients"', hub)

    def test_seed_script_exists(self) -> None:
        self.assertTrue((ROOT / "scripts/seed_seo_pilot_client_settings.py").is_file())

    def test_oauth_routes_declared(self) -> None:
        text = (ROOT / "services/ptt-crm-api/src/seo-admin/seo-admin.controller.ts").read_text(
            encoding="utf-8"
        )
        self.assertIn('gsc/oauth/url', text)
        self.assertIn('ga4/oauth/url', text)
        callback = (ROOT / "services/ptt-crm-api/src/seo-admin/seo-oauth.controller.ts").read_text(
            encoding="utf-8"
        )
        self.assertIn('gsc/oauth/callback', callback)
        self.assertIn('ga4/oauth/callback', callback)

    def test_hub_has_gsc_trend_type(self) -> None:
        text = (ROOT / "services/ptt-crm-api/src/seo-admin/seo-admin.types.ts").read_text(
            encoding="utf-8"
        )
        self.assertIn('gsc_trend', text)


    def test_rbac_caps_in_staff_stub(self) -> None:
        text = (ROOT / "services/ptt-crm-api/src/staff-auth/staff-auth.service.ts").read_text(
            encoding="utf-8"
        )
        self.assertIn("crm_seo_aeo", text)
        self.assertIn("crm_seo_aeo_settings", text)


if __name__ == "__main__":
    unittest.main()
