"""Tests L3.4 — dual cohort funnel (presales-on-lead + lifecycle legacy)."""
from __future__ import annotations

import os
import sqlite3
import unittest

from crm_lead_intake import ensure_schema as intake_schema
from crm_lead_presales import ensure_schema as presales_schema
from crm_svc_finance import create_presales_expense, ensure_schema as finance_schema
from crm_svc_presales import get_funnel_stats


def _setup_dual_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(
        """
        CREATE TABLE crm_staff (id INTEGER PRIMARY KEY, name TEXT, active INTEGER DEFAULT 1);
        INSERT INTO crm_staff (id, name) VALUES (1, 'AM One'), (2, 'AM Two');

        CREATE TABLE crm_leads (
            id INTEGER PRIMARY KEY,
            full_name TEXT,
            owner_id INTEGER,
            care_stage_current TEXT NOT NULL DEFAULT 'first_contact',
            care_stages_done_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL DEFAULT '2026-06-01 08:00:00'
        );
        INSERT INTO crm_leads (id, full_name, owner_id) VALUES
            (10, 'Lead Won', 1),
            (11, 'Lead Active', 1),
            (20, 'Lead Legacy', 2);

        CREATE TABLE crm_service_lifecycle (
            id INTEGER PRIMARY KEY,
            lead_id INTEGER,
            assigned_am INTEGER,
            service_slug TEXT NOT NULL DEFAULT 'dich-vu-aeo',
            stage TEXT NOT NULL DEFAULT 'lead',
            status TEXT NOT NULL DEFAULT 'draft',
            contract_id INTEGER,
            stage_entered_at TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL DEFAULT ''
        );

        CREATE TABLE crm_service_lifecycle_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lifecycle_id INTEGER NOT NULL,
            from_stage TEXT,
            to_stage TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT ''
        );

        CREATE TABLE crm_lead_intake_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lead_id INTEGER,
            lifecycle_id INTEGER,
            service_slug TEXT,
            mode TEXT,
            status TEXT,
            decision TEXT,
            started_at TEXT,
            completed_at TEXT
        );
        """
    )
    presales_schema(conn)
    finance_schema(conn)
    intake_schema(conn)

    # Active presales path — lead 11
    conn.execute(
        """
        INSERT INTO crm_lead_presales
            (id, lead_id, service_slug, stage, status, assigned_am,
             lifecycle_id, stage_entered_at, created_at, updated_at)
        VALUES
            (1, 11, 'dich-vu-aeo', 'proposal', 'active', 1,
             NULL, '2026-06-08 09:00:00', '2026-06-02 08:00:00', '2026-06-08 09:00:00')
        """
    )
    conn.execute(
        """
        INSERT INTO crm_lead_intake_sessions
            (lead_id, mode, status, decision, completed_at, service_slug)
        VALUES
            (11, 'phone', 'completed', 'go', '2026-06-02 09:30:00', 'dich-vu-aeo'),
            (11, 'in_person', 'completed', 'go', '2026-06-04 15:00:00', 'dich-vu-aeo')
        """
    )
    create_presales_expense(
        conn,
        title="Gọi lead",
        category="dien_thoai",
        amount_vnd=300_000,
        expense_on="2026-06-02",
        lead_id=11,
    )

    # Converted presales — won on presales cohort (lead 10)
    conn.execute(
        """
        INSERT INTO crm_service_lifecycle
            (id, lead_id, assigned_am, service_slug, stage, status, contract_id,
             stage_entered_at, created_at, updated_at)
        VALUES
            (100, 10, 1, 'dich-vu-aeo', 'onboard', 'active', 55,
             '2026-06-15 10:00:00', '2026-06-14 08:00:00', '2026-06-15 10:00:00')
        """
    )
    conn.execute(
        """
        INSERT INTO crm_lead_presales
            (id, lead_id, service_slug, stage, status, assigned_am,
             lifecycle_id, stage_entered_at, created_at, updated_at)
        VALUES
            (2, 10, 'dich-vu-aeo', 'proposal', 'converted', 1,
             100, '2026-06-10 09:00:00', '2026-06-01 08:00:00', '2026-06-15 10:00:00')
        """
    )
    conn.execute(
        """
        INSERT INTO crm_lead_intake_sessions
            (lead_id, mode, status, decision, completed_at, service_slug)
        VALUES
            (10, 'phone', 'completed', 'go', '2026-06-01 09:30:00', 'dich-vu-aeo')
        """
    )

    # Legacy lifecycle — lead 20, no presales row
    conn.execute(
        """
        INSERT INTO crm_service_lifecycle
            (id, lead_id, assigned_am, service_slug, stage, status, contract_id,
             stage_entered_at, created_at, updated_at)
        VALUES
            (200, 20, 2, 'dich-vu-seo-tong-the', 'consult', 'draft', NULL,
             '2026-06-05 10:00:00', '2026-06-03 09:00:00', '2026-06-05 10:00:00')
        """
    )
    conn.execute(
        """
        INSERT INTO crm_lead_intake_sessions
            (lifecycle_id, mode, status, decision, completed_at, service_slug)
        VALUES
            (200, 'phone', 'completed', 'go', '2026-06-03 10:20:00', 'dich-vu-seo-tong-the')
        """
    )
    conn.execute(
        """
        INSERT INTO crm_service_lifecycle_events
            (lifecycle_id, from_stage, to_stage, created_at)
        VALUES (200, 'lead', 'consult', '2026-06-05 10:00:00')
        """
    )

    # Lifecycle linked to presales lead — should be excluded from lifecycle cohort
    conn.execute(
        """
        INSERT INTO crm_service_lifecycle
            (id, lead_id, assigned_am, service_slug, stage, status, contract_id,
             stage_entered_at, created_at, updated_at)
        VALUES
            (101, 10, 1, 'dich-vu-aeo', 'lead', 'draft', NULL,
             '2026-06-04 09:00:00', '2026-06-04 09:00:00', '2026-06-04 09:00:00')
        """
    )

    conn.commit()
    return conn


