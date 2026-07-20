#!/usr/bin/env python3
"""Unit tests — Wave 5 CRM gates."""
from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from ptt_crm.config import payroll_ops_on_ops_web, re_projects_ops_on_ops_web
from ptt_crm.crm_flask_retirement_registry import CRM_MODULES, CrmModuleStatus
from ptt_crm.wave5_gates import run_gates


class Wave5GateTests(unittest.TestCase):
    def test_wave5_config_flags(self) -> None:
        with patch.dict(
            os.environ,
            {
                "PTT_CRM_RE_PROJECTS_UPSTREAM": "ops-web",
                "PTT_FLASK_CRM_RE_PROJECTS_RETIRED": "1",
                "PTT_CRM_PAYROLL_UPSTREAM": "ops-web",
                "PTT_FLASK_CRM_PAYROLL_RETIRED": "1",
            },
            clear=False,
        ):
            self.assertTrue(re_projects_ops_on_ops_web())
            self.assertTrue(payroll_ops_on_ops_web())

    def test_wave5_modules_partial(self) -> None:
        for mid in ("re_projects", "payroll"):
            mod = next(m for m in CRM_MODULES if m.id == mid)
            self.assertEqual(mod.status, CrmModuleStatus.PARTIAL)
            self.assertIsNotNone(mod.nest_module)
            self.assertIsNotNone(mod.ops_web_route)

    def test_wave5_infra_gates(self) -> None:
        with patch.dict(
            os.environ,
            {
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
            },
            clear=False,
        ):
            report = run_gates()
        infra_ids = {"W5-G03", "W5-G05"}
        for check in report["checks"]:
            if check["id"] in infra_ids:
                self.assertTrue(check["ok"], msg=f"{check['id']}: {check}")
        ids = [c["id"] for c in report["checks"]]
        self.assertIn("W5-G03", ids)
        self.assertIn("W5-G05", ids)


if __name__ == "__main__":
    unittest.main()
