"""Tests — nghiệp vụ Facebook Lead → tối ưu → chấm điểm → phân hạng → phân công."""
from __future__ import annotations

import json
import sqlite3
import unittest
import unittest.mock

from crm_facebook_config import matches_facebook_source, merge_facebook_config
from crm_facebook_leads import (
    build_facebook_lead_item,
    extract_facebook_leadgen_events,
    find_lead_by_facebook_leadgen_id,
    graph_error_is_rate_limit,
    graph_row_to_lead_item,
    is_graph_rate_limited,
    normalize_facebook_field_data,
    optimize_facebook_lead_item,
    process_facebook_lead_item,
    process_facebook_webhook_payload,
    record_graph_rate_limit,
    _since_to_unix,
    _summarize_facebook_webhook_results,
)
from crm_lead_auto_assign import config_with_only
from crm_lead_rules import save_lead_config
from crm_lead_store import ensure_lead_schema
from crm_re_projects import ensure_re_projects_schema

TS = "2026-06-05 12:00:00"

FB_CFG = {
    "enabled": True,
    "page_id": "page_123",
    "form_ids": ["form_abc"],
    "auto_optimize": True,
    "auto_assign": True,
    "webhook_enabled": True,
}


class FacebookLeadsTestBase(unittest.TestCase):
    def setUp(self) -> None:
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

    def tearDown(self) -> None:
        self.conn.close()


class TestFacebookFieldMapping(FacebookLeadsTestBase):
    def test_normalize_vietnamese_fields(self) -> None:
        fields = normalize_facebook_field_data(
            [
                {"name": "ho_ten", "values": ["Nguyen Van A"]},
                {"name": "so_dien_thoai", "values": ["0901234567"]},
                {"name": "email", "values": ["a@test.com"]},
                {"name": "khu_vuc", "values": ["Quận 7"]},
                {"name": "san_pham", "values": ["căn hộ"]},
            ]
        )
        self.assertEqual(fields["full_name"], "Nguyen Van A")
        self.assertEqual(fields["phone"], "0901234567")
        self.assertEqual(fields["region"], "Quận 7")

    def test_optimize_normalizes_phone_and_region(self) -> None:
        item = optimize_facebook_lead_item(
            build_facebook_lead_item(
                full_name="tran van b",
                phone="+84901234567",
                region="Quận 7",
                product_interest="căn hộ",
                need="",
            )
        )
        self.assertEqual(item["phone"], "0901234567")
        self.assertEqual(item["region"], "q.7")
        self.assertIn("căn hộ", item["need"].lower())


class TestFacebookSourceFilter(FacebookLeadsTestBase):
    def test_matches_configured_form(self) -> None:
        item = build_facebook_lead_item(
            full_name="X",
            phone="0901112222",
            form_id="form_abc",
            page_id="page_123",
        )
        ok, _ = matches_facebook_source(item, merge_facebook_config(FB_CFG))
        self.assertTrue(ok)

    def test_rejects_wrong_form(self) -> None:
        item = build_facebook_lead_item(
            full_name="X",
            phone="0901112222",
            form_id="form_other",
            page_id="page_123",
        )
        ok, msg = matches_facebook_source(item, merge_facebook_config(FB_CFG))
        self.assertFalse(ok)
        self.assertIn("Form", msg)
        self.assertIn("cấu hình CRM", msg)

    def test_webhook_summary_human_readable(self) -> None:
        msg = _summarize_facebook_webhook_results(
            [],
            created=[],
            skipped=[
                {
                    "status": "filtered_out",
                    "message": "Form 2814926042203269 chưa được thêm trong cấu hình CRM.",
                    "facebook_form_id": "2814926042203269",
                }
            ],
        )
        self.assertIn("Không có lead Facebook mới", msg)
        self.assertNotIn("filtered_out", msg)
        self.assertIn("2814926042203269", msg)
        self.assertIn("Facebook Lead", msg)


