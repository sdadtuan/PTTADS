"""Tests: đồng bộ crm_leads.owner_id → crm_service_lifecycle.assigned_am (P0)."""
from __future__ import annotations

import sqlite3
import unittest

from crm_service_lifecycle import (
    backfill_assigned_am_from_leads,
    create_draft_lifecycle,
    ensure_schema,
    sync_assigned_am_for_lead,
    sync_assigned_am_from_lead,
)


def _setup_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    ensure_schema(conn)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS crm_leads (
            id INTEGER PRIMARY KEY,
            owner_id INTEGER,
            re_project_id INTEGER,
            full_name TEXT DEFAULT '',
            phone TEXT DEFAULT '',
            phone_norm TEXT DEFAULT '',
            email TEXT DEFAULT '',
            email_norm TEXT DEFAULT '',
            source TEXT DEFAULT 'web',
            region TEXT DEFAULT '',
            product_interest TEXT DEFAULT '',
            need TEXT DEFAULT '',
            lead_score INTEGER DEFAULT 0,
            lead_level TEXT DEFAULT 'warm',
            status TEXT DEFAULT 'new',
            meta_json TEXT DEFAULT '{}',
            status_entered_at TEXT DEFAULT '',
            updated_at TEXT DEFAULT '',
            updated_by TEXT DEFAULT '',
            created_at TEXT DEFAULT '',
            created_by TEXT DEFAULT '',
            care_stage_current TEXT DEFAULT '',
            care_stages_done_json TEXT DEFAULT '{}'
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS crm_staff (
            id INTEGER PRIMARY KEY,
            name TEXT DEFAULT '',
            active INTEGER DEFAULT 1
        )
        """
    )
    conn.execute("INSERT INTO crm_staff (id, name) VALUES (5, 'AM Five'), (9, 'AM Nine')")
    conn.execute("INSERT INTO crm_leads (id, owner_id) VALUES (1, 5), (2, NULL)")
    conn.commit()
    return conn


class TestLeadAmSync(unittest.TestCase):
    def test_create_draft_sets_assigned_am_from_lead_owner(self):
        conn = _setup_conn()
        lid = create_draft_lifecycle(conn, lead_id=1, service_slug="dich-vu-aeo")
        row = conn.execute(
            "SELECT assigned_am FROM crm_service_lifecycle WHERE id = ?", (lid,)
        ).fetchone()
        self.assertEqual(int(row["assigned_am"]), 5)

    def test_create_draft_without_lead_owner_leaves_am_null(self):
        conn = _setup_conn()
        lid = create_draft_lifecycle(conn, lead_id=2, service_slug="dich-vu-aeo")
        row = conn.execute(
            "SELECT assigned_am FROM crm_service_lifecycle WHERE id = ?", (lid,)
        ).fetchone()
        self.assertIsNone(row["assigned_am"])

    def test_sync_after_owner_assigned_on_existing_lifecycle(self):
        conn = _setup_conn()
        lid = create_draft_lifecycle(conn, lead_id=2, service_slug="dich-vu-seo-tong-the")
        conn.execute("UPDATE crm_leads SET owner_id = 9 WHERE id = 2")
        conn.commit()
        self.assertTrue(sync_assigned_am_from_lead(conn, lid, overwrite=False))
        row = conn.execute(
            "SELECT assigned_am FROM crm_service_lifecycle WHERE id = ?", (lid,)
        ).fetchone()
        self.assertEqual(int(row["assigned_am"]), 9)

    def test_sync_does_not_overwrite_without_flag(self):
        conn = _setup_conn()
        lid = create_draft_lifecycle(conn, lead_id=1, service_slug="dich-vu-aeo")
        conn.execute(
            "UPDATE crm_service_lifecycle SET assigned_am = 9 WHERE id = ?", (lid,)
        )
        conn.commit()
        self.assertFalse(sync_assigned_am_from_lead(conn, lid, overwrite=False))
        row = conn.execute(
            "SELECT assigned_am FROM crm_service_lifecycle WHERE id = ?", (lid,)
        ).fetchone()
        self.assertEqual(int(row["assigned_am"]), 9)

    def test_reassign_lead_owner_overwrites_assigned_am(self):
        conn = _setup_conn()
        lid = create_draft_lifecycle(conn, lead_id=1, service_slug="quang-cao-google")
        conn.execute("UPDATE crm_leads SET owner_id = 9 WHERE id = 1")
        conn.commit()
        updated = sync_assigned_am_for_lead(conn, 1, overwrite=True)
        self.assertEqual(updated, 1)
        row = conn.execute(
            "SELECT assigned_am FROM crm_service_lifecycle WHERE id = ?", (lid,)
        ).fetchone()
        self.assertEqual(int(row["assigned_am"]), 9)

    def test_update_lead_owner_pattern_syncs_lifecycle(self):
        conn = _setup_conn()
        lid = create_draft_lifecycle(conn, lead_id=2, service_slug="dich-vu-seo-local")
        conn.execute("UPDATE crm_leads SET owner_id = 9 WHERE id = 2")
        conn.commit()
        sync_assigned_am_for_lead(conn, 2, overwrite=True)
        row = conn.execute(
            "SELECT assigned_am FROM crm_service_lifecycle WHERE id = ?", (lid,)
        ).fetchone()
        self.assertEqual(int(row["assigned_am"]), 9)

    def test_backfill_only_null_assigned_am(self):
        conn = _setup_conn()
        lid1 = create_draft_lifecycle(conn, lead_id=1, service_slug="dich-vu-aeo")
        conn.execute(
            "UPDATE crm_service_lifecycle SET assigned_am = NULL WHERE id = ?", (lid1,)
        )
        conn.commit()
        count = backfill_assigned_am_from_leads(conn)
        self.assertGreaterEqual(count, 1)
        row = conn.execute(
            "SELECT assigned_am FROM crm_service_lifecycle WHERE id = ?", (lid1,)
        ).fetchone()
        self.assertEqual(int(row["assigned_am"]), 5)

    def test_backfill_for_staff_aggregates_lead_sync(self):
        conn = _setup_conn()
        from crm_service_lifecycle import backfill_assigned_am_for_staff

        lid = create_draft_lifecycle(conn, lead_id=1, service_slug="dich-vu-seo-tong-the")
        conn.execute(
            "UPDATE crm_service_lifecycle SET assigned_am = NULL WHERE id = ?", (lid,)
        )
        conn.commit()
        result = backfill_assigned_am_for_staff(conn, 5)
        self.assertGreaterEqual(result["total_updated"], 1)
        row = conn.execute(
            "SELECT assigned_am FROM crm_service_lifecycle WHERE id = ?", (lid,)
        ).fetchone()
        self.assertEqual(int(row["assigned_am"]), 5)

    def test_sync_assigned_am_for_lead_multiple_lifecycles(self):
        conn = _setup_conn()
        create_draft_lifecycle(conn, lead_id=1, service_slug="dich-vu-aeo")
        create_draft_lifecycle(conn, lead_id=1, service_slug="dich-vu-seo-tong-the")
        conn.execute("UPDATE crm_leads SET owner_id = 9 WHERE id = 1")
        conn.commit()
        updated = sync_assigned_am_for_lead(conn, 1, overwrite=True)
        self.assertEqual(updated, 2)
        rows = conn.execute(
            "SELECT assigned_am FROM crm_service_lifecycle WHERE lead_id = 1"
        ).fetchall()
        self.assertTrue(all(int(r["assigned_am"]) == 9 for r in rows))


if __name__ == "__main__":
    unittest.main()
