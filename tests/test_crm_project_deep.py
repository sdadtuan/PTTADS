"""KĐT hỗn hợp — phân khu, giữ chỗ SP, scope NV, import CSV."""
from __future__ import annotations

import sqlite3
import unittest

from crm_lead_auto_assign import LeadAssignContext, auto_assign_lead_owner, config_with_only
from crm_lead_store import create_lead, ensure_lead_schema, fetch_leads, lead_row_to_dict
from crm_project_deep import (
    ensure_project_deep_schema,
    hold_product_for_lead,
    import_products_csv,
    inventory_by_zone_summary,
    list_project_zones,
    release_product_hold,
    search_available_products,
    staff_matches_lead_scope,
)
from crm_project_leads import add_project_staff, fetch_project_assign_staff_ids, update_project_staff
from crm_re_projects import create_project, ensure_re_projects_schema, save_product

TS = "2026-06-15 10:00:00"


def _setup_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    ensure_re_projects_schema(conn)
    ensure_lead_schema(conn)
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
    conn.execute("INSERT INTO crm_staff (id, name, active) VALUES (1, 'Sales A', 1)")
    conn.execute("INSERT INTO crm_staff (id, name, active) VALUES (2, 'Sales B', 1)")
    conn.commit()
    return conn


class TestCrmProjectDeep(unittest.TestCase):
    def setUp(self) -> None:
        self.conn = _setup_conn()
        proj = create_project(self.conn, {"name": "KĐT Mixed", "code": "MIX", "project_type": "mixed"}, ts=TS)
        self.project_id = int(proj["id"])
        save_product(
            self.conn,
            self.project_id,
            {
                "unit_code": "SH-A-01",
                "zone": "Shophouse A",
                "product_line": "shophouse",
                "status": "available",
            },
            ts=TS,
        )
        save_product(
            self.conn,
            self.project_id,
            {
                "unit_code": "BT-B-01",
                "zone": "Biệt thự B",
                "product_line": "biet_thu",
                "status": "available",
            },
            ts=TS,
        )
        self.conn.commit()

    def tearDown(self) -> None:
        self.conn.close()

    def test_list_zones_and_search_products(self) -> None:
        zones = list_project_zones(self.conn, self.project_id)
        self.assertEqual(zones, ["Biệt thự B", "Shophouse A"])
        found = search_available_products(
            self.conn,
            self.project_id,
            product_line="shophouse",
            zone="Shophouse A",
        )
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["unit_code"], "SH-A-01")

    def test_create_lead_with_segment_fields(self) -> None:
        row, _, _ = create_lead(
            self.conn,
            full_name="Khách segment",
            phone="0902000001",
            email="",
            re_project_id=self.project_id,
            product_line="shophouse",
            zone="Shophouse A",
            auto_assign=False,
            created_by="test",
            ts=TS,
        )
        out = lead_row_to_dict(row, self.conn)
        self.assertEqual(out["product_line"], "shophouse")
        self.assertEqual(out["zone"], "Shophouse A")
        rows = fetch_leads(self.conn, product_line="shophouse")
        self.assertEqual(len(rows), 1)

    def test_hold_and_release_product(self) -> None:
        prod = search_available_products(self.conn, self.project_id, q="SH-A")[0]
        row, _, _ = create_lead(
            self.conn,
            full_name="Hold test",
            phone="0902000002",
            email="",
            re_project_id=self.project_id,
            re_product_id=int(prod["id"]),
            auto_assign=False,
            created_by="test",
            ts=TS,
        )
        lead_id = int(row["id"])
        hold_product_for_lead(self.conn, lead_id, int(prod["id"]), updated_by="test", ts=TS)
        self.conn.commit()
        st = self.conn.execute(
            "SELECT status, hold_lead_id FROM crm_re_project_products WHERE id = ?",
            (int(prod["id"]),),
        ).fetchone()
        self.assertEqual(st["status"], "hold")
        self.assertEqual(int(st["hold_lead_id"]), lead_id)
        release_product_hold(self.conn, lead_id, updated_by="test", ts=TS)
        self.conn.commit()
        st2 = self.conn.execute(
            "SELECT status, hold_lead_id FROM crm_re_project_products WHERE id = ?",
            (int(prod["id"]),),
        ).fetchone()
        self.assertEqual(st2["status"], "available")
        self.assertIsNone(st2["hold_lead_id"])

    def test_staff_scope_filters_auto_assign_pool(self) -> None:
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
        add_project_staff(
            self.conn,
            self.project_id,
            staff_id=2,
            role="sales",
            assign_enabled=True,
            scope_product_lines=["biet_thu"],
            scope_zones=["Biệt thự B"],
            ts=TS,
        )
        self.conn.commit()
        all_ids = fetch_project_assign_staff_ids(self.conn, self.project_id)
        self.assertEqual(set(all_ids), {1, 2})
        scoped_sh = fetch_project_assign_staff_ids(
            self.conn,
            self.project_id,
            product_line="shophouse",
            zone="Shophouse A",
        )
        self.assertEqual(scoped_sh, [1])
        scoped = fetch_project_assign_staff_ids(
            self.conn,
            self.project_id,
            product_line="biet_thu",
            zone="Biệt thự B",
        )
        self.assertEqual(scoped, [2])
        self.assertTrue(
            staff_matches_lead_scope(
                {"scope_product_lines": ["shophouse"], "scope_zones": []},
                product_line="shophouse",
                zone="Shophouse A",
            )
        )
        self.assertFalse(
            staff_matches_lead_scope(
                {"scope_product_lines": ["shophouse"], "scope_zones": []},
                product_line="biet_thu",
                zone="",
            )
        )
        cfg = config_with_only("round_robin")
        ctx = LeadAssignContext(
            lead_level="warm",
            re_project_id=self.project_id,
            product_line="biet_thu",
            zone="Biệt thự B",
        )
        sid, _, _ = auto_assign_lead_owner(self.conn, ctx, config=cfg)
        self.assertEqual(sid, 2)

    def test_update_staff_scope(self) -> None:
        add_project_staff(self.conn, self.project_id, staff_id=1, role="sales", assign_enabled=True, ts=TS)
        update_project_staff(
            self.conn,
            self.project_id,
            1,
            scope_product_lines=["can_ho"],
            scope_zones=["Tower A"],
            ts=TS,
        )
        self.conn.commit()
        ids = fetch_project_assign_staff_ids(
            self.conn,
            self.project_id,
            product_line="can_ho",
            zone="Tower A",
        )
        self.assertEqual(ids, [1])

    def test_import_products_csv(self) -> None:
        csv_text = (
            "unit_code,zone,product_line,status,price_batch\n"
            "LK-C-01,Khu liền kề C,lien_ke,available,Dot1\n"
            "LK-C-02,Khu liền kề C,lien_ke,available,Dot1\n"
        )
        result = import_products_csv(self.conn, self.project_id, csv_text, updated_by="test", ts=TS)
        self.assertEqual(result["created"], 2)
        self.assertEqual(result["updated"], 0)
        zones = list_project_zones(self.conn, self.project_id)
        self.assertIn("Khu liền kề C", zones)
        inv = inventory_by_zone_summary(self.conn, self.project_id)
        lk = next((z for z in inv if z.get("key") == "Khu liền kề C"), None)
        self.assertIsNotNone(lk)
        assert lk is not None
        self.assertGreaterEqual(lk.get("total", 0), 2)

    def test_hold_rejects_double_book(self) -> None:
        prod = search_available_products(self.conn, self.project_id, q="SH-A")[0]
        product_id = int(prod["id"])
        row1, _, _ = create_lead(
            self.conn,
            full_name="Lead A",
            phone="0902000101",
            email="",
            re_project_id=self.project_id,
            auto_assign=False,
            created_by="test",
            ts=TS,
        )
        row2, _, _ = create_lead(
            self.conn,
            full_name="Lead B",
            phone="0902000102",
            email="",
            re_project_id=self.project_id,
            auto_assign=False,
            created_by="test",
            ts=TS,
        )
        hold_product_for_lead(self.conn, int(row1["id"]), product_id, updated_by="test", ts=TS)
        self.conn.commit()
        with self.assertRaises(ValueError):
            hold_product_for_lead(self.conn, int(row2["id"]), product_id, updated_by="test", ts=TS)

    def test_price_batch_filter_and_summary(self) -> None:
        from crm_project_deep import inventory_by_price_batch_summary, list_price_batches

        save_product(
            self.conn,
            self.project_id,
            {
                "unit_code": "LK-D-01",
                "zone": "Liền kề D",
                "product_line": "lien_ke",
                "status": "available",
                "price_batch": "Dot2-2026",
            },
            ts=TS,
        )
        self.conn.commit()
        batches = list_price_batches(self.conn, self.project_id)
        self.assertIn("Dot2-2026", batches)
        found = search_available_products(self.conn, self.project_id, price_batch="Dot2-2026")
        self.assertEqual(len(found), 1)
        summary = inventory_by_price_batch_summary(self.conn, self.project_id)
        dot2 = next((x for x in summary if x.get("key") == "Dot2-2026"), None)
        self.assertIsNotNone(dot2)
        assert dot2 is not None
        self.assertEqual(dot2["total"], 1)


if __name__ == "__main__":
    unittest.main()
