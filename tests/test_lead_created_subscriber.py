"""Tests for LeadCreated → CAPI subscriber (Phase 2 P2 #12)."""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from ptt_jobs.events_catalog import build_event_idempotency_key, lead_created_idempotency_key
from ptt_meta.lead_created_subscriber import process_lead_created_outbox


class TestLeadCreatedSubscriber(unittest.TestCase):
    def test_lead_created_idempotency_key(self) -> None:
        self.assertEqual(lead_created_idempotency_key(42), "lead:42:created")
        key = build_event_idempotency_key("LeadCreated", {"lead_id": 99})
        self.assertEqual(key, "lead:99:created")

    @patch("ptt_meta.capi_dispatch.enqueue_capi_lead_dispatch")
    @patch("ptt_meta.capi_dispatch.capi_stub_mode", return_value=True)
    @patch("ptt_meta.capi_dispatch.capi_dispatch_enabled", return_value=True)
    @patch("ptt_meta.lead_created_subscriber.fetch_recent_lead_created_events")
    def test_process_enqueues(
        self,
        mock_fetch: MagicMock,
        _en: MagicMock,
        _stub: MagicMock,
        mock_enqueue: MagicMock,
    ) -> None:
        mock_fetch.return_value = [
            {
                "id": "ev1",
                "payload": {"lead_id": 5, "client_id": "550e8400-e29b-41d4-a716-446655440000"},
                "correlation_id": "c1",
            }
        ]
        mock_enqueue.return_value = {"job_id": "j1"}
        out = process_lead_created_outbox()
        self.assertTrue(out["ok"])
        self.assertEqual(out["enqueued"], 1)
        mock_enqueue.assert_called_once()

    @patch("ptt_meta.capi_dispatch.capi_dispatch_enabled", return_value=False)
    @patch("ptt_meta.capi_dispatch.capi_stub_mode", return_value=False)
    def test_skips_when_disabled(self, _stub: MagicMock, _en: MagicMock) -> None:
        out = process_lead_created_outbox()
        self.assertTrue(out.get("skipped"))


if __name__ == "__main__":
    unittest.main()
