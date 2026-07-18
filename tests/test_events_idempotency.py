"""Tests for domain event idempotency (Phase 2 P1 #8)."""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from ptt_jobs.events_catalog import build_event_idempotency_key, lead_assigned_idempotency_key


class TestEventsCatalog(unittest.TestCase):
    def test_lead_assigned_key(self) -> None:
        self.assertEqual(lead_assigned_idempotency_key(42, 7), "lead:42:assigned:7")

    def test_build_key_lead_assigned(self) -> None:
        key = build_event_idempotency_key("LeadAssigned", {"lead_id": 1, "owner_id": 2})
        self.assertEqual(key, "lead:1:assigned:2")

    def test_build_key_unknown(self) -> None:
        self.assertIsNone(build_event_idempotency_key("JobCompleted", {"job_id": 1}))

    def test_build_key_lead_created(self) -> None:
        key = build_event_idempotency_key("LeadCreated", {"lead_id": 7})
        self.assertEqual(key, "lead:7:created")


class TestEmitDomainEventIdempotency(unittest.TestCase):
    @patch("ptt_jobs.events.pg_connection")
    def test_emit_with_idempotency_key(self, mock_pg: MagicMock) -> None:
        conn = MagicMock()
        cur = MagicMock()
        cur.fetchone.return_value = ("ev-1",)
        conn.cursor.return_value.__enter__.return_value = cur
        mock_pg.return_value.__enter__.return_value = conn

        from ptt_jobs.events import emit_domain_event

        out = emit_domain_event(
            "LeadAssigned",
            "lead",
            "42",
            {"lead_id": 42, "owner_id": 7},
        )
        self.assertEqual(out, "ev-1")
        sql = cur.execute.call_args[0][0]
        self.assertIn("idempotency_key", sql)
        self.assertIn("ON CONFLICT", sql)

    @patch("ptt_jobs.events.pg_connection")
    def test_emit_duplicate_returns_none(self, mock_pg: MagicMock) -> None:
        conn = MagicMock()
        cur = MagicMock()
        cur.fetchone.return_value = None
        conn.cursor.return_value.__enter__.return_value = cur
        mock_pg.return_value.__enter__.return_value = conn

        from ptt_jobs.events import emit_domain_event

        out = emit_domain_event(
            "LeadAssigned",
            "lead",
            "42",
            {"lead_id": 42, "owner_id": 7},
        )
        self.assertIsNone(out)


if __name__ == "__main__":
    unittest.main()
