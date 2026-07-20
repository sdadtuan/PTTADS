#!/usr/bin/env python3
"""Unit tests — Wave 2 CRM customers + intake gates."""
from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from ptt_crm.wave2_gates import run_gates


class Wave2GateTests(unittest.TestCase):
    def test_wave2_gates_pass(self) -> None:
        with patch.dict(
            os.environ,
            {
                "PTT_CRM_CUSTOMERS_UPSTREAM": "ops-web",
                "PTT_FLASK_CRM_CUSTOMERS_RETIRED": "1",
                "PTT_CRM_INTAKE_UPSTREAM": "ops-web",
                "PTT_FLASK_CRM_INTAKE_RETIRED": "1",
                "WAVE2_EXPECT_CUSTOMERS_OPS_WEB": "1",
                "WAVE2_EXPECT_INTAKE_OPS_WEB": "1",
            },
            clear=False,
        ):
            report = run_gates()
        self.assertTrue(report["ok"])
        ids = [c["id"] for c in report["checks"]]
        self.assertIn("W2-G01", ids)
        self.assertIn("W2-G04", ids)


if __name__ == "__main__":
    unittest.main()
