"""Tests sổ quỹ + cash forecast dashboard tuần."""
from __future__ import annotations

import sqlite3
import unittest
from datetime import date

from crm_owner_cash_ledger import (
    POSITION_SOURCE_LEDGER,
    POSITION_SOURCE_PROXY,
    build_cash_forecast_30d,
    delete_cash_snapshot,
    get_cash_position,
    list_cash_snapshots,
    upsert_cash_snapshot,
)
from crm_owner_weekly_dashboard import get_owner_weekly_dashboard
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
            created_at TEXT DEFAULT '2026-06-01 10:00:00',
            updated_at TEXT DEFAULT '2026-06-01 10:00:00',
            status_entered_at TEXT DEFAULT '2026-06-01 10:00:00'
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
        """
    )
    ensure_schema(conn)
    ensure_tasks_schema(conn)
    ensure_kpi_config_schema(conn)
    return conn


class TestCashLedger(unittest.TestCase):
    def test_proxy_when_no_snapshot(self) -> None:
        conn = _setup_conn()
        conn.execute(
            """
            INSERT INTO crm_svc_payments
                (lifecycle_id, amount_vnd, received_on, status)
            VALUES (1, 10000000, '2026-06-20', 'received')
            """
        )
        conn.commit()
        meta = get_cash_position(conn, date(2026, 6, 25))
        self.assertEqual(meta["source"], POSITION_SOURCE_PROXY)
        self.assertEqual(meta["position_vnd"], 10_000_000)

    def test_ledger_snapshot_plus_flow(self) -> None:
        conn = _setup_conn()
        upsert_cash_snapshot(
            conn,
            snapshot_on=date(2026, 6, 22),
            balance_vnd=100_000_000,
            source="bank",
            notes="TK chính",
        )
        conn.executemany(
            """
            INSERT INTO crm_svc_payments
                (lifecycle_id, amount_vnd, received_on, status)
            VALUES (1, ?, ?, 'received')
            """,
            [(5_000_000, "2026-06-23"), (3_000_000, "2026-06-24")],
        )
        conn.execute(
            """
            INSERT INTO crm_svc_expenses
                (lifecycle_id, amount_vnd, expense_on, cost_phase)
            VALUES (1, 2000000, '2026-06-24', 'delivery')
            """
        )
        conn.commit()
        meta = get_cash_position(conn, date(2026, 6, 24))
        self.assertEqual(meta["source"], POSITION_SOURCE_LEDGER)
        self.assertEqual(meta["position_vnd"], 106_000_000)
        snaps = list_cash_snapshots(conn)
        self.assertEqual(len(snaps), 1)
        self.assertEqual(snaps[0]["source"], "bank")

    def test_forecast_includes_ar_and_expense(self) -> None:
        conn = _setup_conn()
        upsert_cash_snapshot(
            conn,
            snapshot_on=date(2026, 6, 28),
            balance_vnd=50_000_000,
        )
        conn.executemany(
            """
            INSERT INTO crm_svc_payments
                (lifecycle_id, amount_vnd, received_on, due_on, status)
            VALUES (1, ?, ?, ?, ?)
            """,
            [
                (10_000_000, "2026-06-01", "2026-07-05", "pending"),
                (20_000_000, "2026-05-01", "2026-05-15", "pending"),
            ],
        )
        conn.execute(
            """
            INSERT INTO crm_svc_expenses
                (lifecycle_id, amount_vnd, expense_on, cost_phase)
            VALUES (1, 30000000, '2026-06-15', 'delivery')
            """
        )
        conn.commit()
        as_of = date(2026, 6, 29)
        pos = int(get_cash_position(conn, as_of)["position_vnd"])
        fc = build_cash_forecast_30d(conn, as_of, current_position=pos)
        self.assertEqual(fc["ar_due_future_vnd"], 10_000_000)
        self.assertEqual(fc["ar_overdue_vnd"], 20_000_000)
        self.assertEqual(fc["ar_overdue_collect_vnd"], 10_000_000)
        self.assertEqual(fc["ar_inflow_vnd"], 20_000_000)
        self.assertGreater(fc["projected_outflow_30d_vnd"], 0)
        self.assertEqual(
            fc["forecast_vnd"],
            pos + fc["ar_inflow_vnd"] - fc["projected_outflow_30d_vnd"],
        )

    def test_delete_snapshot(self) -> None:
        conn = _setup_conn()
        upsert_cash_snapshot(conn, snapshot_on=date(2026, 6, 1), balance_vnd=1)
        self.assertTrue(delete_cash_snapshot(conn, date(2026, 6, 1)))
        self.assertEqual(list_cash_snapshots(conn), [])


class TestOwnerWeeklyCashLedger(unittest.TestCase):
    def test_dashboard_uses_ledger_when_snapshot_exists(self) -> None:
        conn = _setup_conn()
        upsert_cash_snapshot(
            conn,
            snapshot_on=date(2026, 6, 22),
            balance_vnd=200_000_000,
        )
        conn.commit()
        dash = get_owner_weekly_dashboard(conn, week_end=date(2026, 6, 29))
        cl = dash["cash_ledger"]
        self.assertTrue(cl["has_snapshot"])
        self.assertEqual(cl["position_source"], POSITION_SOURCE_LEDGER)
        cash_close = next(
            m for m in dash["blocks"]["cash"]["metrics"] if m["key"] == "cash_close"
        )
        self.assertIn("Sổ quỹ", cash_close["note"])


if __name__ == "__main__":
    unittest.main()
