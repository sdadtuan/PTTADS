"""QA wiring for Email Marketing P1 — UX parity (ops-web + Nest, no Flask)."""
from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class EmailP1QaTests(unittest.TestCase):
    def test_p1_module_files_exist(self) -> None:
        for rel in (
            "services/ops-web/src/components/email/EmailDomainOnboardingWizard.tsx",
            "services/ptt-crm-api/src/email-marketing/email-alert-notify.util.ts",
            "scripts/email_p1_gate.sh",
            "docs/huong-dan-email-marketing-ops.md",
            "docs/forms/email-marketing-ops-checklist-a4.html",
            "scripts/generate_email_marketing_training_pptx.py",
        ):
            self.assertTrue((ROOT / rel).is_file(), rel)

    def test_governance_write_routes(self) -> None:
        ctrl = (ROOT / "services/ptt-crm-api/src/email-marketing/email-marketing.controller.ts").read_text(
            encoding="utf-8"
        )
        for fragment in (
            "@Post('governance/rules')",
            "@Patch('governance/rules/:id')",
            "@Delete('governance/rules/:id')",
            "reports/bi-status",
            "hubWithAlerts",
        ):
            self.assertIn(fragment, ctrl)

    def test_segment_builder_p1_tabs(self) -> None:
        sb = (ROOT / "services/ops-web/src/components/email/SegmentBuilder.tsx").read_text(encoding="utf-8")
        for tab in ("'rfm'", "'lifecycle'", "'behavior'"):
            self.assertIn(tab, sb)

    def test_compute_segment_rfm_lifecycle(self) -> None:
        repo = (
            ROOT / "services/ptt-crm-api/src/email-marketing/email-marketing-campaign.repository.ts"
        ).read_text(encoding="utf-8")
        for fragment in ("segment_type === 'rfm'", "lifecycle_stage", "last_open_within_days"):
            self.assertIn(fragment, repo)

    def test_playwright_p1_spec_fragments(self) -> None:
        spec = (ROOT / "services/ops-web/e2e/email-handoff.spec.ts").read_text(encoding="utf-8")
        for fragment in (
            "RFM/lifecycle/behavior",
            "Domain onboarding wizard",
            "BI & Grafana",
            "bi-status API",
            "Audit log",
        ):
            self.assertIn(fragment, spec)

    def test_deliverability_wizard_wired(self) -> None:
        page = (ROOT / "services/ops-web/src/app/email/deliverability/page.tsx").read_text(encoding="utf-8")
        self.assertIn("EmailDomainOnboardingWizard", page)
        self.assertIn("fetchEmailClients", page)

    def test_reports_bi_status_wired(self) -> None:
        page = (ROOT / "services/ops-web/src/app/email/reports/page.tsx").read_text(encoding="utf-8")
        self.assertIn("fetchEmailBiStatus", page)
        self.assertIn("grafana_url", page)


if __name__ == "__main__":
    unittest.main()
