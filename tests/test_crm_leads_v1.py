"""Tests for /api/v1/leads and domain events."""
from __future__ import annotations


import os
import unittest

if os.environ.get("PTT_RUN_FLASK_TESTS") != "1":
    raise unittest.SkipTest(
        "Flask HTTP removed — set PTT_RUN_FLASK_TESTS=1 to run integration tests"
    )
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch


class TestCrmLeadsV1(unittest.TestCase):
    def _seed_db(self, tmp: str) -> Path:
        db = Path(tmp) / "t.db"
        conn = sqlite3.connect(db)
        conn.execute(
            """

            CREATE TABLE crm_leads (
                id INTEGER PRIMARY KEY,
                full_name TEXT, phone TEXT, email TEXT,
                status TEXT, source TEXT, owner_id INTEGER,
                created_at TEXT, is_duplicate INTEGER DEFAULT 0,
                meta_json TEXT NOT NULL DEFAULT '{}'
            )
            """
        )
        cid = "550e8400-e29b-41d4-a716-446655440000"
        conn.execute(
            "INSERT INTO crm_leads (full_name, phone, status, source, created_at, meta_json) VALUES (?,?,?,?,?,?)",
            (
                "Lead A",
                "0901111111",
                "new",
                "facebook",
                "2026-07-17",
                json.dumps({"agency_client_id": cid, "channel": "meta", "facebook_leadgen_id": "fb-1"}),
            ),
        )
        conn.commit()
        conn.close()
        return db

    def test_list_leads_v1_filters_client(self) -> None:
        from ptt_crm.leads_read import get_lead_v1, list_leads_v1

        with tempfile.TemporaryDirectory() as tmp:
            db = self._seed_db(tmp)
            with patch("ptt_crm.leads_read.sqlite_db_path", return_value=str(db)):
                rows, total = list_leads_v1(client_id="550e8400-e29b-41d4-a716-446655440000")
                self.assertEqual(total, 1)
                self.assertEqual(rows[0]["full_name"], "Lead A")
                self.assertEqual(rows[0]["channel"], "meta")
                self.assertEqual(rows[0]["external_lead_id"], "fb-1")
                lead = get_lead_v1(1)
                self.assertIsNotNone(lead)
                assert lead is not None
                self.assertEqual(lead["client_id"], "550e8400-e29b-41d4-a716-446655440000")

    @patch("app._admin_logged_in", return_value=True)
    @patch("blueprints.crm_leads_v1._can", return_value=True)
    def test_api_list_leads(self, _can: MagicMock, _auth: MagicMock) -> None:
        from app import app

        client = app.test_client()
        with patch(
            "ptt_crm.leads_read.list_leads_v1",
            return_value=([{"id": 1, "full_name": "X"}], 1),
        ):
            resp = client.get("/api/v1/leads?limit=10")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data["total"], 1)
        self.assertEqual(data["leads"][0]["full_name"], "X")

    @patch("app._admin_logged_in", return_value=True)
    @patch("blueprints.crm_leads_v1._can", return_value=True)
    def test_api_get_lead_404(self, _can: MagicMock, _auth: MagicMock) -> None:
        from app import app

        client = app.test_client()
        with patch("ptt_crm.leads_read.get_lead_v1", return_value=None):
            resp = client.get("/api/v1/leads/999")
        self.assertEqual(resp.status_code, 404)


class TestDomainEvents(unittest.TestCase):
    @patch("ptt_jobs.broker.event_publish_rmq_enabled", return_value=False)
    def test_publish_pending_noop_when_disabled(self, _flag: MagicMock) -> None:
        from ptt_jobs.broker import publish_pending_events

        self.assertEqual(publish_pending_events(), 0)

    @patch("ptt_jobs.broker.event_publish_rmq_enabled", return_value=True)
    @patch("ptt_jobs.broker.publish_domain_event_message", return_value=True)
    @patch("ptt_jobs.events_store.mark_event_published", return_value=True)
    @patch("ptt_jobs.events_store.fetch_unpublished_events")
    def test_publish_pending_marks_published(
        self,
        mock_fetch: MagicMock,
        _mark: MagicMock,
        _pub: MagicMock,
        _flag: MagicMock,
    ) -> None:
        from ptt_jobs.broker import publish_pending_events

        mock_fetch.return_value = [{"id": "ev-1", "event_type": "LeadCreated", "payload": {}}]
        self.assertEqual(publish_pending_events(), 1)

    @patch("app._admin_logged_in", return_value=True)
    @patch("blueprints.crm_leads_v1._can", return_value=True)
    @patch("ptt_jobs.events_store.list_domain_events", return_value=[])
    @patch("ptt_jobs.events_store.event_stats", return_value={"total": 0, "unpublished": 0})
    def test_api_events(self, _stats: MagicMock, _list: MagicMock, _can: MagicMock, _auth: MagicMock) -> None:
        from app import app

        client = app.test_client()
        resp = client.get("/api/v1/events")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("events", resp.get_json())


if __name__ == "__main__":
    unittest.main()
