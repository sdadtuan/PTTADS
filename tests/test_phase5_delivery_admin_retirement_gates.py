#!/usr/bin/env python3
"""Unit tests — delivery admin Flask retirement gates."""
from __future__ import annotations

import unittest
from unittest.mock import patch

from ptt_crm.phase5_delivery_admin_retirement_gates import run_gates


class DeliveryAdminRetireTests(unittest.TestCase):
    @patch.dict(
        "os.environ",
        {
            "PTT_FLASK_SEO_ADMIN_RETIRED": "1",
            "PTT_FLASK_EMAIL_ADMIN_RETIRED": "1",
            "PHASE5DA_SKIP_BUILD": "1",
        },
        clear=False,
    )
    def test_gates_pass(self) -> None:
        report = run_gates()
        self.assertTrue(report["ok"], report.get("failed_ids"))


if __name__ == "__main__":
    unittest.main()
