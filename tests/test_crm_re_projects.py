"""Test CRM RE Projects — quản lý dự án BĐS."""
from __future__ import annotations

import sqlite3
import unittest

from crm_re_projects import (
    compute_product_inventory_stats,
    compute_kpi_board_stats,
    compute_project_workflow,
    create_project,
    default_business_plan,
    delete_kpi,
    delete_project,
    delete_project_type,
    ensure_re_projects_schema,
    fetch_project,
    fetch_project_summary,
    list_kpis,
    list_products,
    list_project_types,
    list_projects,
    save_budget_line,
    save_kpi,
    save_product,
    save_project_type,
    save_risk,
    seed_re_kpi_metrics,
    sync_project_kpis_to_staff,
    update_project,
    validate_project_type,
)

TS = "2026-05-25 10:00:00"


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    ensure_re_projects_schema(conn)
    return conn


def _conn_with_crm_kpi() -> sqlite3.Connection:
    conn = _conn()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS crm_kpi_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT NOT NULL DEFAULT '',
            name TEXT NOT NULL,
            unit TEXT NOT NULL DEFAULT '',
            description TEXT NOT NULL DEFAULT '',
            sort_order INTEGER NOT NULL DEFAULT 0,
            active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            higher_is_better INTEGER NOT NULL DEFAULT 1,
            warn_ratio REAL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS crm_staff (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            active INTEGER NOT NULL DEFAULT 1,
            sort_order INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS crm_staff_kpi (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            staff_id INTEGER NOT NULL,
            metric_id INTEGER NOT NULL,
            year INTEGER NOT NULL,
            month INTEGER NOT NULL,
            target_value REAL,
            actual_value REAL,
            status TEXT NOT NULL DEFAULT 'draft',
            note TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE(staff_id, metric_id, year, month)
        )
        """
    )
    seed_re_kpi_metrics(conn)
    conn.commit()
    return conn


class TestCrmReProjects(unittest.TestCase):
    def test_schema_seeds_sample_project(self) -> None:
        conn = _conn()
        rows = list_projects(conn)
        self.assertGreaterEqual(len(rows), 1)
        self.assertIn("Green City", rows[0]["name"])

    def test_create_and_update_project(self) -> None:
        conn = _conn()
        conn.execute("DELETE FROM crm_re_projects")
        proj = create_project(
            conn,
            {"name": "Sunrise Tower", "code": "ST-01", "total_units": 200},
            ts=TS,
        )
        self.assertEqual(proj["code"], "ST-01")
        self.assertEqual(proj["total_units"], 200)
        bp = default_business_plan()
        bp["vision"] = "Top 3 khu vực"
        updated = update_project(conn, proj["id"], {"business_plan": bp}, ts=TS)
        self.assertEqual(updated["business_plan"]["vision"], "Top 3 khu vực")

    def test_project_workflow_progress(self) -> None:
        conn = _conn()
        proj = create_project(conn, {"name": "WF Test", "code": "WF01", "district": "Q1"}, ts=TS)
        wf = compute_project_workflow(conn, int(proj["id"]))
        self.assertEqual(wf["total_steps"], 8)
        self.assertEqual([s["id"] for s in wf["steps"]], [
            "overview", "business", "budget", "products", "sales", "marketing", "kpi", "risks",
        ])
        self.assertIn(wf["steps"][0]["status"], ("done", "in_progress"))
        self.assertTrue(wf.get("methodology_note"))
        bp = default_business_plan()
        bp["vision"] = "Test vision"
        bp["mission"] = "Test mission"
        bp["revenue_target_vnd"] = 1_000_000_000
        update_project(conn, proj["id"], {"business_plan": bp}, ts=TS)
        save_kpi(
            conn,
            proj["id"],
            {"metric_name": "Doanh thu", "category": "revenue", "target_value": 100, "actual_value": 50},
            ts=TS,
        )
        wf2 = compute_project_workflow(conn, int(proj["id"]))
        business = next(s for s in wf2["steps"] if s["id"] == "business")
        kpi = next(s for s in wf2["steps"] if s["id"] == "kpi")
        self.assertEqual(business["status"], "done")
        self.assertEqual(kpi["status"], "in_progress")
        self.assertGreater(wf2["progress_pct"], wf["progress_pct"])

    def test_workflow_step_free_navigation(self) -> None:
        conn = _conn()
        proj = create_project(conn, {"name": "Free Nav Test", "code": "LK01"}, ts=TS)
        wf = compute_project_workflow(conn, int(proj["id"]))
        for step in wf["steps"]:
            self.assertTrue(step["accessible"])
            self.assertFalse(step["locked"])
            self.assertNotEqual(step["status_label"], "Đang khóa")
        business = next(s for s in wf["steps"] if s["id"] == "business")
        self.assertIn(business["status_label"], ("Chưa bắt đầu", "Đang làm", "Hoàn thành"))
        update_project(
            conn,
            proj["id"],
            {
                "code": "LK01",
                "district": "Q1",
                "total_units": 100,
            },
            ts=TS,
        )
        wf2 = compute_project_workflow(conn, int(proj["id"]))
        self.assertEqual(wf2["steps"][0]["status"], "done")
        self.assertFalse(wf2["steps"][1]["locked"])

    def test_products_kpis_risks_budget_summary(self) -> None:
        conn = _conn()
        conn.execute("DELETE FROM crm_re_projects")
        proj = create_project(conn, {"name": "Test Project", "total_units": 10}, ts=TS)
        pid = proj["id"]
        save_product(
            conn,
            pid,
            {
                "unit_code": "A-01-05",
                "zone": "Phân khu A",
                "product_line": "can_ho",
                "typology": "2pn",
                "list_price_vnd": 2_000_000_000,
                "status": "available",
            },
            ts=TS,
        )
        save_product(
            conn,
            pid,
            {
                "unit_code": "SH-01",
                "zone": "Khu shophouse",
                "product_line": "shophouse",
                "typology": "shophouse",
                "list_price_vnd": 2_100_000_000,
                "status": "sold",
            },
            ts=TS,
        )
        save_kpi(
            conn,
            pid,
            {
                "metric_name": "Doanh thu tháng",
                "metric_code": "revenue_signed",
                "target_value": 100,
                "actual_value": 80,
                "unit": "%",
                "owner_name": "NV A",
                "track_status": "active",
            },
            ts=TS,
        )
        save_risk(
            conn,
            pid,
            {"title": "Chậm pháp lý", "probability_pct": 40, "impact_pct": 70, "risk_level": "high"},
            ts=TS,
        )
        save_budget_line(
            conn,
            pid,
            {"line_item": "Doanh thu bán căn", "category": "revenue", "planned_vnd": 5_000_000_000, "actual_vnd": 4_000_000_000},
            ts=TS,
        )
        save_budget_line(
            conn,
            pid,
            {"line_item": "Chi marketing", "category": "marketing", "planned_vnd": 500_000_000, "actual_vnd": 450_000_000},
            ts=TS,
        )
        summary = fetch_project_summary(conn, pid)
        self.assertEqual(summary["product_count"], 2)
        self.assertEqual(summary["products_sold"], 1)
        self.assertEqual(summary["products_available"], 1)
        self.assertEqual(summary["product_lines_count"], 2)
        self.assertEqual(summary["kpi_with_owner_count"], 1)
        self.assertIn("inventory", summary)
        self.assertIn("kpi_board", summary)
        self.assertEqual(summary["kpi_count"], 1)
        self.assertEqual(summary["risk_count"], 1)
        self.assertEqual(summary["high_risk_count"], 1)
        self.assertEqual(summary["budget_revenue_planned_vnd"], 5_000_000_000)
        self.assertEqual(summary["profit_planned_vnd"], 5_000_000_000 - 500_000_000)
        kpis = list_kpis(conn, pid)
        self.assertAlmostEqual(kpis[0]["achievement_pct"], 80.0)
        products = list_products(conn, pid)
        apt = next(p for p in products if p["unit_code"] == "A-01-05")
        self.assertEqual(apt["product_line_label"], "Căn hộ chung cư")
        inv = compute_product_inventory_stats(products)
        self.assertEqual(inv["total"], 2)
        self.assertEqual(len(inv["by_product_line"]), 2)
        board = compute_kpi_board_stats(kpis)
        self.assertEqual(board["with_owner_count"], 1)

    def test_kpi_sync_to_staff_module(self) -> None:
        conn = _conn_with_crm_kpi()
        conn.execute(
            """
            INSERT INTO crm_staff (name, active, sort_order, created_at, updated_at)
            VALUES ('NV Bán A', 1, 1, ?, ?)
            """,
            (TS, TS),
        )
        staff_id = int(conn.execute("SELECT id FROM crm_staff WHERE name = 'NV Bán A'").fetchone()["id"])
        proj = create_project(conn, {"name": "Sync Test", "code": "SY01"}, ts=TS)
        kpi = save_kpi(
            conn,
            proj["id"],
            {
                "metric_code": "RE_UNITS_SOLD",
                "metric_name": "Số căn bán ký HĐ",
                "category": "sales",
                "unit": "căn",
                "target_value": 10,
                "actual_value": 4,
                "period_month": "2026-05",
                "owner_staff_id": staff_id,
                "track_status": "active",
            },
            ts=TS,
        )
        self.assertTrue(kpi.get("synced_to_staff"))
        sk_count = conn.execute(
            "SELECT COUNT(*) AS c FROM crm_staff_kpi WHERE staff_id = ? AND year = 2026 AND month = 5",
            (staff_id,),
        ).fetchone()["c"]
        self.assertEqual(int(sk_count), 1)
        result = sync_project_kpis_to_staff(conn, proj["id"], ts=TS)
        self.assertGreaterEqual(result["synced"], 1)

    def test_delete_project_cascades_children(self) -> None:
        conn = _conn()
        conn.execute("DELETE FROM crm_re_projects")
        proj = create_project(conn, {"name": "Temp"}, ts=TS)
        pid = proj["id"]
        kpi = save_kpi(conn, pid, {"metric_name": "X", "target_value": 1}, ts=TS)
        delete_kpi(conn, pid, int(kpi["id"]))
        delete_project(conn, pid)
        self.assertIsNone(fetch_project(conn, pid))


    def test_project_types_crud(self) -> None:
        conn = _conn()
        types = list_project_types(conn)
        self.assertGreaterEqual(len(types), 6)
        row = save_project_type(
            conn,
            {"code": "nha_xuong", "name": "Nhà xưởng", "description": "KCN", "sort_order": 99},
            ts=TS,
        )
        self.assertEqual(row["code"], "nha_xuong")
        proj = create_project(conn, {"name": "P1", "project_type": "nha_xuong"}, ts=TS)
        self.assertEqual(proj["project_type"], "nha_xuong")
        with self.assertRaises(ValueError):
            delete_project_type(conn, int(row["id"]))
        delete_project(conn, proj["id"])
        delete_project_type(conn, int(row["id"]))
        with self.assertRaises(ValueError):
            validate_project_type(conn, "nha_xuong")

    def test_save_risk_returns_labels(self) -> None:
        conn = _conn()
        conn.execute("DELETE FROM crm_re_projects")
        proj = create_project(conn, {"name": "Risk labels"}, ts=TS)
        risk = save_risk(
            conn,
            proj["id"],
            {"title": "Test", "probability_pct": 30, "impact_pct": 40, "risk_level": "medium"},
            ts=TS,
        )
        self.assertEqual(risk.get("risk_level_label"), "Trung bình")
        self.assertIn("score", risk)

    def test_save_budget_returns_variance(self) -> None:
        conn = _conn()
        conn.execute("DELETE FROM crm_re_projects")
        proj = create_project(conn, {"name": "Budget var"}, ts=TS)
        line = save_budget_line(
            conn,
            proj["id"],
            {"line_item": "X", "category": "marketing", "planned_vnd": 100, "actual_vnd": 80},
            ts=TS,
        )
        self.assertEqual(line["variance_vnd"], -20)
        self.assertEqual(line["variance_pct"], -20.0)


if __name__ == "__main__":
    unittest.main()
