"""Tests: KPI readiness banner + backfill AM cho staff."""
from __future__ import annotations

import sqlite3
import unittest

from crm_service_lifecycle import (
    backfill_assigned_am_for_staff,
    create_draft_lifecycle,
    ensure_schema,
)
from crm_svc_kpi import get_staff_kpi_readiness


def _setup_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    ensure_schema(conn)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS crm_leads (
            id INTEGER PRIMARY KEY,
            owner_id INTEGER
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
    conn.execute("INSERT INTO crm_staff (id, name) VALUES (5, 'AM Five'), (6, 'AM Six')")
    conn.execute("INSERT INTO crm_leads (id, owner_id) VALUES (50, 6), (54, 6), (99, 5)")
    conn.commit()
    return conn


class TestStaffKpiReadiness(unittest.TestCase):
    def test_gap_banner_when_leads_but_no_lifecycle(self):
        conn = _setup_conn()
        r = get_staff_kpi_readiness(conn, 6)
        self.assertEqual(r["leads_owned"], 2)
        self.assertEqual(r["lifecycles_as_am"], 0)
        self.assertTrue(r["show_gap_banner"])
        self.assertIn(50, r["lead_ids"])
        self.assertIn(54, r["lead_ids"])

    def test_no_gap_when_lifecycle_assigned(self):
        conn = _setup_conn()
        create_draft_lifecycle(conn, lead_id=50, service_slug="dich-vu-aeo")
        r = get_staff_kpi_readiness(conn, 6)
        self.assertFalse(r["show_gap_banner"])
        self.assertEqual(r["lifecycles_as_am"], 1)

    def test_backfill_for_staff_syncs_from_lead_owner(self):
        conn = _setup_conn()
        lid = create_draft_lifecycle(conn, lead_id=50, service_slug="dich-vu-aeo")
        conn.execute(
            "UPDATE crm_service_lifecycle SET assigned_am = NULL WHERE id = ?", (lid,)
        )
        conn.commit()
        result = backfill_assigned_am_for_staff(conn, 6)
        self.assertGreaterEqual(result["total_updated"], 1)
        row = conn.execute(
            "SELECT assigned_am FROM crm_service_lifecycle WHERE id = ?", (lid,)
        ).fetchone()
        self.assertEqual(int(row["assigned_am"]), 6)


if __name__ == "__main__":
    unittest.main()
