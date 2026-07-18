"""Tests for PG → SQLite lead shadow sync (Phase 2 W2)."""
from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from ptt_crm.lead_shadow_sync import pg_row_to_sqlite_record, upsert_sqlite_lead


class TestShadowSyncMapping(unittest.TestCase):
    def test_pg_row_to_sqlite_record(self) -> None:
        row = {
            "sqlite_lead_id": 42,
            "full_name": "Shadow Lead",
            "phone": "0903333333",
            "email": "a@b.com",
            "status": "assigned",
            "source": "facebook",
            "owner_id": 7,
            "is_duplicate": False,
            "meta_json": {"score": 80},
            "agency_client_id": "550e8400-e29b-41d4-a716-446655440000",
            "channel": "meta",
            "external_lead_id": "fb-shadow-1",
            "campaign_id": "camp-1",
            "received_at": None,
            "created_at": "2026-07-17",
            "sync_version": 5,
            "updated_at": "2026-07-17",
            "updated_by": "nest",
            "write_source": "nest",
        }
        rec = pg_row_to_sqlite_record(row)
        self.assertEqual(rec["id"], 42)
        self.assertEqual(rec["owner_id"], 7)
        self.assertEqual(rec["phone_norm"], "0903333333")
        meta = json.loads(rec["meta_json"])
        self.assertEqual(meta["agency_client_id"], "550e8400-e29b-41d4-a716-446655440000")
        self.assertEqual(meta["facebook_leadgen_id"], "fb-shadow-1")
        self.assertTrue(meta["shadow_from_pg"])

    def test_upsert_sqlite_insert_and_update(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "shadow.db"
            conn = sqlite3.connect(db)
            conn.execute(
                """
                CREATE TABLE crm_leads (
                    id INTEGER PRIMARY KEY,
                    full_name TEXT, phone TEXT, phone_norm TEXT,
                    email TEXT, email_norm TEXT, source TEXT, status TEXT,
                    owner_id INTEGER, is_duplicate INTEGER DEFAULT 0,
                    meta_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT, updated_at TEXT,
                    created_by TEXT DEFAULT '', updated_by TEXT DEFAULT ''
                )
                """
            )
            conn.commit()
            conn.close()

            rec = pg_row_to_sqlite_record(
                {
                    "sqlite_lead_id": 99,
                    "full_name": "A",
                    "phone": "0901",
                    "email": "",
                    "status": "new",
                    "source": "staging",
                    "owner_id": None,
                    "is_duplicate": False,
                    "meta_json": {},
                    "agency_client_id": None,
                    "channel": "",
                    "external_lead_id": None,
                    "campaign_id": None,
                    "received_at": None,
                    "created_at": "2026-07-17",
                    "sync_version": 1,
                    "write_source": "nest",
                }
            )
            with patch("ptt_crm.lead_shadow_sync.sqlite_db_path", return_value=str(db)):
                self.assertEqual(upsert_sqlite_lead(rec), "insert")
                rec["status"] = "assigned"
                rec["owner_id"] = 3
                self.assertEqual(upsert_sqlite_lead(rec), "update")
                conn = sqlite3.connect(db)
                row = conn.execute("SELECT status, owner_id FROM crm_leads WHERE id = 99").fetchone()
                self.assertEqual(row, ("assigned", 3))
                conn.close()


@unittest.skipUnless(
    __import__("ptt_jobs.db", fromlist=["pg_available"]).pg_available()
    and __import__("ptt_crm.pg_schema", fromlist=["pg_shadow_ready"]).pg_shadow_ready(),
    "PostgreSQL shadow state unavailable",
)
class TestShadowSyncIntegration(unittest.TestCase):
    def test_shadow_incremental_skips_replica_rows(self) -> None:
        from ptt_jobs.db import pg_connection

        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "shadow.db"
            conn = sqlite3.connect(db)
            conn.execute(
                """
                CREATE TABLE crm_leads (
                    id INTEGER PRIMARY KEY,
                    full_name TEXT, phone TEXT, phone_norm TEXT,
                    email TEXT, email_norm TEXT, source TEXT, status TEXT,
                    owner_id INTEGER, is_duplicate INTEGER DEFAULT 0,
                    meta_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT, updated_at TEXT,
                    created_by TEXT DEFAULT '', updated_by TEXT DEFAULT ''
                )
                """
            )
            conn.commit()
            conn.close()

            lead_id = 880_000_001
            with pg_connection() as pg:
                with pg.cursor() as cur:
                    cur.execute("DELETE FROM crm_leads WHERE sqlite_lead_id = %s", (lead_id,))
                    cur.execute(
                        """
                        INSERT INTO crm_leads (
                            sqlite_lead_id, full_name, phone, status, source, owner_id,
                            write_source, sync_version, meta_json
                        ) VALUES (%s, %s, %s, %s, %s, %s, 'nest', 999001, '{}'::jsonb)
                        ON CONFLICT (sqlite_lead_id) DO UPDATE SET
                            full_name = EXCLUDED.full_name,
                            phone = EXCLUDED.phone,
                            write_source = 'nest',
                            sync_version = GREATEST(crm_leads.sync_version, 999001),
                            owner_id = EXCLUDED.owner_id,
                            status = EXCLUDED.status
                        """,
                        (lead_id, "Shadow IT", "0908888888", "assigned", "staging", 5),
                    )
                    cur.execute(
                        """
                        UPDATE crm_leads_shadow_state
                        SET last_pg_version = 0
                        WHERE id = 1
                        """
                    )
                pg.commit()

            with patch("ptt_crm.lead_shadow_sync.sqlite_db_path", return_value=str(db)):
                with patch("ptt_crm.lead_shadow_sync.lead_shadow_sync_enabled", return_value=True):
                    from ptt_crm.lead_shadow_sync import sync_shadow_lead_ids

                    out = sync_shadow_lead_ids([lead_id])
                    self.assertTrue(out["ok"], out)
                    self.assertEqual(out.get("synced"), 1)
                    sqlite = sqlite3.connect(db)
                    row = sqlite.execute(
                        "SELECT full_name, owner_id FROM crm_leads WHERE id = ?",
                        (lead_id,),
                    ).fetchone()
                    sqlite.close()
                    self.assertIsNotNone(row)
                    self.assertEqual(row[0], "Shadow IT")
                    self.assertEqual(row[1], 5)


class TestSyncLeadShadowJob(unittest.TestCase):
    @patch("ptt_jobs.handlers.sync_lead_shadow.sync_shadow_incremental")
    @patch("ptt_jobs.handlers.sync_lead_shadow.mark_job_done")
    def test_job_incremental(self, mock_done: MagicMock, mock_sync: MagicMock) -> None:
        from ptt_jobs.handlers.sync_lead_shadow import run_sync_lead_shadow_job

        mock_sync.return_value = {"ok": True, "synced": 2}
        run_sync_lead_shadow_job({"id": "j1", "payload": {"mode": "incremental"}, "attempts": 1, "max_attempts": 3})
        mock_done.assert_called_once()


if __name__ == "__main__":
    unittest.main()
