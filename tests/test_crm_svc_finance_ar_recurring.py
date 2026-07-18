"""Tests nhóm 1 — AR aging + recurring billing_type."""
from __future__ import annotations

import sqlite3
import unittest

from crm_svc_finance import (
    BILLING_TYPE_RECURRING,
    create_payment,
    ensure_schema,
    get_ar_aging,
    get_recurring_revenue_summary,
    get_summary,
    infer_billing_type_from_service_slug,
    migrate_contract_billing_type,
    normalize_billing_type,
    resolve_payment_due_on,
    update_payment,
)


def _setup_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE crm_customers (id INTEGER PRIMARY KEY, name TEXT);
        INSERT INTO crm_customers (id, name) VALUES (1, 'KH A');

        CREATE TABLE crm_contracts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER,
            service_slug TEXT DEFAULT '',
            billing_type TEXT NOT NULL DEFAULT 'one_off',
            status TEXT DEFAULT 'active',
            amount_vnd INTEGER DEFAULT 0
        );
        INSERT INTO crm_contracts (id, customer_id, service_slug, billing_type, status, amount_vnd)
        VALUES (10, 1, 'dich-vu-seo-tong-the', 'recurring', 'active', 12000000),
               (11, 1, 'thiet-ke-landing-page', 'one_off', 'active', 5000000);

        CREATE TABLE crm_service_lifecycle (
            id INTEGER PRIMARY KEY,
            customer_id INTEGER,
            contract_id INTEGER,
            service_slug TEXT,
            assigned_am INTEGER,
            status TEXT DEFAULT 'active'
        );
        INSERT INTO crm_service_lifecycle
            (id, customer_id, contract_id, service_slug, assigned_am, status)
        VALUES (1, 1, 10, 'dich-vu-seo-tong-the', 5, 'active'),
               (2, 1, 11, 'thiet-ke-landing-page', 5, 'active');
        """
    )
    ensure_schema(conn)
    migrate_contract_billing_type(conn)
    conn.commit()
    return conn


class TestBillingType(unittest.TestCase):
    def test_infer_recurring_from_retainer_slug(self) -> None:
        self.assertEqual(
            infer_billing_type_from_service_slug("dich-vu-seo-tong-the"),
            BILLING_TYPE_RECURRING,
        )
        self.assertEqual(
            infer_billing_type_from_service_slug("thiet-ke-landing-page"),
            "one_off",
        )

    def test_normalize_invalid(self) -> None:
        self.assertEqual(normalize_billing_type("invalid"), "one_off")


class TestArAging(unittest.TestCase):
    def test_buckets_overdue_and_not_due(self) -> None:
        conn = _setup_conn()
        create_payment(
            conn, 1, 1_000_000, "2026-05-01", status="pending", due_on="2026-05-15"
        )
        create_payment(
            conn, 1, 2_000_000, "2026-06-01", status="pending", due_on="2026-06-20"
        )
        create_payment(
            conn, 2, 500_000, "2026-06-01", status="received", due_on="2026-06-01"
        )
        aging = get_ar_aging(conn, as_of="2026-06-10")
        self.assertEqual(aging["total_pending_vnd"], 3_000_000)
        self.assertEqual(aging["total_overdue_vnd"], 1_000_000)
        self.assertEqual(aging["buckets"]["overdue_1_30"], 1_000_000)
        self.assertEqual(aging["buckets"]["not_due"], 2_000_000)
        self.assertEqual(len(aging["items"]), 2)

    def test_resolve_due_on_fallback(self) -> None:
        self.assertEqual(
            resolve_payment_due_on({"status": "pending", "received_on": "2026-06-01"}),
            "2026-06-01",
        )
        self.assertEqual(
            resolve_payment_due_on({"status": "pending", "due_on": "2026-06-15", "received_on": "2026-06-01"}),
            "2026-06-15",
        )

    def test_filter_by_am(self) -> None:
        conn = _setup_conn()
        conn.execute(
            "INSERT INTO crm_service_lifecycle (id, customer_id, contract_id, assigned_am, status) "
            "VALUES (3, 1, 10, 99, 'active')"
        )
        create_payment(conn, 3, 800_000, "2026-05-01", status="pending", due_on="2026-05-01")
        create_payment(conn, 1, 200_000, "2026-05-01", status="pending", due_on="2026-05-01")
        conn.commit()
        aging = get_ar_aging(conn, as_of="2026-06-01", am_id=99)
        self.assertEqual(aging["total_pending_vnd"], 800_000)
        self.assertEqual(len(aging["items"]), 1)

    def test_summary_includes_ar_overdue(self) -> None:
        conn = _setup_conn()
        create_payment(
            conn, 1, 1_500_000, "2026-05-01", status="pending", due_on="2026-05-01"
        )
        s = get_summary(conn, 1, 10_000_000)
        self.assertEqual(s["ar_pending_vnd"], 1_500_000)
        self.assertEqual(s["ar_overdue_vnd"], 1_500_000)


class TestRecurringRevenue(unittest.TestCase):
    def test_received_recurring_in_month(self) -> None:
        conn = _setup_conn()
        create_payment(
            conn, 1, 3_000_000, "2026-06-05", status="received", due_on="2026-06-05"
        )
        create_payment(
            conn, 2, 1_000_000, "2026-06-10", status="received", due_on="2026-06-10"
        )
        create_payment(
            conn, 1, 500_000, "2026-06-12", status="pending", due_on="2026-06-12"
        )
        summary = get_recurring_revenue_summary(conn, year=2026, month=6)
        self.assertEqual(summary["received_recurring_vnd"], 3_000_000)
        self.assertEqual(summary["pending_recurring_vnd"], 500_000)
        self.assertEqual(summary["active_recurring_contracts"], 1)

    def test_am_filter_recurring(self) -> None:
        conn = _setup_conn()
        conn.execute("UPDATE crm_service_lifecycle SET assigned_am = 7 WHERE id = 1")
        conn.commit()
        create_payment(
            conn, 1, 2_000_000, "2026-06-01", status="received", due_on="2026-06-01"
        )
        s_am = get_recurring_revenue_summary(conn, year=2026, month=6, am_id=7)
        s_other = get_recurring_revenue_summary(conn, year=2026, month=6, am_id=5)
        self.assertEqual(s_am["received_recurring_vnd"], 2_000_000)
        self.assertEqual(s_other["received_recurring_vnd"], 0)


class TestPaymentDueOnMigration(unittest.TestCase):
    def test_create_pending_sets_due_on_from_received(self) -> None:
        conn = _setup_conn()
        pid = create_payment(conn, 1, 100_000, "2026-06-01", status="pending")
        row = conn.execute(
            "SELECT due_on FROM crm_svc_payments WHERE id = ?", (pid,)
        ).fetchone()
        self.assertEqual(row["due_on"], "2026-06-01")

    def test_update_due_on(self) -> None:
        conn = _setup_conn()
        pid = create_payment(conn, 1, 100_000, "2026-06-01", status="pending")
        update_payment(conn, pid, due_on="2026-06-15")
        row = conn.execute(
            "SELECT due_on FROM crm_svc_payments WHERE id = ?", (pid,)
        ).fetchone()
        self.assertEqual(row["due_on"], "2026-06-15")


if __name__ == "__main__":
    unittest.main()
