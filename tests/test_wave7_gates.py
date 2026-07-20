#!/usr/bin/env python3
"""Unit tests — Wave 7 CRM gates (Phase 5 readiness)."""
from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from ptt_crm.config import crm_shell_ops_on_ops_web, phase5_migration_ready
from ptt_crm.crm_flask_retirement_registry import CRM_MODULES, CrmModuleStatus, gap_report
from ptt_crm.wave7_gates import run_gates


class Wave7GateTests(unittest.TestCase):
    _WAVE7_ENV = {
        "PTT_CRM_RE_PROJECTS_UPSTREAM": "ops-web",
        "PTT_FLASK_CRM_RE_PROJECTS_RETIRED": "1",
        "PTT_CRM_PAYROLL_UPSTREAM": "ops-web",
        "PTT_FLASK_CRM_PAYROLL_RETIRED": "1",
        "WAVE5_EXPECT_OPS_WEB": "1",
        "PTT_CRM_SALES_UPSTREAM": "ops-web",
        "PTT_FLASK_CRM_SALES_RETIRED": "1",
        "PTT_CRM_KPI_UPSTREAM": "ops-web",
        "PTT_FLASK_CRM_KPI_RETIRED": "1",
        "PTT_CRM_STAFF_UPSTREAM": "ops-web",
        "PTT_FLASK_CRM_STAFF_RETIRED": "1",
        "WAVE4_EXPECT_OPS_WEB": "1",
        "PTT_CRM_PROPOSALS_UPSTREAM": "ops-web",
        "PTT_FLASK_CRM_PROPOSALS_RETIRED": "1",
        "WAVE4P_EXPECT_OPS_WEB": "1",
        "PTT_CRM_RE_PROJECTS_ACCOUNTING_UPSTREAM": "nest",
        "PTT_FLASK_CRM_RE_PROJECTS_ACCOUNTING_RETIRED": "1",
        "WAVE5P_EXPECT_ACCOUNTING_NEST": "1",
        "PTT_CRM_RE_PROJECTS_KPI_RISKS_UPSTREAM": "nest",
        "PTT_FLASK_CRM_RE_PROJECTS_KPI_RISKS_RETIRED": "1",
        "WAVE5PP_EXPECT_KPI_RISKS_NEST": "1",
        "PTT_CRM_RE_PROJECTS_OPS_UPSTREAM": "nest",
        "PTT_FLASK_CRM_RE_PROJECTS_OPS_RETIRED": "1",
        "WAVE5PPP_EXPECT_OPS_NEST": "1",
        "PTT_CRM_FINANCE_UPSTREAM": "ops-web",
        "PTT_FLASK_CRM_FINANCE_RETIRED": "1",
        "WAVE6_EXPECT_FINANCE_NEST": "1",
        "PTT_CRM_SHELL_UPSTREAM": "ops-web",
        "PTT_FLASK_CRM_SHELL_RETIRED": "1",
        "WAVE7_EXPECT_SHELL_OPS_WEB": "1",
        "WAVE7_EXPECT_PHASE5_READY": "1",
    }

    def test_wave7_config_flags(self) -> None:
        with patch.dict(os.environ, self._WAVE7_ENV, clear=False):
            self.assertTrue(crm_shell_ops_on_ops_web())
            self.assertTrue(phase5_migration_ready())

    def test_wave7_gates_pass(self) -> None:
        with patch.dict(os.environ, self._WAVE7_ENV, clear=False):
            report = run_gates()
        self.assertTrue(report["ok"], msg=str(report.get("failed_ids")))
        ids = [c["id"] for c in report["checks"]]
        self.assertIn("W7-G01", ids)
        self.assertIn("W7-G02", ids)
        self.assertIn("W7-G03", ids)
        self.assertIn("W7-G04", ids)

    def test_wave7_registry_crm_shell_retired(self) -> None:
        mod = next(m for m in CRM_MODULES if m.id == "crm_shell")
        self.assertEqual(mod.status, CrmModuleStatus.RETIRED)
        self.assertIn("crm-board", mod.nest_module or "")
        self.assertEqual(mod.ops_web_route, "/crm")
        report = gap_report()
        self.assertTrue(report["can_stop_ptt_service"])
        self.assertEqual(report["flask_only"], 0)
        self.assertEqual(report["partial"], 0)
        self.assertEqual(report["ops_web"], 0)


if __name__ == "__main__":
    unittest.main()
