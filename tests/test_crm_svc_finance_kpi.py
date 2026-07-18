"""Tests nhóm 6 — finance KPI alerts + export."""
from __future__ import annotations

import os
import sqlite3
import unittest

from crm_svc_finance import COST_PHASE_PRESALES, ensure_schema
from crm_svc_finance_kpi import (
    ALERT_WARNING,
    build_finance_kpi_export_sheets,
    collect_finance_kpi_alerts,
    load_finance_kpi_bundle,
)
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

        CREATE TABLE crm_service_lifecycle (
            id INTEGER PRIMARY KEY,
            customer_id INTEGER,
            contract_id INTEGER,
            assigned_am INTEGER,
            assigned_sp INTEGER,
            service_slug TEXT DEFAULT 'dich-vu-seo-tong-the',
            stage TEXT DEFAULT 'deliver',
            status TEXT DEFAULT 'active',
            stage_entered_at TEXT DEFAULT '2026-06-01 10:00:00',
            created_at TEXT DEFAULT '2026-06-01 10:00:00'
        );

        CREATE TABLE crm_service_lifecycle_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lifecycle_id INTEGER,
            to_stage TEXT,
            created_at TEXT
        );

        CREATE TABLE crm_staff (
            id INTEGER PRIMARY KEY,
            name TEXT,
            active INTEGER NOT NULL DEFAULT 1
        );
        INSERT INTO crm_staff (id, name) VALUES (10, 'AM One');
        """
    )
    ensure_schema(conn)
    ensure_tasks_schema(conn)
    return conn


class TestFinanceKpiAlerts(unittest.TestCase):
    def test_concentration_warning(self) -> None:
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

        out = collect_finance_kpi_alerts(conn, year=2026, month=6)
        ids = {a["id"] for a in out["alerts"]}
        self.assertTrue(
            "concentration_warning" in ids or "concentration_critical" in ids
        )
        self.assertGreater(out["alert_count"], 0)

    def test_ar_overdue_warning(self) -> None:
        conn = _setup_conn()
        conn.execute(
            "INSERT INTO crm_service_lifecycle (id, customer_id, status) VALUES (1, 1, 'active')"
        )
        conn.execute(
            """
            INSERT INTO crm_svc_payments
                (lifecycle_id, amount_vnd, received_on, due_on, status)
            VALUES (1, 5000000, '', '2026-05-01', 'pending')
            """
        )
        conn.commit()

        out = collect_finance_kpi_alerts(conn, year=2026, month=6)
        ids = {a["id"] for a in out["alerts"]}
        self.assertIn("ar_overdue_warning", ids)

    def test_no_alerts_when_healthy(self) -> None:
        conn = _setup_conn()
        out = collect_finance_kpi_alerts(conn, year=2026, month=6)
        self.assertEqual(out["alert_count"], 0)
        self.assertFalse(out["has_critical"])


class TestFinanceKpiExport(unittest.TestCase):
    def test_export_sheets_include_summary(self) -> None:
        conn = _setup_conn()
        bundle = load_finance_kpi_bundle(conn, year=2026, month=6)
        sheets = build_finance_kpi_export_sheets(bundle)
        self.assertGreaterEqual(len(sheets), 5)
        summary = sheets[0]
        self.assertEqual(summary[0], "Tom tat")
        flat = [str(cell) for row in summary[2] for cell in row]
        self.assertTrue(any("2026" in cell or "06" in cell for cell in flat))


class TestDeliveryOntimeAlert(unittest.TestCase):
    def setUp(self) -> None:
        os.environ["PTT_DELIVERY_TASK_SLA_DAYS"] = "7"

    def tearDown(self) -> None:
        os.environ.pop("PTT_DELIVERY_TASK_SLA_DAYS", None)

    def test_ontime_warning_when_late(self) -> None:
        conn = _setup_conn()
        conn.execute(
            """
            INSERT INTO crm_service_lifecycle
                (id, customer_id, stage, status, stage_entered_at)
            VALUES (10, 1, 'deliver', 'active', '2026-06-01 10:00:00')
            """
        )
        conn.execute(
            """
            INSERT INTO crm_service_lifecycle_events (lifecycle_id, to_stage, created_at)
            VALUES (10, 'deliver', '2026-06-01 10:00:00')
            """
        )
        conn.executescript(
            """
            INSERT INTO crm_svc_tasks
                (lifecycle_id, stage, title, is_done, done_at, due_on, created_at, updated_at)
            VALUES
                (10, 'deliver', 'On time', 1, '2026-06-05 12:00:00', '2026-06-08', '', ''),
                (10, 'deliver', 'Late', 1, '2026-06-12 12:00:00', '2026-06-08', '', '');
            """
        )
        conn.commit()

        out = collect_finance_kpi_alerts(conn, year=2026, month=6)
        ids = {a["id"] for a in out["alerts"]}
        self.assertIn("delivery_ontime_warning", ids)
        alert = next(a for a in out["alerts"] if a["id"] == "delivery_ontime_warning")
        self.assertEqual(alert["level"], ALERT_WARNING)


if __name__ == "__main__":
    unittest.main()
