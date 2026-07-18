"""Tests nhóm 4 — Lead qualified + close rate thống nhất."""
from __future__ import annotations

import sqlite3
import unittest

from crm_lead_kpi_metrics import (
    count_qualified_leads_in_month,
    get_staff_close_rate_pct,
    get_unified_lead_kpi_summary,
    is_lead_qualified,
    is_lead_won,
    summarize_leads_kpi,
)


def _setup_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE crm_leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT,
            owner_id INTEGER,
            status TEXT DEFAULT 'first_contact',
            is_duplicate INTEGER NOT NULL DEFAULT 0,
            created_at TEXT DEFAULT '2026-06-01 10:00:00',
            updated_at TEXT DEFAULT '2026-06-01 10:00:00',
            source TEXT DEFAULT 'manual',
            lead_level TEXT DEFAULT 'warm',
            re_project_id INTEGER
        );
        CREATE TABLE crm_lead_intake_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lead_id INTEGER,
            lifecycle_id INTEGER,
            mode TEXT DEFAULT 'phone',
            status TEXT DEFAULT 'draft',
            decision TEXT DEFAULT '',
            completed_at TEXT DEFAULT ''
        );
        CREATE TABLE crm_lead_presales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lead_id INTEGER UNIQUE,
            service_slug TEXT DEFAULT 'dich-vu-seo-tong-the',
            stage TEXT DEFAULT 'lead',
            status TEXT DEFAULT 'active',
            assigned_am INTEGER,
            lifecycle_id INTEGER,
            stage_entered_at TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            created_at TEXT DEFAULT '',
            updated_at TEXT DEFAULT ''
        );
        CREATE TABLE crm_service_lifecycle (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lead_id INTEGER,
            service_slug TEXT DEFAULT '',
            stage TEXT DEFAULT 'lead',
            status TEXT DEFAULT 'draft',
            contract_id INTEGER,
            stage_entered_at TEXT DEFAULT '',
            created_at TEXT DEFAULT ''
        );
        CREATE TABLE crm_contracts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lead_id INTEGER,
            status TEXT DEFAULT 'draft',
            amount_vnd INTEGER DEFAULT 0
        );
        """
    )
    return conn


class TestQualifiedLead(unittest.TestCase):
    def test_go_intake_is_qualified(self) -> None:
        conn = _setup_conn()
        conn.execute(
            "INSERT INTO crm_leads (id, owner_id, status) VALUES (1, 10, 'first_contact')"
        )
        conn.execute(
            """
            INSERT INTO crm_lead_intake_sessions
                (lead_id, status, decision, completed_at)
            VALUES (1, 'completed', 'go', '2026-06-05 12:00:00')
            """
        )
        conn.commit()
        self.assertTrue(is_lead_qualified(conn, 1))

    def test_presales_is_qualified_without_go(self) -> None:
        conn = _setup_conn()
        conn.execute("INSERT INTO crm_leads (id, owner_id) VALUES (2, 10)")
        conn.execute(
            """
            INSERT INTO crm_lead_presales (lead_id, created_at)
            VALUES (2, '2026-06-08 09:00:00')
            """
        )
        conn.commit()
        self.assertTrue(is_lead_qualified(conn, 2))

    def test_duplicate_excluded(self) -> None:
        conn = _setup_conn()
        conn.execute(
            "INSERT INTO crm_leads (id, owner_id, is_duplicate) VALUES (3, 10, 1)"
        )
        conn.execute(
            """
            INSERT INTO crm_lead_intake_sessions
                (lead_id, status, decision, completed_at)
            VALUES (3, 'completed', 'go', '2026-06-05 12:00:00')
            """
        )
        conn.commit()
        self.assertFalse(is_lead_qualified(conn, 3))


class TestCloseRate(unittest.TestCase):
    def test_close_rate_won_over_qualified(self) -> None:
        conn = _setup_conn()
        for lid, owner, go, won_status in (
            (1, 10, True, False),
            (2, 10, True, True),
            (3, 10, False, False),
        ):
            conn.execute(
                "INSERT INTO crm_leads (id, owner_id, status) VALUES (?, 10, ?)",
                (lid, "post_sale" if won_status else "first_contact"),
            )
            if go:
                conn.execute(
                    """
                    INSERT INTO crm_lead_intake_sessions
                        (lead_id, status, decision, completed_at)
                    VALUES (?, 'completed', 'go', '2026-06-10 10:00:00')
                    """,
                    (lid,),
                )
        conn.commit()
        summary = summarize_leads_kpi(conn, [1, 2, 3])
        self.assertEqual(summary["qualified_leads"], 2)
        self.assertEqual(summary["won_leads"], 1)
        self.assertEqual(summary["close_rate_pct"], 50.0)

    def test_lifecycle_won(self) -> None:
        conn = _setup_conn()
        conn.execute("INSERT INTO crm_leads (id, owner_id) VALUES (5, 10)")
        conn.execute(
            """
            INSERT INTO crm_lead_intake_sessions
                (lead_id, status, decision, completed_at)
            VALUES (5, 'completed', 'go', '2026-06-12 10:00:00')
            """
        )
        conn.execute(
            """
            INSERT INTO crm_service_lifecycle
                (id, lead_id, stage, status, contract_id, stage_entered_at)
            VALUES (50, 5, 'onboard', 'active', 99, '2026-06-20 10:00:00')
            """
        )
        conn.commit()
        self.assertTrue(is_lead_won(conn, 5))

    def test_month_cohort_and_decided_rate(self) -> None:
        conn = _setup_conn()
        conn.execute("INSERT INTO crm_leads (id, owner_id, status) VALUES (10, 10, 'first_contact')")
        conn.execute("INSERT INTO crm_leads (id, owner_id, status) VALUES (11, 10, 'post_sale')")
        conn.execute("INSERT INTO crm_leads (id, owner_id, status) VALUES (12, 10, 'lost')")
        conn.executemany(
            """
            INSERT INTO crm_lead_intake_sessions
                (lead_id, status, decision, completed_at)
            VALUES (?, 'completed', 'go', ?)
            """,
            [
                (10, "2026-06-03 10:00:00"),
                (11, "2026-06-04 10:00:00"),
                (12, "2026-06-05 10:00:00"),
            ],
        )
        conn.commit()
        metrics = get_unified_lead_kpi_summary(conn, year=2026, month=6, period_cohort=True)
        self.assertEqual(metrics["qualified_in_month"], 3)
        self.assertEqual(metrics["qualified_in_cohort"], 3)
        self.assertEqual(metrics["won_from_month_cohort"], 1)
        self.assertEqual(metrics["lost_from_month_cohort"], 1)
        self.assertAlmostEqual(metrics["cohort_close_rate_pct"], 33.3)
        self.assertEqual(metrics["cohort_close_rate_decided_pct"], 50.0)

    def test_staff_close_rate(self) -> None:
        conn = _setup_conn()
        conn.execute("INSERT INTO crm_leads (id, owner_id, status) VALUES (20, 7, 'post_sale')")
        conn.execute("INSERT INTO crm_leads (id, owner_id, status) VALUES (21, 7, 'first_contact')")
        conn.executemany(
            """
            INSERT INTO crm_lead_intake_sessions
                (lead_id, status, decision, completed_at)
            VALUES (?, 'completed', 'go', '2026-06-01 10:00:00')
            """,
            [(20,), (21,)],
        )
        conn.commit()
        self.assertEqual(get_staff_close_rate_pct(conn, 7), 50.0)

    def test_week_cohort_excludes_outside_week(self) -> None:
        conn = _setup_conn()
        conn.execute("INSERT INTO crm_leads (id, owner_id) VALUES (30, 10)")
        conn.execute("INSERT INTO crm_leads (id, owner_id) VALUES (31, 10)")
        conn.executemany(
            """
            INSERT INTO crm_lead_intake_sessions
                (lead_id, status, decision, completed_at)
            VALUES (?, 'completed', 'go', ?)
            """,
            [(30, "2026-06-23 10:00:00"), (31, "2026-07-02 10:00:00")],
        )
        conn.commit()
        from datetime import date

        week = get_unified_lead_kpi_summary(
            conn,
            period_start=date(2026, 6, 23),
            period_end=date(2026, 6, 29),
            period_cohort=True,
        )
        self.assertEqual(week["qualified_in_cohort"], 1)
        month = get_unified_lead_kpi_summary(conn, year=2026, month=6, period_cohort=True)
        self.assertEqual(month["qualified_in_cohort"], 1)
        july = get_unified_lead_kpi_summary(conn, year=2026, month=7, period_cohort=True)
        self.assertEqual(july["qualified_in_cohort"], 1)


class TestReLeadsNewQualified(unittest.TestCase):
    def test_count_qualified_in_month_by_project(self) -> None:
        conn = _setup_conn()
        conn.execute(
            "INSERT INTO crm_leads (id, owner_id, re_project_id) VALUES (1, 1, 100)"
        )
        conn.execute(
            """
            INSERT INTO crm_lead_intake_sessions
                (lead_id, status, decision, completed_at)
            VALUES (1, 'completed', 'go', '2026-06-15 10:00:00')
            """
        )
        conn.execute(
            "INSERT INTO crm_leads (id, owner_id, re_project_id) VALUES (2, 1, 100)"
        )
        conn.commit()
        self.assertEqual(
            count_qualified_leads_in_month(
                conn, year=2026, month=6, re_project_id=100
            ),
            1,
        )


if __name__ == "__main__":
    unittest.main()
