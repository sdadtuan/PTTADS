"""Tests for SQLite → PG lead replica sync (Phase 1b Bước 6)."""
from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from ptt_crm.lead_sync import sqlite_row_to_pg_record, sync_lead_ids


class TestLeadSyncMapping(unittest.TestCase):
    def test_sqlite_row_to_pg_record(self) -> None:
        row = {
            "id": 1,
            "full_name": "Lead A",
            "phone": "0901111111",
            "email": "",
            "status": "new",
            "source": "facebook",
            "owner_id": None,
            "created_at": "2026-07-17",
            "is_duplicate": 0,
            "meta_json": json.dumps(
                {
                    "agency_client_id": "550e8400-e29b-41d4-a716-446655440000",
                    "channel": "meta",
                    "facebook_leadgen_id": "fb-1",
                }
            ),
        }
        rec = sqlite_row_to_pg_record(row)
        self.assertEqual(rec["sqlite_lead_id"], 1)
        self.assertEqual(rec["channel"], "meta")
        self.assertEqual(rec["agency_client_id"], "550e8400-e29b-41d4-a716-446655440000")
        self.assertEqual(rec["external_lead_id"], "fb-1")


@unittest.skipUnless(
    __import__("ptt_jobs.db", fromlist=["pg_available"]).pg_available()
    and __import__("ptt_crm.pg_schema", fromlist=["pg_leads_replica_ready"]).pg_leads_replica_ready(),
    "PostgreSQL crm_leads replica unavailable",
)
class TestLeadSyncIntegration(unittest.TestCase):
    def test_sync_and_reconcile_roundtrip(self) -> None:
        from ptt_crm.lead_sync import reconcile_leads, sync_lead_ids

        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "sync.db"
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
            conn.execute(
                "INSERT INTO crm_leads (full_name, phone, status, source, created_at, meta_json) VALUES (?,?,?,?,?,?)",
                (
                    "Sync Test",
                    "0902222222",
                    "new",
                    "facebook",
                    "2026-07-17",
                    json.dumps({"channel": "meta", "facebook_leadgen_id": "sync-1"}),
                ),
            )
            conn.commit()
            lead_id = int(conn.execute("SELECT id FROM crm_leads").fetchone()[0])
            conn.close()

            with patch("ptt_crm.lead_sync.sqlite_db_path", return_value=str(db)):
                with patch("ptt_crm.leads_read.sqlite_db_path", return_value=str(db)):
                    out = sync_lead_ids([lead_id])
                    self.assertTrue(out["ok"])
                    self.assertEqual(out["synced"], 1)
                    report = reconcile_leads(sample_size=5)
                    self.assertTrue(report["ok"], report)


class TestSyncLeadReplicaJob(unittest.TestCase):
    @patch("ptt_jobs.handlers.sync_lead_replica.sync_incremental")
    @patch("ptt_jobs.handlers.sync_lead_replica.mark_job_done")
    def test_job_incremental(self, mock_done: MagicMock, mock_sync: MagicMock) -> None:
        from ptt_jobs.handlers.sync_lead_replica import run_sync_lead_replica_job

        mock_sync.return_value = {"ok": True, "synced": 3}
        run_sync_lead_replica_job({"id": "j1", "payload": {"mode": "incremental"}, "attempts": 1, "max_attempts": 3})
        mock_done.assert_called_once()


if __name__ == "__main__":
    unittest.main()
