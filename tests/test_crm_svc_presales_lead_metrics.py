"""Tests get_am_lead_metrics — Phase L2."""
from __future__ import annotations

import sqlite3
import unittest

from crm_lead_intake import ensure_schema as intake_schema
from crm_svc_finance import create_expense, ensure_schema as finance_schema
from crm_svc_presales import get_am_lead_metrics


def _setup_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        "CREATE TABLE crm_staff (id INTEGER PRIMARY KEY, name TEXT, active INTEGER DEFAULT 1)"
    )
    conn.execute("INSERT INTO crm_staff (id, name) VALUES (1, 'AM One')")
    conn.execute("""
        CREATE TABLE crm_service_lifecycle (
            id INTEGER PRIMARY KEY,
            assigned_am INTEGER,
            stage TEXT NOT NULL DEFAULT 'lead',
            status TEXT NOT NULL DEFAULT 'draft',
            service_slug TEXT DEFAULT 'dich-vu-aeo',
            created_at TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL DEFAULT ''
        )
    """)
    conn.execute("""
        CREATE TABLE crm_svc_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lifecycle_id INTEGER NOT NULL,
            stage TEXT NOT NULL DEFAULT 'lead',
            title TEXT DEFAULT '',
            is_done INTEGER NOT NULL DEFAULT 0,
            updated_at TEXT NOT NULL DEFAULT ''
        )
    """)
    finance_schema(conn)
    intake_schema(conn)
    conn.execute(
        """
        INSERT INTO crm_service_lifecycle
            (id, assigned_am, stage, status, created_at, updated_at)
        VALUES
            (1, 1, 'lead', 'draft', '2026-06-02 08:00:00', '2026-06-02 08:00:00'),
            (2, 1, 'consult', 'draft', '2026-06-03 09:00:00', '2026-06-05 10:00:00'),
            (3, 2, 'lead', 'draft', '2026-06-04 09:00:00', '2026-06-04 09:00:00')
        """
    )
    conn.execute(
        """
        INSERT INTO crm_lead_intake_sessions
            (lifecycle_id, mode, status, decision, started_at, completed_at, service_slug)
        VALUES
            (1, 'phone', 'completed', 'go',
             '2026-06-02 09:00:00', '2026-06-02 09:20:00', 'dich-vu-aeo'),
            (2, 'in_person', 'completed', 'go',
             '2026-06-05 10:00:00', '2026-06-05 11:00:00', 'dich-vu-aeo')
        """
    )
    conn.execute(
        """
        INSERT INTO crm_svc_tasks (lifecycle_id, stage, title, is_done, updated_at)
        VALUES (1, 'lead', 'Lead task', 1, '2026-06-02 12:00:00')
        """
    )
    create_expense(
        conn,
        1,
        "Gọi",
        "dien_thoai",
        100_000,
        "2026-06-02",
        cost_phase="presales",
        lifecycle_stage="lead",
    )
    conn.commit()
    return conn


class TestAmLeadMetrics(unittest.TestCase):
    def test_empty_staff_returns_zeros(self):
        conn = _setup_conn()
        m = get_am_lead_metrics(conn, 99, 2026, 6)
        self.assertEqual(m["lead_intake_completed"], 0)
        self.assertEqual(m["presales_cost_vnd"], 0)

    def test_counts_intake_go_consult_presales(self):
        conn = _setup_conn()
        m = get_am_lead_metrics(conn, 1, 2026, 6)
        self.assertEqual(m["lead_intake_completed"], 2)
        self.assertEqual(m["lead_go_decisions"], 2)
        self.assertEqual(m["lead_to_consult_num"], 1)
        self.assertEqual(m["lead_to_consult_pct"], 50.0)
        self.assertEqual(m["lead_task_done"], 1)
        self.assertEqual(m["presales_cost_vnd"], 100_000)
        self.assertAlmostEqual(m["lead_avg_phone_minutes"], 20.0, places=1)

    def test_phone_within_48h_pct(self):
        conn = _setup_conn()
        m = get_am_lead_metrics(conn, 1, 2026, 6)
        self.assertEqual(m["lead_phone_within_48h_denom"], 2)
        self.assertEqual(m["lead_phone_within_48h_num"], 1)
        self.assertEqual(m["lead_phone_within_48h_pct"], 50.0)


if __name__ == "__main__":
    unittest.main()
