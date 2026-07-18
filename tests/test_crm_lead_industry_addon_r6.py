"""R6 — Add-on ngành; gỡ BĐS legacy trên lead."""
from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path


class LeadIndustryAddonR6Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "test.db"
        conn = sqlite3.connect(self.db)
        conn.row_factory = sqlite3.Row
        conn.executescript(
            """
            CREATE TABLE crm_leads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                full_name TEXT,
                phone TEXT,
                phone_norm TEXT,
                email TEXT,
                email_norm TEXT,
                source TEXT,
                region TEXT,
                product_interest TEXT,
                industry_slug TEXT DEFAULT '',
                need TEXT,
                lead_score INTEGER DEFAULT 0,
                lead_level TEXT DEFAULT 'cold',
                status TEXT DEFAULT 'new',
                owner_id INTEGER,
                re_project_id INTEGER,
                product_line TEXT DEFAULT '',
                zone TEXT DEFAULT '',
                re_product_id INTEGER,
                duplicate_of_id INTEGER,
                is_duplicate INTEGER DEFAULT 0,
                utm_campaign TEXT DEFAULT '',
                meta_json TEXT DEFAULT '{}',
                status_entered_at TEXT,
                created_at TEXT,
                updated_at TEXT,
                created_by TEXT,
                updated_by TEXT,
                care_stage_current TEXT DEFAULT 'first_contact',
                care_stages_done_json TEXT DEFAULT '{}'
            );
            CREATE TABLE crm_staff (
                id INTEGER PRIMARY KEY,
                name TEXT,
                active INTEGER DEFAULT 1,
                internal_code TEXT DEFAULT '',
                department_id INTEGER,
                notes TEXT DEFAULT '',
                sales_level TEXT DEFAULT ''
            );
            INSERT INTO crm_staff (id, name) VALUES (1, 'AM');
            """
        )
        from crm_lead_catalog import ensure_lead_catalog_schema
        from crm_lead_rules import ensure_lead_settings_schema
        from crm_lead_store import ensure_lead_schema
        from crm_re_projects import ensure_re_projects_schema

        ensure_re_projects_schema(conn)
        conn.execute(
            """
            INSERT INTO crm_re_projects (id, code, name, created_at, updated_at)
            VALUES (5, 'DA-A', 'Dự án Legacy', '2026-01-01', '2026-01-01')
            """
        )
        ensure_lead_schema(conn)
        ensure_lead_catalog_schema(conn)
        ensure_lead_settings_schema(conn)
        conn.commit()
        conn.close()

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db)
        conn.row_factory = sqlite3.Row
        return conn

    def test_reject_re_legacy_on_create(self) -> None:
        from crm_lead_store import create_lead, ensure_lead_schema

        with self._conn() as conn:
            with self.assertRaises(ValueError) as ctx:
                create_lead(
                    conn,
                    full_name="Legacy Lead",
                    phone="0901111222",
                    source="manual",
                    re_project_id=5,
                    auto_assign=False,
                    ts="2026-06-01 10:00:00",
                )
            self.assertIn("legacy", str(ctx.exception).lower())

    def test_bootstrap_traits_and_addon_pack(self) -> None:
        from crm_lead_industry_addon import bootstrap_industry_traits, resolve_addon_pack

        with self._conn() as conn:
            bootstrap_industry_traits(conn)
            conn.commit()
            pack = resolve_addon_pack(conn, "bds")
            self.assertIsNotNone(pack)
            assert pack is not None
            self.assertEqual(pack["addon_key"], "bds")
            keys = [f["key"] for f in pack["fields"]]
            self.assertIn("du_an", keys)
            self.assertIn("khu_vuc", keys)

    def test_update_lead_industry_addon(self) -> None:
        from crm_lead_industry_addon import (
            bootstrap_industry_traits,
            ensure_r6_schema,
            lead_industry_addon_payload,
            update_lead_industry_addon,
        )
        from crm_lead_store import create_lead, ensure_lead_schema

        with self._conn() as conn:
            ensure_r6_schema(conn)
            bootstrap_industry_traits(conn)
            row, _, _ = create_lead(
                conn,
                full_name="BDS Lead",
                phone="0903333444",
                source="manual",
                industry_slug="bds",
                auto_assign=False,
                ts="2026-06-01 10:00:00",
            )
            lid = int(row["id"])
            update_lead_industry_addon(
                conn,
                lid,
                {
                    "data": {
                        "du_an": "Sunrise City",
                        "loai_sp": "can_ho",
                        "khu_vuc": "Q7",
                    }
                },
            )
            payload = lead_industry_addon_payload(conn, lid)
            self.assertTrue(payload["has_pack"])
            self.assertEqual(payload["data"]["du_an"], "Sunrise City")
            self.assertEqual(payload["data"]["loai_sp"], "can_ho")

    def test_migrate_re_legacy_to_industry_addon(self) -> None:
        from crm_lead_industry_addon import (
            ensure_r6_schema,
            get_lead_addon_row,
            migrate_re_legacy_to_industry_addon,
        )
        from crm_lead_store import ensure_lead_schema

        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO crm_leads (
                    full_name, phone, phone_norm, email, email_norm, source,
                    re_project_id, product_line, zone, status, created_at, updated_at
                ) VALUES ('Old RE', '0909999888', '909999888', '', '', 'manual',
                    5, 'can_ho', 'Q2', 'new', '2026-01-01', '2026-01-01')
                """
            )
            conn.commit()
            summary = migrate_re_legacy_to_industry_addon(conn)
            self.assertEqual(summary["migrated"], 1)
            lead = conn.execute(
                "SELECT id, re_project_id, industry_slug FROM crm_leads WHERE phone = '0909999888'"
            ).fetchone()
            self.assertIsNone(lead["re_project_id"])
            self.assertEqual(lead["industry_slug"], "bds")
            addon = get_lead_addon_row(conn, int(lead["id"]))
            self.assertIsNotNone(addon)
            assert addon is not None
            import json

            data = json.loads(addon["data_json"])
            self.assertIn("du_an", data)
            self.assertEqual(data["khu_vuc"], "Q2")


if __name__ == "__main__":
    unittest.main()
