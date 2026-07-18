"""Tests for ptt_jobs queue and webhook wiring."""
from __future__ import annotations

import json
import unittest
from unittest.mock import MagicMock, patch

from ptt_channel.enums import ChannelCode
from ptt_channel.mappers import normalized_lead_to_legacy


class TestNormalizedLeadToLegacy(unittest.TestCase):
    def test_from_normalized_dict(self) -> None:
        lead = {
            "channel": "meta",
            "external_lead_id": "12345",
            "contact": {"full_name": "A", "phone": "0901111222", "email": "a@x.com"},
            "utm": {"campaign": "camp1"},
            "fields": {},
            "raw": {},
        }
        item = normalized_lead_to_legacy(lead)
        self.assertEqual(item["full_name"], "A")
        self.assertEqual(item["source"], "facebook")
        self.assertEqual(item["meta"]["facebook_leadgen_id"], "12345")
        self.assertEqual(item["utm_campaign"], "camp1")

    def test_prefers_raw_legacy_row(self) -> None:
        raw = {
            "full_name": "Legacy",
            "phone": "090",
            "email": "",
            "source": "facebook",
            "meta": {"facebook_leadgen_id": "99"},
        }
        lead = {"channel": "meta", "contact": {}, "raw": raw}
        self.assertEqual(normalized_lead_to_legacy(lead), raw)


class TestEnqueueSyncFallback(unittest.TestCase):
    def test_sync_when_pg_unavailable(self) -> None:
        leads = [
            {
                "channel": "meta",
                "external_lead_id": "ext-1",
                "idempotency_key": "ingest:meta:ext-1",
                "contact": {"full_name": "T", "phone": "0909999888", "email": ""},
                "raw": {
                    "full_name": "T",
                    "phone": "0909999888",
                    "email": "",
                    "source": "facebook",
                    "meta": {"facebook_leadgen_id": "ext-1"},
                },
            }
        ]
        with patch("ptt_jobs.enqueue.pg_available", return_value=False):
            with patch("ptt_jobs.enqueue.process_leads_sync") as mock_sync:
                mock_sync.return_value = {"created_count": 1, "results": []}
                from ptt_jobs.enqueue import enqueue_ingest_leads

                out = enqueue_ingest_leads(leads, channel="meta", correlation_id="c1")
        self.assertEqual(out["mode"], "sync")
        mock_sync.assert_called_once()


class TestChannelWebhookBlueprint(unittest.TestCase):
    def setUp(self) -> None:
        from app import app

        self.app = app
        self.client = app.test_client()

    @patch("ptt_jobs.enqueue.enqueue_ingest_leads")
    @patch("blueprints.channel_webhooks.parse_channel_webhook")
    def test_webhook_enqueues_leads(self, mock_parse: MagicMock, mock_enqueue: MagicMock) -> None:
        mock_parse.return_value = {
            "verified": True,
            "channel": "meta",
            "leads": [{"external_lead_id": "1", "idempotency_key": "k1"}],
            "events": [],
        }
        mock_enqueue.return_value = {
            "mode": "queue",
            "jobs": [{"id": "job-uuid", "created": True}],
            "ingest": None,
        }
        resp = self.client.post(
            "/api/v1/webhooks/meta",
            data=b"{}",
            headers={"Content-Type": "application/json", "X-PTT-Client-Id": "client-1"},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data.get("accepted"))
        self.assertEqual(data.get("mode"), "queue")
        self.assertEqual(data.get("job_ids"), ["job-uuid"])
        mock_enqueue.assert_called_once()

    @patch("blueprints.channel_webhooks.parse_channel_webhook")
    def test_webhook_challenge(self, mock_parse: MagicMock) -> None:
        mock_parse.return_value = {"verified": True, "challenge": "999"}
        resp = self.client.get("/api/v1/webhooks/meta?hub.mode=subscribe")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data.decode(), "999")


class TestIngestLeadHandler(unittest.TestCase):
    def test_process_ingest_calls_crm(self) -> None:
        payload = {
            "channel": "meta",
            "client_id": "550e8400-e29b-41d4-a716-446655440000",
            "lead": {
                "channel": "meta",
                "external_lead_id": "ingest-test-001",
                "contact": {"full_name": "Queue Test", "phone": "0901234567", "email": ""},
                "raw": {
                    "full_name": "Queue Test",
                    "phone": "0901234567",
                    "email": "",
                    "source": "facebook",
                    "meta": {"facebook_leadgen_id": "ingest-test-001"},
                },
            },
        }
        mock_conn = MagicMock()
        with patch("ptt_jobs.handlers.ingest_lead.sqlite3.connect", return_value=mock_conn):
            with patch("crm_lead_webhooks.ingest_webhook_leads") as mock_ingest:
                mock_ingest.return_value = {"created_count": 1, "created_ids": [42], "skipped": []}
                with patch("ptt_jobs.handlers.ingest_lead.emit_domain_event", return_value="ev-1"):
                    from ptt_jobs.handlers.ingest_lead import process_ingest_lead_payload

                    result = process_ingest_lead_payload(payload, correlation_id="corr-1")

        self.assertTrue(result.get("ok"))
        self.assertEqual(result.get("created_count"), 1)
        mock_ingest.assert_called_once()
        call_item = mock_ingest.call_args[0][1][0]
        self.assertEqual(call_item["meta"]["facebook_leadgen_id"], "ingest-test-001")
        self.assertEqual(call_item["meta"]["agency_client_id"], "550e8400-e29b-41d4-a716-446655440000")


if __name__ == "__main__":
    unittest.main()
