"""Tests for PROD-H gates (Prod-S4)."""
from __future__ import annotations

import os
import unittest
from unittest import mock


class TestProdHStubAudit(unittest.TestCase):
    def test_stub_flags_off_by_default(self) -> None:
        from ptt_crm.prod_h_gates import audit_prod_stub_flags

        with mock.patch.dict(os.environ, {}, clear=False):
            for name in (
                "PTT_ZALO_ADS_STUB",
                "PTT_GOOGLE_ADS_STUB",
                "PTT_META_TOKEN_REFRESH_STUB",
            ):
                os.environ.pop(name, None)
            out = audit_prod_stub_flags()
        self.assertTrue(out.get("ok"))


if __name__ == "__main__":
    unittest.main()
