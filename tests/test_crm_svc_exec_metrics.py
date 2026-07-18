"""Tests executive KPI — CAC, delivery on-time, MRR/ARR."""
from __future__ import annotations

import os
import sqlite3
import unittest

from crm_svc_exec_metrics import (
    get_cac_metrics,
    get_delivery_ontime_metrics,
    get_exec_metrics,
    get_mrr_arr_metrics,
    set_marketing_spend_vnd,
)
from crm_svc_finance import (
    BILLING_CYCLE_QUARTERLY,
    BILLING_TYPE_RECURRING,
    COST_PHASE_PRESALES,
    contract_amount_to_mrr_vnd,
    ensure_schema,
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
        INSERT INTO crm_customers (id, name) VALUES (1, 'KH mới'), (2, 'KH cũ');

        CREATE TABLE crm_contracts (
            id INTEGER PRIMARY KEY,
            customer_id INTEGER,
            billing_type TEXT NOT NULL DEFAULT 'one_off',
            billing_cycle TEXT NOT NULL DEFAULT 'monthly',
            status TEXT DEFAULT 'active',
            amount_vnd INTEGER DEFAULT 0
        );

        CREATE TABLE crm_service_lifecycle (
            id INTEGER PRIMARY KEY,
            customer_id INTEGER,
            contract_id INTEGER,
            assigned_am INTEGER,
            service_slug TEXT DEFAULT '',
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
        """
    )
    ensure_schema(conn)
    ensure_tasks_schema(conn)
    return conn


class TestCacMetrics(unittest.TestCase):
    def setUp(self) -> None:
        os.environ["PTT_MONTHLY_MARKETING_SPEND_VND"] = "2000000"

    def tearDown(self) -> None:
        os.environ.pop("PTT_MONTHLY_MARKETING_SPEND_VND", None)

    def test_cac_new_customer_first_payment(self) -> None:
        conn = _setup_conn()
        conn.execute(
            "INSERT INTO crm_service_lifecycle (id, customer_id, status) VALUES (1, 1, 'active')"
        )
        conn.execute(
            "INSERT INTO crm_service_lifecycle (id, customer_id, status) VALUES (2, 2, 'active')"
        )
        conn.execute(
            """
            INSERT INTO crm_svc_payments (lifecycle_id, amount_vnd, received_on, status)
            VALUES (2, 5000000, '2026-05-15', 'received')
            """
        )
        conn.execute(
            """
            INSERT INTO crm_svc_payments (lifecycle_id, amount_vnd, received_on, status)
            VALUES (1, 10000000, '2026-06-10', 'received')
            """
        )
        conn.execute(
            """
            INSERT INTO crm_svc_expenses
                (lifecycle_id, title, category, amount_vnd, expense_on, cost_phase)
            VALUES (1, 'Pre', 'cong_lead', 3000000, '2026-06-05', ?)
            """,
            (COST_PHASE_PRESALES,),
        )
        conn.commit()

        m = get_cac_metrics(conn, year=2026, month=6)
        self.assertEqual(m["new_customers"], 1)
        self.assertEqual(m["presales_cost_vnd"], 3_000_000)
        self.assertEqual(m["marketing_cost_vnd"], 2_000_000)
        self.assertEqual(m["acquisition_cost_vnd"], 5_000_000)
        self.assertEqual(m["cac_vnd"], 5_000_000)

    def test_cac_marketing_spend_db_overrides_env(self) -> None:
        conn = _setup_conn()
        set_marketing_spend_vnd(conn, year=2026, month=6, amount_vnd=8_000_000)
        conn.execute(
            "INSERT INTO crm_service_lifecycle (id, customer_id, status) VALUES (1, 1, 'active')"
        )
        conn.execute(
            """
            INSERT INTO crm_svc_payments (lifecycle_id, amount_vnd, received_on, status)
            VALUES (1, 10000000, '2026-06-10', 'received')
            """
        )
        conn.commit()

        m = get_cac_metrics(conn, year=2026, month=6)
        self.assertEqual(m["marketing_cost_vnd"], 8_000_000)
        self.assertEqual(m["marketing_spend_source"], "db")
        self.assertEqual(m["cac_vnd"], 8_000_000)


class TestBillingCycleMrr(unittest.TestCase):
    def test_contract_amount_to_mrr_quarterly(self) -> None:
        self.assertEqual(contract_amount_to_mrr_vnd(12_000_000, BILLING_CYCLE_QUARTERLY), 4_000_000)


class TestDeliveryOntime(unittest.TestCase):
    def setUp(self) -> None:
        os.environ["PTT_DELIVERY_TASK_SLA_DAYS"] = "7"

    def tearDown(self) -> None:
        os.environ.pop("PTT_DELIVERY_TASK_SLA_DAYS", None)

    def test_on_time_rate_decided_only(self) -> None:
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

        m = get_delivery_ontime_metrics(conn, year=2026, month=6)
        self.assertEqual(m["tasks_on_time"], 1)
        self.assertEqual(m["tasks_late"], 1)
        self.assertEqual(m["on_time_rate_pct"], 50.0)


class TestMrrArr(unittest.TestCase):
    def test_mrr_arr_bookings_and_cash(self) -> None:
        conn = _setup_conn()
        conn.execute(
            """
            INSERT INTO crm_contracts (id, customer_id, billing_type, status, amount_vnd)
            VALUES (100, 1, ?, 'active', 15000000),
                   (101, 2, 'one_off', 'active', 5000000)
            """,
            (BILLING_TYPE_RECURRING,),
        )
        conn.execute(
            """
            INSERT INTO crm_service_lifecycle (id, customer_id, contract_id, status)
            VALUES (1, 1, 100, 'active'), (2, 2, 101, 'active')
            """
        )
        conn.execute(
            """
            INSERT INTO crm_svc_payments (lifecycle_id, amount_vnd, received_on, status)
            VALUES (1, 12000000, '2026-06-20', 'received'),
                   (2, 5000000, '2026-06-21', 'received')
            """
        )
        conn.commit()

        m = get_mrr_arr_metrics(conn, year=2026, month=6)
        self.assertEqual(m["mrr_bookings_vnd"], 15_000_000)
        self.assertEqual(m["arr_bookings_vnd"], 180_000_000)
        self.assertEqual(m["mrr_cash_vnd"], 12_000_000)
        self.assertEqual(m["active_recurring_contracts"], 1)
        self.assertEqual(m["recurring_revenue_share_pct"], 70.6)

    def test_mrr_quarterly_billing_cycle(self) -> None:
        conn = _setup_conn()
        conn.execute(
            """
            INSERT INTO crm_contracts
                (id, customer_id, billing_type, billing_cycle, status, amount_vnd)
            VALUES (100, 1, ?, ?, 'active', 12000000)
            """,
            (BILLING_TYPE_RECURRING, BILLING_CYCLE_QUARTERLY),
        )
        conn.execute(
            """
            INSERT INTO crm_service_lifecycle (id, customer_id, contract_id, status)
            VALUES (1, 1, 100, 'active')
            """
        )
        conn.commit()

        m = get_mrr_arr_metrics(conn, year=2026, month=6)
        self.assertEqual(m["mrr_bookings_vnd"], 4_000_000)
        self.assertEqual(m["arr_bookings_vnd"], 48_000_000)


class TestExecBundle(unittest.TestCase):
    def test_get_exec_metrics(self) -> None:
        conn = _setup_conn()
        out = get_exec_metrics(conn, year=2026, month=6)
        self.assertIn("cac", out)
        self.assertIn("delivery_ontime", out)
        self.assertIn("mrr_arr", out)


if __name__ == "__main__":
    unittest.main()
