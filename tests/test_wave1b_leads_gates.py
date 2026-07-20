#!/usr/bin/env python3
"""Unit tests — Wave 1b CRM leads legacy gates."""
from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from ptt_crm.wave1b_leads_gates import run_gates


class Wave1bLeadsGateTests(unittest.TestCase):
    def test_wave1b_leads_gates_pass(self) -> None:
        with patch.dict(
            os.environ,
            {
                "PTT_CRM_LEADS_LEGACY_UPSTREAM": "nest",
                "PTT_FLASK_CRM_LEADS_LEGACY_RETIRED": "1",
                "WAVE1B_EXPECT_LEADS_LEGACY_NEST": "1",
                "WAVE1B_SKIP_BUILD": "1",
            },
            clear=False,
        ):
            report = run_gates()
        self.assertTrue(report["ok"])
        ids = [c["id"] for c in report["checks"]]
        self.assertIn("W1B-G01", ids)
        self.assertIn("W1B-G02", ids)


if __name__ == "__main__":
    unittest.main()
