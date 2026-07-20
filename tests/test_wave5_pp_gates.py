#!/usr/bin/env python3
"""Unit tests — Wave 5++ CRM gates (RE KPI/risks/budget phase)."""
from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from ptt_crm.config import re_projects_kpi_risks_on_nest
from ptt_crm.crm_flask_retirement_registry import CRM_MODULES, CrmModuleStatus
from ptt_crm.wave5_pp_gates import run_gates


class Wave5PpGateTests(unittest.TestCase):
    _WAVE5_PP_ENV = {
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
    }

    def test_wave5_pp_config_flags(self) -> None:
        with patch.dict(os.environ, self._WAVE5_PP_ENV, clear=False):
            self.assertTrue(re_projects_kpi_risks_on_nest())

    def test_wave5_pp_gates_pass(self) -> None:
        with patch.dict(os.environ, self._WAVE5_PP_ENV, clear=False):
            report = run_gates()
        self.assertTrue(report["ok"], msg=str(report.get("failed_ids")))
        ids = [c["id"] for c in report["checks"]]
        self.assertIn("W5PP-G01", ids)
        self.assertIn("W5PP-G02", ids)
        self.assertIn("W5PP-G03", ids)

    def test_wave5_pp_registry_notes(self) -> None:
        mod = next(m for m in CRM_MODULES if m.id == "re_projects")
        self.assertEqual(mod.status, CrmModuleStatus.PARTIAL)
        notes = mod.notes.lower()
        self.assertIn("kpi", notes)
        self.assertIn("risks", notes)
        self.assertIn("budget", notes)


if __name__ == "__main__":
    unittest.main()
