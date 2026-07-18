from __future__ import annotations

import os
import sqlite3
import unittest

from crm_svc_kpi import (
    ensure_schema,
    get_am_metrics,
    get_latest_kpi_scan,
    get_lifecycle_staff_metrics,
    get_sp_metrics,
    get_targets,
    run_ai_kpi_scan,
    set_target,
)


def _setup_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS crm_staff (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            active INTEGER NOT NULL DEFAULT 1
        )
    """)
    conn.execute("INSERT INTO crm_staff (id, name, active) VALUES (1, 'Nguyễn AM', 1)")
    conn.execute("INSERT INTO crm_staff (id, name, active) VALUES (2, 'Trần SP', 1)")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS crm_contracts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            amount_vnd INTEGER NOT NULL DEFAULT 0
        )
    """)
    conn.execute("INSERT INTO crm_contracts (id, amount_vnd) VALUES (1, 10000000)")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS crm_service_lifecycle (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            service_slug TEXT NOT NULL DEFAULT '',
            stage TEXT NOT NULL DEFAULT 'deliver',
            status TEXT NOT NULL DEFAULT 'active',
            assigned_am INTEGER REFERENCES crm_staff(id),
            assigned_sp INTEGER REFERENCES crm_staff(id),
            contract_id INTEGER REFERENCES crm_contracts(id),
            created_at TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL DEFAULT ''
        )
    """)
    conn.execute("""
        INSERT INTO crm_service_lifecycle
            (id, service_slug, stage, status, assigned_am, assigned_sp, contract_id,
             created_at, updated_at)
        VALUES (1, 'seo', 'deliver', 'active', 1, 2, 1,
                '2026-06-01 00:00:00', '2026-06-01 00:00:00')
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS crm_svc_payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lifecycle_id INTEGER NOT NULL,
            amount_vnd INTEGER NOT NULL DEFAULT 0,
            received_on TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'pending',
            notes TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL DEFAULT ''
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS crm_svc_expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lifecycle_id INTEGER NOT NULL,
            title TEXT NOT NULL DEFAULT '',
            category TEXT NOT NULL DEFAULT 'khac',
            amount_vnd INTEGER NOT NULL DEFAULT 0,
            expense_on TEXT NOT NULL DEFAULT '',
            notes TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL DEFAULT ''
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS crm_svc_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lifecycle_id INTEGER NOT NULL,
            stage TEXT NOT NULL DEFAULT '',
            title TEXT NOT NULL DEFAULT '',
            is_done INTEGER NOT NULL DEFAULT 0,
            done_by INTEGER REFERENCES crm_staff(id),
            updated_at TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT ''
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS crm_svc_risks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lifecycle_id INTEGER NOT NULL,
            title TEXT NOT NULL DEFAULT '',
            is_active INTEGER NOT NULL DEFAULT 1,
            updated_at TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT ''
        )
    """)
    from crm_svc_finance import ensure_schema as finance_schema
    finance_schema(conn)
    conn.commit()
    ensure_schema(conn)
    return conn


class TestEnsureSchema(unittest.TestCase):
    def test_tables_created(self):
        conn = _setup_conn()
        tables = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()}
        self.assertIn("crm_svc_kpi_targets", tables)
        self.assertIn("crm_svc_kpi_scans", tables)

    def test_idempotent(self):
        conn = _setup_conn()
        ensure_schema(conn)  # calling twice should not raise


class TestGetAmMetrics(unittest.TestCase):
    def test_no_data_all_zeros(self):
        conn = _setup_conn()
        result = get_am_metrics(conn, staff_id=1, year=2026, month=6)
        self.assertEqual(result["received_revenue"], 0)
        self.assertEqual(result["active_services"], 1)  # lifecycle id=1 exists, active
        self.assertEqual(result["avg_margin_pct"], 0.0)
        self.assertGreaterEqual(result["outstanding"], 0)

    def test_received_revenue_correct_month(self):
        conn = _setup_conn()
        conn.execute(
            "INSERT INTO crm_svc_payments (lifecycle_id, amount_vnd, received_on, status) "
            "VALUES (1, 3000000, '2026-06-10', 'received')"
        )
        conn.execute(
            "INSERT INTO crm_svc_payments (lifecycle_id, amount_vnd, received_on, status) "
            "VALUES (1, 1000000, '2026-05-15', 'received')"
        )
        conn.commit()
        result = get_am_metrics(conn, staff_id=1, year=2026, month=6)
        self.assertEqual(result["received_revenue"], 3000000)

    def test_pending_not_in_received_revenue(self):
        conn = _setup_conn()
        conn.execute(
            "INSERT INTO crm_svc_payments (lifecycle_id, amount_vnd, received_on, status) "
            "VALUES (1, 5000000, '2026-06-01', 'pending')"
        )
        conn.commit()
        result = get_am_metrics(conn, staff_id=1, year=2026, month=6)
        self.assertEqual(result["received_revenue"], 0)

    def test_avg_margin_pct_with_data(self):
        conn = _setup_conn()
        conn.execute(
            "INSERT INTO crm_svc_payments (lifecycle_id, amount_vnd, received_on, status) "
            "VALUES (1, 5000000, '2026-06-01', 'received')"
        )
        conn.execute(
            "INSERT INTO crm_svc_expenses (lifecycle_id, title, category, amount_vnd, expense_on) "
            "VALUES (1, 'Chi phí', 'khac', 1000000, '2026-06-01')"
        )
        conn.commit()
        result = get_am_metrics(conn, staff_id=1, year=2026, month=6)
        self.assertAlmostEqual(result["avg_margin_pct"], 80.0, places=1)

    def test_outstanding_is_contract_minus_received(self):
        conn = _setup_conn()
        conn.execute(
            "INSERT INTO crm_svc_payments (lifecycle_id, amount_vnd, received_on, status) "
            "VALUES (1, 3000000, '2026-06-01', 'received')"
        )
        conn.commit()
        result = get_am_metrics(conn, staff_id=1, year=2026, month=6)
        self.assertEqual(result["outstanding"], 7000000)

    def test_no_active_lifecycles_avg_margin_zero(self):
        conn = _setup_conn()
        conn.execute(
            "UPDATE crm_service_lifecycle SET status = 'closed' WHERE id = 1"
        )
        conn.commit()
        result = get_am_metrics(conn, staff_id=1, year=2026, month=6)
        self.assertEqual(result["active_services"], 0)
        self.assertEqual(result["avg_margin_pct"], 0.0)


class TestGetSpMetrics(unittest.TestCase):
    def test_no_data_all_zeros(self):
        conn = _setup_conn()
        result = get_sp_metrics(conn, staff_id=2, year=2026, month=6)
        self.assertEqual(result["tasks_completed"], 0)
        self.assertEqual(result["tasks_pending"], 0)
        self.assertEqual(result["risks_resolved"], 0)

    def test_tasks_completed_correct_month(self):
        conn = _setup_conn()
        conn.execute(
            "INSERT INTO crm_svc_tasks (lifecycle_id, stage, title, is_done, done_by, updated_at) "
            "VALUES (1, 'deliver', 'Task A', 1, 2, '2026-06-10 10:00:00')"
        )
        conn.execute(
            "INSERT INTO crm_svc_tasks (lifecycle_id, stage, title, is_done, done_by, updated_at) "
            "VALUES (1, 'deliver', 'Task B', 1, 2, '2026-05-20 10:00:00')"
        )
        conn.commit()
        result = get_sp_metrics(conn, staff_id=2, year=2026, month=6)
        self.assertEqual(result["tasks_completed"], 1)

    def test_tasks_pending_current_state(self):
        conn = _setup_conn()
        conn.execute(
            "INSERT INTO crm_svc_tasks (lifecycle_id, stage, title, is_done, updated_at) "
            "VALUES (1, 'deliver', 'Pending Task', 0, '2026-06-01 00:00:00')"
        )
        conn.execute(
            "INSERT INTO crm_svc_tasks (lifecycle_id, stage, title, is_done, done_by, updated_at) "
            "VALUES (1, 'deliver', 'Done Task', 1, 2, '2026-06-05 00:00:00')"
        )
        conn.commit()
        result = get_sp_metrics(conn, staff_id=2, year=2026, month=6)
        self.assertEqual(result["tasks_pending"], 1)

    def test_risks_resolved_correct_month(self):
        conn = _setup_conn()
        conn.execute(
            "INSERT INTO crm_svc_risks (lifecycle_id, title, is_active, updated_at) "
            "VALUES (1, 'Risk A', 0, '2026-06-15 00:00:00')"
        )
        conn.execute(
            "INSERT INTO crm_svc_risks (lifecycle_id, title, is_active, updated_at) "
            "VALUES (1, 'Risk B', 0, '2026-05-10 00:00:00')"
        )
        conn.execute(
            "INSERT INTO crm_svc_risks (lifecycle_id, title, is_active, updated_at) "
            "VALUES (1, 'Risk C', 1, '2026-06-10 00:00:00')"
        )
        conn.commit()
        result = get_sp_metrics(conn, staff_id=2, year=2026, month=6)
        self.assertEqual(result["risks_resolved"], 1)


class TestGetLifecycleStaffMetrics(unittest.TestCase):
    def test_lifecycle_not_found(self):
        conn = _setup_conn()
        result = get_lifecycle_staff_metrics(conn, lifecycle_id=999)
        self.assertIsNone(result["am"])
        self.assertIsNone(result["sp"])

    def test_with_am_and_sp(self):
        conn = _setup_conn()
        conn.execute(
            "INSERT INTO crm_svc_tasks (lifecycle_id, stage, title, is_done, done_by, updated_at) "
            "VALUES (1, 'deliver', 'Task', 1, 2, '2026-06-01 00:00:00')"
        )
        conn.execute(
            "INSERT INTO crm_svc_payments (lifecycle_id, amount_vnd, received_on, status) "
            "VALUES (1, 4000000, '2026-06-01', 'received')"
        )
        conn.execute(
            "INSERT INTO crm_svc_risks (lifecycle_id, title, is_active, updated_at) "
            "VALUES (1, 'Risk', 0, '2026-06-01 00:00:00')"
        )
        conn.commit()
        result = get_lifecycle_staff_metrics(conn, lifecycle_id=1)
        am = result["am"]
        sp = result["sp"]
        self.assertIsNotNone(am)
        self.assertEqual(am["id"], 1)
        self.assertEqual(am["name"], "Nguyễn AM")
        self.assertEqual(am["received_revenue"], 4000000)
        self.assertIsNotNone(sp)
        self.assertEqual(sp["id"], 2)
        self.assertEqual(sp["tasks_done"], 1)
        self.assertEqual(sp["risks_resolved"], 1)

    def test_no_am_no_sp(self):
        conn = _setup_conn()
        conn.execute(
            "UPDATE crm_service_lifecycle SET assigned_am = NULL, assigned_sp = NULL WHERE id = 1"
        )
        conn.commit()
        result = get_lifecycle_staff_metrics(conn, lifecycle_id=1)
        self.assertIsNone(result["am"])
        self.assertIsNone(result["sp"])


class TestTargets(unittest.TestCase):
    def test_set_and_get_target(self):
        conn = _setup_conn()
        set_target(conn, staff_id=1, role="am", metric_key="received_revenue",
                   year=2026, month=6, target_value=50000000.0)
        targets = get_targets(conn, staff_id=1, year=2026, month=6)
        self.assertAlmostEqual(targets["received_revenue"], 50000000.0)

    def test_overwrite_target(self):
        conn = _setup_conn()
        set_target(conn, 1, "am", "active_services", 2026, 6, 5.0)
        set_target(conn, 1, "am", "active_services", 2026, 6, 8.0)
        targets = get_targets(conn, 1, 2026, 6)
        self.assertAlmostEqual(targets["active_services"], 8.0)

    def test_get_targets_empty(self):
        conn = _setup_conn()
        targets = get_targets(conn, staff_id=1, year=2026, month=6)
        self.assertEqual(targets, {})

    def test_different_month_not_returned(self):
        conn = _setup_conn()
        set_target(conn, 1, "am", "received_revenue", 2026, 5, 30000000.0)
        targets = get_targets(conn, 1, 2026, 6)
        self.assertNotIn("received_revenue", targets)


class TestGetLatestKpiScan(unittest.TestCase):
    def test_no_scan_returns_empty(self):
        conn = _setup_conn()
        result = get_latest_kpi_scan(conn, staff_id=1, role="am", year=2026, month=6)
        self.assertEqual(result, "")

    def test_returns_latest_scan(self):
        conn = _setup_conn()
        conn.execute(
            "INSERT INTO crm_svc_kpi_scans (staff_id, ai_output, role, year, month, created_at) "
            "VALUES (1, 'Phân tích A', 'am', 2026, 6, '2026-06-01 10:00:00')"
        )
        conn.execute(
            "INSERT INTO crm_svc_kpi_scans (staff_id, ai_output, role, year, month, created_at) "
            "VALUES (1, 'Phân tích B', 'am', 2026, 6, '2026-06-01 11:00:00')"
        )
        conn.commit()
        result = get_latest_kpi_scan(conn, staff_id=1, role="am", year=2026, month=6)
        self.assertEqual(result, "Phân tích B")

    def test_role_filter(self):
        conn = _setup_conn()
        conn.execute(
            "INSERT INTO crm_svc_kpi_scans (staff_id, ai_output, role, year, month, created_at) "
            "VALUES (1, 'AM scan', 'am', 2026, 6, '2026-06-01 10:00:00')"
        )
        conn.commit()
        self.assertEqual(get_latest_kpi_scan(conn, 1, "sp", 2026, 6), "")
        self.assertEqual(get_latest_kpi_scan(conn, 1, "am", 2026, 6), "AM scan")


class TestRunAiKpiScan(unittest.TestCase):
    def test_no_api_key_returns_empty(self):
        conn = _setup_conn()
        os.environ.pop("ANTHROPIC_API_KEY", None)
        result = run_ai_kpi_scan(
            conn, staff_id=1, role="am", year=2026, month=6,
            context={
                "staff_name": "Test", "month": 6, "year": 2026,
                "received_revenue": 0, "active_services": 0,
                "avg_margin_pct": 0.0, "outstanding": 0,
                "target_received_revenue": 0, "target_active_services": 0,
                "target_avg_margin_pct": 0.0,
            },
        )
        self.assertEqual(result, "")


if __name__ == "__main__":
    unittest.main()
