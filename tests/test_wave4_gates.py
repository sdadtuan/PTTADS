#!/usr/bin/env python3
"""Unit tests — Wave 4 CRM gates."""
from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from ptt_crm.crm_flask_retirement_registry import CRM_MODULES, CrmModuleStatus
from ptt_crm.wave4_gates import run_gates


class Wave4GateTests(unittest.TestCase):
    def test_wave4_gates_pass(self) -> None:
        with patch.dict(
            os.environ,
            {
                "PTT_CRM_SALES_UPSTREAM": "ops-web",
                "PTT_FLASK_CRM_SALES_RETIRED": "1",
                "PTT_CRM_KPI_UPSTREAM": "ops-web",
                "PTT_FLASK_CRM_KPI_RETIRED": "1",
                "PTT_CRM_STAFF_UPSTREAM": "ops-web",
                "PTT_FLASK_CRM_STAFF_RETIRED": "1",
                "WAVE4_EXPECT_OPS_WEB": "1",
            },
            clear=False,
        ):
            report = run_gates()
        self.assertTrue(report["ok"])
        ids = [c["id"] for c in report["checks"]]
        self.assertIn("W4-G01", ids)

    def test_wave4_modules_partial(self) -> None:
        for mid in ("sales", "kpi", "staff"):
            mod = next(m for m in CRM_MODULES if m.id == mid)
            self.assertEqual(mod.status, CrmModuleStatus.PARTIAL)
            self.assertIsNotNone(mod.nest_module)


if __name__ == "__main__":
    unittest.main()
