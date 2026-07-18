"""Tests for LeadAssigned RMQ E2E gate (Phase 2 P1 #7)."""
from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from ptt_crm.lead_assigned_e2e import (
    count_lead_assigned_events,
    run_lead_assigned_rmq_e2e,
    verify_idempotency_duplicate_assign,
    wait_for_event_published,
)


class TestLeadAssignedE2E(unittest.TestCase):
    @patch("ptt_crm.lead_assigned_e2e._http_json")
    def test_create_staging_lead(self, mock_http: MagicMock) -> None:
        from ptt_crm.lead_assigned_e2e import create_staging_lead

        mock_http.return_value = (201, {"id": 900_000_001, "full_name": "X"})
        out = create_staging_lead()
        self.assertTrue(out["ok"])
        self.assertEqual(out["lead_id"], 900_000_001)

    @patch("ptt_jobs.db.pg_connection")
    def test_count_lead_assigned_events(self, mock_pg: MagicMock) -> None:
        conn = MagicMock()
        cur = MagicMock()
        now = datetime.now(timezone.utc)
        cur.fetchall.return_value = [
            ("e1", "lead:42:assigned:7", now, now - timedelta(seconds=2), {"owner_id": 7}),
        ]
        conn.cursor.return_value.__enter__.return_value = cur
        mock_pg.return_value.__enter__.return_value = conn
        out = count_lead_assigned_events(lead_id=42, owner_id=7)
        self.assertTrue(out["ok"])
        self.assertEqual(out["count"], 1)
        self.assertEqual(out["idempotency_key"], "lead:42:assigned:7")

    @patch("ptt_crm.lead_assigned_e2e.publish_outbox_batch", return_value={"ok": True, "published_count": 1})
    @patch("ptt_jobs.db.pg_connection")
    def test_wait_for_event_published(self, mock_pg: MagicMock, _pub: MagicMock) -> None:
        conn = MagicMock()
        cur = MagicMock()
        now = datetime.now(timezone.utc)
        cur.fetchone.return_value = ("e1", now, now - timedelta(seconds=1), "lead:42:assigned:7")
        conn.cursor.return_value.__enter__.return_value = cur
        mock_pg.return_value.__enter__.return_value = conn
        out = wait_for_event_published("e1", timeout_sec=2, auto_publish=False)
        self.assertTrue(out["ok"])
        self.assertLessEqual(float(out["publish_lag_sec"]), 30)

    @patch("ptt_crm.lead_assigned_e2e.verify_idempotency_duplicate_assign")
    @patch("ptt_crm.lead_assigned_e2e.wait_for_event_published")
    @patch("ptt_crm.lead_assigned_e2e.publish_outbox_batch")
    @patch("ptt_crm.lead_assigned_e2e.count_lead_assigned_events")
    @patch("ptt_crm.lead_assigned_e2e.assign_lead_via_nest")
    @patch("ptt_crm.lead_assigned_e2e.create_staging_lead")
    def test_run_lead_assigned_rmq_e2e(
        self,
        mock_create: MagicMock,
        mock_assign: MagicMock,
        mock_count: MagicMock,
        mock_pub: MagicMock,
        mock_wait: MagicMock,
        mock_idem: MagicMock,
    ) -> None:
        mock_create.return_value = {"ok": True, "lead_id": 900_000_010}
        mock_assign.return_value = {"ok": True, "lead_id": 900_000_010, "owner_id": 99}
        mock_count.return_value = {"ok": True, "count": 1, "events": [{"id": "ev-1"}]}
        mock_pub.return_value = {"ok": True, "published_count": 1}
        mock_wait.return_value = {"ok": True, "publish_lag_sec": 1.0}
        mock_idem.return_value = {"ok": True, "event_count": 1}
        out = run_lead_assigned_rmq_e2e()
        self.assertTrue(out["ok"])

    @patch("ptt_crm.lead_assigned_e2e.count_lead_assigned_events")
    @patch("ptt_crm.lead_assigned_e2e.assign_lead_via_nest")
    def test_verify_idempotency(self, mock_assign: MagicMock, mock_count: MagicMock) -> None:
        mock_assign.return_value = {"ok": True}
        mock_count.return_value = {"ok": True, "count": 1, "events": []}
        out = verify_idempotency_duplicate_assign(42, 7)
        self.assertTrue(out["ok"])
        self.assertEqual(mock_assign.call_count, 3)


if __name__ == "__main__":
    unittest.main()
