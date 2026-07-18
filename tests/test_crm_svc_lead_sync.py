# tests/test_crm_svc_lead_sync.py
from __future__ import annotations

import sqlite3
import unittest

from crm_lead_care_pipeline import ensure_lead_care_pipeline_schema
from crm_service_lifecycle import create_draft_lifecycle, ensure_schema
from crm_svc_lead_sync import sync_lead_from_lifecycle_stage, sync_lifecycle_from_lead_care_stage
from crm_svc_tasks import complete_all_stage_tasks, ensure_schema as task_schema, seed_tasks


def _setup_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE crm_leads (
            id INTEGER PRIMARY KEY,
            meta_json TEXT DEFAULT '{}',
            status TEXT NOT NULL DEFAULT 'new',
            status_entered_at TEXT NOT NULL DEFAULT '',
            care_stage_current TEXT NOT NULL DEFAULT 'intake',
            care_stages_done_json TEXT NOT NULL DEFAULT '{}',
            updated_at TEXT NOT NULL DEFAULT '',
            updated_by TEXT NOT NULL DEFAULT '',
            full_name TEXT NOT NULL DEFAULT '',
            phone TEXT NOT NULL DEFAULT '',
            email TEXT NOT NULL DEFAULT ''
        )
        """
    )
    conn.execute("CREATE TABLE crm_staff (id INTEGER PRIMARY KEY)")
    conn.execute("INSERT INTO crm_leads (id, status) VALUES (1, 'new')")
    ensure_schema(conn)
    task_schema(conn)
    ensure_lead_care_pipeline_schema(conn)
    conn.commit()
    return conn


class TestSvcLeadSync(unittest.TestCase):
    def test_lifecycle_to_lead_updates_care_stage(self):
        conn = _setup_conn()
        lid = create_draft_lifecycle(conn, lead_id=1, service_slug="dich-vu-seo-tong-the")
        sync_lead_from_lifecycle_stage(
            conn,
            lifecycle_id=lid,
            to_stage="consult",
            ts="2026-06-30 10:00:00",
            actor="tester",
        )
        row = conn.execute(
            "SELECT care_stage_current FROM crm_leads WHERE id = 1"
        ).fetchone()
        self.assertEqual(row["care_stage_current"], "qualify")

    def test_lead_care_sync_advances_lifecycle(self):
        conn = _setup_conn()
        lid = create_draft_lifecycle(conn, lead_id=1, service_slug="dich-vu-seo-audit")
        seed_tasks(conn, lifecycle_id=lid, service_slug="dich-vu-seo-audit")
        sync_lifecycle_from_lead_care_stage(
            conn,
            lead_id=1,
            care_stage_key="closing",
            ts="2026-06-30 11:00:00",
            actor="tester",
        )
        row = conn.execute(
            "SELECT stage FROM crm_service_lifecycle WHERE id = ?", (lid,)
        ).fetchone()
        self.assertEqual(row["stage"], "onboard")


if __name__ == "__main__":
    unittest.main()
