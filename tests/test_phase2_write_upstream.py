"""Phase 2 — agency Nest module + write upstream config."""
from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from ptt_crm.config import lead_shadow_sync_enabled, leads_write_upstream
from ptt_crm.leads_write_upstream import nest_write_upstream_enabled


class TestPhase2WriteUpstream(unittest.TestCase):
    def test_default_flask_upstream(self) -> None:
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("PTT_LEADS_WRITE_UPSTREAM", None)
            self.assertEqual(leads_write_upstream(), "flask")
            self.assertFalse(nest_write_upstream_enabled())

    def test_nest_upstream(self) -> None:
        with patch.dict(os.environ, {"PTT_LEADS_WRITE_UPSTREAM": "nest"}, clear=False):
            self.assertEqual(leads_write_upstream(), "nest")
            self.assertTrue(nest_write_upstream_enabled())

    def test_shadow_sync_on_phase2_staging(self) -> None:
        with patch.dict(
            os.environ,
            {"PTT_LEADS_WRITE_SOURCE": "pg", "PTT_LEAD_SHADOW_SYNC": "1"},
            clear=False,
        ):
            self.assertTrue(lead_shadow_sync_enabled())


if __name__ == "__main__":
    unittest.main()
