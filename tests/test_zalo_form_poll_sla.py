"""Tests for Zalo form poll SLA monitor (Prod-S3)."""
from __future__ import annotations

import os
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch


class TestZaloFormPollSla(unittest.TestCase):
    @patch.dict(os.environ, {"PTT_ZALO_FORM_POLL_SLA": "0"}, clear=False)
    def test_disabled(self) -> None:
        from ptt_zalo.form_poll_sla import evaluate_form_poll_sla

        out = evaluate_form_poll_sla()
        self.assertTrue(out.get("skipped"))

    @patch("ptt_zalo.form_poll_sla.pg_zalo_leads_ready", return_value=True)
    @patch("ptt_zalo.form_poll_sla.list_stale_form_cursors")
    def test_dry_run_stale_count(self, mock_list, _ready) -> None:
        from ptt_zalo.form_poll_sla import evaluate_form_poll_sla

        old = datetime.now(timezone.utc) - timedelta(hours=1)
        mock_list.return_value = [
            {
                "client_id": "c-1",
                "client_code": "DEMO",
                "form_id": "f1",
                "oa_id": "oa1",
                "last_polled_at": old.isoformat(),
            }
        ]
        out = evaluate_form_poll_sla(dry_run=True)
        self.assertEqual(out.get("stale_count"), 1)


if __name__ == "__main__":
    unittest.main()
