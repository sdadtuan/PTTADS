"""Tests crm_svc_consult_bridge — Phase C1 Consult Brief."""
from __future__ import annotations

import json
import sqlite3
import unittest

from crm_lead_intake import ensure_schema as intake_schema
from crm_svc_consult_bridge import (
    build_ai_context_for_consult,
    get_consult_brief,
    get_lifecycle_funnel_progress,
    on_intake_completed,
    prefill_consult_task,
    validate_consult_advance,
)
from crm_svc_tasks import ensure_schema as tasks_schema, seed_tasks, update_task


def _anthropic_available() -> bool:
    try:
        import anthropic  # noqa: F401
        return True
    except ImportError:
        return False


def _insert_completed_intake(
    conn: sqlite3.Connection,
    lifecycle_id: int,
    *,
    mode: str = "phone",
    decision: str = "go",
    bant_total: int = 26,
    ai_summary: str = "",
    answers_json: dict | None = None,
) -> None:
    conn.execute(
        """
        INSERT INTO crm_lead_intake_sessions
            (lifecycle_id, service_slug, mode, status, decision, bant_total,
             lead_temperature, ai_summary, answers_json, stakeholders_json,
             commitments_json, completed_at, created_at, updated_at)
        VALUES (?, 'dich-vu-seo-tong-the', ?, 'completed', ?, ?,
                'hot', ?, ?, '[]', '[]', '2026-06-05 10:00:00',
                '2026-06-05 09:00:00', '2026-06-05 10:00:00')
        """,
        (
            lifecycle_id,
            mode,
            decision,
            bant_total,
            ai_summary,
            json.dumps(answers_json or {}, ensure_ascii=False),
        ),
    )


