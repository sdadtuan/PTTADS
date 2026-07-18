"""Tests nhóm 7 — thresholds, trends, notify dispatch."""
from __future__ import annotations

import os
import sqlite3
import unittest
from unittest.mock import patch

from crm_svc_finance import ensure_schema
from crm_svc_finance_kpi import (
    get_alert_thresholds,
    get_finance_kpi_trends,
    set_alert_thresholds,
)
from crm_svc_finance_kpi_notify import build_alert_digest, dispatch_finance_kpi_alerts
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
            is_duplicate INTEGER NOT NULL DEFAULT 0
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
        """
    )
    ensure_schema(conn)
    ensure_tasks_schema(conn)
    return conn


class TestAlertThresholds(unittest.TestCase):
    def test_env_override(self) -> None:
        os.environ["PTT_KPI_ALERT_TOP2_WARN_PCT"] = "45"
        conn = _setup_conn()
        th = get_alert_thresholds(conn)
        self.assertEqual(th["top2_warn_pct"], 45.0)
        os.environ.pop("PTT_KPI_ALERT_TOP2_WARN_PCT", None)

    def test_db_overrides_env(self) -> None:
        os.environ["PTT_KPI_ALERT_TOP2_WARN_PCT"] = "45"
        conn = _setup_conn()
        set_alert_thresholds(conn, {"top2_warn_pct": 38})
        th = get_alert_thresholds(conn)
        self.assertEqual(th["top2_warn_pct"], 38.0)
        os.environ.pop("PTT_KPI_ALERT_TOP2_WARN_PCT", None)


class TestFinanceTrends(unittest.TestCase):
    def test_trend_series_length(self) -> None:
        conn = _setup_conn()
        trends = get_finance_kpi_trends(conn, year=2026, month=6, months=6)
        self.assertEqual(len(trends["labels"]), 6)
        self.assertEqual(len(trends["mrr_bookings_vnd"]), 6)
        self.assertEqual(len(trends["cac_vnd"]), 6)


class TestNotifyDispatch(unittest.TestCase):
    def test_build_digest(self) -> None:
        subject, body = build_alert_digest(
            {
                "year": 2026,
                "month": 6,
                "alert_count": 1,
                "critical_count": 1,
                "alerts": [
                    {
                        "level": "critical",
                        "title": "Test",
                        "message": "Msg",
                    }
                ],
            }
        )
        self.assertIn("2026", subject)
        self.assertIn("Test", body)

    def test_dispatch_skips_without_channels(self) -> None:
        conn = _setup_conn()
        conn.execute(
            """
            INSERT INTO crm_service_lifecycle (id, customer_id, status)
            VALUES (1, 1, 'active')
            """
        )
        conn.execute(
            """
            INSERT INTO crm_svc_payments
                (lifecycle_id, amount_vnd, received_on, due_on, status)
            VALUES (1, 5000000, '', '2026-05-01', 'pending')
            """
        )
        conn.commit()
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("PTT_FINANCE_KPI_SLACK_WEBHOOK", None)
            os.environ.pop("PTT_FINANCE_KPI_ALERT_EMAIL", None)
            out = dispatch_finance_kpi_alerts(
                conn, year=2026, month=6, only_critical=False
            )
        self.assertFalse(out.get("sent"))
        self.assertIn(out.get("reason"), ("no_channels_configured", "inbox_only", "no_alerts"))


if __name__ == "__main__":
    unittest.main()
