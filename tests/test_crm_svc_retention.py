"""Tests nhóm 3 — retention / churn / renewal cohort từ crm_contracts."""
from __future__ import annotations

import sqlite3
import unittest

from datetime import date

from crm_svc_retention import get_retention_metrics, get_retention_metrics_for_period


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
        INSERT INTO crm_customers (id, name, is_placeholder) VALUES
            (1, 'KH giữ', 0),
            (2, 'KH churn', 0),
            (3, 'Placeholder', 1);

        CREATE TABLE crm_contracts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER,
            title TEXT DEFAULT '',
            status TEXT DEFAULT 'active',
            starts_on TEXT DEFAULT '',
            ends_on TEXT DEFAULT '',
            amount_vnd INTEGER DEFAULT 0
        );
        """
    )
    return conn


class TestCustomerRetention(unittest.TestCase):
    def test_mom_retention_and_churn(self) -> None:
        conn = _setup_conn()
        # KH 1: active cả tháng 5 và 6
        conn.execute(
            """
            INSERT INTO crm_contracts
                (customer_id, title, status, starts_on, ends_on, amount_vnd)
            VALUES (1, 'HĐ A', 'active', '2026-01-01', '2026-12-31', 10000000)
            """
        )
        # KH 2: active tháng 5, hết hạn cuối tháng 5 → churn tháng 6
        conn.execute(
            """
            INSERT INTO crm_contracts
                (customer_id, title, status, starts_on, ends_on, amount_vnd)
            VALUES (2, 'HĐ B', 'active', '2026-01-01', '2026-05-31', 5000000)
            """
        )
        conn.commit()

        metrics = get_retention_metrics(conn, year=2026, month=6)
        self.assertEqual(metrics["active_customers_prev"], 2)
        self.assertEqual(metrics["active_customers"], 1)
        self.assertEqual(metrics["customers_retained"], 1)
        self.assertEqual(metrics["customer_retention_pct"], 50.0)
        self.assertEqual(metrics["customer_churn_pct"], 50.0)


class TestPeriodRetention(unittest.TestCase):
    def test_week_over_week_churn(self) -> None:
        conn = _setup_conn()
        conn.executemany(
            """
            INSERT INTO crm_contracts
                (customer_id, title, status, starts_on, ends_on, amount_vnd)
            VALUES (?, 'A', 'active', '2026-01-01', ?, 1000000)
            """,
            [(1, "2026-12-31"), (2, "2026-06-20")],
        )
        conn.commit()
        metrics = get_retention_metrics_for_period(
            conn,
            period_start=date(2026, 6, 23),
            period_end=date(2026, 6, 29),
        )
        self.assertEqual(metrics["active_customers_prev"], 2)
        self.assertEqual(metrics["active_customers"], 1)
        self.assertEqual(metrics["customer_churn_pct"], 50.0)


class TestRenewalCohort(unittest.TestCase):
    def test_cohort_outcomes_in_month(self) -> None:
        conn = _setup_conn()
        rows = [
            (1, "renewed", "2026-06-15", 12000000),
            (1, "lost", "2026-06-20", 8000000),
            (2, "cancelled", "2026-06-25", 6000000),
            (2, "completed", "2026-06-28", 4000000),
            (1, "active", "2026-06-30", 3000000),
            (1, "draft", "2026-06-10", 1000000),
            (1, "active", "2026-07-15", 2000000),
        ]
        for cid, status, ends_on, amount in rows:
            conn.execute(
                """
                INSERT INTO crm_contracts
                    (customer_id, title, status, starts_on, ends_on, amount_vnd)
                VALUES (?, ?, ?, '2026-01-01', ?, ?)
                """,
                (cid, f"HĐ {status}", status, ends_on, amount),
            )
        conn.commit()

        metrics = get_retention_metrics(conn, year=2026, month=6)
        rc = metrics["renewal_cohort"]
        self.assertEqual(rc["contracts_ending"], 5)
        self.assertEqual(rc["renewed"], 1)
        self.assertEqual(rc["churned"], 2)
        self.assertEqual(rc["completed"], 1)
        self.assertEqual(rc["pending"], 1)
        self.assertEqual(rc["renewal_rate_pct"], 25.0)
        self.assertEqual(rc["contracts_decided"], 4)
        self.assertEqual(rc["cohort_churn_rate_pct"], 40.0)

    def test_excludes_placeholder_customers(self) -> None:
        conn = _setup_conn()
        conn.execute(
            """
            INSERT INTO crm_contracts
                (customer_id, title, status, starts_on, ends_on, amount_vnd)
            VALUES (3, 'PH renewed', 'renewed', '2026-01-01', '2026-06-15', 1000000)
            """
        )
        conn.commit()

        metrics = get_retention_metrics(conn, year=2026, month=6)
        self.assertEqual(metrics["renewal_cohort"]["contracts_ending"], 0)


if __name__ == "__main__":
    unittest.main()