class TestDualFunnelStats(unittest.TestCase):
    def setUp(self) -> None:
        self._env = os.environ.get("PTT_PRESALES_ON_LEAD")
        os.environ["PTT_PRESALES_ON_LEAD"] = "1"

    def tearDown(self) -> None:
        if self._env is None:
            os.environ.pop("PTT_PRESALES_ON_LEAD", None)
        else:
            os.environ["PTT_PRESALES_ON_LEAD"] = self._env

    def test_dual_cohort_flag_and_presales_counts(self) -> None:
        conn = _setup_dual_conn()
        stats = get_funnel_stats(
            conn, period_start="2026-06-01", period_end="2026-06-30"
        )
        self.assertTrue(stats["dual_cohort"])
        self.assertEqual(stats["cohort_mode"], "dual")

        ps = stats["presales_on_lead"]
        self.assertEqual(ps["cohort_mode"], "presales_created")
        self.assertEqual(ps["funnel_entered"], 2)
        self.assertEqual(ps["funnel_intake_done"], 2)
        self.assertEqual(ps["funnel_go"], 2)
        self.assertEqual(ps["funnel_consult"], 2)
        self.assertEqual(ps["funnel_proposal"], 2)
        self.assertEqual(ps["funnel_won"], 1)
        self.assertEqual(ps["presales_cost_total_vnd"], 300_000)
        self.assertEqual(ps["in_person_before_consult_num"], 1)

    def test_lifecycle_cohort_excludes_presales_leads(self) -> None:
        conn = _setup_dual_conn()
        stats = get_funnel_stats(
            conn, period_start="2026-06-01", period_end="2026-06-30"
        )
        lc = stats["lifecycle"]
        self.assertEqual(lc["cohort_mode"], "lifecycle_created")
        self.assertEqual(lc["funnel_entered"], 1)
        self.assertEqual(lc["funnel_go"], 1)
        self.assertEqual(lc["funnel_consult"], 1)

    def test_no_double_count_won(self) -> None:
        conn = _setup_dual_conn()
        stats = get_funnel_stats(
            conn, period_start="2026-06-01", period_end="2026-06-30"
        )
        self.assertEqual(stats["presales_on_lead"]["funnel_won"], 1)
        self.assertEqual(stats["lifecycle"]["funnel_won"], 0)

    def test_filter_am_presales_cohort(self) -> None:
        conn = _setup_dual_conn()
        stats = get_funnel_stats(
            conn,
            am_id=2,
            period_start="2026-06-01",
            period_end="2026-06-30",
        )
        self.assertEqual(stats["presales_on_lead"]["funnel_entered"], 0)
        self.assertEqual(stats["lifecycle"]["funnel_entered"], 1)

    def test_top_level_mirrors_presales_for_compat(self) -> None:
        conn = _setup_dual_conn()
        stats = get_funnel_stats(
            conn, period_start="2026-06-01", period_end="2026-06-30"
        )
        self.assertEqual(stats["funnel_entered"], stats["presales_on_lead"]["funnel_entered"])
        self.assertEqual(
            stats["presales_cost_total_vnd"],
            stats["presales_on_lead"]["presales_cost_total_vnd"],
        )


if __name__ == "__main__":
    unittest.main()
