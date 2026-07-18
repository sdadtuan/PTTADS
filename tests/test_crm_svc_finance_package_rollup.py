"""Tests nhóm 2 — rollup doanh thu + gross margin theo service_slug."""
from __future__ import annotations

import sqlite3
import unittest

from crm_svc_finance import (
    create_expense,
    create_payment,
    ensure_schema,
    get_service_package_rollup,
    migrate_contract_billing_type,
)


def _setup_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE crm_customers (id INTEGER PRIMARY KEY, name TEXT);
        INSERT INTO crm_customers (id, name) VALUES (1, 'KH A');

        CREATE TABLE crm_contracts (
            id INTEGER PRIMARY KEY,
            customer_id INTEGER,
            service_slug TEXT DEFAULT '',
            billing_type TEXT NOT NULL DEFAULT 'one_off',
            status TEXT DEFAULT 'active',
            amount_vnd INTEGER DEFAULT 0
        );
        INSERT INTO crm_contracts (id, customer_id, amount_vnd)
        VALUES (10, 1, 10000000), (11, 1, 5000000);

        CREATE TABLE crm_service_lifecycle (
            id INTEGER PRIMARY KEY,
            customer_id INTEGER,
            contract_id INTEGER,
            service_slug TEXT,
            stage TEXT NOT NULL DEFAULT 'deliver',
            status TEXT DEFAULT 'active'
        );
        INSERT INTO crm_service_lifecycle (id, customer_id, contract_id, service_slug, status)
        VALUES (1, 1, 10, 'dich-vu-seo-tong-the', 'active'),
               (2, 1, 11, 'dich-vu-seo-tong-the', 'active'),
               (3, 1, 11, 'thiet-ke-landing-page', 'active');
        """
    )
    ensure_schema(conn)
    migrate_contract_billing_type(conn)
    conn.commit()
    return conn


class TestServicePackageRollup(unittest.TestCase):
    def test_rollup_groups_by_slug_and_month_margin(self) -> None:
        conn = _setup_conn()
        create_payment(conn, 1, 4_000_000, "2026-06-05", status="received")
        create_payment(conn, 2, 2_000_000, "2026-06-10", status="received")
        create_payment(conn, 3, 5_000_000, "2026-06-08", status="received")
        create_expense(conn, 1, "NV", "nhan-cong", 1_000_000, "2026-06-06")
        create_expense(conn, 2, "Tool", "cong-cu", 400_000, "2026-06-11")
        create_expense(conn, 3, "Design", "khac", 1_500_000, "2026-06-09")

        rollup = get_service_package_rollup(conn, year=2026, month=6)
        self.assertEqual(rollup["year"], 2026)
        self.assertEqual(rollup["month"], 6)
        self.assertEqual(len(rollup["packages"]), 2)

        seo = next(p for p in rollup["packages"] if p["service_slug"] == "dich-vu-seo-tong-the")
        self.assertEqual(seo["lifecycle_count"], 2)
        self.assertEqual(seo["received_month_vnd"], 6_000_000)
        self.assertEqual(seo["delivery_expenses_month_vnd"], 1_400_000)
        self.assertAlmostEqual(seo["gross_margin_month_pct"], 76.67, places=1)
        self.assertEqual(seo["received_lifetime_vnd"], 6_000_000)

        landing = next(
            p for p in rollup["packages"] if p["service_slug"] == "thiet-ke-landing-page"
        )
        self.assertEqual(landing["lifecycle_count"], 1)
        self.assertEqual(landing["received_month_vnd"], 5_000_000)
        self.assertAlmostEqual(landing["gross_margin_month_pct"], 70.0, places=1)

        totals = rollup["totals"]
        self.assertEqual(totals["lifecycle_count"], 3)
        self.assertEqual(totals["received_month_vnd"], 11_000_000)
        self.assertEqual(totals["delivery_expenses_month_vnd"], 2_900_000)
        self.assertAlmostEqual(totals["gross_margin_month_pct"], 73.64, places=1)

    def test_excludes_non_active_lifecycle(self) -> None:
        conn = _setup_conn()
        conn.execute(
            "UPDATE crm_service_lifecycle SET status = 'lost' WHERE id = 3"
        )
        conn.commit()
        create_payment(conn, 3, 9_000_000, "2026-06-01", status="received")
        rollup = get_service_package_rollup(conn, year=2026, month=6)
        slugs = {p["service_slug"] for p in rollup["packages"]}
        self.assertNotIn("thiet-ke-landing-page", slugs)
        self.assertEqual(rollup["totals"]["lifecycle_count"], 2)

    def test_month_filter_excludes_other_months(self) -> None:
        conn = _setup_conn()
        create_payment(conn, 1, 3_000_000, "2026-05-28", status="received")
        create_payment(conn, 1, 2_000_000, "2026-06-02", status="received")
        create_expense(conn, 1, "May cost", "khac", 500_000, "2026-05-29")
        create_expense(conn, 1, "Jun cost", "khac", 200_000, "2026-06-03")
        rollup = get_service_package_rollup(conn, year=2026, month=6)
        seo = rollup["packages"][0]
        self.assertEqual(seo["received_month_vnd"], 2_000_000)
        self.assertEqual(seo["delivery_expenses_month_vnd"], 200_000)
        self.assertEqual(seo["received_lifetime_vnd"], 5_000_000)
        self.assertAlmostEqual(seo["gross_margin_month_pct"], 90.0, places=1)

    def test_zero_revenue_month_margin_is_zero(self) -> None:
        conn = _setup_conn()
        create_payment(conn, 1, 1_000_000, "2026-05-01", status="received")
        rollup = get_service_package_rollup(conn, year=2026, month=6)
        seo = next(p for p in rollup["packages"] if p["service_slug"] == "dich-vu-seo-tong-the")
        self.assertEqual(seo["received_month_vnd"], 0)
        self.assertEqual(seo["gross_margin_month_pct"], 0.0)
        self.assertEqual(seo["received_lifetime_vnd"], 1_000_000)


if __name__ == "__main__":
    unittest.main()
