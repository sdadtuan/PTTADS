"""P3 — Gỡ RE khỏi funnel lead (ingest / assign / migration)."""
from __future__ import annotations

import sqlite3
import unittest

from crm_lead_auto_assign import LeadAssignContext, auto_assign_lead_owner
from crm_lead_product_model_p3 import (
    clear_re_columns_on_leads,
    ensure_p3_schema,
    resolve_facebook_industry_slug,
)
from crm_lead_store import create_lead, ensure_lead_schema, lead_row_to_dict
from crm_re_projects import ensure_re_projects_schema

TS = "2026-06-01 10:00:00"


class CrmP3Test(unittest.TestCase):
    def setUp(self) -> None:
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        ensure_re_projects_schema(self.conn)
        ensure_lead_schema(self.conn)
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS crm_staff (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                active INTEGER NOT NULL DEFAULT 1,
                internal_code TEXT NOT NULL DEFAULT '',
                sales_level TEXT NOT NULL DEFAULT '',
                notes TEXT NOT NULL DEFAULT ''
            );
            INSERT INTO crm_staff (id, name) VALUES (1, 'AM A'), (2, 'AM B');
            """
        )
        from crm_lead_catalog import ensure_lead_catalog_schema
        from crm_lead_assign_scope import ensure_staff_assign_scope_schema

        ensure_lead_catalog_schema(self.conn)
        ensure_staff_assign_scope_schema(self.conn)
        self.conn.execute(
            """
            INSERT INTO crm_staff_assign_scope
                (staff_id, industry_slug, service_slug, active, created_at, updated_at)
            VALUES (1, 'spa', 'quang-cao-facebook', 1, ?, ?)
            """,
            (TS, TS),
        )
        self.conn.commit()

    def test_p3_migration_clears_re_columns(self) -> None:
        row, _, _ = create_lead(
            self.conn,
            full_name="Legacy RE",
            phone="0901000100",
            source="manual",
            industry_slug="bds",
            auto_assign=False,
            ts=TS,
        )
        self.conn.execute(
            """
            UPDATE crm_leads
            SET re_project_id = 9, product_line = 'can_ho', zone = 'Q1'
            WHERE id = ?
            """,
            (int(row["id"]),),
        )
        self.conn.commit()
        stats = ensure_p3_schema(self.conn)
        self.conn.commit()
        self.assertIn("skipped", stats)
        self.assertFalse(stats.get("skipped"))
        cleared = self.conn.execute(
            "SELECT re_project_id, product_line, zone FROM crm_leads WHERE id = ?",
            (int(row["id"]),),
        ).fetchone()
        self.assertIsNone(cleared["re_project_id"])
        self.assertEqual(str(cleared["product_line"] or ""), "")
        self.assertEqual(str(cleared["zone"] or ""), "")

    def test_auto_assign_ignores_re_project(self) -> None:
        ensure_p3_schema(self.conn)
        self.conn.commit()
        ctx = LeadAssignContext(
            lead_level="warm",
            lead_score=50,
            industry_slug="spa",
            product_interest="quang-cao-facebook",
            re_project_id=999,
        )
        sid, _name, strategy = auto_assign_lead_owner(self.conn, ctx)
        self.assertEqual(sid, 1)
        self.assertNotEqual(strategy, "no_project_staff")

    def test_facebook_industry_default_khac(self) -> None:
        ensure_p3_schema(self.conn)
        slug = resolve_facebook_industry_slug(self.conn, {"full_name": "FB"})
        self.assertEqual(slug, "khac")

    def test_create_lead_without_re_project(self) -> None:
        ensure_p3_schema(self.conn)
        row, _, _ = create_lead(
            self.conn,
            full_name="No RE",
            phone="0901000101",
            source="manual",
            industry_slug="spa",
            auto_assign=False,
            ts=TS,
        )
        out = lead_row_to_dict(row, self.conn)
        self.assertIsNone(out.get("re_project_id"))
        self.assertEqual(out.get("industry_slug"), "spa")


if __name__ == "__main__":
    unittest.main()
