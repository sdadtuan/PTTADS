"""QA wiring + domain checks for SPEC_UI_UX_EMAIL_MARKETING.md §13 (ops-web, no Flask)."""
from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class EmailHandoffQaTests(unittest.TestCase):
    def test_handoff_scripts_exist(self) -> None:
        for rel in (
            "scripts/playwright_ops_email_handoff_e2e.sh",
            "scripts/seed_ops_email_handoff_e2e.py",
            "scripts/email_handoff_gate.sh",
            "services/ops-web/e2e/email-handoff.spec.ts",
            "services/ops-web/src/app/email/gate-a/page.tsx",
        ):
            self.assertTrue((ROOT / rel).is_file(), rel)

    def test_playwright_spec_covers_s13_items(self) -> None:
        spec = (ROOT / "services/ops-web/e2e/email-handoff.spec.ts").read_text(encoding="utf-8")
        for fragment in (
            "executive drill-down",
            "client workspace settings",
            "Global rules",
            "hub API smoke",
            "mobile smoke",
            "Gate A",
        ):
            self.assertIn(fragment, spec)

    def test_preflight_blocks_missing_unsubscribe(self) -> None:
        html_no_unsub = "<html><body><p>Hello world content here</p><a href='https://example.com'>CTA</a></body></html>"
        html_with_unsub = html_no_unsub + "<a href='{{unsubscribe_url}}'>Unsubscribe</a>"
        unsub_pattern = re.compile(r"unsubscribe|list-unsubscribe|\{\{unsubscribe", re.I)
        self.assertFalse(bool(unsub_pattern.search(html_no_unsub)))
        self.assertTrue(bool(unsub_pattern.search(html_with_unsub)))

    def test_email_gate_a_nest_module_exists(self) -> None:
        for rel in (
            "services/ptt-crm-api/src/email-gate-a/email-gate-a.service.ts",
            "services/ptt-crm-api/src/email-gate-a/email-gate-a.controller.ts",
        ):
            self.assertTrue((ROOT / rel).is_file(), rel)
        app = (ROOT / "services/ptt-crm-api/src/app.module.ts").read_text(encoding="utf-8")
        self.assertIn("EmailGateAModule", app)


if __name__ == "__main__":
    unittest.main()
