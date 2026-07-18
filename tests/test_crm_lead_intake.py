# tests/test_crm_lead_intake.py
"""Tests cho crm_lead_intake module."""
from __future__ import annotations

import json
import sqlite3
import unittest

from crm_lead_intake import (
    build_recap_from_session,
    complete_session,
    compute_bant_total,
    create_session,
    ensure_schema,
    fetch_lead_prefill,
    get_intake_stats,
    get_latest_completed_session,
    get_session,
    list_sessions,
    merge_to_lead_task,
    prefill_session,
    reopen_session,
    resolve_intake_entry,
    save_intake_ai_result,
    suggest_decision,
    update_session,
)
from crm_lead_intake_definitions import COMMON_FORM_SLUG, get_ui_definition
from crm_ai_qualify import map_product_interest_to_slug
from crm_svc_tasks import ensure_schema as ensure_tasks_schema, seed_tasks


def _setup_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS crm_service_lifecycle (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            service_slug TEXT NOT NULL DEFAULT '',
            customer_id INTEGER,
            lead_id INTEGER,
            stage TEXT NOT NULL DEFAULT 'lead',
            status TEXT NOT NULL DEFAULT 'active',
            stage_entered_at TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL DEFAULT ''
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS crm_leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL DEFAULT '',
            phone TEXT NOT NULL DEFAULT '',
            email TEXT NOT NULL DEFAULT '',
            source TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'new',
            need TEXT NOT NULL DEFAULT '',
            meta_json TEXT NOT NULL DEFAULT '{}',
            care_stage_current TEXT NOT NULL DEFAULT 'intake',
            care_stages_done_json TEXT NOT NULL DEFAULT '[]',
            created_at TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL DEFAULT ''
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS crm_lead_activities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lead_id INTEGER NOT NULL,
            user_id INTEGER,
            activity_type TEXT NOT NULL DEFAULT 'note',
            content TEXT NOT NULL DEFAULT '',
            result TEXT NOT NULL DEFAULT '',
            next_action TEXT NOT NULL DEFAULT '',
            next_action_at TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT '',
            created_by TEXT NOT NULL DEFAULT '',
            lead_status_at_log TEXT NOT NULL DEFAULT '',
            care_contact_type TEXT NOT NULL DEFAULT '',
            care_status TEXT NOT NULL DEFAULT '',
            care_stage_key TEXT NOT NULL DEFAULT ''
        )
    """)
    conn.execute("""
        INSERT INTO crm_leads (id, full_name, need, source, status, meta_json, created_at, updated_at)
        VALUES (10, 'Nguyễn Test', 'Cần SEO', 'facebook', 'new', '{}',
                '2026-06-23 00:00:00', '2026-06-23 00:00:00')
    """)
    conn.execute("""
        INSERT INTO crm_service_lifecycle
            (id, service_slug, lead_id, stage, status, stage_entered_at, created_at, updated_at)
        VALUES (1, 'dich-vu-seo-tong-the', 10, 'lead', 'active',
                '2026-06-23 00:00:00', '2026-06-23 00:00:00', '2026-06-23 00:00:00')
    """)
    conn.commit()
    ensure_schema(conn)
    ensure_tasks_schema(conn)
    seed_tasks(conn, lifecycle_id=1, service_slug="dich-vu-seo-tong-the")
    return conn


class TestLeadIntakeSchema(unittest.TestCase):
    def test_table_created(self):
        conn = _setup_conn()
        tables = {
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        self.assertIn("crm_lead_intake_sessions", tables)


class TestLeadIntakeCrud(unittest.TestCase):
    def test_create_and_update(self):
        conn = _setup_conn()
        sid = create_session(
            conn,
            lifecycle_id=1,
            service_slug="dich-vu-seo-tong-the",
            mode="phone",
            company_name="Cty ABC",
        )
        self.assertGreater(sid, 0)
        row = get_session(conn, sid)
        assert row is not None
        self.assertEqual(row["company_name"], "Cty ABC")
        self.assertEqual(row["status"], "draft")

        updated = update_session(
            conn,
            sid,
            {
                "contact_name": "Nguyễn A",
                "bant_json": {
                    "budget": 4,
                    "authority": 4,
                    "need": 4,
                    "timeline": 4,
                    "fit": 4,
                    "history": 4,
                },
                "answers_json": {
                    "phone": {"p0": "example.com"},
                    "crm_fields": {"domain": "example.com", "budget": "10tr"},
                },
            },
        )
        assert updated is not None
        self.assertEqual(updated["bant_total"], 24)
        self.assertEqual(updated["contact_name"], "Nguyễn A")

    def test_list_sessions(self):
        conn = _setup_conn()
        create_session(conn, lifecycle_id=1, service_slug="dich-vu-seo-tong-the")
        create_session(
            conn,
            lifecycle_id=1,
            service_slug="dich-vu-seo-tong-the",
            mode="in_person",
        )
        rows = list_sessions(conn, lifecycle_id=1)
        self.assertEqual(len(rows), 2)


class TestBantScoring(unittest.TestCase):
    def test_compute_and_suggest(self):
        total = compute_bant_total(
            {"budget": 5, "authority": 4, "need": 5, "timeline": 4, "fit": 3, "history": 3}
        )
        self.assertEqual(total, 24)
        self.assertEqual(suggest_decision(24), "go")
        self.assertEqual(suggest_decision(20), "nurture")
        self.assertEqual(suggest_decision(12), "no_go")


class TestCompleteAndMerge(unittest.TestCase):
    def test_complete_merges_lead_task(self):
        conn = _setup_conn()
        sid = create_session(
            conn,
            lifecycle_id=1,
            service_slug="dich-vu-seo-tong-the",
            mode="phone",
        )
        update_session(
            conn,
            sid,
            {
                "decision": "go",
                "bant_json": {
                    "budget": 4,
                    "authority": 4,
                    "need": 4,
                    "timeline": 4,
                    "fit": 4,
                    "history": 4,
                },
                "answers_json": {
                    "crm_fields": {
                        "domain": "test.vn",
                        "budget": "15000000",
                        "niche": "B2B SaaS",
                        "need": "Tăng organic",
                    }
                },
            },
        )
        result = complete_session(conn, sid)
        assert result is not None
        self.assertEqual(result["status"], "completed")

        task = conn.execute(
            """
            SELECT form_data, notes FROM crm_svc_tasks
            WHERE lifecycle_id = 1 AND stage = 'lead'
            ORDER BY id LIMIT 1
            """
        ).fetchone()
        form_data = json.loads(task["form_data"])
        self.assertEqual(form_data.get("domain"), "test.vn")
        self.assertEqual(form_data.get("intake_session_id"), sid)
        self.assertIn("[Intake #", task["notes"])

    def test_reopen_allows_edit(self):
        conn = _setup_conn()
        sid = create_session(
            conn, lifecycle_id=1, service_slug="dich-vu-seo-tong-the"
        )
        update_session(conn, sid, {"decision": "nurture"})
        complete_session(conn, sid)
        reopened = reopen_session(conn, sid)
        assert reopened is not None
        self.assertEqual(reopened["status"], "draft")

    def test_merge_to_lead_task_direct(self):
        conn = _setup_conn()
        sid = create_session(
            conn, lifecycle_id=1, service_slug="dich-vu-seo-tong-the"
        )
        update_session(
            conn,
            sid,
            {
                "decision": "go",
                "answers_json": {"crm_fields": {"need": "Pain point X"}},
            },
        )
        ok = merge_to_lead_task(conn, sid)
        self.assertTrue(ok)


class TestPrefillAndRecap(unittest.TestCase):
    def test_fetch_lead_prefill(self):
        conn = _setup_conn()
        data = fetch_lead_prefill(conn, 10)
        self.assertEqual(data["contact_name"], "Nguyễn Test")
        self.assertIn("need", data["answers_json"]["crm_fields"])

    def test_in_person_prefill_from_phone(self):
        conn = _setup_conn()
        phone_id = create_session(
            conn, lifecycle_id=1, service_slug="dich-vu-seo-tong-the", mode="phone"
        )
        update_session(
            conn,
            phone_id,
            {
                "decision": "go",
                "contact_name": "An",
                "bant_json": {
                    "budget": 4, "authority": 4, "need": 4,
                    "timeline": 4, "fit": 4, "history": 4,
                },
                "answers_json": {
                    "phone": {"p0": "example.com"},
                    "meta": {"pain_summary": "Traffic thấp"},
                },
            },
        )
        complete_session(conn, phone_id)
        meet_id = create_session(
            conn, lifecycle_id=1, service_slug="dich-vu-seo-tong-the", mode="in_person"
        )
        row = get_session(conn, meet_id)
        assert row is not None
        meta = row["answers_json"].get("meta") or {}
        self.assertTrue(meta.get("recap") or row["answers_json"].get("recap"))
        self.assertEqual(row["contact_name"], "An")

    def test_resolve_intake_entry(self):
        conn = _setup_conn()
        result = resolve_intake_entry(conn, lead_id=10, mode="phone")
        self.assertTrue(result["ok"])
        self.assertEqual(result["lifecycle_id"], 1)

    def test_resolve_intake_common_without_lifecycle(self):
        conn = _setup_conn()
        conn.execute("DELETE FROM crm_service_lifecycle WHERE lead_id = 10")
        conn.commit()
        result = resolve_intake_entry(conn, lead_id=10, mode="phone", form="common")
        self.assertTrue(result["ok"])
        self.assertIsNone(result.get("lifecycle_id"))
        self.assertEqual(result["service_slug"], COMMON_FORM_SLUG)
        self.assertIn("lead_id=10", result["redirect_url"])

    def test_common_ui_definition(self):
        defn = get_ui_definition(COMMON_FORM_SLUG)
        self.assertTrue(defn.get("is_common_form"))
        self.assertGreaterEqual(len(defn.get("phone_questions") or []), 10)
        self.assertGreaterEqual(len(defn.get("inperson_questions") or []), 10)

    def test_create_common_session_by_lead_only(self):
        conn = _setup_conn()
        conn.execute("DELETE FROM crm_service_lifecycle WHERE lead_id = 10")
        conn.commit()
        sid = create_session(
            conn,
            lead_id=10,
            service_slug=COMMON_FORM_SLUG,
            mode="phone",
        )
        row = get_session(conn, sid)
        assert row is not None
        self.assertEqual(row["service_slug"], COMMON_FORM_SLUG)
        self.assertEqual(row["lead_id"], 10)
        self.assertIsNone(row["lifecycle_id"])

    def test_complete_common_logs_activity(self):
        conn = _setup_conn()
        conn.execute("DELETE FROM crm_service_lifecycle WHERE lead_id = 10")
        conn.commit()
        sid = create_session(conn, lead_id=10, service_slug=COMMON_FORM_SLUG)
        update_session(conn, sid, {"decision": "nurture"})
        complete_session(conn, sid)
        count = conn.execute(
            "SELECT COUNT(*) FROM crm_lead_activities WHERE lead_id = 10"
        ).fetchone()[0]
        self.assertGreaterEqual(count, 1)

    def test_complete_logs_activity(self):
        conn = _setup_conn()
        sid = create_session(
            conn, lifecycle_id=1, service_slug="dich-vu-seo-tong-the", lead_id=10
        )
        update_session(conn, sid, {"decision": "nurture"})
        complete_session(conn, sid)
        count = conn.execute(
            "SELECT COUNT(*) FROM crm_lead_activities WHERE lead_id = 10"
        ).fetchone()[0]
        self.assertGreaterEqual(count, 1)


class TestIntakeAiAndStats(unittest.TestCase):
    def test_save_intake_ai_result(self):
        conn = _setup_conn()
        sid = create_session(
            conn, lifecycle_id=1, service_slug="dich-vu-seo-tong-the"
        )
        updated = save_intake_ai_result(
            conn,
            sid,
            {
                "summary": "Khách cần SEO tổng thể, ngân sách 15tr/tháng.",
                "risks": ["Chưa có decision maker"],
                "missing_questions": ["Domain chính thức?", "Timeline kỳ vọng?"],
            },
        )
        assert updated is not None
        self.assertIn("SEO", updated["ai_summary"])
        self.assertEqual(len(updated["ai_suggested_questions"]), 2)

    def test_get_intake_stats(self):
        conn = _setup_conn()
        sid = create_session(
            conn, lifecycle_id=1, service_slug="dich-vu-seo-tong-the"
        )
        update_session(
            conn,
            sid,
            {
                "decision": "go",
                "bant_json": {
                    "budget": 4, "authority": 4, "need": 4,
                    "timeline": 4, "fit": 4, "history": 4,
                },
            },
        )
        complete_session(conn, sid)
        stats = get_intake_stats(conn)
        self.assertEqual(stats["completed_intake_sessions"], 1)
        self.assertEqual(stats["lifecycles_with_completed_intake"], 1)
        self.assertEqual(stats["total_lifecycles"], 1)
        self.assertEqual(stats["intake_coverage_pct"], 100.0)
        self.assertEqual(len(stats["avg_bant_by_slug"]), 1)
        self.assertEqual(stats["avg_bant_by_slug"][0]["avg_bant_total"], 24.0)

    def test_get_intake_stats_by_am(self):
        conn = _setup_conn()
        conn.execute(
            "ALTER TABLE crm_service_lifecycle ADD COLUMN assigned_am INTEGER"
        )
        conn.execute(
            "CREATE TABLE crm_staff (id INTEGER PRIMARY KEY, name TEXT, active INTEGER DEFAULT 1)"
        )
        conn.execute("INSERT INTO crm_staff (id, name) VALUES (5, 'AM Five')")
        conn.execute(
            "UPDATE crm_service_lifecycle SET assigned_am = 5 WHERE id = 1"
        )
        sid = create_session(
            conn, lifecycle_id=1, service_slug="dich-vu-seo-tong-the"
        )
        update_session(conn, sid, {"decision": "go"})
        complete_session(conn, sid)
        conn.commit()
        stats = get_intake_stats(conn, by_am=True)
        self.assertIn("by_am", stats)
        self.assertEqual(len(stats["by_am"]), 1)
        self.assertEqual(stats["by_am"][0]["staff_id"], 5)
        self.assertEqual(stats["by_am"][0]["intake_completed"], 1)

    def test_prefill_includes_qualify_questions(self):
        conn = _setup_conn()
        conn.execute(
            """
            UPDATE crm_leads SET meta_json = ? WHERE id = 10
            """,
            (
                json.dumps(
                    {
                        "ai_qualify_brief": {
                            "summary": "Cần SEO local cho 3 chi nhánh",
                            "service_slug": "dich-vu-seo-local",
                            "qualify_questions": ["Có bao nhiêu chi nhánh?", "Google Business đã verify?"],
                            "opening_line": "Chào anh, em gọi từ PTT về SEO local…",
                        }
                    },
                    ensure_ascii=False,
                ),
            ),
        )
        conn.commit()
        data = fetch_lead_prefill(conn, 10)
        meta = data["answers_json"]["meta"]
        self.assertEqual(meta["qualify_service_slug"], "dich-vu-seo-local")
        self.assertEqual(len(meta["qualify_questions"]), 2)

    def test_map_product_interest_to_slug(self):
        self.assertEqual(
            map_product_interest_to_slug("Quảng cáo Google Ads"),
            "quang-cao-google",
        )
        self.assertEqual(
            map_product_interest_to_slug("dich-vu-seo-tong-the"),
            "dich-vu-seo-tong-the",
        )
        self.assertEqual(map_product_interest_to_slug(""), "")


if __name__ == "__main__":
    unittest.main()
