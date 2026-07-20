#!/usr/bin/env python3
"""Unit tests — Wave 1 CRM catalog gates."""
from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from ptt_crm.wave1_catalog_gates import run_gates


class Wave1CatalogGateTests(unittest.TestCase):
    def test_wave1_catalog_gates_pass(self) -> None:
        with patch.dict(
            os.environ,
            {
                "PTT_CRM_CATALOG_UPSTREAM": "ops-web",
                "PTT_FLASK_CRM_CATALOG_RETIRED": "1",
                "WAVE1_EXPECT_CATALOG_OPS_WEB": "1",
                "WAVE1_SKIP_JEST": "1",
            },
            clear=False,
        ):
            report = run_gates()
        self.assertTrue(report["ok"])
        ids = [c["id"] for c in report["checks"]]
        self.assertIn("W1-G01", ids)
        self.assertIn("W1-G02", ids)


if __name__ == "__main__":
    unittest.main()
