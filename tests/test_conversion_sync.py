"""Tests for B9 conversion_sync backfill."""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from ptt_meta.conversion_sync import (
    intent_already_sent,
    process_conversion_eval_payload,
    process_conversion_intents,
    run_conversion_sync,
)


class TestConversionSync(unittest.TestCase):
    @patch("ptt_meta.conversion_sync.find_capi_log_dedup")
    def test_intent_already_sent_true(self, mock_find: MagicMock) -> None:
        mock_find.return_value = {"status": "sent"}
        self.assertTrue(
            intent_already_sent(
                {
                    "client_id": "c1",
                    "event_name": "CompleteRegistration",
                    "event_id": "e1",
                }
            )
        )

    @patch("ptt_meta.conversion_sync.enqueue_conversion_intent")
    @patch("ptt_meta.conversion_sync.intent_already_sent", return_value=False)
    def test_process_intents_enqueue(self, _dedup: MagicMock, mock_enqueue: MagicMock) -> None:
        mock_enqueue.return_value = {"id": "j1"}
        out = process_conversion_intents(
            [
                {
                    "ok": True,
                    "client_id": "c1",
                    "lead_id": 1,
                    "event_name": "CompleteRegistration",
                    "event_id": "e1",
                    "event": {"event_name": "CompleteRegistration", "event_id": "e1"},
                }
            ],
            mode="enqueue",
        )
        self.assertEqual(out.get("enqueued"), 1)

    @patch("ptt_meta.conversion_sync.process_conversion_intents")
    @patch("ptt_meta.conversion_sync.evaluate_conversion_rules")
    @patch("ptt_meta.conversion_sync.load_lead_for_capi")
    def test_process_conversion_eval_payload(
        self,
        mock_load: MagicMock,
        mock_eval: MagicMock,
        mock_process: MagicMock,
    ) -> None:
        mock_load.return_value = {"id": 5, "status": "qualified", "agency_client_id": "c1"}
        mock_eval.return_value = [{"ok": True, "event_name": "CompleteRegistration"}]
        mock_process.return_value = {"ok": True, "dispatch_count": 1}
        out = process_conversion_eval_payload(
            {
                "lead_id": 5,
                "client_id": "c1",
                "old_status": "new",
                "new_status": "qualified",
            }
        )
        self.assertTrue(out.get("ok") is not False or out.get("dispatch_count") is not None)

    @patch("ptt_meta.conversion_sync.process_conversion_intents")
    @patch("ptt_meta.conversion_sync.evaluate_conversion_rules")
    @patch("ptt_meta.conversion_sync.load_lead_for_capi")
    @patch("ptt_meta.conversion_sync.list_leads_for_conversion_sync")
    @patch("ptt_meta.conversion_sync.pg_capi_ready", return_value=True)
    @patch("ptt_meta.conversion_sync.conversion_sync_enabled", return_value=True)
    def test_run_conversion_sync_scans_leads(
        self,
        _enabled: MagicMock,
        _ready: MagicMock,
        mock_list: MagicMock,
        mock_load: MagicMock,
        mock_eval: MagicMock,
        mock_process: MagicMock,
    ) -> None:
        mock_list.return_value = [
            {"sqlite_lead_id": 1, "agency_client_id": "c1", "status": "qualified"},
        ]
        mock_load.return_value = {"id": 1, "status": "qualified"}
        mock_eval.return_value = []
        mock_process.return_value = {"enqueued": 0, "deduped": 0}
        out = run_conversion_sync(client_id="c1", lookback_hours=24)
        self.assertTrue(out.get("ok"))
        self.assertEqual(out.get("leads_scanned"), 1)


if __name__ == "__main__":
    unittest.main()
