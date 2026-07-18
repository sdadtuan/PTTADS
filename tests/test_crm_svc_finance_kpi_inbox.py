"""Tests inbox KPI finance → crm_reminders."""
from __future__ import annotations

import os
import sqlite3
import unittest
from unittest.mock import patch

from crm_svc_finance import ensure_schema
from crm_svc_finance_kpi import collect_finance_kpi_alerts
from crm_svc_finance_kpi_inbox import (
    KIND_KPI_ALERT,
    SCOPE_FINANCE_KPI,
    get_finance_kpi_inbox_summary,
    period_ref_id,
    sync_finance_kpi_inbox,
)
from crm_svc_finance_kpi_notify import dispatch_finance_kpi_alerts
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
        INSERT INTO crm_customers (id, name) VALUES (1, 'KH lớn A'), (2, 'KH lớn B'), (3, 'KH nhỏ');

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
            is_duplicate INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE crm_staff (
            id INTEGER PRIMARY KEY,
            name TEXT,
            active INTEGER NOT NULL DEFAULT 1
        );

        CREATE TABLE crm_service_lifecycle (
            id INTEGER PRIMARY KEY,
            customer_id INTEGER,
            contract_id INTEGER,
            assigned_am INTEGER,
            assigned_sp INTEGER,
            status TEXT DEFAULT 'active',
            service_slug TEXT DEFAULT 'dich-vu-seo-tong-the',
            stage TEXT DEFAULT 'deliver'
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


class TestFinanceKpiInbox(unittest.TestCase):
    def test_sync_creates_reminders_for_alerts(self) -> None:
        conn = _setup_conn()
        for lc_id, cid in ((1, 1), (2, 2), (3, 3)):
            conn.execute(
                "INSERT INTO crm_service_lifecycle (id, customer_id, status) VALUES (?, ?, 'active')",
                (lc_id, cid),
            )
        conn.executemany(
            """
            INSERT INTO crm_svc_payments (lifecycle_id, amount_vnd, received_on, status)
            VALUES (?, ?, '2026-06-15', 'received')
            """,
            [(1, 50_000_000), (2, 30_000_000), (3, 20_000_000)],
        )
        conn.commit()

        alerts = collect_finance_kpi_alerts(conn, year=2026, month=6)
        out = sync_finance_kpi_inbox(conn, year=2026, month=6, alerts_result=alerts)
        self.assertGreater(out["synced"], 0)
        self.assertEqual(out["period_ref"], period_ref_id(2026, 6))

        rows = conn.execute(
            """
            SELECT COUNT(*) FROM crm_reminders
            WHERE scope = ? AND reminder_kind = ? AND status = 'pending'
            """,
            (SCOPE_FINANCE_KPI, KIND_KPI_ALERT),
        ).fetchone()
        self.assertEqual(int(rows[0]), out["synced"])

        summary = get_finance_kpi_inbox_summary(conn)
        self.assertEqual(summary["pending_count"], out["synced"])

    def test_sync_clears_stale_reminders(self) -> None:
        conn = _setup_conn()
        conn.execute(
            """
            INSERT INTO crm_reminders
                (scope, ref_id, reminder_kind, title, body, remind_at, status,
                 meta_json, created_at, updated_at)
            VALUES (?, ?, ?, 'Old', 'body', '2026-06-01', 'pending',
                    '{"alert_id":"stale_alert"}', '2026-06-01', '2026-06-01')
            """,
            (SCOPE_FINANCE_KPI, period_ref_id(2026, 6), KIND_KPI_ALERT),
        )
        conn.commit()
        out = sync_finance_kpi_inbox(
            conn, year=2026, month=6, alerts_result={"alerts": [], "alert_count": 0}
        )
        self.assertEqual(out["synced"], 0)
        self.assertGreaterEqual(out["removed"], 1)

    def test_dispatch_always_syncs_inbox(self) -> None:
        conn = _setup_conn()
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("PTT_FINANCE_KPI_SLACK_WEBHOOK", None)
            os.environ.pop("PTT_FINANCE_KPI_ALERT_EMAIL", None)
            out = dispatch_finance_kpi_alerts(conn, year=2026, month=6, only_critical=False)
        self.assertIn("inbox", out)
        self.assertIn(out.get("reason"), ("no_alerts", "inbox_only"))


if __name__ == "__main__":
    unittest.main()
