#!/usr/bin/env python3
"""Unit tests — Wave 5+ CRM gates (RE accounting phase)."""
from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from ptt_crm.config import re_projects_accounting_on_nest
from ptt_crm.crm_flask_retirement_registry import CRM_MODULES, CrmModuleStatus
from ptt_crm.wave5_plus_gates import run_gates


class Wave5PlusGateTests(unittest.TestCase):
    _WAVE5_PLUS_ENV = {
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
    }

    def test_wave5_plus_config_flags(self) -> None:
        with patch.dict(os.environ, self._WAVE5_PLUS_ENV, clear=False):
            self.assertTrue(re_projects_accounting_on_nest())

    def test_wave5_plus_gates_pass(self) -> None:
        with patch.dict(os.environ, self._WAVE5_PLUS_ENV, clear=False):
            report = run_gates()
        self.assertTrue(report["ok"], msg=str(report.get("failed_ids")))
        ids = [c["id"] for c in report["checks"]]
        self.assertIn("W5P-G01", ids)
        self.assertIn("W5P-G02", ids)
        self.assertIn("W5P-G03", ids)

    def test_wave5_plus_registry_notes(self) -> None:
        mod = next(m for m in CRM_MODULES if m.id == "re_projects")
        self.assertEqual(mod.status, CrmModuleStatus.PARTIAL)
        self.assertIn("accounting", mod.notes.lower())


if __name__ == "__main__":
    unittest.main()