def _setup_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE crm_service_lifecycle (
            id INTEGER PRIMARY KEY,
            lead_id INTEGER,
            service_slug TEXT NOT NULL DEFAULT 'dich-vu-seo-tong-the',
            stage TEXT NOT NULL DEFAULT 'lead',
            status TEXT NOT NULL DEFAULT 'draft',
            notes TEXT NOT NULL DEFAULT '',
            stage_entered_at TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL DEFAULT ''
        )
    """)
    conn.execute("""
        CREATE TABLE crm_service_lifecycle_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lifecycle_id INTEGER NOT NULL,
            from_stage TEXT,
            to_stage TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT ''
        )
    """)
    conn.execute("""
        CREATE TABLE crm_leads (
            id INTEGER PRIMARY KEY,
            full_name TEXT NOT NULL DEFAULT '',
            phone TEXT NOT NULL DEFAULT '',
            need TEXT NOT NULL DEFAULT '',
            source TEXT NOT NULL DEFAULT '',
            meta_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL DEFAULT ''
        )
    """)
    conn.execute(
        "INSERT INTO crm_leads (id, full_name, need) VALUES (10, 'KH Test', 'Cần SEO')"
    )
    intake_schema(conn)
    tasks_schema(conn)
    return conn


class TestGetConsultBrief(unittest.TestCase):
    def test_lifecycle_not_found(self):
        conn = _setup_conn()
        with self.assertRaises(ValueError):
            get_consult_brief(conn, 99)

    def test_no_intake_recommends_open_intake(self):
        conn = _setup_conn()
        conn.execute(
            """
            INSERT INTO crm_service_lifecycle (id, lead_id, stage, service_slug)
            VALUES (1, 10, 'consult', 'dich-vu-seo-tong-the')
            """
        )
        seed_tasks(conn, lifecycle_id=1, service_slug="dich-vu-seo-tong-the")
        conn.commit()
        brief = get_consult_brief(conn, 1)
        self.assertEqual(brief["lifecycle_id"], 1)
        self.assertFalse(brief["readiness"]["has_any_intake"])
        self.assertIn("PHẦN A", brief["recommended_actions"][0])

    def test_intake_completed_includes_bant_and_decision(self):
        conn = _setup_conn()
        conn.execute(
            """
            INSERT INTO crm_service_lifecycle (id, lead_id, stage, service_slug)
            VALUES (1, 10, 'consult', 'dich-vu-seo-tong-the')
            """
        )
        seed_tasks(conn, lifecycle_id=1, service_slug="dich-vu-seo-tong-the")
        _insert_completed_intake(
            conn,
            1,
            answers_json={
                "crm_fields": {
                    "niche": "Bất động sản",
                    "budget": 15000000,
                    "domain": "example.com",
                    "need": "Tăng traffic organic",
                },
                "red_flags": ["Từ chối GSC"],
            },
            bant_total=29,
            ai_summary="KH cần SEO tổng thể, ngân sách 15tr/tháng.",
        )
        lead_row = conn.execute(
            "SELECT id FROM crm_svc_tasks WHERE lifecycle_id = 1 AND stage = 'lead'"
        ).fetchone()
        update_task(
            conn,
            int(lead_row[0]),
            is_done=True,
            form_data={
                "niche": "Bất động sản",
                "budget": 15000000,
                "domain": "example.com",
                "need": "Tăng traffic organic",
            },
        )
        conn.commit()

        brief = get_consult_brief(conn, 1)
        self.assertEqual(brief["readiness"]["decision"], "go")
        self.assertEqual(brief["readiness"]["bant_total"], 29)
        self.assertEqual(brief["readiness"]["consult_gate_level"], "ok")
        self.assertTrue(brief["readiness"]["has_intake_phone"])
        self.assertFalse(brief["readiness"]["has_intake_in_person"])
        self.assertEqual(brief["highlights"]["domain"], "example.com")
        self.assertEqual(brief["highlights"]["budget_vnd"], 15000000)
        self.assertEqual(brief["red_flags"], ["Từ chối GSC"])
        self.assertIn("PHẦN B", " ".join(brief["recommended_actions"]))
        self.assertIn("GSC/GA4", " ".join(brief["recommended_actions"]))
        self.assertIn("SEO tổng thể", brief["latest_intake_summary"])

    def test_no_go_gate_block(self):
        conn = _setup_conn()
        conn.execute(
            """
            INSERT INTO crm_service_lifecycle (id, lead_id, stage, service_slug)
            VALUES (2, 10, 'consult', 'quang-cao-facebook')
            """
        )
        seed_tasks(conn, lifecycle_id=2, service_slug="quang-cao-facebook")
        conn.execute(
            """
            INSERT INTO crm_lead_intake_sessions
                (lifecycle_id, service_slug, mode, status, decision, bant_total,
                 completed_at, created_at, updated_at)
            VALUES (2, 'quang-cao-facebook', 'phone', 'completed', 'no_go', 10,
                    '2026-06-05 10:00:00', '2026-06-05 09:00:00', '2026-06-05 10:00:00')
            """
        )
        conn.commit()
        brief = get_consult_brief(conn, 2)
        self.assertEqual(brief["readiness"]["consult_gate_level"], "block")
        self.assertTrue(
            any("No-Go" in a for a in brief["recommended_actions"])
        )


class TestPrefillConsultTask(unittest.TestCase):
    def _seed_consult_lifecycle(self, conn: sqlite3.Connection, slug: str = "dich-vu-seo-tong-the") -> None:
        conn.execute(
            """
            INSERT INTO crm_service_lifecycle (id, lead_id, stage, service_slug)
            VALUES (1, 10, 'consult', ?)
            """,
            (slug,),
        )
        seed_tasks(conn, lifecycle_id=1, service_slug=slug)

    def test_prefill_fills_current_status_from_need(self):
        conn = _setup_conn()
        self._seed_consult_lifecycle(conn)
        lead_row = conn.execute(
            "SELECT id FROM crm_svc_tasks WHERE lifecycle_id = 1 AND stage = 'lead'"
        ).fetchone()
        update_task(
            conn,
            int(lead_row[0]),
            form_data={
                "need": "Tăng traffic organic",
                "niche": "Bất động sản",
                "domain": "example.com",
                "budget": 15000000,
            },
        )
        conn.commit()

        result = prefill_consult_task(conn, 1)
        conn.commit()

        consult_row = conn.execute(
            "SELECT form_data, notes FROM crm_svc_tasks WHERE lifecycle_id = 1 AND stage = 'consult'"
        ).fetchone()
        form = json.loads(consult_row[0])
        self.assertIn("current_status", result["fields"])
        self.assertIn("Pain: Tăng traffic organic", form["current_status"])
        self.assertEqual(form.get("target_audience"), "Bất động sản")
        self.assertIn("Ngành:", consult_row[1])

    def test_prefill_does_not_overwrite_existing(self):
        conn = _setup_conn()
        self._seed_consult_lifecycle(conn)
        lead_row = conn.execute(
            "SELECT id FROM crm_svc_tasks WHERE lifecycle_id = 1 AND stage = 'lead'"
        ).fetchone()
        consult_row = conn.execute(
            "SELECT id FROM crm_svc_tasks WHERE lifecycle_id = 1 AND stage = 'consult'"
        ).fetchone()
        update_task(
            conn,
            int(lead_row[0]),
            form_data={"need": "Lead need mới"},
        )
        update_task(
            conn,
            int(consult_row[0]),
            form_data={"current_status": "Đã audit thủ công"},
        )
        conn.commit()

        result = prefill_consult_task(conn, 1, overwrite=False)
        conn.commit()

        form = json.loads(
            conn.execute(
                "SELECT form_data FROM crm_svc_tasks WHERE lifecycle_id = 1 AND stage = 'consult'"
            ).fetchone()[0]
        )
        self.assertEqual(form["current_status"], "Đã audit thủ công")
        self.assertIn("current_status", result["skipped_existing"])

    def test_get_crm_field_map_covers_twelve_slugs(self):
        from crm_lead_intake_definitions import get_crm_field_map

        slugs = [
            "dich-vu-seo-tong-the",
            "dich-vu-aeo",
            "dich-vu-seo-local",
            "dich-vu-seo-audit",
            "dich-vu-quan-tri-website",
            "thiet-ke-website",
            "thiet-ke-website-tron-goi",
            "thiet-ke-landing-page",
            "quang-cao-facebook",
            "quang-cao-google",
            "thue-tai-khoan-quang-cao",
            "tiep-thi-noi-dung",
        ]
        for slug in slugs:
            m = get_crm_field_map(slug)
            self.assertIsInstance(m, dict)
            self.assertGreater(len(m), 0, slug)


class TestValidateConsultAdvance(unittest.TestCase):
    def _seed_lead_ready(self, conn: sqlite3.Connection, *, decision: str, bant: int) -> None:
        conn.execute(
            """
            INSERT INTO crm_service_lifecycle (id, lead_id, stage, service_slug)
            VALUES (1, 10, 'lead', 'dich-vu-seo-tong-the')
            """
        )
        seed_tasks(conn, lifecycle_id=1, service_slug="dich-vu-seo-tong-the")
        lead_row = conn.execute(
            "SELECT id FROM crm_svc_tasks WHERE lifecycle_id = 1 AND stage = 'lead'"
        ).fetchone()
        update_task(conn, int(lead_row[0]), is_done=True)
        _insert_completed_intake(conn, 1, decision=decision, bant_total=bant)
        conn.commit()

    def test_no_go_blocks_without_override(self):
        conn = _setup_conn()
        self._seed_lead_ready(conn, decision="no_go", bant=10)
        gate = validate_consult_advance(conn, 1)
        self.assertFalse(gate["ok"])
        self.assertEqual(gate["level"], "block")
        self.assertTrue(gate["requires_override"])

    def test_no_go_allows_director_override(self):
        conn = _setup_conn()
        self._seed_lead_ready(conn, decision="no_go", bant=10)
        gate = validate_consult_advance(
            conn, 1, override_reason="KH đổi scope", allow_override=True
        )
        self.assertTrue(gate["ok"])
        self.assertTrue(gate["requires_confirm"])

    def test_nurture_warns_with_confirm(self):
        conn = _setup_conn()
        self._seed_lead_ready(conn, decision="nurture", bant=20)
        gate = validate_consult_advance(conn, 1)
        self.assertTrue(gate["ok"])
        self.assertEqual(gate["level"], "warn")
        self.assertTrue(gate["requires_confirm"])

    def test_go_ready_ok(self):
        conn = _setup_conn()
        self._seed_lead_ready(conn, decision="go", bant=26)
        gate = validate_consult_advance(conn, 1)
        self.assertTrue(gate["ok"])
        self.assertEqual(gate["level"], "ok")
        self.assertFalse(gate["requires_confirm"])


class TestOnIntakeCompleted(unittest.TestCase):
    def test_in_person_go_auto_marks_lead_done(self):
        conn = _setup_conn()
        conn.execute(
            """
            INSERT INTO crm_service_lifecycle (id, lead_id, stage, service_slug)
            VALUES (1, 10, 'lead', 'dich-vu-seo-tong-the')
            """
        )
        seed_tasks(conn, lifecycle_id=1, service_slug="dich-vu-seo-tong-the")
        sid = conn.execute(
            """
            INSERT INTO crm_lead_intake_sessions
                (lifecycle_id, service_slug, mode, status, decision, bant_total,
                 completed_at, created_at, updated_at)
            VALUES (1, 'dich-vu-seo-tong-the', 'in_person', 'completed', 'go', 26,
                    '2026-06-05 10:00:00', '2026-06-05 09:00:00', '2026-06-05 10:00:00')
            """
        ).lastrowid
        conn.commit()
        result = on_intake_completed(conn, int(sid))
        conn.commit()
        self.assertIn("lead_task_auto_done", result["actions"])
        done = conn.execute(
            "SELECT is_done FROM crm_svc_tasks WHERE lifecycle_id = 1 AND stage = 'lead'"
        ).fetchone()[0]
        self.assertEqual(done, 1)

    def test_no_go_appends_lifecycle_note(self):
        conn = _setup_conn()
        conn.execute(
            """
            INSERT INTO crm_service_lifecycle (id, lead_id, stage, service_slug, notes)
            VALUES (1, 10, 'lead', 'dich-vu-seo-tong-the', '')
            """
        )
        sid = conn.execute(
            """
            INSERT INTO crm_lead_intake_sessions
                (lifecycle_id, service_slug, mode, status, decision, bant_total,
                 completed_at, created_at, updated_at)
            VALUES (1, 'dich-vu-seo-tong-the', 'phone', 'completed', 'no_go', 8,
                    '2026-06-05 10:00:00', '2026-06-05 09:00:00', '2026-06-05 10:00:00')
            """
        ).lastrowid
        conn.commit()
        result = on_intake_completed(conn, int(sid))
        conn.commit()
        self.assertIn("no_go_lifecycle_note", result["actions"])
        notes = conn.execute(
            "SELECT notes FROM crm_service_lifecycle WHERE id = 1"
        ).fetchone()[0]
        self.assertIn("No-Go", notes)


class TestBuildAiContextForConsult(unittest.TestCase):
    def test_merges_intake_summary_and_bant(self):
        conn = _setup_conn()
        conn.execute(
            """
            INSERT INTO crm_service_lifecycle (id, lead_id, stage, service_slug)
            VALUES (1, 10, 'consult', 'dich-vu-seo-tong-the')
            """
        )
        seed_tasks(conn, lifecycle_id=1, service_slug="dich-vu-seo-tong-the")
        _insert_completed_intake(
            conn,
            1,
            answers_json={
                "crm_fields": {
                    "niche": "Bất động sản",
                    "budget": 15000000,
                    "domain": "example.com",
                    "need": "Tăng traffic organic",
                },
                "red_flags": ["Từ chối GSC"],
            },
            bant_total=29,
            ai_summary="KH cần SEO tổng thể, ngân sách 15tr/tháng.",
        )
        lead_row = conn.execute(
            "SELECT id FROM crm_svc_tasks WHERE lifecycle_id = 1 AND stage = 'lead'"
        ).fetchone()
        consult_row = conn.execute(
            "SELECT id FROM crm_svc_tasks WHERE lifecycle_id = 1 AND stage = 'consult'"
        ).fetchone()
        update_task(
            conn,
            int(lead_row[0]),
            form_data={"niche": "Bất động sản", "need": "Tăng traffic organic"},
        )
        conn.commit()

        ctx = build_ai_context_for_consult(
            conn,
            1,
            int(consult_row[0]),
            {"current_status": "Website mới"},
        )
        self.assertEqual(ctx["bant_total"], 29)
        self.assertEqual(ctx["decision"], "GO")
        self.assertIn("SEO tổng thể", ctx["intake_summary"])
        self.assertIn("Bất động sản", ctx["lead_form_json"])
        self.assertIn("GSC", ctx["red_flags"])
        self.assertEqual(ctx["current_status"], "Website mới")

    @unittest.skipUnless(_anthropic_available(), "anthropic not installed")
    def test_run_ai_assist_prompt_contains_intake_excerpt(self):
        import os
        from unittest.mock import MagicMock, patch

        from crm_svc_tasks import run_ai_assist

        conn = _setup_conn()
        conn.execute(
            """
            INSERT INTO crm_service_lifecycle (id, lead_id, stage, service_slug)
            VALUES (1, 10, 'consult', 'dich-vu-seo-tong-the')
            """
        )
        seed_tasks(conn, lifecycle_id=1, service_slug="dich-vu-seo-tong-the")
        _insert_completed_intake(
            conn,
            1,
            ai_summary="EXCERPT_UNIQUE_INTAKE_SUMMARY_FOR_TEST",
            bant_total=27,
        )
        consult_row = conn.execute(
            "SELECT id FROM crm_svc_tasks WHERE lifecycle_id = 1 AND stage = 'consult'"
        ).fetchone()
        conn.commit()
        task_id = int(consult_row[0])

        ctx = build_ai_context_for_consult(conn, 1, task_id, {})
        ctx["service_name"] = "SEO Tổng thể"
        ctx["customer_name"] = "KH Test"

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="Phân tích consult AI")]

        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
            with patch("anthropic.Anthropic") as mock_cls:
                mock_cls.return_value.messages.create.return_value = mock_response
                output = run_ai_assist(conn, task_id, ctx)

        self.assertEqual(output, "Phân tích consult AI")
        call_kwargs = mock_cls.return_value.messages.create.call_args.kwargs
        prompt = call_kwargs["messages"][0]["content"]
        self.assertIn("EXCERPT_UNIQUE_INTAKE_SUMMARY_FOR_TEST", prompt)
        self.assertIn("BANT Intake: 27/30", prompt)


class TestLifecycleFunnelProgress(unittest.TestCase):
    def test_milestones_and_days_to_proposal(self):
        conn = _setup_conn()
        conn.execute(
            """
            INSERT INTO crm_service_lifecycle
                (id, lead_id, stage, service_slug, created_at, stage_entered_at)
            VALUES (1, 10, 'proposal', 'dich-vu-seo-tong-the',
                    '2026-06-03 09:00:00', '2026-06-08 09:00:00')
            """
        )
        _insert_completed_intake(conn, 1, bant_total=27)
        conn.execute(
            """
            INSERT INTO crm_service_lifecycle_events
                (lifecycle_id, from_stage, to_stage, created_at)
            VALUES
                (1, 'lead', 'consult', '2026-06-05 10:00:00'),
                (1, 'consult', 'proposal', '2026-06-08 09:00:00')
            """
        )
        conn.commit()

        progress = get_lifecycle_funnel_progress(conn, 1)
        self.assertEqual(progress["current_stage"], "proposal")
        self.assertEqual(progress["decision"], "go")
        self.assertEqual(progress["bant_total"], 27)
        self.assertTrue(progress["milestones"][0]["done"])
        self.assertTrue(progress["milestones"][2]["done"])
        self.assertTrue(progress["milestones"][3]["done"])
        self.assertEqual(progress["days_to_proposal"], 3.0)
        self.assertTrue(progress["within_7d_proposal"])
        self.assertIn("service_slug=dich-vu-seo-tong-the", progress["dashboard_funnel_url"])
        self.assertIn("from=2026-06-01", progress["dashboard_funnel_url"])

    def test_lifecycle_not_found(self):
        conn = _setup_conn()
        with self.assertRaises(ValueError):
            get_lifecycle_funnel_progress(conn, 99)


if __name__ == "__main__":
    unittest.main()
