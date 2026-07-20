#!/usr/bin/env python3
"""Unit tests — Wave 3 CRM gates."""
from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from ptt_crm.crm_flask_retirement_registry import CRM_MODULES, CrmModuleStatus
from ptt_crm.wave3_gates import run_gates


class Wave3GateTests(unittest.TestCase):
    def test_wave3_gates_pass(self) -> None:
        with patch.dict(
            os.environ,
            {
                "PTT_CRM_MARKETING_PLANS_UPSTREAM": "ops-web",
                "PTT_FLASK_CRM_MARKETING_PLANS_RETIRED": "1",
                "PTT_CRM_SERVICE_LIFECYCLE_UPSTREAM": "ops-web",
                "PTT_FLASK_CRM_SERVICE_LIFECYCLE_RETIRED": "1",
                "PTT_CRM_SOP_UPSTREAM": "ops-web",
                "PTT_FLASK_CRM_SOP_RETIRED": "1",
                "WAVE3_EXPECT_OPS_WEB": "1",
            },
            clear=False,
        ):
            report = run_gates()
        self.assertTrue(report["ok"])
        ids = [c["id"] for c in report["checks"]]
        self.assertIn("W3-G01", ids)
        self.assertIn("W3-G07", ids)

    def test_wave3_modules_partial(self) -> None:
        for mid in ("marketing_plans", "service_lifecycle", "sop"):
            mod = next(m for m in CRM_MODULES if m.id == mid)
            self.assertEqual(mod.status, CrmModuleStatus.PARTIAL)
            self.assertIsNotNone(mod.nest_module)


if __name__ == "__main__":
    unittest.main()
