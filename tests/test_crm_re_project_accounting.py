"""Kế toán dự án — dòng tiền, sync KH, dashboard, AI."""
from __future__ import annotations

import sqlite3
import unittest

from crm_lead_ai import ai_search_leads
from crm_lead_store import ensure_lead_schema
from crm_project_deep import ensure_project_deep_schema
from crm_project_leads import ensure_project_leads_schema
from crm_re_project_accounting import (
    ai_project_finance_query,
    apply_predicted_risks_to_register,
    build_accounting_export_sheets,
    compute_accounting_dashboard,
    ensure_accounting_schema,
    forecast_financial_outlook,
    import_cash_flow_csv,
    list_cash_flow_lines,
    predict_financial_risks,
    save_cash_flow_line,
    sync_budget_from_plans,
    sync_revenue_from_inventory,
)
from crm_re_projects import (
    create_project,
    ensure_re_projects_schema,
    list_budget_lines,
    save_product,
)

TS = "2026-06-20 10:00:00"


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    ensure_re_projects_schema(conn)
    ensure_lead_schema(conn)
    ensure_project_leads_schema(conn)
    ensure_project_deep_schema(conn)
    ensure_accounting_schema(conn)
    conn.commit()
    return conn


class TestCrmReProjectAccounting(unittest.TestCase):
    def setUp(self) -> None:
        self.conn = _conn()
        proj = create_project(
            self.conn,
            {
                "name": "Acct Test",
                "code": "ACCT",
                "project_type": "mixed",
                "business_plan": {
                    "revenue_target_vnd": 10_000_000_000,
                    "financial_plan": {
                        "marketing_cost_vnd": 500_000_000,
                        "land_cost_vnd": 2_000_000_000,
                    },
                },
                "marketing_plan": {
                    "budget_total_vnd": 600_000_000,
                    "budget_breakdown": [
                        {"channel": "Facebook Ads", "amount_vnd": 300_000_000, "sub_category": "fb_ads"},
                        {"channel": "Google Ads", "amount_vnd": 200_000_000, "sub_category": "google_ads"},
                    ],
                },
                "sales_plan": {"revenue_target_vnd": 9_000_000_000},
            },
            ts=TS,
        )
        self.project_id = int(proj["id"])
        save_product(
            self.conn,
            self.project_id,
            {
                "unit_code": "S-01",
                "zone": "Z1",
                "product_line": "can_ho",
                "status": "sold",
                "net_price_vnd": 2_500_000_000,
            },
            ts=TS,
        )
        save_product(
            self.conn,
            self.project_id,
            {
                "unit_code": "S-02",
                "zone": "Z1",
                "product_line": "can_ho",
                "status": "available",
                "net_price_vnd": 2_000_000_000,
            },
            ts=TS,
        )
        self.conn.commit()

    def tearDown(self) -> None:
        self.conn.close()

    def test_sync_budget_from_plans(self) -> None:
        out = sync_budget_from_plans(self.conn, self.project_id, ts=TS)
        self.assertGreater(out["created"], 0)
        lines = list_budget_lines(self.conn, self.project_id)
        items = {b["line_item"]: b for b in lines}
        self.assertIn("Doanh thu mục tiêu (KH kinh doanh)", items)
        self.assertEqual(items["Doanh thu mục tiêu (KH kinh doanh)"]["planned_vnd"], 10_000_000_000)
        self.assertTrue(any("MKT — Facebook Ads" in b["line_item"] for b in lines))
        out2 = sync_budget_from_plans(self.conn, self.project_id, ts=TS)
        self.assertGreaterEqual(out2["skipped"], 1)

    def test_cash_flow_and_dashboard(self) -> None:
        save_cash_flow_line(
            self.conn,
            self.project_id,
            {
                "flow_type": "outflow",
                "category": "marketing",
                "sub_category": "fb_ads",
                "line_item": "Chi FB tháng 6",
                "amount_vnd": 50_000_000,
                "period_month": "2026-06",
                "status": "paid",
            },
            created_by="test",
            ts=TS,
        )
        save_cash_flow_line(
            self.conn,
            self.project_id,
            {
                "flow_type": "inflow",
                "category": "revenue",
                "line_item": "Thu cọc khách A",
                "amount_vnd": 100_000_000,
                "period_month": "2026-06",
                "status": "paid",
            },
            ts=TS,
        )
        dash = compute_accounting_dashboard(self.conn, self.project_id)
        self.assertEqual(dash["cash_flow"]["inflow_paid_vnd"], 100_000_000)
        self.assertEqual(dash["cash_flow"]["outflow_paid_vnd"], 50_000_000)
        self.assertEqual(dash["cash_flow"]["net_cash_paid_vnd"], 50_000_000)
        mkt = dash["marketing"]["by_channel"]
        self.assertTrue(any(c.get("sub_category") == "fb_ads" for c in mkt))

    def test_sync_revenue_from_inventory(self) -> None:
        out = sync_revenue_from_inventory(self.conn, self.project_id, ts=TS, created_by="test")
        self.assertEqual(out["sold_units"], 1)
        self.assertEqual(out["revenue_vnd"], 2_500_000_000)
        dash = compute_accounting_dashboard(self.conn, self.project_id)
        self.assertEqual(dash["inventory"]["revenue_vnd"], 2_500_000_000)
        lines = list_cash_flow_lines(self.conn, self.project_id, flow_type="inflow")
        self.assertTrue(any("tồn kho" in c["line_item"].lower() for c in lines))

    def test_import_cash_flow_csv(self) -> None:
        csv_text = (
            "flow_type,category,line_item,amount_vnd,period_month,status,sub_category\n"
            "outflow,marketing,Google Q2,25000000,2026-06,paid,google_ads\n"
        )
        res = import_cash_flow_csv(self.conn, self.project_id, csv_text, ts=TS)
        self.assertEqual(res["created"], 1)
        lines = list_cash_flow_lines(self.conn, self.project_id)
        self.assertEqual(len(lines), 1)
        self.assertEqual(lines[0]["amount_vnd"], 25_000_000)

    def test_ai_finance_query(self) -> None:
        sync_budget_from_plans(self.conn, self.project_id, ts=TS)
        save_cash_flow_line(
            self.conn,
            self.project_id,
            {
                "flow_type": "outflow",
                "category": "marketing",
                "sub_category": "fb_ads",
                "line_item": "MKT test",
                "amount_vnd": 10_000_000,
                "status": "paid",
            },
            ts=TS,
        )
        out = ai_project_finance_query(
            self.conn,
            "Chi phí marketing dự án này?",
            re_project_id=self.project_id,
        )
        self.assertIn("Marketing", out["answer"])
        self.assertEqual(out["focus"], "marketing")

    def test_ai_search_routes_finance_with_project(self) -> None:
        sync_budget_from_plans(self.conn, self.project_id, ts=TS)
        out = ai_search_leads(
            self.conn,
            "Dòng tiền và lợi nhuận dự án",
            re_project_id=self.project_id,
        )
        self.assertIn("answer", out)
        self.assertTrue("dashboard" in out or "P&L" in out["answer"] or "Dòng tiền" in out["answer"])

    def test_predict_financial_risks_negative_cash(self) -> None:
        save_cash_flow_line(
            self.conn,
            self.project_id,
            {
                "flow_type": "outflow",
                "category": "marketing",
                "line_item": "Chi lớn",
                "amount_vnd": 500_000_000,
                "status": "paid",
            },
            ts=TS,
        )
        pack = predict_financial_risks(self.conn, self.project_id)
        codes = {r["code"] for r in pack.get("risks") or []}
        self.assertIn("cash_negative", codes)
        self.assertGreater(pack["summary"]["total"], 0)

    def test_forecast_outlook(self) -> None:
        save_cash_flow_line(
            self.conn,
            self.project_id,
            {
                "flow_type": "outflow",
                "category": "admin",
                "line_item": "Chi T1",
                "amount_vnd": 10_000_000,
                "period_month": "2026-05",
                "status": "paid",
            },
            ts=TS,
        )
        save_cash_flow_line(
            self.conn,
            self.project_id,
            {
                "flow_type": "outflow",
                "category": "admin",
                "line_item": "Chi T2",
                "amount_vnd": 12_000_000,
                "period_month": "2026-06",
                "status": "paid",
            },
            ts=TS,
        )
        fc = forecast_financial_outlook(self.conn, self.project_id, months_ahead=3)
        self.assertEqual(fc["months_ahead"], 3)
        self.assertEqual(len(fc.get("projections") or []), 3)
        self.assertIn(fc.get("outlook"), ("positive", "neutral", "at_risk", "critical"))

    def test_build_accounting_export_sheets(self) -> None:
        sync_budget_from_plans(self.conn, self.project_id, ts=TS)
        sheets = build_accounting_export_sheets(self.conn, self.project_id)
        self.assertEqual(len(sheets), 7)
        titles = [s[0] for s in sheets]
        self.assertIn("Rủi ro AI", titles)
        self.assertIn("Dự báo", titles)

    def test_apply_predicted_risks(self) -> None:
        save_cash_flow_line(
            self.conn,
            self.project_id,
            {
                "flow_type": "outflow",
                "category": "marketing",
                "line_item": "Overspend",
                "amount_vnd": 800_000_000,
                "status": "paid",
            },
            ts=TS,
        )
        sync_budget_from_plans(self.conn, self.project_id, ts=TS)
        from crm_re_projects import list_risks

        res = apply_predicted_risks_to_register(self.conn, self.project_id, ts=TS)
        self.assertGreater(res["applied"], 0)
        risks = list_risks(self.conn, self.project_id)
        self.assertTrue(any("[AI-KT:" in str(r.get("description") or "") for r in risks))
        res2 = apply_predicted_risks_to_register(self.conn, self.project_id, ts=TS)
        self.assertGreater(res2["skipped"], 0)


if __name__ == "__main__":
    unittest.main()