class TestFacebookPipeline(FacebookLeadsTestBase):
    def test_process_lead_scores_tiers_and_assigns(self) -> None:
        item = build_facebook_lead_item(
            full_name="FB Lead Test",
            phone="0908887776",
            email="fb@test.com",
            need="Hỏi giá căn hộ q.7",
            product_interest="căn hộ",
            region="q.7",
            leadgen_id="fb_lead_001",
            form_id="form_abc",
            page_id="page_123",
        )
        result = process_facebook_lead_item(
            self.conn, item, created_by="test:facebook", ts=TS
        )
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
            leadgen_id="fb_dup_99",
            form_id="form_abc",
            page_id="page_123",
        )
        r1 = process_facebook_lead_item(self.conn, item, created_by="t", ts=TS)
        r2 = process_facebook_lead_item(self.conn, item, created_by="t", ts=TS)
        self.assertEqual(r1["status"], "created_assigned")
        self.assertEqual(r2["status"], "duplicate_seen")
        self.assertTrue(r2.get("repeat_webhook"))
        self.assertEqual(find_lead_by_facebook_leadgen_id(self.conn, "fb_dup_99"), r1["lead_id"])

    def test_webhook_payload_when_enabled(self) -> None:
        payload = {
            "full_name": "Webhook FB",
            "phone": "0905556667",
            "email": "wh@example.com",
            "region": "q.2",
            "need": "Tư vấn nhà phố",
            "meta": {"facebook_leadgen_id": "wh_001", "facebook_form_id": "form_abc", "facebook_page_id": "page_123"},
        }
        batch = process_facebook_webhook_payload(
            self.conn, payload, created_by="webhook:facebook", ts=TS
        )
        self.assertEqual(batch["created_count"], 1)
        self.assertEqual(batch["results"][0]["status"], "created_assigned")

    def test_webhook_disabled_when_facebook_off(self) -> None:
        save_lead_config(
            self.conn,
            config={"facebook_config": {"enabled": False}},
            updated_by="test",
            ts=TS,
        )
        batch = process_facebook_webhook_payload(
            self.conn,
            {"full_name": "X", "phone": "0909998888"},
            created_by="webhook:facebook",
            ts=TS,
        )
        self.assertEqual(batch["created_count"], 0)
        self.assertIn("chưa bật", batch.get("message", "").lower())

    def test_skip_without_contact(self) -> None:
        item = build_facebook_lead_item(
            full_name="No Contact",
            leadgen_id="nc_1",
            form_id="form_abc",
            page_id="page_123",
        )
        result = process_facebook_lead_item(self.conn, item, created_by="t", ts=TS)
        self.assertIn(result["status"], ("created_assigned", "created_unassigned"))
        row = self.conn.execute(
            "SELECT meta_json FROM crm_leads WHERE id = ?",
            (int(result["lead_id"]),),
        ).fetchone()
        meta = json.loads(row["meta_json"])
        self.assertTrue(meta.get("awaiting_facebook_graph"))

    def test_enrich_facebook_placeholder(self) -> None:
        item = build_facebook_lead_item(
            full_name="No Contact",
            leadgen_id="nc_enrich",
            form_id="form_abc",
            page_id="page_123",
        )
        first = process_facebook_lead_item(self.conn, item, created_by="t", ts=TS)
        self.assertIn(first["status"], ("created_assigned", "created_unassigned"))
        second_item = build_facebook_lead_item(
            full_name="Real Name",
            phone="0901234567",
            leadgen_id="nc_enrich",
            form_id="form_abc",
            page_id="page_123",
        )
        second = process_facebook_lead_item(self.conn, second_item, created_by="t2", ts=TS)
        self.assertIn(second["status"], ("created_assigned", "created_unassigned", "enriched"))
        self.assertEqual(int(second["lead_id"]), int(first["lead_id"]))
        self.assertEqual(second["phone"], "0901234567")

    def test_since_to_unix(self) -> None:
        self.assertEqual(_since_to_unix(""), 0)
        self.assertEqual(_since_to_unix("1717500000"), 1717500000)
        ts = _since_to_unix("2026-06-08 17:51:41")
        self.assertGreater(ts, 1700000000)

    def test_extract_leadgen_webhook_events(self) -> None:
        payload = {
            "object": "page",
            "entry": [
                {
                    "id": "page_123",
                    "changes": [
                        {
                            "field": "leadgen",
                            "value": {
                                "leadgen_id": "lg_999",
                                "page_id": "page_123",
                                "form_id": "form_abc",
                            },
                        }
                    ],
                }
            ],
        }
        events = extract_facebook_leadgen_events(payload)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["leadgen_id"], "lg_999")
        self.assertEqual(events[0]["form_id"], "form_abc")

    def test_default_auto_sync_enabled(self) -> None:
        cfg = merge_facebook_config({"enabled": True, "page_id": "p1"})
        self.assertTrue(cfg["auto_sync"])
        self.assertEqual(cfg["sync_interval_minutes"], 5)

    def test_graph_rate_limit_detection(self) -> None:
        err = {
            "_graph_error": "(#80005) There have been too many leadgen api calls",
            "_graph_error_code": 80005,
        }
        self.assertTrue(graph_error_is_rate_limit(err))
        self.assertFalse(graph_error_is_rate_limit({"_graph_error": "Invalid token", "_graph_error_code": 190}))

    def test_graph_row_to_lead_item(self) -> None:
        row = {
            "id": "lg_1",
            "created_time": "2026-01-01T00:00:00+0000",
            "field_data": [{"name": "phone_number", "values": ["0901234567"]}],
            "form_id": "form_abc",
        }
        item = graph_row_to_lead_item(row, page_id="page_123", form_id="form_abc")
        self.assertEqual(item["phone"], "0901234567")
        self.assertEqual(item["meta"]["facebook_leadgen_id"], "lg_1")

    def test_record_graph_rate_limit(self) -> None:
        record_graph_rate_limit(self.conn, "rate limit test", minutes=15, updated_by="test")
        limited, msg = is_graph_rate_limited(self.conn)
        self.assertTrue(limited)
        self.assertTrue(msg)

    def test_webhook_accepts_leadgen_outside_configured_form(self) -> None:
        """Webhook Meta đã subscribe — không lọc form/page khi ingest realtime."""
        payload = {
            "object": "page",
            "entry": [
                {
                    "id": "page_999",
                    "time": 1,
                    "changes": [
                        {
                            "field": "leadgen",
                            "value": {
                                "leadgen_id": "lg_other_form",
                                "form_id": "form_OTHER",
                                "page_id": "page_999",
                            },
                        }
                    ],
                }
            ],
        }
        with unittest.mock.patch(
            "crm_facebook_leads.fetch_facebook_lead_from_graph_with_retry",
            return_value={
                "full_name": "FB Webhook",
                "phone": "0908887776",
                "email": "",
                "meta": {},
            },
        ):
            result = process_facebook_webhook_payload(
                self.conn, payload, created_by="webhook:test", ts=TS
            )
        self.assertEqual(int(result.get("created_count") or 0), 1)
        lid = find_lead_by_facebook_leadgen_id(self.conn, "lg_other_form")
        self.assertIsNotNone(lid)


class FacebookWebhookRouteTest(unittest.TestCase):
    def test_webhook_post_with_leadgen_payload_returns_200(self) -> None:
        try:
            import openpyxl  # noqa: F401
        except ImportError:
            self.skipTest("openpyxl chưa cài — bỏ qua test route Flask")
        from app import app

        client = app.test_client()
        body = (
            b'{"object":"page","entry":[{"id":"1","time":1,'
            b'"changes":[{"field":"leadgen","value":{"leadgen_id":"123"}}]}]}'
        )
        resp = client.post(
            "/api/crm/integration/webhooks/facebook",
            data=body,
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"EVENT_RECEIVED", resp.data)


if __name__ == "__main__":
    unittest.main()
