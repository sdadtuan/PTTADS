"""Bảng giá version — CRUD, apply bulk, compare, AI."""
from __future__ import annotations

import sqlite3
import unittest

from crm_lead_ai import ai_price_list_query, ai_search_leads
from crm_lead_store import ensure_lead_schema
from crm_project_leads import ensure_project_leads_schema
from crm_project_deep import ensure_project_deep_schema
from crm_re_price_lists import (
    apply_price_list,
    compare_price_lists,
    ensure_price_lists_schema,
    import_price_list_items_csv,
    list_price_lists,
    products_on_price_version,
    save_price_list,
)
from crm_re_projects import create_project, ensure_re_projects_schema, save_product

TS = "2026-06-20 10:00:00"


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    ensure_re_projects_schema(conn)
    ensure_lead_schema(conn)
    ensure_project_leads_schema(conn)
    ensure_project_deep_schema(conn)
    ensure_price_lists_schema(conn)
    conn.commit()
    return conn


class TestCrmRePriceLists(unittest.TestCase):
    def setUp(self) -> None:
        self.conn = _conn()
        proj = create_project(self.conn, {"name": "Price Test", "code": "PR", "project_type": "mixed"}, ts=TS)
        self.project_id = int(proj["id"])
        save_product(
            self.conn,
            self.project_id,
            {
                "unit_code": "A-01",
                "zone": "Z1",
                "product_line": "can_ho",
                "status": "available",
                "list_price_vnd": 1_000_000_000,
                "net_price_vnd": 950_000_000,
                "price_batch": "Dot1-2026",
            },
            ts=TS,
        )
        save_product(
            self.conn,
            self.project_id,
            {
                "unit_code": "A-02",
                "zone": "Z1",
                "product_line": "can_ho",
                "status": "available",
                "list_price_vnd": 1_100_000_000,
                "net_price_vnd": 1_000_000_000,
                "price_batch": "Dot1-2026",
            },
            ts=TS,
        )
        self.conn.commit()

    def tearDown(self) -> None:
        self.conn.close()

    def test_create_import_apply_price_list(self) -> None:
        pl = save_price_list(
            self.conn,
            self.project_id,
            {"version_code": "Dot2-2026", "name": "Đợt 2", "effective_date": "2026-07-01"},
            created_by="test",
            ts=TS,
        )
        csv_text = (
            "unit_code,list_price_vnd,net_price_vnd\n"
            "A-01,1200000000,1150000000\n"
            "A-02,1300000000,1250000000\n"
        )
        imp = import_price_list_items_csv(self.conn, int(pl["id"]), csv_text, ts=TS)
        self.assertEqual(imp["created"], 2)
        res = apply_price_list(self.conn, self.project_id, int(pl["id"]), updated_by="test", ts=TS)
        self.conn.commit()
        self.assertEqual(res["matched"], 2)
        self.assertEqual(res["version_code"], "Dot2-2026")
        on_v2 = products_on_price_version(self.conn, self.project_id, "Dot2-2026")
        self.assertEqual(len(on_v2), 2)
        self.assertEqual(int(on_v2[0]["list_price_vnd"]), 1_200_000_000)
        lists = list_price_lists(self.conn, self.project_id)
        active = [x for x in lists if x["status"] == "active"]
        self.assertEqual(len(active), 1)
        self.assertEqual(active[0]["version_code"], "Dot2-2026")

    def test_compare_price_lists(self) -> None:
        pl1 = save_price_list(
            self.conn,
            self.project_id,
            {"version_code": "Dot1-2026", "effective_date": "2026-01-01"},
            ts=TS,
        )
        pl2 = save_price_list(
            self.conn,
            self.project_id,
            {"version_code": "Dot2-2026", "effective_date": "2026-07-01"},
            ts=TS,
        )
        import_price_list_items_csv(
            self.conn,
            int(pl1["id"]),
            "unit_code,list_price_vnd,net_price_vnd\nA-01,1000000000,950000000\n",
            ts=TS,
        )
        import_price_list_items_csv(
            self.conn,
            int(pl2["id"]),
            "unit_code,list_price_vnd,net_price_vnd\nA-01,1200000000,1150000000\nA-03,800000000,750000000\n",
            ts=TS,
        )
        cmp = compare_price_lists(self.conn, self.project_id, "Dot1-2026", "Dot2-2026")
        self.assertEqual(cmp["version_a"], "Dot1-2026")
        self.assertEqual(cmp["version_b"], "Dot2-2026")
        sm = cmp["summary"]
        self.assertGreaterEqual(sm["increased"], 1)
        self.assertEqual(sm["only_b"], 1)

    def test_ai_products_on_version(self) -> None:
        out = ai_price_list_query(
            self.conn,
            "Căn nào đang áp giá Dot1-2026?",
            re_project_id=self.project_id,
        )
        self.assertGreaterEqual(len(out.get("products") or []), 2)
        self.assertIn("Dot1-2026", out.get("answer") or "")

    def test_ai_compare_versions(self) -> None:
        pl1 = save_price_list(
            self.conn,
            self.project_id,
            {"version_code": "Dot1-2026"},
            ts=TS,
        )
        pl2 = save_price_list(
            self.conn,
            self.project_id,
            {"version_code": "Dot2-2026"},
            ts=TS,
        )
        import_price_list_items_csv(
            self.conn,
            int(pl1["id"]),
            "unit_code,list_price_vnd\nA-01,1000000000\n",
            ts=TS,
        )
        import_price_list_items_csv(
            self.conn,
            int(pl2["id"]),
            "unit_code,list_price_vnd\nA-01,1200000000\n",
            ts=TS,
        )
        out = ai_price_list_query(
            self.conn,
            "So sánh giá Dot1-2026 vs Dot2-2026",
            re_project_id=self.project_id,
        )
        self.assertIsNotNone(out.get("compare"))
        self.assertIn("So sánh", out.get("answer") or "")

    def test_ai_search_price_list_branch(self) -> None:
        out = ai_search_leads(
            self.conn,
            "Căn nào đang áp giá Dot1-2026",
            re_project_id=self.project_id,
        )
        self.assertIn("products", out)
        self.assertGreaterEqual(len(out.get("products") or []), 1)


if __name__ == "__main__":
    unittest.main()
