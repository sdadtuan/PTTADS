#!/usr/bin/env python3
"""Unit tests — Wave 2+ CRM gates."""
from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from ptt_crm.wave2_plus_gates import run_gates


class Wave2PlusGateTests(unittest.TestCase):
    def test_wave2_plus_gates_pass(self) -> None:
        with patch.dict(
            os.environ,
            {
                "PTT_CRM_CUSTOMERS_UPSTREAM": "ops-web",
                "PTT_FLASK_CRM_CUSTOMERS_RETIRED": "1",
                "PTT_CRM_INTAKE_UPSTREAM": "ops-web",
                "PTT_FLASK_CRM_INTAKE_RETIRED": "1",
                "WAVE2_EXPECT_CUSTOMERS_OPS_WEB": "1",
                "WAVE2_EXPECT_INTAKE_OPS_WEB": "1",
                "PTT_CRM_CASES_UPSTREAM": "nest",
                "PTT_FLASK_CRM_CASES_RETIRED": "1",
                "WAVE2P_EXPECT_CASES_NEST": "1",
            },
            clear=False,
        ):
            report = run_gates()
        self.assertTrue(report["ok"])
        ids = [c["id"] for c in report["checks"]]
        self.assertIn("W2P-G03", ids)


if __name__ == "__main__":
    unittest.main()
