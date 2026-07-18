"""Tests cho crm_svc_finance module."""
from __future__ import annotations

import os
import sqlite3
import unittest

from crm_svc_finance import (
    COST_PHASE_DELIVERY,
    COST_PHASE_PRESALES,
    ExpenseValidationError,
    create_expense,
    create_payment,
    delete_expense,
    delete_payment,
    ensure_schema,
    get_latest_finance_scan,
    get_summary,
    list_expenses,
    list_payments,
    run_ai_finance_scan,
    update_expense,
    update_payment,
)


def _setup_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS crm_service_lifecycle (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            service_slug TEXT NOT NULL DEFAULT '',
            stage TEXT NOT NULL DEFAULT 'lead',
            status TEXT NOT NULL DEFAULT 'active',
            stage_entered_at TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL DEFAULT ''
        )
    """)
    conn.execute("""
        INSERT INTO crm_service_lifecycle
            (id, service_slug, stage, status, stage_entered_at, created_at, updated_at)
        VALUES (1, 'dich-vu-seo-tong-the', 'deliver', 'active',
                '2026-06-23 00:00:00', '2026-06-23 00:00:00', '2026-06-23 00:00:00')
    """)
    conn.commit()
    ensure_schema(conn)
    return conn


class TestEnsureSchema(unittest.TestCase):
    def test_tables_created(self):
        conn = _setup_conn()
        tables = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()}
        self.assertIn("crm_svc_payments", tables)
        self.assertIn("crm_svc_expenses", tables)
        self.assertIn("crm_svc_finance_scans", tables)

    def test_idempotent(self):
        conn = _setup_conn()
        ensure_schema(conn)
        ensure_schema(conn)


class TestGetSummary(unittest.TestCase):
    def test_no_data_returns_zeros(self):
        conn = _setup_conn()
        s = get_summary(conn, 1, 0)
        self.assertEqual(s["expected_revenue"], 0)
        self.assertEqual(s["received_revenue"], 0)
        self.assertEqual(s["pending_revenue"], 0)
        self.assertEqual(s["total_expenses"], 0)
        self.assertEqual(s["profit"], 0)
        self.assertEqual(s["margin_pct"], 0.0)
        self.assertEqual(s["outstanding"], 0)

    def test_received_only(self):
        conn = _setup_conn()
        create_payment(conn, 1, 5_000_000, "2026-06-01", status="received")
        s = get_summary(conn, 1, 10_000_000)
        self.assertEqual(s["received_revenue"], 5_000_000)
        self.assertEqual(s["outstanding"], 5_000_000)

    def test_pending_not_counted_in_received(self):
        conn = _setup_conn()
        create_payment(conn, 1, 3_000_000, "2026-06-01", status="pending")
        s = get_summary(conn, 1, 10_000_000)
        self.assertEqual(s["received_revenue"], 0)
        self.assertEqual(s["pending_revenue"], 3_000_000)

    def test_cancelled_excluded_from_both(self):
        conn = _setup_conn()
        create_payment(conn, 1, 2_000_000, "2026-06-01", status="cancelled")
        s = get_summary(conn, 1, 10_000_000)
        self.assertEqual(s["received_revenue"], 0)
        self.assertEqual(s["pending_revenue"], 0)

    def test_profit_calculation(self):
        conn = _setup_conn()
        create_payment(conn, 1, 10_000_000, "2026-06-01", status="received")
        create_expense(conn, 1, "Chi phí A", "nhan-cong", 3_000_000, "2026-06-05")
        s = get_summary(conn, 1, 10_000_000)
        self.assertEqual(s["profit"], 7_000_000)

    def test_margin_pct_calculation(self):
        conn = _setup_conn()
        create_payment(conn, 1, 10_000_000, "2026-06-01", status="received")
        create_expense(conn, 1, "Chi phí", "khac", 2_000_000, "2026-06-05")
        s = get_summary(conn, 1, 10_000_000)
        self.assertAlmostEqual(s["margin_pct"], 80.0, places=1)

    def test_division_by_zero_guard_when_received_zero(self):
        conn = _setup_conn()
        create_expense(conn, 1, "Chi phí", "khac", 1_000_000, "2026-06-05")
        s = get_summary(conn, 1, 0)
        self.assertEqual(s["margin_pct"], 0.0)

    def test_presales_expense_excluded_from_profit(self):
        conn = _setup_conn()
        conn.execute(
            """
            INSERT INTO crm_service_lifecycle
                (id, service_slug, stage, status, stage_entered_at, created_at, updated_at)
            VALUES (2, 'dich-vu-aeo', 'lead', 'draft',
                    '2026-06-01', '2026-06-01', '2026-06-01')
            """
        )
        conn.commit()
        create_payment(conn, 1, 10_000_000, "2026-06-01", status="received")
        create_expense(conn, 1, "Triển khai", "nhan-cong", 3_000_000, "2026-06-05")
        create_expense(
            conn,
            2,
            "Gọi lead",
            "dien_thoai",
            500_000,
            "2026-06-02",
            cost_phase=COST_PHASE_PRESALES,
            lifecycle_stage="lead",
        )
        s = get_summary(conn, 1, 10_000_000)
        self.assertEqual(s["delivery_expenses"], 3_000_000)
        self.assertEqual(s["presales_expenses"], 0)
        self.assertEqual(s["profit"], 7_000_000)
        s2 = get_summary(conn, 2, 0)
        self.assertEqual(s2["presales_expenses"], 500_000)
        self.assertEqual(s2["delivery_expenses"], 0)

    def test_auto_presales_phase_on_draft_lead(self):
        conn = _setup_conn()
        conn.execute(
            """
            INSERT INTO crm_service_lifecycle
                (id, service_slug, stage, status, stage_entered_at, created_at, updated_at)
            VALUES (2, 'dich-vu-aeo', 'lead', 'draft',
                    '2026-06-01', '2026-06-01', '2026-06-01')
            """
        )
        conn.commit()
        eid = create_expense(conn, 2, "Công lead", "cong_lead", 200_000, "2026-06-03")
        row = conn.execute(
            "SELECT cost_phase, lifecycle_stage FROM crm_svc_expenses WHERE id = ?",
            (eid,),
        ).fetchone()
        self.assertEqual(row[0], COST_PHASE_PRESALES)
        self.assertEqual(row[1], "lead")

    def test_migration_columns_exist(self):
        conn = _setup_conn()
        cols = {r[1] for r in conn.execute("PRAGMA table_info(crm_svc_expenses)").fetchall()}
        self.assertIn("cost_phase", cols)
        self.assertIn("lifecycle_stage", cols)
        self.assertIn("lead_id", cols)
        self.assertIn("presales_id", cols)


class TestPayments(unittest.TestCase):
    def test_create_returns_positive_id(self):
        conn = _setup_conn()
        pid = create_payment(conn, 1, 5_000_000, "2026-06-01")
        self.assertIsInstance(pid, int)
        self.assertGreater(pid, 0)

    def test_list_ordered_newest_first(self):
        conn = _setup_conn()
        create_payment(conn, 1, 1_000_000, "2026-06-01", status="received")
        create_payment(conn, 1, 2_000_000, "2026-06-15", status="received")
        payments = list_payments(conn, 1)
        self.assertEqual(payments[0]["received_on"], "2026-06-15")
        self.assertEqual(payments[1]["received_on"], "2026-06-01")

    def test_update_amount(self):
        conn = _setup_conn()
        pid = create_payment(conn, 1, 5_000_000, "2026-06-01")
        update_payment(conn, pid, amount_vnd=7_000_000)
        row = conn.execute(
            "SELECT amount_vnd FROM crm_svc_payments WHERE id = ?", (pid,)
        ).fetchone()
        self.assertEqual(row[0], 7_000_000)

    def test_update_status(self):
        conn = _setup_conn()
        pid = create_payment(conn, 1, 5_000_000, "2026-06-01")
        update_payment(conn, pid, status="received")
        row = conn.execute(
            "SELECT status FROM crm_svc_payments WHERE id = ?", (pid,)
        ).fetchone()
        self.assertEqual(row[0], "received")

    def test_delete_existing_returns_true(self):
        conn = _setup_conn()
        pid = create_payment(conn, 1, 5_000_000, "2026-06-01")
        self.assertTrue(delete_payment(conn, pid))
        self.assertIsNone(
            conn.execute(
                "SELECT id FROM crm_svc_payments WHERE id = ?", (pid,)
            ).fetchone()
        )

    def test_delete_nonexistent_returns_false(self):
        conn = _setup_conn()
        self.assertFalse(delete_payment(conn, 99999))


class TestExpenses(unittest.TestCase):
    def test_create_returns_positive_id(self):
        conn = _setup_conn()
        eid = create_expense(conn, 1, "Chi phí content", "nhan-cong", 2_000_000, "2026-06-05")
        self.assertIsInstance(eid, int)
        self.assertGreater(eid, 0)

    def test_list_ordered_newest_first(self):
        conn = _setup_conn()
        create_expense(conn, 1, "Chi A", "khac", 1_000_000, "2026-06-01")
        create_expense(conn, 1, "Chi B", "khac", 2_000_000, "2026-06-15")
        expenses = list_expenses(conn, 1)
        self.assertEqual(expenses[0]["expense_on"], "2026-06-15")
        self.assertEqual(expenses[1]["expense_on"], "2026-06-01")

    def test_update_title_and_category(self):
        conn = _setup_conn()
        eid = create_expense(conn, 1, "Cũ", "khac", 1_000_000, "2026-06-01")
        update_expense(conn, eid, title="Mới", category="outsource")
        row = conn.execute(
            "SELECT title, category FROM crm_svc_expenses WHERE id = ?", (eid,)
        ).fetchone()
        self.assertEqual(row[0], "Mới")
        self.assertEqual(row[1], "outsource")

    def test_update_amount_and_date(self):
        conn = _setup_conn()
        eid = create_expense(conn, 1, "Chi phí", "khac", 1_000_000, "2026-06-01")
        update_expense(conn, eid, amount_vnd=3_000_000, expense_on="2026-06-20")
        row = conn.execute(
            "SELECT amount_vnd, expense_on FROM crm_svc_expenses WHERE id = ?", (eid,)
        ).fetchone()
        self.assertEqual(row[0], 3_000_000)
        self.assertEqual(row[1], "2026-06-20")

    def test_delete_existing_returns_true(self):
        conn = _setup_conn()
        eid = create_expense(conn, 1, "Chi phí", "khac", 1_000_000, "2026-06-01")
        self.assertTrue(delete_expense(conn, eid))
        self.assertIsNone(
            conn.execute(
                "SELECT id FROM crm_svc_expenses WHERE id = ?", (eid,)
            ).fetchone()
        )

    def test_delete_nonexistent_returns_false(self):
        conn = _setup_conn()
        self.assertFalse(delete_expense(conn, 99999))


class TestGetLatestFinanceScan(unittest.TestCase):
    def test_no_scan_returns_empty_string(self):
        conn = _setup_conn()
        self.assertEqual(get_latest_finance_scan(conn, 1, "health"), "")

    def test_returns_latest_not_first(self):
        conn = _setup_conn()
        conn.execute(
            "INSERT INTO crm_svc_finance_scans (lifecycle_id, ai_output, scan_type, created_at) "
            "VALUES (1, 'health cũ', 'health', '2026-06-23 08:00:00')"
        )
        conn.execute(
            "INSERT INTO crm_svc_finance_scans (lifecycle_id, ai_output, scan_type, created_at) "
            "VALUES (1, 'health mới', 'health', '2026-06-23 09:00:00')"
        )
        conn.commit()
        self.assertEqual(get_latest_finance_scan(conn, 1, "health"), "health mới")

    def test_scan_types_isolated(self):
        conn = _setup_conn()
        conn.execute(
            "INSERT INTO crm_svc_finance_scans (lifecycle_id, ai_output, scan_type, created_at) "
            "VALUES (1, 'health result', 'health', '2026-06-23 08:00:00')"
        )
        conn.execute(
            "INSERT INTO crm_svc_finance_scans (lifecycle_id, ai_output, scan_type, created_at) "
            "VALUES (1, 'forecast result', 'forecast', '2026-06-23 08:00:00')"
        )
        conn.commit()
        self.assertEqual(get_latest_finance_scan(conn, 1, "health"), "health result")
        self.assertEqual(get_latest_finance_scan(conn, 1, "forecast"), "forecast result")


class TestRunAiFinanceScan(unittest.TestCase):
    def test_no_api_key_returns_empty_string(self):
        conn = _setup_conn()
        old_key = os.environ.pop("ANTHROPIC_API_KEY", None)
        try:
            result = run_ai_finance_scan(conn, 1, "health", {
                "service_name": "SEO Tổng thể",
                "customer_name": "KH Test",
                "contract_amount_vnd": 10_000_000,
                "received_revenue": 5_000_000,
                "total_expenses": 2_000_000,
                "profit": 3_000_000,
                "margin_pct": 60.0,
            })
            self.assertEqual(result, "")
        finally:
            if old_key is not None:
                os.environ["ANTHROPIC_API_KEY"] = old_key


if __name__ == "__main__":
    unittest.main()
