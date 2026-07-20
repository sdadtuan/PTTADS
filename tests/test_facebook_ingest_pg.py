"""Tests — Facebook lead ingest on PostgreSQL-primary path."""
from __future__ import annotations

import json
import sqlite3
import unittest
from typing import Any
from unittest.mock import patch

from crm_facebook_config import merge_facebook_config
from crm_facebook_leads import build_facebook_lead_item
from crm_lead_auto_assign import config_with_only
from crm_lead_rules import save_lead_config
from crm_lead_store import ensure_lead_schema
from crm_re_projects import ensure_re_projects_schema
from ptt_crm.facebook_ingest_pg import process_facebook_lead_item_pg

TS = "2026-06-05 12:00:00"

FB_CFG = {
    "enabled": True,
    "page_id": "page_123",
    "form_ids": ["form_abc"],
    "auto_optimize": True,
    "auto_assign": True,
    "webhook_enabled": True,
}


class FakePgStore:
    def __init__(self) -> None:
        self.leads: dict[int, dict[str, Any]] = {}
        self.next_id = 880_001_000

    def next_lead_id(self, _cur=None) -> int:
        lead_id = self.next_id
        self.next_id += 1
        return lead_id

    def insert(self, record: dict[str, Any]) -> None:
        lid = int(record["sqlite_lead_id"])
        meta = record.get("meta_json")
        if isinstance(meta, str):
            meta_obj = json.loads(meta)
        else:
            meta_obj = dict(meta or {})
        self.leads[lid] = {
            **record,
            "meta_json": meta_obj,
            "is_duplicate": bool(record.get("is_duplicate")),
        }

    def fetch(self, lead_id: int) -> dict[str, Any] | None:
        row = self.leads.get(int(lead_id))
        if row is None:
            return None
        out = dict(row)
        out["meta_json"] = dict(row.get("meta_json") or {})
        return out

    def find_external(
        self,
        *,
        agency_client_id: str | None,
        channel: str,
        external_lead_id: str,
    ) -> int | None:
        ch = channel.strip().lower()
        for lid, row in sorted(self.leads.items(), reverse=True):
            if row.get("external_lead_id") != external_lead_id:
                continue
            if row.get("is_duplicate"):
                continue
            if ch and str(row.get("channel") or "").lower() != ch:
                continue
            if agency_client_id and str(row.get("agency_client_id") or "") != agency_client_id:
                continue
            return lid
        return None

    def find_contacts(self, *, phone: str = "", email: str = "", exclude_id: int | None = None) -> list[dict[str, Any]]:
        from crm_lead_store import normalize_email, normalize_phone

        ph = normalize_phone(phone)
        em = normalize_email(email)
        out: list[dict[str, Any]] = []
        for lid, row in sorted(self.leads.items()):
            if exclude_id and lid == exclude_id:
                continue
            if row.get("is_duplicate"):
                continue
            row_ph = normalize_phone(str(row.get("phone") or ""))
            row_em = normalize_email(str(row.get("email") or ""))
            if (ph and row_ph == ph) or (em and row_em == em):
                out.append({"lead_id": lid, "sqlite_lead_id": lid, **row})
        return out

    def update(self, lead_id: int, **fields: Any) -> None:
        row = self.leads.get(int(lead_id))
        if row is None:
            return
        if "meta_json" in fields and isinstance(fields["meta_json"], dict):
            row["meta_json"] = dict(fields.pop("meta_json"))
        row.update(fields)


