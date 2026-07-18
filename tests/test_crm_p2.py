"""P2 — Admin add-on pack, TMMT @ Deliver workflow, ngành bắt buộc."""
from __future__ import annotations

import json
import sqlite3
import unittest

from crm_lead_catalog import (
    ensure_lead_catalog_schema,
    normalize_industry_traits,
    update_catalog_industry,
)
from crm_lead_presales_marketing_plan import (
    ensure_r5_schema,
    official_plan_payload,
    update_official_plan,
    validate_lifecycle_deliver_advance,
)
from crm_lead_store import create_lead, ensure_lead_schema
from crm_re_projects import ensure_re_projects_schema

TS = "2026-06-01 10:00:00"


class CrmP2Test(unittest.TestCase):
    def setUp(self) -> None:
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        ensure_re_projects_schema(self.conn)
        ensure_lead_schema(self.conn)
        ensure_lead_catalog_schema(self.conn)
        ensure_r5_schema(self.conn)
        self.conn.executescript(
            f"""
            CREATE TABLE IF NOT EXISTS crm_staff (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                active INTEGER NOT NULL DEFAULT 1,
                internal_code TEXT NOT NULL DEFAULT ''
            );
            INSERT INTO crm_staff (id, name) VALUES (1, 'AM');
            CREATE TABLE IF NOT EXISTS crm_service_lifecycle (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lead_id INTEGER,
                customer_id INTEGER,
                service_slug TEXT NOT NULL DEFAULT '',
                stage TEXT NOT NULL DEFAULT 'onboard',
                marketing_plan_id INTEGER,
                created_at TEXT NOT NULL DEFAULT '',
                updated_at TEXT NOT NULL DEFAULT ''
            );
            INSERT INTO crm_service_lifecycle (id, stage, service_slug, created_at, updated_at)
            VALUES (1, 'onboard', 'quang-cao-facebook', '{TS}', '{TS}');
            """
        )
        self.conn.execute(
            """
            INSERT INTO crm_marketing_plans (
                id, name, plan_kind, lifecycle_id, strategy_framework_json,
                target_market_prof_json, created_at, updated_at
            ) VALUES (1, 'KH chính thức', 'official', 1, '{}', '{}', ?, ?)
            """,
            (TS, TS),
        )
        self.conn.execute(
            "UPDATE crm_service_lifecycle SET marketing_plan_id = 1 WHERE id = 1"
        )
        self.conn.commit()

    def test_normalize_industry_traits_validates_select(self) -> None:
        traits = normalize_industry_traits(
            {
                "addon_key": "demo",
                "addon_label": "Demo",
                "fields": [
                    {
                        "key": "loai",
                        "label": "Loại",
                        "type": "select",
                        "options": [{"value": "a", "label": "A"}],
                    }
                ],
            }
        )
        self.assertEqual(traits["addon_key"], "demo")
        self.assertEqual(len(traits["fields"]), 1)
        with self.assertRaises(ValueError):
            normalize_industry_traits({"fields": [{"key": "x", "type": "select"}]})

    def test_update_catalog_industry_traits_persisted(self) -> None:
        from crm_lead_catalog import list_catalog_industries

        ind = list_catalog_industries(self.conn)[0]
        updated = update_catalog_industry(
            self.conn,
            ind["id"],
            traits={
                "addon_key": "spa",
                "addon_label": "Add-on Spa test",
                "fields": [{"key": "vi_tri", "label": "Vị trí", "type": "text"}],
            },
        )
        self.assertEqual(updated["traits"]["addon_key"], "spa")
        row = self.conn.execute(
            "SELECT traits_json FROM crm_catalog_industries WHERE id = ?",
            (ind["id"],),
        ).fetchone()
        stored = json.loads(row["traits_json"])
        self.assertEqual(stored["fields"][0]["key"], "vi_tri")

    def test_official_tmmt_gate_and_update(self) -> None:
        blocked = validate_lifecycle_deliver_advance(self.conn, 1)
        self.assertFalse(blocked["ok"])
        update_official_plan(
            self.conn,
            1,
            {
                "strategy_framework": {"target_market": "TMMT tóm tắt P2"},
                "target_market_prof": {
                    "market_context": "ctx",
                    "segmentation_icp": "icp",
                    "personas_roles": "persona",
                    "pains_desired_outcomes": "pain",
                    "tam_sam_som": "tam",
                    "geo_behavior": "geo",
                },
            },
        )
        payload = official_plan_payload(self.conn, 1)
        self.assertTrue(payload["validation"]["complete"])
        ok = validate_lifecycle_deliver_advance(self.conn, 1)
        self.assertTrue(ok["ok"])

    def test_create_lead_without_industry_allowed_at_store(self) -> None:
        """API POST /api/crm/leads bắt buộc ngành; store vẫn cho ingest mặc định."""
        row, _, _ = create_lead(
            self.conn,
            full_name="Ingest",
            phone="0901000099",
            source="facebook",
            industry_slug="",
            auto_assign=False,
            ts=TS,
        )
        self.assertEqual(str(row["industry_slug"] or ""), "")


if __name__ == "__main__":
    unittest.main()
