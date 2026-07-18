"""Tests: backfill draft lifecycle → presales (P4)."""
from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path


class PresalesLegacyBackfillTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "test.db"
        conn = sqlite3.connect(self.db)
        conn.row_factory = sqlite3.Row
        conn.executescript(
            """
            CREATE TABLE crm_leads (
                id INTEGER PRIMARY KEY,
                full_name TEXT,
                owner_id INTEGER,
                care_stage_current TEXT NOT NULL DEFAULT 'advise',
                care_stages_done_json TEXT NOT NULL DEFAULT '{"intake":"2026-01-01","first_contact":"2026-01-01","qualify":"2026-01-01"}'
            );
            INSERT INTO crm_leads (id, full_name, owner_id) VALUES (1, 'Lead A', 5);

            CREATE TABLE crm_staff (id INTEGER PRIMARY KEY, name TEXT);
            INSERT INTO crm_staff (id, name) VALUES (5, 'AM');

            CREATE TABLE crm_service_lifecycle (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lead_id INTEGER,
                customer_id INTEGER,
                contract_id INTEGER,
                service_slug TEXT,
                stage TEXT,
                status TEXT,
                assigned_am INTEGER,
                stage_entered_at TEXT,
                notes TEXT,
                created_at TEXT,
                updated_at TEXT
            );

            CREATE TABLE crm_service_lifecycle_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lifecycle_id INTEGER,
                from_stage TEXT,
                to_stage TEXT,
                actor_type TEXT,
                notes TEXT,
                created_at TEXT
            );

            CREATE TABLE crm_svc_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lifecycle_id INTEGER,
                stage TEXT,
                step_index INTEGER,
                title TEXT,
                description TEXT,
                form_fields TEXT DEFAULT '[]',
                form_data TEXT DEFAULT '{}',
                is_done INTEGER DEFAULT 0,
                done_at TEXT DEFAULT '',
                done_by INTEGER,
                notes TEXT DEFAULT '',
                is_custom INTEGER DEFAULT 0,
                created_at TEXT,
                updated_at TEXT
            );

            CREATE TABLE crm_contracts (
                id INTEGER PRIMARY KEY,
                customer_id INTEGER,
                lead_id INTEGER,
                title TEXT,
                status TEXT DEFAULT 'draft',
                service_slug TEXT DEFAULT '',
                created_at TEXT,
                updated_at TEXT
            );
            """
        )
        conn.commit()
        conn.close()

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db)
        conn.row_factory = sqlite3.Row
        return conn

    def _seed_draft_lifecycle(self, conn: sqlite3.Connection) -> int:
        from crm_lead_presales import ensure_schema
        from crm_svc_tasks import ensure_schema as ensure_svc_tasks

        ensure_schema(conn)
        ensure_svc_tasks(conn)
        cur = conn.execute(
            """
            INSERT INTO crm_service_lifecycle
                (lead_id, service_slug, stage, status, assigned_am, notes, created_at, updated_at)
            VALUES (1, 'dich-vu-aeo', 'consult', 'draft', 5, '', '2026-01-01', '2026-01-01')
            """
        )
        lc_id = int(cur.lastrowid)
        conn.execute(
            """
            INSERT INTO crm_svc_tasks
                (lifecycle_id, stage, step_index, title, form_data, is_done, notes, created_at, updated_at)
            VALUES (?, 'lead', 0, 'Lead task', '{"x":1}', 1, 'done lead', '2026-01-01', '2026-01-01')
            """,
            (lc_id,),
        )
        conn.commit()
        return lc_id

    def test_list_pending(self) -> None:
        from crm_lead_presales_legacy import list_draft_lifecycles_pending_backfill

        with self._conn() as conn:
            lc_id = self._seed_draft_lifecycle(conn)
            pending = list_draft_lifecycles_pending_backfill(conn)
            self.assertEqual(len(pending), 1)
            self.assertEqual(int(pending[0]["id"]), lc_id)

    def test_migrate_creates_presales_and_archives_lifecycle(self) -> None:
        from crm_lead_presales_legacy import migrate_draft_lifecycle_to_presales

        with self._conn() as conn:
            lc_id = self._seed_draft_lifecycle(conn)
            summary = migrate_draft_lifecycle_to_presales(conn, lc_id)
            self.assertEqual(summary["action"], "migrated")
            self.assertEqual(summary["presales_stage"], "consult")
            self.assertGreaterEqual(int(summary["tasks_copied"]), 1)

            lc = conn.execute(
                "SELECT status, notes FROM crm_service_lifecycle WHERE id = ?",
                (lc_id,),
            ).fetchone()
            self.assertEqual(lc["status"], "closed")
            self.assertIn("[P4 backfill]", lc["notes"])

            ps = conn.execute(
                "SELECT stage, status FROM crm_lead_presales WHERE lead_id = 1"
            ).fetchone()
            self.assertEqual(ps["stage"], "consult")
            self.assertEqual(ps["status"], "active")

            done = conn.execute(
                """
                SELECT is_done, form_data FROM crm_lead_presales_tasks t
                INNER JOIN crm_lead_presales p ON p.id = t.presales_id
                WHERE p.lead_id = 1 AND t.stage = 'lead'
                """
            ).fetchone()
            self.assertEqual(int(done["is_done"]), 1)
            self.assertIn('"x"', done["form_data"])

    def test_skip_when_presales_already_active(self) -> None:
        from crm_lead_presales import ensure_presales, ensure_schema
        from crm_lead_presales_legacy import migrate_draft_lifecycle_to_presales

        with self._conn() as conn:
            ensure_schema(conn)
            lc_id = self._seed_draft_lifecycle(conn)
            ensure_presales(conn, 1, "dich-vu-aeo")
            summary = migrate_draft_lifecycle_to_presales(conn, lc_id)
            self.assertEqual(summary["action"], "skip")
            self.assertEqual(summary["reason"], "presales_active")

            lc = conn.execute(
                "SELECT status FROM crm_service_lifecycle WHERE id = ?", (lc_id,)
            ).fetchone()
            self.assertEqual(lc["status"], "draft")


if __name__ == "__main__":
    unittest.main()
