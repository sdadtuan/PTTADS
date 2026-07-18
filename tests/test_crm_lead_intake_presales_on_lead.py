"""Tests L5 — intake stats dual path + AM cap alerts presales-on-lead."""
from __future__ import annotations

import os
import sqlite3
import unittest

from crm_lead_intake import ensure_schema as intake_schema
from crm_lead_intake import get_intake_stats
from crm_lead_presales import ensure_schema as presales_schema
from crm_svc_finance import create_presales_expense, ensure_schema as finance_schema
from crm_svc_presales import (
    get_am_presales_cap_alerts,
    set_presales_cost_cap_for_presales,
)


def _setup_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(
        """
        CREATE TABLE crm_staff (id INTEGER PRIMARY KEY, name TEXT, active INTEGER DEFAULT 1);
        INSERT INTO crm_staff (id, name) VALUES (1, 'AM One');

        CREATE TABLE crm_leads (
            id INTEGER PRIMARY KEY,
            full_name TEXT,
            owner_id INTEGER,
            created_at TEXT NOT NULL DEFAULT '2026-06-01 08:00:00'
        );
        INSERT INTO crm_leads (id, full_name, owner_id) VALUES
            (10, 'Lead Presales', 1),
            (20, 'Lead Legacy', 2);

        CREATE TABLE crm_service_lifecycle (
            id INTEGER PRIMARY KEY,
            lead_id INTEGER,
            assigned_am INTEGER,
            service_slug TEXT NOT NULL DEFAULT 'dich-vu-aeo',
            stage TEXT NOT NULL DEFAULT 'lead',
            status TEXT NOT NULL DEFAULT 'draft',
            created_at TEXT NOT NULL DEFAULT '2026-06-01 08:00:00'
        );
        INSERT INTO crm_service_lifecycle
            (id, lead_id, assigned_am, service_slug, stage, status)
        VALUES
            (100, 20, 2, 'dich-vu-seo-tong-the', 'lead', 'draft'),
            (101, 10, 1, 'dich-vu-aeo', 'lead', 'draft');
        """
    )
    presales_schema(conn)
    finance_schema(conn)
    intake_schema(conn)
    conn.execute(
        """
        INSERT INTO crm_lead_presales
            (id, lead_id, service_slug, stage, status, assigned_am,
             created_at, updated_at)
        VALUES
            (1, 10, 'dich-vu-aeo', 'lead', 'active', 1,
             '2026-06-02', '2026-06-02')
        """
    )
    conn.commit()
    return conn


class TestIntakeStatsPresalesOnLead(unittest.TestCase):
    def setUp(self) -> None:
        self._env = os.environ.get("PTT_PRESALES_ON_LEAD")
        os.environ["PTT_PRESALES_ON_LEAD"] = "1"

    def tearDown(self) -> None:
        if self._env is None:
            os.environ.pop("PTT_PRESALES_ON_LEAD", None)
        else:
            os.environ["PTT_PRESALES_ON_LEAD"] = self._env

    def test_dual_intake_counts_presales_path(self) -> None:
        conn = _setup_conn()
        conn.execute(
            """
            INSERT INTO crm_lead_intake_sessions
                (lead_id, service_slug, mode, status, decision, bant_total, completed_at)
            VALUES (10, 'dich-vu-aeo', 'phone', 'completed', 'go', 24, '2026-06-03 10:00:00')
            """
        )
        conn.commit()

        stats = get_intake_stats(conn)
        self.assertTrue(stats["dual_intake"])
        self.assertEqual(stats["presales_on_lead"]["total_presales"], 1)
        self.assertEqual(stats["presales_on_lead"]["presales_with_completed_intake"], 1)
        self.assertEqual(stats["lifecycle"]["total_lifecycles"], 1)
        self.assertEqual(stats["lifecycle"]["lifecycles_with_completed_intake"], 0)
        self.assertEqual(stats["total_lifecycles"], 2)
        self.assertEqual(stats["lifecycles_with_completed_intake"], 1)
        self.assertEqual(stats["intake_coverage_pct"], 50.0)

    def test_legacy_lifecycle_intake_still_counted(self) -> None:
        conn = _setup_conn()
        conn.execute(
            """
            INSERT INTO crm_lead_intake_sessions
                (lifecycle_id, service_slug, mode, status, decision, completed_at)
            VALUES (100, 'dich-vu-seo-tong-the', 'phone', 'completed', 'go', '2026-06-03 10:00:00')
            """
        )
        conn.commit()

        stats = get_intake_stats(conn)
        self.assertEqual(stats["lifecycle"]["lifecycles_with_completed_intake"], 1)
        self.assertEqual(stats["presales_on_lead"]["presales_with_completed_intake"], 0)

    def test_am_cap_alerts_for_presales_lead(self) -> None:
        conn = _setup_conn()
        set_presales_cost_cap_for_presales(conn, 1, 100_000)
        create_presales_expense(
            conn,
            lead_id=10,
            title="Gọi",
            category="dien_thoai",
            amount_vnd=150_000,
            expense_on="2026-06-03",
        )
        alerts = get_am_presales_cap_alerts(conn, 1)
        self.assertEqual(alerts["over_cap_count"], 1)
        self.assertEqual(alerts["alerts"][0]["lead_id"], 10)


if __name__ == "__main__":
    unittest.main()
