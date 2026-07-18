"""Tests dashboard tuần chủ doanh nghiệp."""
from __future__ import annotations

import sqlite3
import unittest
from datetime import date

from crm_owner_weekly_dashboard import (
    RAG_RED,
    build_owner_weekly_export_sheets,
    build_pre_execution_brief,
    get_owner_weekly_dashboard,
    get_owner_weekly_targets,
    get_owner_weekly_trends,
    resolve_week_bounds,
    set_owner_weekly_targets,
)
from crm_svc_finance import ensure_schema
from crm_svc_finance_kpi import ensure_kpi_config_schema
from crm_svc_tasks import ensure_schema as ensure_tasks_schema


def _setup_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE crm_customers (
            id INTEGER PRIMARY KEY,
            name TEXT,
            is_placeholder INTEGER NOT NULL DEFAULT 0
        );
        INSERT INTO crm_customers (id, name) VALUES (1, 'KH A');
        INSERT INTO crm_customers (id, name) VALUES (2, 'KH B');

        CREATE TABLE crm_contracts (
            id INTEGER PRIMARY KEY,
            customer_id INTEGER,
            lead_id INTEGER,
            title TEXT DEFAULT '',
            billing_type TEXT NOT NULL DEFAULT 'one_off',
            billing_cycle TEXT NOT NULL DEFAULT 'monthly',
            status TEXT DEFAULT 'active',
            amount_vnd INTEGER DEFAULT 0,
            starts_on TEXT DEFAULT '',
            ends_on TEXT DEFAULT ''
        );

        CREATE TABLE crm_leads (
            id INTEGER PRIMARY KEY,
            owner_id INTEGER,
            status TEXT DEFAULT 'new',
            is_duplicate INTEGER NOT NULL DEFAULT 0,
            created_at TEXT DEFAULT '2026-06-23 10:00:00',
            updated_at TEXT DEFAULT '2026-06-23 10:00:00',
            status_entered_at TEXT DEFAULT '2026-06-23 10:00:00'
        );
        CREATE TABLE crm_lead_intake_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lead_id INTEGER,
            status TEXT DEFAULT 'draft',
            decision TEXT DEFAULT '',
            completed_at TEXT DEFAULT ''
        );
        -- Không seed lead — tránh gọi lead KPI cần schema đầy đủ

        CREATE TABLE crm_service_lifecycle (
            id INTEGER PRIMARY KEY,
            customer_id INTEGER,
            contract_id INTEGER,
            lead_id INTEGER,
            assigned_am INTEGER,
            assigned_sp INTEGER,
            service_slug TEXT DEFAULT 'dich-vu-seo-tong-the',
            stage TEXT DEFAULT 'deliver',
            status TEXT DEFAULT 'active',
            stage_entered_at TEXT DEFAULT '2026-06-01 10:00:00',
            created_at TEXT DEFAULT '2026-06-01 10:00:00'
        );
        INSERT INTO crm_service_lifecycle (id, customer_id, status) VALUES (1, 1, 'active');

        CREATE TABLE crm_cases (
            id INTEGER PRIMARY KEY,
            customer_id INTEGER,
            title TEXT DEFAULT '',
            pipeline_stage TEXT DEFAULT 'moi',
            stage_entered_at TEXT DEFAULT '',
            deal_value_vnd INTEGER DEFAULT 0,
            created_at TEXT DEFAULT '2026-06-01 10:00:00',
            status TEXT DEFAULT 'open',
            channel TEXT DEFAULT 'khac',
            updated_at TEXT DEFAULT '2026-06-01 10:00:00'
        );

        CREATE TABLE crm_staff (
            id INTEGER PRIMARY KEY,
            name TEXT,
            active INTEGER NOT NULL DEFAULT 1
        );
        """
    )
    ensure_schema(conn)
    ensure_tasks_schema(conn)
    ensure_kpi_config_schema(conn)
    return conn


class TestOwnerWeeklyBounds(unittest.TestCase):
    def test_iso_week_bounds(self) -> None:
        start, end, y, w = resolve_week_bounds(year=2026, iso_week=26)
        self.assertEqual(y, 2026)
        self.assertEqual(w, 26)
        self.assertEqual(start.weekday(), 0)
        self.assertEqual(end.weekday(), 6)
        self.assertEqual((end - start).days, 6)


class TestOwnerWeeklyDashboard(unittest.TestCase):
    def test_dashboard_has_four_blocks(self) -> None:
        conn = _setup_conn()
        dash = get_owner_weekly_dashboard(conn, year=2026, iso_week=26)
        self.assertIn("cash", dash["blocks"])
        self.assertIn("sales", dash["blocks"])
        self.assertIn("efficiency", dash["blocks"])
        self.assertIn("risk", dash["blocks"])
        self.assertEqual(len(dash["blocks"]["cash"]["metrics"]), 6)
        self.assertEqual(len(dash["blocks"]["sales"]["metrics"]), 6)

    def test_cash_red_when_below_safe_min(self) -> None:
        conn = _setup_conn()
        conn.execute(
            """
            INSERT INTO crm_svc_expenses
                (lifecycle_id, amount_vnd, expense_on, cost_phase)
            VALUES (1, 100000000, '2026-06-01', 'delivery')
            """
        )
        conn.commit()
        dash = get_owner_weekly_dashboard(conn, week_end=date(2026, 6, 29))
        cash_close = next(m for m in dash["blocks"]["cash"]["metrics"] if m["key"] == "cash_close")
        self.assertEqual(cash_close["status"], RAG_RED)

    def test_ar_overdue_red_when_rising_two_weeks(self) -> None:
        conn = _setup_conn()
        conn.executemany(
            """
            INSERT INTO crm_svc_payments
                (lifecycle_id, amount_vnd, received_on, due_on, status)
            VALUES (1, ?, '', ?, 'pending')
            """,
            [
                (5_000_000, "2026-05-01"),
                (8_000_000, "2026-06-20"),
                (12_000_000, "2026-06-27"),
            ],
        )
        conn.commit()
        dash = get_owner_weekly_dashboard(conn, week_end=date(2026, 6, 29))
        ar = next(m for m in dash["blocks"]["cash"]["metrics"] if m["key"] == "ar_overdue")
        self.assertEqual(ar["status"], RAG_RED)
        self.assertGreater(int(ar["value"]), int(ar.get("prior_value") or 0))

    def test_pre_execution_brief_lists_non_green(self) -> None:
        conn = _setup_conn()
        conn.execute(
            """
            INSERT INTO crm_svc_expenses
                (lifecycle_id, amount_vnd, expense_on, cost_phase)
            VALUES (1, 200000000, '2026-06-01', 'delivery')
            """
        )
        conn.commit()
        dash = get_owner_weekly_dashboard(conn, week_end=date(2026, 6, 29))
        brief = build_pre_execution_brief(dash)
        self.assertGreater(brief["action_count"], 0)
        self.assertTrue(any(a["status"] == RAG_RED for a in brief["actions"]))

    def test_qualified_uses_week_not_month(self) -> None:
        conn = _setup_conn()
        conn.execute(
            """
            INSERT INTO crm_leads (id, owner_id, status, created_at, updated_at)
            VALUES (10, 1, 'first_contact', '2026-06-01', '2026-06-01')
            """
        )
        conn.execute(
            """
            INSERT INTO crm_lead_intake_sessions
                (lead_id, status, decision, completed_at)
            VALUES (10, 'completed', 'go', '2026-06-23 10:00:00')
            """
        )
        conn.commit()
        dash = get_owner_weekly_dashboard(conn, week_end=date(2026, 6, 29))
        qualified = next(
            m for m in dash["blocks"]["sales"]["metrics"] if m["key"] == "leads_qualified"
        )
        self.assertEqual(int(qualified["value"]), 1)
        gross = next(
            m for m in dash["blocks"]["efficiency"]["metrics"] if m["key"] == "gross_margin"
        )
        self.assertNotIn("Tháng", gross.get("note") or "")

    def test_proposals_dedupe_by_customer(self) -> None:
        conn = _setup_conn()
        conn.executescript(
            """
            CREATE TABLE crm_proposals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id INTEGER NOT NULL,
                lifecycle_id INTEGER,
                service_slugs TEXT DEFAULT '[]',
                total_vnd INTEGER DEFAULT 0,
                timeline_months INTEGER DEFAULT 1,
                notes TEXT DEFAULT '',
                ai_output TEXT DEFAULT '{}',
                created_at TEXT DEFAULT '',
                updated_at TEXT DEFAULT ''
            );
            INSERT INTO crm_proposals (customer_id, created_at, updated_at)
            VALUES (1, '2026-06-24 10:00:00', '2026-06-24 10:00:00'),
                   (1, '2026-06-25 11:00:00', '2026-06-25 11:00:00');
            """
        )
        conn.commit()
        dash = get_owner_weekly_dashboard(conn, week_end=date(2026, 6, 29))
        proposals = next(
            m for m in dash["blocks"]["sales"]["metrics"] if m["key"] == "proposals_sent"
        )
        self.assertEqual(int(proposals["value"]), 1)

    def test_pipeline_next_week_filters_followup_date(self) -> None:
        conn = _setup_conn()
        conn.executemany(
            """
            INSERT INTO crm_cases
                (customer_id, title, pipeline_stage, stage_entered_at, deal_value_vnd, status, channel, created_at, updated_at)
            VALUES (?, 'Deal', ?, ?, ?, 'open', 'khac', '2026-06-01', '2026-06-01')
            """,
            [
                (1, "sql", "2026-06-28 10:00:00", 50_000_000),
                (1, "sql", "2026-06-01 10:00:00", 20_000_000),
            ],
        )
        conn.commit()
        dash = get_owner_weekly_dashboard(conn, week_end=date(2026, 6, 29))
        pipeline = next(
            m for m in dash["blocks"]["sales"]["metrics"] if m["key"] == "pipeline_next"
        )
        self.assertEqual(int(pipeline["value"]), 50_000_000)

    def test_trends_and_drill_urls(self) -> None:
        conn = _setup_conn()
        dash = get_owner_weekly_dashboard(conn, week_end=date(2026, 6, 29), trend_weeks=6)
        self.assertEqual(dash["trends"]["weeks"], 6)
        self.assertEqual(len(dash["trends"]["cash_close_vnd"]), 6)
        cash_close = next(
            m for m in dash["blocks"]["cash"]["metrics"] if m["key"] == "cash_close"
        )
        self.assertTrue(cash_close.get("drill_url"))
        self.assertEqual(len(cash_close.get("trend_values") or []), 6)

    def test_weekly_churn_in_dashboard(self) -> None:
        conn = _setup_conn()
        conn.executemany(
            """
            INSERT INTO crm_contracts
                (customer_id, title, status, starts_on, ends_on, amount_vnd)
            VALUES (?, 'HĐ', 'active', '2026-01-01', ?, 1000000)
            """,
            [
                (1, "2026-12-31"),
                (2, "2026-06-20"),
            ],
        )
        conn.commit()
        dash = get_owner_weekly_dashboard(conn, week_end=date(2026, 6, 29))
        churn = next(m for m in dash["blocks"]["risk"]["metrics"] if m["key"] == "churn")
        self.assertIn("WoW", churn.get("note") or "")
        self.assertIn("retention_weekly", dash)


class TestOwnerWeeklyConfigExport(unittest.TestCase):
    def test_set_targets_persisted(self) -> None:
        conn = _setup_conn()
        updated = set_owner_weekly_targets(
            conn, {"cash_safe_min_vnd": 99_000_000, "lead_new_target": 8}
        )
        self.assertEqual(updated["cash_safe_min_vnd"], 99_000_000)
        self.assertEqual(updated["lead_new_target"], 8)
        reloaded = get_owner_weekly_targets(conn)
        self.assertEqual(reloaded["cash_safe_min_vnd"], 99_000_000)

    def test_db_overrides_default(self) -> None:
        conn = _setup_conn()
        conn.execute(
            """
            INSERT INTO crm_finance_kpi_config (config_key, config_value, updated_at)
            VALUES ('owner_revenue_target_vnd', '7777777', '2026-06-01')
            """
        )
        conn.commit()
        targets = get_owner_weekly_targets(conn)
        self.assertEqual(targets["revenue_target_vnd"], 7_777_777)

    def test_export_sheets(self) -> None:
        conn = _setup_conn()
        dash = get_owner_weekly_dashboard(conn, week_end=date(2026, 6, 29))
        sheets = build_owner_weekly_export_sheets(dash)
        self.assertGreaterEqual(len(sheets), 3)
        summary = sheets[0]
        self.assertEqual(summary[0], "Tom tat")
        detail = sheets[1]
        self.assertEqual(detail[0], "Chi tiet")
        self.assertGreater(len(detail[2]), 10)


if __name__ == "__main__":
    unittest.main()
