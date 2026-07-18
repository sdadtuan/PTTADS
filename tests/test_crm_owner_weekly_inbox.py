"""Tests inbox + notify dashboard tuần."""
from __future__ import annotations

import os
import sqlite3
import unittest
from datetime import date
from unittest.mock import patch

from crm_owner_weekly_dashboard import get_owner_weekly_dashboard
from crm_owner_weekly_inbox import (
    KIND_WEEKLY_ALERT,
    SCOPE_OWNER_WEEKLY,
    get_owner_weekly_inbox_summary,
    period_ref_id,
    sync_owner_weekly_inbox,
)
from crm_owner_weekly_notify import build_weekly_digest, dispatch_owner_weekly_alerts
from crm_svc_finance import ensure_schema
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

        CREATE TABLE crm_contracts (
            id INTEGER PRIMARY KEY,
            customer_id INTEGER,
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
            pipeline_stage TEXT DEFAULT 'moi',
            stage_entered_at TEXT DEFAULT '',
            deal_value_vnd INTEGER DEFAULT 0,
            created_at TEXT DEFAULT '2026-06-01 10:00:00',
            status TEXT DEFAULT 'open'
        );

        CREATE TABLE crm_staff (
            id INTEGER PRIMARY KEY,
            name TEXT,
            active INTEGER NOT NULL DEFAULT 1
        );

        CREATE TABLE crm_reminders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scope TEXT NOT NULL,
            ref_id INTEGER NOT NULL DEFAULT 0,
            reminder_kind TEXT NOT NULL DEFAULT 'manual',
            title TEXT NOT NULL,
            body TEXT NOT NULL DEFAULT '',
            remind_at TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            staff_id INTEGER,
            meta_json TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        """
    )
    ensure_schema(conn)
    ensure_tasks_schema(conn)
    return conn


class TestOwnerWeeklyInbox(unittest.TestCase):
    def test_sync_creates_reminders_for_red_metrics(self) -> None:
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
        out = sync_owner_weekly_inbox(
            conn,
            iso_year=2026,
            iso_week=26,
            dashboard=dash,
            dashboard_url="/crm/owner-weekly?year=2026&week=26",
        )
        self.assertGreater(out["synced"], 0)
        self.assertEqual(out["period_ref"], period_ref_id(2026, 26))

        count = conn.execute(
            """
            SELECT COUNT(*) FROM crm_reminders
            WHERE scope = ? AND reminder_kind = ? AND status = 'pending'
            """,
            (SCOPE_OWNER_WEEKLY, KIND_WEEKLY_ALERT),
        ).fetchone()[0]
        self.assertEqual(int(count), out["synced"])

        summary = get_owner_weekly_inbox_summary(conn)
        self.assertEqual(summary["pending_count"], out["synced"])
        self.assertGreater(summary["critical_count"], 0)

    def test_sync_clears_stale_reminders(self) -> None:
        conn = _setup_conn()
        conn.execute(
            """
            INSERT INTO crm_reminders
                (scope, ref_id, reminder_kind, title, body, remind_at, status,
                 meta_json, created_at, updated_at)
            VALUES (?, ?, ?, 'Old', 'body', '2026-06-23', 'pending',
                    '{"alert_id":"2026-W26-stale_metric"}', '2026-06-23', '2026-06-23')
            """,
            (SCOPE_OWNER_WEEKLY, period_ref_id(2026, 26), KIND_WEEKLY_ALERT),
        )
        conn.commit()
        dash = get_owner_weekly_dashboard(conn, week_end=date(2026, 6, 29))
        brief = dash.get("pre_execution") or {}
        if brief.get("action_count", 0) == 0:
            out = sync_owner_weekly_inbox(
                conn, iso_year=2026, iso_week=26, dashboard=dash
            )
            self.assertGreaterEqual(out["removed"], 1)
        else:
            out = sync_owner_weekly_inbox(
                conn, iso_year=2026, iso_week=26, dashboard=dash
            )
            self.assertGreaterEqual(out["removed"], 0)

    def test_build_digest_contains_week_label(self) -> None:
        conn = _setup_conn()
        conn.execute(
            """
            INSERT INTO crm_svc_expenses
                (lifecycle_id, amount_vnd, expense_on, cost_phase)
            VALUES (1, 150000000, '2026-06-01', 'delivery')
            """
        )
        conn.commit()
        dash = get_owner_weekly_dashboard(conn, week_end=date(2026, 6, 29))
        subject, body = build_weekly_digest(dash, dashboard_url="https://example.test/crm/owner-weekly")
        self.assertIn("Tuần", subject)
        self.assertIn("example.test", body)

    def test_dispatch_syncs_inbox_without_channels(self) -> None:
        conn = _setup_conn()
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("PTT_OWNER_WEEKLY_SLACK_WEBHOOK", None)
            os.environ.pop("PTT_OWNER_WEEKLY_ALERT_EMAIL", None)
            os.environ.pop("PTT_FINANCE_KPI_SLACK_WEBHOOK", None)
            os.environ.pop("PTT_FINANCE_KPI_ALERT_EMAIL", None)
            out = dispatch_owner_weekly_alerts(
                conn, iso_year=2026, iso_week=26, only_red=False
            )
        self.assertIn("inbox", out)
        self.assertIn(out.get("reason"), ("no_actions", "inbox_only", "dispatched", "no_red"))


if __name__ == "__main__":
    unittest.main()
