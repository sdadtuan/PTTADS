#!/usr/bin/env python3
"""Unit tests — CRM Flask retirement registry and gates."""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ptt_crm.crm_flask_retirement_gates import run_gates
from ptt_crm.crm_flask_retirement_registry import CRM_MODULES, CrmModuleStatus, gap_report


class CrmRegistryTests(unittest.TestCase):
    def test_gap_report_structure(self) -> None:
        report = gap_report()
        self.assertIn("migrated_pct", report)
        self.assertIn("flask_only", report)
        self.assertTrue(report["can_stop_ptt_service"])
        self.assertEqual(report["flask_only"], 0)
        self.assertEqual(report["partial"], 0)
        self.assertEqual(report["ops_web"], 0)
        self.assertEqual(report["retired"], len(CRM_MODULES))

    def test_all_modules_retired(self) -> None:
        for mod in CRM_MODULES:
            self.assertEqual(
                mod.status,
                CrmModuleStatus.RETIRED,
                msg=f"module {mod.id} should be RETIRED",
            )

    def test_crm_shell_retired(self) -> None:
        shell = next(m for m in CRM_MODULES if m.id == "crm_shell")
        self.assertEqual(shell.status, CrmModuleStatus.RETIRED)
        self.assertEqual(shell.ops_web_route, "/crm")
        self.assertIn("crm-board", shell.nest_module or "")

    def test_email_stays_retired(self) -> None:
        email = next(m for m in CRM_MODULES if m.id == "email")
        self.assertEqual(email.status, CrmModuleStatus.RETIRED)


class CrmGatesTests(unittest.TestCase):
    def test_gates_wave0_pass(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            art = Path(tmp)
            with patch.dict(
                os.environ,
                {
                    "PTT_ARTIFACTS_DIR": str(art),
                    "CRM_FLASK_REQUIRE_FULL_MIGRATION": "1",
                    "CRM_SKIP_PHASE5_PREREQ": "0",
                    "PTT_FLASK_MONOLITH_MODE": "retired",
                    "PTT_FLASK_SEO_ADMIN_RETIRED": "1",
                    "PTT_FLASK_EMAIL_ADMIN_RETIRED": "1",
                    "PTT_FLASK_META_ADS_ADMIN_RETIRED": "1",
                    "PTT_WEBHOOKS_NEST_META": "1",
                    "PTT_WEBHOOKS_FLASK_FALLBACK": "0",
                    "PTT_LEADS_READ_SOURCE": "pg",
                },
                clear=False,
            ):
                report = run_gates()
            self.assertTrue(report["ok"])
            self.assertTrue(report["stop_ptt_service_allowed"])
            saved = json.loads((art / "crm-flask-retirement-gate-report.json").read_text())
            self.assertTrue(saved["ok"])


if __name__ == "__main__":
    unittest.main()
