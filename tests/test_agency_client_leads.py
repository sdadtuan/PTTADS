"""Tests for agency client leads bridge."""
from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch


class TestAgencyClientLeads(unittest.TestCase):
    def test_list_leads_for_client_filters_meta(self) -> None:
        from ptt_agency.leads import list_leads_for_client

        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "t.db"
            conn = sqlite3.connect(db)
            conn.execute(
                """
                CREATE TABLE crm_leads (
                    id INTEGER PRIMARY KEY,
                    full_name TEXT, phone TEXT, email TEXT,
                    status TEXT, source TEXT, created_at TEXT,
                    owner_id INTEGER, is_duplicate INTEGER DEFAULT 0,
                    meta_json TEXT NOT NULL DEFAULT '{}'
                )
                """
            )
            cid = "550e8400-e29b-41d4-a716-446655440000"
            conn.execute(
                "INSERT INTO crm_leads (full_name, phone, status, source, created_at, meta_json) VALUES (?,?,?,?,?,?)",
                ("A", "090", "new", "facebook", "2026-07-17", json.dumps({"agency_client_id": cid})),
            )
            conn.execute(
                "INSERT INTO crm_leads (full_name, phone, status, source, created_at, meta_json) VALUES (?,?,?,?,?,?)",
                ("B", "091", "new", "web", "2026-07-17", json.dumps({"agency_client_id": "other"})),
            )
            conn.commit()
            conn.close()

            with patch("ptt_crm.leads_read.sqlite_db_path", return_value=str(db)):
                rows = list_leads_for_client(cid)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["full_name"], "A")

    @patch("app._admin_logged_in", return_value=True)
    @patch("blueprints.agency._can", return_value=True)
    def test_api_client_leads(self, _can: MagicMock, _auth: MagicMock) -> None:
        from app import app

        client = app.test_client()
        with patch("ptt_agency.clients.fetch_client", return_value={"id": "x", "code": "PTT"}):
            with patch(
                "ptt_agency.leads.list_leads_for_client",
                return_value=[{"id": 1, "full_name": "Test"}],
            ):
                resp = client.get("/api/v1/clients/x/leads")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(len(data["leads"]), 1)


if __name__ == "__main__":
    unittest.main()