class FacebookPgIngestTestBase(unittest.TestCase):
    def setUp(self) -> None:
        self.pg = FakePgStore()
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        ensure_re_projects_schema(self.conn)
        ensure_lead_schema(self.conn)
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS crm_staff (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                notes TEXT NOT NULL DEFAULT '',
                active INTEGER NOT NULL DEFAULT 1,
                sales_level TEXT NOT NULL DEFAULT 'b',
                internal_code TEXT NOT NULL DEFAULT ''
            )
            """
        )
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS crm_assignment_state (
                pool_key TEXT PRIMARY KEY,
                last_staff_id INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        cur = self.conn.execute(
            "INSERT INTO crm_staff (name, notes, active, sales_level) VALUES (?, ?, 1, ?)",
            ("NV Facebook B", "q.7 căn hộ facebook", "b"),
        )
        self.staff_id = int(cur.lastrowid)
        save_lead_config(
            self.conn,
            config={
                "assign_config": config_with_only("skill_based", "round_robin"),
                "facebook_config": FB_CFG,
            },
            updated_by="test",
            ts=TS,
        )
        self.conn.commit()

        patchers = [
            patch("ptt_crm.facebook_ingest_pg.next_prod_lead_id", side_effect=self.pg.next_lead_id),
            patch("ptt_crm.facebook_ingest_pg.insert_pg_lead_record", side_effect=self.pg.insert),
            patch("ptt_crm.facebook_ingest_pg.fetch_pg_lead_by_id", side_effect=self.pg.fetch),
            patch("ptt_crm.facebook_ingest_pg.find_pg_lead_by_external", side_effect=self.pg.find_external),
            patch("ptt_crm.facebook_ingest_pg.find_pg_contact_duplicates", side_effect=self.pg.find_contacts),
            patch("ptt_crm.facebook_ingest_pg.update_pg_lead_fields", side_effect=self.pg.update),
            patch("ptt_crm.facebook_ingest_pg.pg_connection", side_effect=self._fake_pg_connection),
        ]
        self._patchers = patchers
        for p in patchers:
            p.start()
        self.addCleanup(lambda: [p.stop() for p in self._patchers])

    @staticmethod
    def _fake_pg_connection():
        class _Ctx:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def cursor(self):
                class _Cur:
                    def __enter__(self):
                        return self

                    def __exit__(self, *_a):
                        return False

                return _Cur()

            def commit(self):
                return None

        return _Ctx()

    def tearDown(self) -> None:
        self.conn.close()

    def _process(self, item: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        return process_facebook_lead_item_pg(
            item,
            channel=kwargs.pop("channel", "meta"),
            client_id=kwargs.pop("client_id", None),
            created_by=kwargs.pop("created_by", "test:facebook"),
            ts=kwargs.pop("ts", TS),
            config_conn=self.conn,
            fb_cfg=merge_facebook_config(FB_CFG),
            **kwargs,
        )


class TestFacebookPgPipeline(FacebookPgIngestTestBase):
    def test_process_lead_scores_tiers_and_assigns(self) -> None:
        item = build_facebook_lead_item(
            full_name="FB Lead Test",
            phone="0908887776",
            email="fb@test.com",
            need="Hỏi giá căn hộ q.7",
            product_interest="căn hộ",
            region="q.7",
            leadgen_id="fb_pg_001",
            form_id="form_abc",
            page_id="page_123",
        )
        result = self._process(item)
        self.assertEqual(result["status"], "created_assigned")
        self.assertIsNotNone(result.get("lead_id"))
        self.assertGreater(result.get("lead_score", 0), 0)
        self.assertTrue(result.get("lead_level"))
        self.assertEqual(result.get("owner_id"), self.staff_id)
        self.assertEqual(result.get("source"), "facebook")
        self.assertTrue(result.get("optimized"))

    def test_duplicate_leadgen_skipped(self) -> None:
        item = build_facebook_lead_item(
            full_name="FB Dup",
            phone="0901112223",
            leadgen_id="fb_pg_dup_99",
            form_id="form_abc",
            page_id="page_123",
        )
        r1 = self._process(item)
        r2 = self._process(item)
        self.assertEqual(r1["status"], "created_assigned")
        self.assertEqual(r2["status"], "duplicate_seen")
        self.assertTrue(r2.get("repeat_webhook"))
        self.assertEqual(self.pg.find_external(channel="meta", external_lead_id="fb_pg_dup_99", agency_client_id=None), r1["lead_id"])

    def test_filtered_out_wrong_form(self) -> None:
        item = build_facebook_lead_item(
            full_name="X",
            phone="0901112222",
            form_id="form_other",
            page_id="page_123",
        )
        result = self._process(item)
        self.assertEqual(result["status"], "filtered_out")
        self.assertIn("Form", result.get("message", ""))

    def test_placeholder_then_enrich(self) -> None:
        item = build_facebook_lead_item(
            full_name="No Contact",
            leadgen_id="nc_pg_enrich",
            form_id="form_abc",
            page_id="page_123",
        )
        first = self._process(item)
        self.assertIn(first["status"], ("created_assigned", "created_unassigned"))
        row = self.pg.fetch(int(first["lead_id"]))
        assert row is not None
        self.assertTrue(row["meta_json"].get("awaiting_facebook_graph"))

        second_item = build_facebook_lead_item(
            full_name="Real Name",
            phone="0901234567",
            leadgen_id="nc_pg_enrich",
            form_id="form_abc",
            page_id="page_123",
        )
        second = self._process(second_item)
        self.assertIn(second["status"], ("created_assigned", "created_unassigned", "enriched"))
        self.assertEqual(int(second["lead_id"]), int(first["lead_id"]))
        self.assertEqual(second["phone"], "0901234567")

    def test_skip_without_contact_and_no_leadgen(self) -> None:
        item = build_facebook_lead_item(
            full_name="No Contact",
            form_id="form_abc",
            page_id="page_123",
        )
        item["meta"] = dict(item.get("meta") or {})
        item["meta"].pop("facebook_leadgen_id", None)
        result = self._process(item)
        self.assertEqual(result["status"], "skipped")


class TestFacebookPgWebhookBatch(unittest.TestCase):
    @patch("ptt_crm.facebook_ingest_pg.process_facebook_lead_item_pg")
    def test_ingest_webhook_routes_facebook(self, mock_process) -> None:
        from ptt_crm.lead_ingest_pg import ingest_webhook_leads_pg

        mock_process.return_value = {"status": "created_assigned", "lead_id": 880_001_001}
        out = ingest_webhook_leads_pg(
            [{"full_name": "A", "phone": "0901", "meta": {"facebook_leadgen_id": "x"}}],
            channel="meta",
            client_id=None,
            default_source="facebook",
            created_by="worker",
            ts=TS,
        )
        self.assertEqual(out["created_count"], 1)
        mock_process.assert_called_once()


if __name__ == "__main__":
    unittest.main()
