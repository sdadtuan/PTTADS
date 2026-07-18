"""Tests get_funnel_stats — Phase L3."""
from __future__ import annotations

import sqlite3
import unittest

from crm_lead_intake import ensure_schema as intake_schema
from crm_svc_finance import create_expense, ensure_schema as finance_schema
from crm_svc_presales import get_funnel_stats


def _setup_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        "CREATE TABLE crm_staff (id INTEGER PRIMARY KEY, name TEXT, active INTEGER DEFAULT 1)"
    )
    conn.execute("INSERT INTO crm_staff (id, name) VALUES (1, 'AM One'), (2, 'AM Two')")
    conn.execute("""
        CREATE TABLE crm_service_lifecycle (
            id INTEGER PRIMARY KEY,
            assigned_am INTEGER,
            service_slug TEXT NOT NULL DEFAULT 'dich-vu-aeo',
            stage TEXT NOT NULL DEFAULT 'lead',
            status TEXT NOT NULL DEFAULT 'draft',
            contract_id INTEGER,
            stage_entered_at TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL DEFAULT ''
        )
    """)
    conn.execute("""
        CREATE TABLE crm_service_lifecycle_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lifecycle_id INTEGER NOT NULL,
            from_stage TEXT,
            to_stage TEXT NOT NULL,
            actor_id INTEGER,
            actor_type TEXT NOT NULL DEFAULT 'human',
            notes TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT ''
        )
    """)
    finance_schema(conn)
    intake_schema(conn)
    conn.execute(
        """
        INSERT INTO crm_service_lifecycle
            (id, assigned_am, service_slug, stage, status, contract_id,
             stage_entered_at, created_at, updated_at)
        VALUES
            (1, 1, 'dich-vu-aeo', 'consult', 'draft', NULL,
             '2026-06-05 10:00:00', '2026-06-02 08:00:00', '2026-06-05 10:00:00'),
            (2, 1, 'dich-vu-aeo', 'proposal', 'draft', NULL,
             '2026-06-08 09:00:00', '2026-06-03 09:00:00', '2026-06-08 09:00:00'),
            (3, 2, 'dich-vu-seo-tong-the', 'lead', 'draft', NULL,
             '2026-06-04 09:00:00', '2026-06-04 09:00:00', '2026-06-04 09:00:00'),
            (4, 1, 'dich-vu-aeo', 'onboard', 'active', 99,
             '2026-06-15 10:00:00', '2026-06-01 08:00:00', '2026-06-15 10:00:00')
        """
    )
    conn.execute(
        """
        INSERT INTO crm_lead_intake_sessions
            (lifecycle_id, mode, status, decision, started_at, completed_at, service_slug)
        VALUES
            (1, 'phone', 'completed', 'go',
             '2026-06-02 09:00:00', '2026-06-02 09:30:00', 'dich-vu-aeo'),
            (1, 'in_person', 'completed', 'go',
             '2026-06-04 14:00:00', '2026-06-04 15:00:00', 'dich-vu-aeo'),
            (2, 'phone', 'completed', 'go',
             '2026-06-03 10:00:00', '2026-06-03 10:20:00', 'dich-vu-aeo'),
            (3, 'phone', 'completed', 'nurture',
             '2026-06-04 10:00:00', '2026-06-04 10:15:00', 'dich-vu-seo-tong-the')
        """
    )
    conn.execute(
        """
        INSERT INTO crm_service_lifecycle_events
            (lifecycle_id, from_stage, to_stage, created_at)
        VALUES
            (1, 'lead', 'consult', '2026-06-05 10:00:00'),
            (2, 'lead', 'consult', '2026-06-05 11:00:00'),
            (2, 'consult', 'proposal', '2026-06-08 09:00:00')
        """
    )
    create_expense(
        conn, 1, "Gọi", "dien_thoai", 200_000, "2026-06-02",
        cost_phase="presales", lifecycle_stage="lead",
    )
    create_expense(
        conn, 2, "Gặp", "di_lai", 500_000, "2026-06-06",
        cost_phase="presales", lifecycle_stage="consult",
    )
    conn.commit()
    return conn


class TestFunnelStats(unittest.TestCase):
    def test_cohort_counts_and_ratios(self):
        conn = _setup_conn()
        stats = get_funnel_stats(
            conn,
            period_start="2026-06-01",
            period_end="2026-06-30",
        )
        self.assertEqual(stats["funnel_entered"], 4)
        self.assertEqual(stats["funnel_intake_done"], 3)
        self.assertEqual(stats["funnel_go"], 2)
        self.assertEqual(stats["funnel_consult"], 3)
        self.assertEqual(stats["funnel_proposal"], 2)
        self.assertEqual(stats["funnel_won"], 1)
        self.assertEqual(stats["go_to_consult_pct"], 150.0)
        self.assertEqual(stats["consult_to_proposal_7d_num"], 1)
        self.assertEqual(stats["consult_to_proposal_7d_pct"], 33.3)
        self.assertEqual(stats["proposal_to_won_pct"], 50.0)
        self.assertEqual(stats["in_person_before_consult_num"], 1)
        self.assertEqual(stats["in_person_before_consult_pct"], 50.0)
        self.assertEqual(stats["presales_cost_total_vnd"], 700_000)
        self.assertEqual(stats["presales_cost_per_go_vnd"], 350_000)
        self.assertEqual(stats["presales_cost_per_won_vnd"], 700_000)

    def test_filter_am_id(self):
        conn = _setup_conn()
        stats = get_funnel_stats(
            conn,
            am_id=2,
            period_start="2026-06-01",
            period_end="2026-06-30",
        )
        self.assertEqual(stats["funnel_entered"], 1)
        self.assertEqual(stats["funnel_go"], 0)
        self.assertEqual(stats["funnel_intake_done"], 1)

    def test_filter_service_slug(self):
        conn = _setup_conn()
        stats = get_funnel_stats(
            conn,
            service_slug="dich-vu-seo-tong-the",
            period_start="2026-06-01",
            period_end="2026-06-30",
        )
        self.assertEqual(stats["funnel_entered"], 1)
        self.assertEqual(stats["funnel_intake_done"], 1)

    def test_stages_array_for_ui(self):
        conn = _setup_conn()
        stats = get_funnel_stats(
            conn, period_start="2026-06-01", period_end="2026-06-30"
        )
        self.assertEqual(len(stats["stages"]), 6)
        self.assertEqual(stats["stages"][0]["key"], "funnel_entered")
        self.assertEqual(stats["stages"][0]["count"], 4)


if __name__ == "__main__":
    unittest.main()
