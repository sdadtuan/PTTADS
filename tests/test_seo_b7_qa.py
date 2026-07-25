"""QA wiring for SEO Phase 7 (B7) — Gate A go-live."""
from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class SeoB7QaTests(unittest.TestCase):
    def test_gate_a_controller_routes(self) -> None:
        text = (ROOT / "services/ptt-crm-api/src/seo-gate-a/seo-gate-a.controller.ts").read_text(
            encoding="utf-8"
        )
        for fragment in ("@Get('status')", "@Get('readiness')", "signoff-template"):
            self.assertIn(fragment, text)

    def test_nginx_redirect_config(self) -> None:
        nginx = (ROOT / "deploy/nginx-seo-gate-a-redirect.conf").read_text(encoding="utf-8")
        self.assertIn("/crm/seo/", nginx)
        self.assertIn("/seo$1", nginx)

    def test_signoff_template(self) -> None:
        tpl = (ROOT / "docs/evidence/seo-gate-a-signoff.template.json").read_text(encoding="utf-8")
        self.assertIn("head_seo_aeo", tpl)
        self.assertIn("flask_seo_retired", tpl)

    def test_ops_web_gate_a_page(self) -> None:
        page = (ROOT / "services/ops-web/src/app/seo/gate-a/page.tsx").read_text(encoding="utf-8")
        self.assertIn("fetchSeoGateAStatus", page)
        self.assertIn("Staged cutover", page)

    def test_cutover_scripts(self) -> None:
        self.assertTrue((ROOT / "scripts/seo_gate_a_cutover_gate.sh").is_file())
        self.assertTrue((ROOT / "scripts/seo_gate_a_pack.sh").is_file())
        cutover = (ROOT / "scripts/seo_gate_a_cutover_gate.sh").read_text(encoding="utf-8")
        self.assertIn("wave_seo_b7_gate.sh", cutover)
        self.assertIn("phase5_prod_cutover_gate.sh", cutover)

    def test_temporal_links_use_seo_paths(self) -> None:
        temporal = (ROOT / "ptt_temporal/activities/seo_content.py").read_text(encoding="utf-8")
        self.assertIn("/seo/content", temporal)
        self.assertNotIn("/crm/seo/content", temporal)

    def test_env_gate_a_example(self) -> None:
        env = (ROOT / "deploy/env.seo-gate-a-prod.example").read_text(encoding="utf-8")
        self.assertIn("PTT_SEO_GOVERNANCE_ENABLED=1", env)
        self.assertIn("nginx-seo-gate-a-redirect.conf", env)


if __name__ == "__main__":
    unittest.main()
