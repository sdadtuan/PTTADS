"""Tests get_am_lead_metrics — presales-on-lead path (L3.1)."""
from __future__ import annotations

import os
import sqlite3
import unittest

from crm_lead_intake import ensure_schema as intake_schema
from crm_lead_presales import ensure_schema as presales_schema
from crm_svc_finance import ensure_schema as finance_schema
from crm_svc_presales import get_am_lead_metrics


def _setup_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        "CREATE TABLE crm_staff (id INTEGER PRIMARY KEY, name TEXT, active INTEGER DEFAULT 1)"
    )
    conn.execute("INSERT INTO crm_staff (id, name) VALUES (1, 'AM One')")
    conn.execute(
        """
        CREATE TABLE crm_leads (
            id INTEGER PRIMARY KEY,
            full_name TEXT,
            owner_id INTEGER,
            created_at TEXT NOT NULL DEFAULT ''
        )
        """
    )
    conn.execute(
        """
        INSERT INTO crm_leads (id, full_name, owner_id, created_at)
        VALUES
            (10, 'Lead A', 1, '2026-06-02 08:00:00'),
            (11, 'Lead B', 1, '2026-06-03 09:00:00'),
            (12, 'Lead C', 2, '2026-06-04 09:00:00')
        """
    )
    conn.execute(
        """
        CREATE TABLE crm_service_lifecycle (
            id INTEGER PRIMARY KEY,
            lead_id INTEGER,
            assigned_am INTEGER,
            stage TEXT NOT NULL DEFAULT 'lead',
            status TEXT NOT NULL DEFAULT 'draft',
            service_slug TEXT DEFAULT 'dich-vu-aeo',
            created_at TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL DEFAULT ''
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE crm_svc_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lifecycle_id INTEGER NOT NULL,
            stage TEXT NOT NULL DEFAULT 'lead',
            title TEXT DEFAULT '',
            is_done INTEGER NOT NULL DEFAULT 0,
            updated_at TEXT NOT NULL DEFAULT ''
        )
        """
    )
    intake_schema(conn)
    presales_schema(conn)
    finance_schema(conn)
    conn.execute(
        """
        INSERT INTO crm_lead_intake_sessions
            (lead_id, mode, status, decision, started_at, completed_at, service_slug)
        VALUES
            (10, 'phone', 'completed', 'go',
             '2026-06-02 09:00:00', '2026-06-02 09:25:00', 'dich-vu-aeo'),
            (11, 'in_person', 'completed', 'go',
             '2026-06-05 10:00:00', '2026-06-05 11:00:00', 'dich-vu-aeo'),
            (12, 'phone', 'completed', 'nurture',
             '2026-06-04 10:00:00', '2026-06-04 10:15:00', 'dich-vu-aeo')
        """
    )
    conn.execute(
        """
        INSERT INTO crm_lead_presales
            (id, lead_id, service_slug, stage, status, assigned_am,
             stage_entered_at, notes, created_at, updated_at)
        VALUES
            (1, 10, 'dich-vu-aeo', 'consult', 'active', 1,
             '2026-06-05 10:00:00', '', '2026-06-02 08:30:00', '2026-06-05 10:00:00'),
            (2, 11, 'dich-vu-aeo', 'lead', 'active', 1,
             '2026-06-03 09:00:00', '', '2026-06-03 09:00:00', '2026-06-03 09:00:00'),
            (3, 12, 'dich-vu-aeo', 'lead', 'active', 2,
             '2026-06-04 09:00:00', '', '2026-06-04 09:00:00', '2026-06-04 09:00:00')
        """
    )
    conn.execute(
        """
        INSERT INTO crm_lead_presales_tasks
            (presales_id, stage, step_index, title, is_done, done_at, created_at, updated_at)
        VALUES
            (1, 'lead', 0, 'Lead task A', 1, '2026-06-02 12:00:00', '2026-06-02 08:30:00', '2026-06-02 12:00:00'),
            (2, 'lead', 0, 'Lead task B', 0, '', '2026-06-03 09:00:00', '2026-06-03 09:00:00')
        """
    )
    conn.commit()
    return conn


class TestAmLeadMetricsPresalesOnLead(unittest.TestCase):
    def setUp(self) -> None:
        self._env = os.environ.get("PTT_PRESALES_ON_LEAD")
        os.environ["PTT_PRESALES_ON_LEAD"] = "1"

    def tearDown(self) -> None:
        if self._env is None:
            os.environ.pop("PTT_PRESALES_ON_LEAD", None)
        else:
            os.environ["PTT_PRESALES_ON_LEAD"] = self._env

    def test_lead_only_intake_counts_without_lifecycle(self) -> None:
        conn = _setup_conn()
        m = get_am_lead_metrics(conn, 1, 2026, 6)
        self.assertEqual(m["lead_intake_completed"], 2)
        self.assertEqual(m["lead_go_decisions"], 2)
        self.assertEqual(m["lead_to_consult_num"], 1)
        self.assertEqual(m["lead_to_consult_pct"], 50.0)

    def test_presales_lead_tasks_counted(self) -> None:
        conn = _setup_conn()
        m = get_am_lead_metrics(conn, 1, 2026, 6)
        self.assertEqual(m["lead_task_done"], 1)

    def test_phone_within_48h_uses_lead_created_at(self) -> None:
        conn = _setup_conn()
        m = get_am_lead_metrics(conn, 1, 2026, 6)
        self.assertEqual(m["lead_phone_within_48h_denom"], 2)
        self.assertEqual(m["lead_phone_within_48h_num"], 1)
        self.assertEqual(m["lead_phone_within_48h_pct"], 50.0)

    def test_avg_phone_minutes_from_lead_intake(self) -> None:
        conn = _setup_conn()
        m = get_am_lead_metrics(conn, 1, 2026, 6)
        self.assertAlmostEqual(m["lead_avg_phone_minutes"], 25.0, places=1)

    def test_other_am_not_counted(self) -> None:
        conn = _setup_conn()
        m = get_am_lead_metrics(conn, 2, 2026, 6)
        self.assertEqual(m["lead_intake_completed"], 1)
        self.assertEqual(m["lead_go_decisions"], 0)


if __name__ == "__main__":
    unittest.main()
