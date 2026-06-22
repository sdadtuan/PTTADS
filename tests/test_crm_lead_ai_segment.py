"""AI Lead — segment KĐT hỗn hợp (product_line, zone, giữ chỗ, gợi ý căn)."""
from __future__ import annotations

import sqlite3
import unittest

from crm_lead_ai import (
    ai_recommend_lead,
    ai_search_leads,
    ai_suggest_products_for_lead,
    ai_summarize_lead,
)
from crm_lead_store import create_lead, ensure_lead_schema, lead_row_to_dict
from crm_project_deep import ensure_project_deep_schema
from crm_project_leads import add_project_staff, ensure_project_leads_schema
from crm_re_projects import create_project, ensure_re_projects_schema, save_product

TS = "2026-06-15 11:00:00"


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    ensure_re_projects_schema(conn)
    ensure_lead_schema(conn)
    ensure_project_leads_schema(conn)
    ensure_project_deep_schema(conn)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS crm_staff (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            active INTEGER NOT NULL DEFAULT 1,
            internal_code TEXT NOT NULL DEFAULT '',
            notes TEXT NOT NULL DEFAULT ''
        )
        """
    )
    conn.execute("INSERT INTO crm_staff (id, name, active) VALUES (1, 'Sales SH', 1)")
    conn.commit()
    return conn


class TestCrmLeadAiSegment(unittest.TestCase):
    def setUp(self) -> None:
        self.conn = _conn()
        proj = create_project(
            self.conn,
            {"name": "KĐT AI Test", "code": "AI-MIX", "project_type": "mixed"},
            ts=TS,
        )
        self.project_id = int(proj["id"])
        save_product(
            self.conn,
            self.project_id,
            {
                "unit_code": "SH-01",
                "zone": "Shophouse A",
                "product_line": "shophouse",
                "status": "available",
                "list_price_vnd": 5_000_000_000,
            },
            ts=TS,
        )
        add_project_staff(
            self.conn,
            self.project_id,
            staff_id=1,
            role="sales",
            assign_enabled=True,
            scope_product_lines=["shophouse"],
            scope_zones=["Shophouse A"],
            ts=TS,
        )
        row, _, _ = create_lead(
            self.conn,
            full_name="Khách shophouse",
            phone="0903000001",
            email="",
            re_project_id=self.project_id,
            product_line="shophouse",
            zone="Shophouse A",
            product_interest="Shophouse góc",
            auto_assign=False,
            created_by="test",
            ts=TS,
        )
        self.lead_id = int(row["id"])
        self.conn.commit()

    def tearDown(self) -> None:
        self.conn.close()

    def test_ai_search_by_product_line(self) -> None:
        out = ai_search_leads(
            self.conn,
            "Lead shophouse phân khu Shophouse A",
            re_project_id=self.project_id,
        )
        self.assertTrue(out["leads"])
        self.assertEqual(out["leads"][0]["id"], self.lead_id)

    def test_ai_suggest_products_for_lead(self) -> None:
        out = ai_suggest_products_for_lead(self.conn, self.lead_id, limit=5)
        self.assertGreaterEqual(len(out.get("products") or []), 1)
        self.assertEqual(out["products"][0]["unit_code"], "SH-01")

    def test_ai_recommend_includes_product_and_scoped_assign(self) -> None:
        out = ai_recommend_lead(self.conn, self.lead_id)
        types = {r.get("type") for r in out.get("recommendations") or []}
        self.assertIn("product", types)
        self.assertIn("assign", types)

    def test_ai_summary_includes_segment(self) -> None:
        out = ai_summarize_lead(self.conn, self.lead_id)
        summary = out.get("summary") or ""
        self.assertIn("shophouse", summary.lower())
        self.assertIn("Shophouse A", summary)


if __name__ == "__main__":
    unittest.main()
