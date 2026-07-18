"""Tests: danh mục Dịch vụ + Ngành (R3)."""
from __future__ import annotations

import sqlite3
import unittest

from crm_lead_catalog import (
    catalog_public_payload,
    create_catalog_industry,
    create_catalog_service,
    ensure_lead_catalog_schema,
    list_catalog_industries,
    list_catalog_services,
    normalize_product_interest,
    update_catalog_service,
    validate_service_slug,
)
from crm_lead_presales import ensure_presales, ensure_schema as ensure_presales_schema
from crm_lead_store import create_lead, ensure_lead_schema, lead_row_to_dict
from crm_re_projects import ensure_re_projects_schema


TS = "2026-06-01 10:00:00"


class LeadCatalogTest(unittest.TestCase):
    def setUp(self) -> None:
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        ensure_re_projects_schema(self.conn)
        ensure_lead_schema(self.conn)
        ensure_presales_schema(self.conn)
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS crm_staff (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                active INTEGER NOT NULL DEFAULT 1,
                internal_code TEXT NOT NULL DEFAULT '',
                department_id INTEGER,
                notes TEXT NOT NULL DEFAULT '',
                sales_level TEXT NOT NULL DEFAULT ''
            );
            INSERT INTO crm_staff (id, name) VALUES (1, 'AM');
            """
        )

    def test_bootstrap_seeds_default_services_and_industries(self) -> None:
        services = list_catalog_services(self.conn)
        industries = list_catalog_industries(self.conn)
        self.assertGreaterEqual(len(services), 10)
        self.assertGreaterEqual(len(industries), 5)
        slugs = {s["slug"] for s in services}
        self.assertIn("dich-vu-seo-local", slugs)
        self.assertIn("quang-cao-facebook", slugs)

    def test_create_and_deactivate_service(self) -> None:
        row = create_catalog_service(
            self.conn,
            slug="test-custom-svc",
            name="Dịch vụ test",
            sort_order=999,
        )
        self.assertEqual(row["slug"], "test-custom-svc")
        self.assertTrue(row["active"])
        updated = update_catalog_service(self.conn, row["id"], active=False)
        self.assertFalse(updated["active"])
        with self.assertRaises(ValueError):
            validate_service_slug(self.conn, "test-custom-svc")

    def test_create_industry(self) -> None:
        row = create_catalog_industry(
            self.conn,
            slug="y-te",
            name="Y tế",
            description="Bệnh viện, phòng khám",
        )
        self.assertEqual(row["slug"], "y-te")
        payload = catalog_public_payload(self.conn)
        self.assertIn("y-te", payload["industry_slugs"])

    def test_lead_stores_industry_and_service_slug(self) -> None:
        row, _, _ = create_lead(
            self.conn,
            full_name="Khách catalog",
            phone="0901000001",
            source="manual",
            product_interest="dich-vu-seo-local",
            industry_slug="spa",
            auto_assign=False,
            ts=TS,
        )
        out = lead_row_to_dict(row, self.conn)
        self.assertEqual(out["product_interest"], "dich-vu-seo-local")
        self.assertEqual(out["industry_slug"], "spa")
        self.assertIn("SEO", out["product_interest_label"])

    def test_presales_rejects_inactive_service(self) -> None:
        svc = create_catalog_service(
            self.conn,
            slug="inactive-svc",
            name="DV tắt",
        )
        update_catalog_service(self.conn, svc["id"], active=False)
        row, _, _ = create_lead(
            self.conn,
            full_name="Lead presales",
            phone="0901000002",
            source="manual",
            owner_id=1,
            auto_assign=False,
            ts=TS,
        )
        lead_id = int(row["id"])
        self.conn.execute(
            """
            UPDATE crm_leads
            SET care_stage_current = 'first_contact',
                care_stages_done_json = ?
            WHERE id = ?
            """,
            ('{"first_contact": true}', lead_id),
        )
        with self.assertRaises(ValueError):
            ensure_presales(self.conn, lead_id, "inactive-svc")

    def test_legacy_free_text_product_interest_allowed(self) -> None:
        value = normalize_product_interest(self.conn, "Facebook Ads tùy chỉnh")
        self.assertEqual(value, "Facebook Ads tùy chỉnh")


if __name__ == "__main__":
    unittest.main()
