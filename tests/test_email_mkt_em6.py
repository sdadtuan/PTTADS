#!/usr/bin/env python3
"""Unit tests — EM-6 Send Platform."""
from __future__ import annotations

import json
import os
import unittest
import uuid
from unittest.mock import patch

from ptt_channel.adapters.email import EmailAdapter
from ptt_channel.context import AdapterContext
from ptt_email.config import email_send_enabled
from ptt_email.engagement_ingest import ingest_events


class EmailAdapterTests(unittest.TestCase):
    def test_send_batch_dry_run(self) -> None:
        adapter = EmailAdapter()
        ctx = AdapterContext(
            client_id=str(uuid.uuid4()),
            channel_account_id="",
            credential_ref="",
            request_id="req-1",
        )
        out = adapter.send_batch(
            ctx,
            [
                {
                    "send_id": str(uuid.uuid4()),
                    "to_email": "test@example.com",
                    "subject": "Hi",
                    "html_body": "<p>Hello</p>",
                    "from_email": "noreply@example.com",
                    "custom_args": {"send_id": "abc"},
                }
            ],
            api_key=None,
            dry_run=True,
        )
        self.assertTrue(out["ok"])
        self.assertEqual(out["mode"], "dry_run")
        self.assertTrue(out["results"][0]["ok"])

    def test_parse_webhook_events_array(self) -> None:
        adapter = EmailAdapter()
        body = json.dumps([{"event": "open", "email": "a@b.com", "timestamp": 1}]).encode()
        parsed = adapter.parse_webhook({}, body, client_id="client-1")
        self.assertTrue(parsed.verified)
        self.assertEqual(len(parsed.events), 1)


class EngagementIngestTests(unittest.TestCase):
    @patch("ptt_email.engagement_ingest.pg_connection")
    def test_ingest_skips_unknown_event(self, mock_pg) -> None:
        conn = mock_pg.return_value.__enter__.return_value
        cur = conn.cursor.return_value.__enter__.return_value
        cur.fetchone.return_value = None
        out = ingest_events([{"event": "unknown_event"}], client_id=str(uuid.uuid4()))
        self.assertTrue(out["ok"])
        self.assertEqual(out["inserted"], 0)
        self.assertGreaterEqual(out["skipped"], 1)


class EmailConfigTests(unittest.TestCase):
    def test_send_enabled_default(self) -> None:
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("PTT_EMAIL_SEND_ENABLED", None)
            self.assertTrue(email_send_enabled())

    def test_send_disabled(self) -> None:
        with patch.dict(os.environ, {"PTT_EMAIL_SEND_ENABLED": "0"}):
            self.assertFalse(email_send_enabled())


if __name__ == "__main__":
    unittest.main()
