"""Tests nhóm 5 — concentration risk + team capacity."""
from __future__ import annotations

import os
import sqlite3
import unittest

from crm_svc_portfolio import (
    get_capacity_metrics,
    get_concentration_metrics,
    get_portfolio_metrics,
)


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
            (1, 'KH lớn A', 0),
            (2, 'KH lớn B', 0),
            (3, 'KH nhỏ', 0),
            (4, 'Placeholder', 1);

        CREATE TABLE crm_staff (
            id INTEGER PRIMARY KEY,
            name TEXT,
            active INTEGER NOT NULL DEFAULT 1
        );
        INSERT INTO crm_staff (id, name) VALUES (10, 'AM One'), (11, 'AM Two'), (20, 'SP One');

        CREATE TABLE crm_service_lifecycle (
            id INTEGER PRIMARY KEY,
            customer_id INTEGER,
            assigned_am INTEGER,
            assigned_sp INTEGER,
            status TEXT DEFAULT 'active',
            service_slug TEXT DEFAULT 'dich-vu-seo-tong-the'
        );

        CREATE TABLE crm_svc_payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lifecycle_id INTEGER,
            amount_vnd INTEGER,
            received_on TEXT,
            status TEXT DEFAULT 'received'
        );
        """
    )
    return conn


class TestConcentration(unittest.TestCase):
    def test_top2_concentration_pct(self) -> None:
        conn = _setup_conn()
        for lc_id, cid in ((1, 1), (2, 2), (3, 3)):
            conn.execute(
                """
                INSERT INTO crm_service_lifecycle (id, customer_id, status)
                VALUES (?, ?, 'active')
                """,
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

        metrics = get_concentration_metrics(conn, year=2026, month=6)
        self.assertEqual(metrics["total_received_vnd"], 100_000_000)
        self.assertEqual(metrics["top2_concentration_pct"], 80.0)
        self.assertEqual(metrics["top1_share_pct"], 50.0)
        self.assertTrue(metrics["concentration_risk"])
        self.assertEqual(len(metrics["top_customers"]), 3)

    def test_excludes_placeholder_customer(self) -> None:
        conn = _setup_conn()
        conn.execute(
            "INSERT INTO crm_service_lifecycle (id, customer_id) VALUES (9, 4)"
        )
        conn.execute(
            """
            INSERT INTO crm_svc_payments (lifecycle_id, amount_vnd, received_on, status)
            VALUES (9, 99999999, '2026-06-01', 'received')
            """
        )
        conn.commit()
        metrics = get_concentration_metrics(conn, year=2026, month=6)
        self.assertEqual(metrics["paying_customers"], 0)
        self.assertEqual(metrics["total_received_vnd"], 99_999_999)


class TestCapacity(unittest.TestCase):
    def setUp(self) -> None:
        os.environ["PTT_AM_LIFECYCLE_CAPACITY"] = "4"
        os.environ["PTT_SP_LIFECYCLE_CAPACITY"] = "6"

    def tearDown(self) -> None:
        os.environ.pop("PTT_AM_LIFECYCLE_CAPACITY", None)
        os.environ.pop("PTT_SP_LIFECYCLE_CAPACITY", None)

    def test_utilization_and_revenue_per_staff(self) -> None:
        conn = _setup_conn()
        conn.execute(
            "INSERT INTO crm_service_lifecycle (id, customer_id, assigned_am, assigned_sp, status) VALUES (1, 1, 10, 20, 'active')"
        )
        conn.execute(
            "INSERT INTO crm_service_lifecycle (id, customer_id, assigned_am, assigned_sp, status) VALUES (2, 2, 10, 20, 'active')"
        )
        conn.execute(
            "INSERT INTO crm_service_lifecycle (id, customer_id, assigned_am, status) VALUES (3, 3, 11, 'active')"
        )
        conn.execute(
            """
            INSERT INTO crm_svc_payments (lifecycle_id, amount_vnd, received_on, status)
            VALUES (1, 12_000_000, '2026-06-10', 'received')
            """
        )
        conn.commit()

        metrics = get_capacity_metrics(conn, year=2026, month=6)
        self.assertEqual(metrics["am_active_staff"], 2)
        self.assertEqual(metrics["am_active_lifecycles"], 3)
        self.assertEqual(metrics["am_capacity_slots"], 8)
        self.assertEqual(metrics["am_utilization_pct"], 37.5)
        self.assertEqual(metrics["sp_active_lifecycles"], 2)
        self.assertEqual(metrics["sp_utilization_pct"], round(2 / 6 * 100, 1))
        self.assertEqual(metrics["received_month_vnd"], 12_000_000)
        self.assertEqual(metrics["revenue_per_am_vnd"], 6_000_000)
        self.assertEqual(metrics["revenue_per_active_lifecycle_vnd"], 4_000_000)


class TestPortfolioBundle(unittest.TestCase):
    def test_get_portfolio_metrics(self) -> None:
        conn = _setup_conn()
        conn.execute(
            "INSERT INTO crm_service_lifecycle (id, customer_id, assigned_am, status) VALUES (1, 1, 10, 'active')"
        )
        conn.execute(
            """
            INSERT INTO crm_svc_payments (lifecycle_id, amount_vnd, received_on, status)
            VALUES (1, 5_000_000, '2026-06-01', 'received')
            """
        )
        conn.commit()
        out = get_portfolio_metrics(conn, year=2026, month=6)
        self.assertIn("concentration", out)
        self.assertIn("capacity", out)
        self.assertEqual(out["concentration"]["top1_share_pct"], 100.0)


if __name__ == "__main__":
    unittest.main()
