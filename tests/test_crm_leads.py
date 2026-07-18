"""Test CRM Lead Management — map FR-01…FR-12 (spec Word)."""
from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from crm_lead_ai import ai_classify_suggestion, ai_search_leads, ai_summarize_lead
from crm_lead_rules import (
    fetch_lead_config,
    is_status_transition_allowed,
    merge_leads,
    save_lead_config,
    validate_status_transition,
)
from crm_lead_scoring import DEFAULT_SCORING_RULES, score_lead
from crm_lead_scoring_rubric import DEFAULT_LEAD_SCORING_RUBRIC
from crm_lead_sla import reassign_leads_from_inactive_owners
from crm_lead_store import (
    classify_level,
    compute_lead_score,
    create_lead,
    delete_lead,
    ensure_lead_schema,
    fetch_lead_activities,
    fetch_lead_assignment_logs,
    fetch_lead_by_id,
    fetch_lead_status_logs,
    fetch_leads,
    count_leads,
    fetch_max_lead_id,
    fetch_new_assigned_leads,
    find_duplicate_leads,
    is_sla_overdue,
    lead_needs_cleanup,
    lead_pipeline_alert,
    lead_row_to_dict,
    log_lead_activity,
    activity_row_to_dict,
    normalize_level,
    update_lead,
)
from crm_re_projects import ensure_re_projects_schema


TS = "2026-05-30 10:00:00"


def _setup_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    ensure_lead_schema(conn)
    ensure_re_projects_schema(conn)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS crm_assignment_state (
            pool_key TEXT PRIMARY KEY,
            last_staff_id INTEGER NOT NULL DEFAULT 0,
            updated_at TEXT NOT NULL DEFAULT ''
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS crm_reminders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scope TEXT NOT NULL,
            ref_id INTEGER NOT NULL DEFAULT 0,
            reminder_kind TEXT NOT NULL DEFAULT 'manual',
            title TEXT NOT NULL,
            body TEXT NOT NULL DEFAULT '',
            remind_at TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            staff_id INTEGER,
            meta_json TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS crm_departments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT NOT NULL DEFAULT '',
            name TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            sort_order INTEGER NOT NULL DEFAULT 0,
            active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL DEFAULT ''
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS crm_staff (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            active INTEGER NOT NULL DEFAULT 1,
            notes TEXT NOT NULL DEFAULT '',
            internal_code TEXT NOT NULL DEFAULT '',
            email TEXT NOT NULL DEFAULT '',
            department_id INTEGER REFERENCES crm_departments(id)
        )
        """
    )
    conn.execute(
        """
        INSERT INTO crm_departments (id, code, name, active, created_at, updated_at)
        VALUES (1, 'kd', 'Kinh doanh', 1, ?, ?)
        """,
        (TS, TS),
    )
    conn.execute(
        "INSERT INTO crm_staff (id, name, active, internal_code, department_id) VALUES (1, 'Sales A', 1, 'SA-01', 1)"
    )
    conn.execute(
        "INSERT INTO crm_staff (id, name, active, internal_code, department_id) VALUES (2, 'Sales B', 1, 'SB-01', 1)"
    )
    conn.commit()
    return conn


class TestLeadFunctionalRequirements(unittest.TestCase):
    def setUp(self) -> None:
        self.conn = _setup_conn()

    def tearDown(self) -> None:
        self.conn.close()

    def test_fr01_create_lead_manual(self) -> None:
        """FR-01 / TC-01: Tạo lead nhập tay."""
        row, dups, _ = create_lead(
            self.conn,
            full_name="Nguyen Van A",
            phone="0901234567",
            email="a@test.com",
            source="manual",
            need="Tu van dich vu",
            product_interest="CRM",
            created_by="test",
            ts=TS,
        )
        self.conn.commit()
        self.assertEqual(dups, [])
        self.assertEqual(int(row["id"]), 1)
        self.assertGreaterEqual(int(row["lead_score"]), 10)
        self.assertIn(normalize_level(row["lead_level"]), {"vip", "hot", "warm_plus", "warm", "cold_plus", "cold"})

    def test_fr04_classify_default_tiers(self) -> None:
        """FR-04: Phân loại theo bảng mặc định VIP → COLD."""
        from crm_lead_tiers import DEFAULT_LEVEL_TIERS, classify_score_to_tier, tier_display_label

        cfg = fetch_lead_config(self.conn)
        self.assertEqual(len(cfg["level_tiers"]), 6)
        self.assertEqual(classify_level(95, conn=self.conn), "vip")
        self.assertEqual(classify_level(80, conn=self.conn), "hot")
        self.assertEqual(classify_level(60, conn=self.conn), "warm_plus")
        self.assertEqual(classify_level(40, conn=self.conn), "warm")
        self.assertEqual(classify_level(20, conn=self.conn), "cold_plus")
        self.assertEqual(classify_level(5, conn=self.conn), "cold")
        tiers = cfg["level_tiers"]
        self.assertEqual(classify_score_to_tier(20, tiers), "cold_plus")
        vip = next(t for t in DEFAULT_LEVEL_TIERS if t["id"] == "vip")
        self.assertIn("VIP", tier_display_label(vip))
        self.assertEqual(vip["sla_label"], "< 2 phút")

    def test_fr02_duplicate_detection(self) -> None:
        """FR-02: Phát hiện trùng phone/email."""
        create_lead(
            self.conn,
            full_name="Lead 1",
            phone="0911111111",
            email="dup@test.com",
            created_by="test",
            ts=TS,
        )
        self.conn.commit()
        dups = find_duplicate_leads(self.conn, phone="0911111111", email="")
        self.assertEqual(len(dups), 1)
        row2, _, dup_matches = create_lead(
            self.conn,
            full_name="Lead 2",
            phone="0911111111",
            email="other@test.com",
            duplicate_policy="flag",
            created_by="test",
            ts=TS,
        )
        self.assertEqual(int(row2["is_duplicate"]), 1)
        self.assertEqual(dup_matches[0]["match_type"], "phone")

    def test_create_lead_invalid_phone(self) -> None:
        with self.assertRaises(ValueError):
            create_lead(
                self.conn,
                full_name="Bad Phone",
                phone="123",
                email="",
                created_by="test",
                ts=TS,
            )

    def test_create_lead_invalid_email(self) -> None:
        with self.assertRaises(ValueError):
            create_lead(
                self.conn,
                full_name="Bad Email",
                phone="",
                email="not-an-email",
                created_by="test",
                ts=TS,
            )

    def test_duplicate_match_both(self) -> None:
        from crm_lead_store import find_duplicate_matches

        create_lead(
            self.conn,
            full_name="Original",
            phone="0908888777",
            email="both@test.com",
            created_by="test",
            ts=TS,
        )
        self.conn.commit()
        matches = find_duplicate_matches(
            self.conn, phone="0908888777", email="both@test.com"
        )
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["match_type"], "both")

    def test_create_lead_system_activities(self) -> None:
        save_lead_config(
            self.conn,
            config={
                "level_tiers": [
                    {"id": "hot", "label": "Hot", "min_score": 70, "max_score": 100, "enabled": True},
                    {"id": "cold", "label": "Cold", "min_score": 0, "max_score": 69, "enabled": True},
                ]
            },
            updated_by="test",
            ts=TS,
        )
        row, _, _ = create_lead(
            self.conn,
            full_name="Pipeline Lead",
            phone="0901234567",
            email="pipe@test.com",
            need="Can tu van CRM",
            created_by="test",
            ts=TS,
        )
        self.conn.commit()
        acts = fetch_lead_activities(self.conn, int(row["id"]))
        contents = " ".join(str(a["content"]) for a in acts)
        self.assertIn("Kiểm tra liên hệ", contents)
        self.assertIn("Kiểm tra trùng", contents)
        self.assertIn("Chấm điểm", contents)
        self.assertIn("Phân hạng", contents)
        self.assertGreaterEqual(int(row["lead_score"]), 0)

    def test_fr03_lead_scoring(self) -> None:
        """FR-03: Chấm điểm lead theo rubric D1–D6."""
        low = score_lead(
            None,
            source="other",
            phone="",
            email="",
            need="",
            product_interest="",
            region="",
            full_name="A",
        )
        high = score_lead(
            None,
            source="referral",
            phone="0909999888",
            email="x@test.com",
            need="Muon mua ngay, ngan sach 3.5 ty",
            product_interest="Can ho",
            region="HCM",
            full_name="Nguyen A",
            meta={"budget_text": "3.5 tỷ", "site_time_minutes": 8},
            activity_count=4,
        )
        self.assertLess(low["score"], high["score"])
        self.assertGreaterEqual(high["score"], 20)
        self.assertTrue(high.get("rubric"))

    def test_scoring_rules_config(self) -> None:
        """Lưu rubric chấm điểm từ cấu hình."""
        cfg = fetch_lead_config(self.conn)
        self.assertEqual(len(cfg["scoring_rubric"]["groups"]), 6)
        saved = save_lead_config(
            self.conn,
            config={
                "scoring_rubric": DEFAULT_LEAD_SCORING_RUBRIC,
                "scoring_mode": "rubric",
            },
            updated_by="test",
            ts=TS,
        )
        self.assertEqual(len(saved["scoring_rubric"]["groups"]), 6)
        row, _, _ = create_lead(
            self.conn,
            full_name="Score cfg",
            phone="0912345678",
            email="a@t.com",
            need="Tu van",
            product_interest="CRM",
            created_by="test",
            ts=TS,
        )
        self.conn.commit()
        self.assertGreaterEqual(int(row["lead_score"]), 0)

    def test_custom_keyword_scoring_rule(self) -> None:
        """Legacy rule phẳng vẫn hoạt động khi scoring_mode=legacy_rules."""
        save_lead_config(
            self.conn,
            config={
                "scoring_mode": "legacy_rules",
                "scoring_rules": [
                    {
                        "id": "custom_vip",
                        "label": "Khách VIP",
                        "points": 40,
                        "enabled": True,
                        "condition": "keyword",
                        "keywords": ["vip", "ưu tiên"],
                        "custom": True,
                    }
                ],
            },
            updated_by="test",
            ts=TS,
        )
        hit = score_lead(
            self.conn,
            source="manual",
            phone="",
            email="",
            need="Tôi là khách VIP cần tư vấn",
            product_interest="",
            region="",
            full_name="VIP Lead",
        )
        miss = score_lead(
            self.conn,
            source="manual",
            phone="",
            email="",
            need="Lead thường",
            product_interest="",
            region="",
            full_name="Normal",
        )
        self.assertGreaterEqual(hit["score"], 40)
        self.assertLess(miss["score"], hit["score"])

    def test_level_tiers_config(self) -> None:
        """Cấu hình phân hạng lead — thêm/sửa ngưỡng và trường mô tả."""
        from crm_lead_tiers import classify_score_to_tier

        saved = save_lead_config(
            self.conn,
            config={
                "level_tiers": [
                    {
                        "id": "hot",
                        "label": "Siêu hot",
                        "emoji": "🟠",
                        "description": "Nóng",
                        "sla_label": "< 3 phút",
                        "min_score": 80,
                        "max_score": 100,
                        "enabled": True,
                    },
                    {
                        "id": "warm",
                        "label": "Ấm",
                        "min_score": 50,
                        "max_score": 79,
                        "enabled": True,
                    },
                    {
                        "id": "cold",
                        "label": "Lạnh",
                        "min_score": 0,
                        "max_score": 49,
                        "enabled": True,
                    },
                ]
            },
            updated_by="test",
            ts=TS,
        )
        hot = next(t for t in saved["level_tiers"] if t["id"] == "hot")
        self.assertEqual(hot["label"], "Siêu hot")
        self.assertEqual(hot["emoji"], "🟠")
        self.assertEqual(hot["sla_label"], "< 3 phút")
        self.assertEqual(classify_level(75, conn=self.conn), "warm")
        self.assertEqual(classify_level(85, conn=self.conn), "hot")
        tiers = saved["level_tiers"]
        self.assertEqual(classify_score_to_tier(75, tiers), "warm")

    def test_level_tiers_overlap_rejected(self) -> None:
        """Không cho phép khoảng điểm trùng."""
        with self.assertRaises(ValueError):
            save_lead_config(
                self.conn,
                config={
                    "level_tiers": [
                        {"id": "hot", "label": "Hot", "min_score": 60, "max_score": 100, "enabled": True},
                        {"id": "warm", "label": "Warm", "min_score": 40, "max_score": 70, "enabled": True},
                    ]
                },
                updated_by="test",
                ts=TS,
            )

    def test_fr05_owner_assignment(self) -> None:
        """FR-05: Gán owner khi tạo."""
        row, _, _ = create_lead(
            self.conn,
            full_name="Lead co owner",
            phone="0922222222",
            email="owner@test.com",
            auto_assign=True,
            created_by="test",
            ts=TS,
        )
        self.conn.commit()
        self.assertIsNotNone(row["owner_id"])

    def test_fr06_activity_log(self) -> None:
        """FR-06: Ghi activity."""
        row, _, _ = create_lead(
            self.conn,
            full_name="Act Lead",
            phone="0933333333",
            email="act@test.com",
            need="Tu van",
            created_by="test",
            ts=TS,
        )
        lid = int(row["id"])
        log_lead_activity(
            self.conn,
            lead_id=lid,
            activity_type="call",
            content="Goi lan 1",
            result="Hen goi lai",
            user_id=1,
            created_by="test",
            ts=TS,
        )
        self.conn.commit()
        acts = fetch_lead_activities(self.conn, lid)
        self.assertGreaterEqual(len(acts), 2)
        self.assertTrue(any(str(a["activity_type"]) == "call" for a in acts))

    def test_activity_call_keeps_care_stage_status(self) -> None:
        """Gọi điện thường không tự đổi bước — pipeline chăm sóc quản lý trạng thái."""
        row, _, _ = create_lead(
            self.conn,
            full_name="Call Status Lead",
            phone="0933333399",
            email="callstatus@test.com",
            need="Tu van",
            status="new",
            created_by="test",
            ts=TS,
        )
        lid = int(row["id"])
        log_lead_activity(
            self.conn,
            lead_id=lid,
            activity_type="call",
            content="Da goi khach",
            result="Khach nghe may",
            created_by="test",
            ts=TS,
        )
        self.conn.commit()
        updated = fetch_lead_by_id(self.conn, lid)
        assert updated is not None
        self.assertEqual(str(updated["status"]), "first_contact")

    def test_activity_logs_pipeline_status_snapshot(self) -> None:
        row, _, _ = create_lead(
            self.conn,
            full_name="Snap Lead",
            phone="0933333377",
            email="",
            status="qualified",
            need="Tu van",
            industry_slug="spa",
            created_by="test",
            ts=TS,
        )
        lid = int(row["id"])
        log_lead_activity(
            self.conn,
            lead_id=lid,
            activity_type="meeting",
            content="Gap khach",
            created_by="test",
            ts=TS,
        )
        self.conn.commit()
        acts = fetch_lead_activities(self.conn, lid)
        user_acts = [a for a in acts if str(a["activity_type"]) != "system"]
        self.assertTrue(user_acts)
        self.assertEqual(str(dict(user_acts[0]).get("lead_status_at_log") or ""), "first_contact")

    def test_activity_stores_care_report_fields(self) -> None:
        row, _, _ = create_lead(
            self.conn,
            full_name="Care Lead",
            phone="0933333399",
            email="",
            need="Tu van",
            status="new",
            created_by="test",
            ts=TS,
        )
        lid = int(row["id"])
        log_lead_activity(
            self.conn,
            lead_id=lid,
            activity_type="call",
            content="Da goi khach",
            care_contact_type="goi_dien",
            care_status="da_lien_he_thanh_cong",
            next_action="Gui bao gia",
            created_by="test",
            ts=TS,
        )
        self.conn.commit()
        acts = fetch_lead_activities(self.conn, lid)
        user_acts = [a for a in acts if str(a["activity_type"]) != "system"]
        act = activity_row_to_dict(user_acts[0])
        self.assertEqual(act["care_contact_type"], "goi_dien")
        self.assertEqual(act["care_status"], "da_lien_he_thanh_cong")
        self.assertEqual(act["care_contact_type_label"], "Gọi điện")
        self.assertEqual(act["care_status_label"], "Đã liên hệ thành công")
        updated = fetch_lead_by_id(self.conn, lid)
        assert updated is not None
        self.assertEqual(str(updated["status"]), "first_contact")

    def test_activity_note_does_not_auto_status(self) -> None:
        """Ghi chú thường không tự đổi trạng thái."""
        row, _, _ = create_lead(
            self.conn,
            full_name="Note Lead",
            phone="0933333388",
            email="note@test.com",
            need="Tu van",
            status="new",
            created_by="test",
            ts=TS,
        )
        lid = int(row["id"])
        log_lead_activity(
            self.conn,
            lead_id=lid,
            activity_type="note",
            content="Ghi chu noi bo",
            created_by="test",
            ts=TS,
        )
        self.conn.commit()
        updated = fetch_lead_by_id(self.conn, lid)
        assert updated is not None
        self.assertEqual(str(updated["status"]), "first_contact")

    def test_fr08_sla_overdue(self) -> None:
        """FR-08: Phát hiện quá SLA."""
        row, _, _ = create_lead(
            self.conn,
            full_name="SLA Lead",
            phone="0944444444",
            status="new",
            created_by="test",
            ts="2026-05-01 08:00:00",
        )
        self.conn.execute(
            "UPDATE crm_leads SET status_entered_at = ? WHERE id = ?",
            ("2026-05-01 08:00:00", int(row["id"])),
        )
        self.conn.commit()
        updated = fetch_lead_by_id(self.conn, int(row["id"]))
        assert updated is not None
        self.assertTrue(is_sla_overdue(str(updated["status"]), str(updated["status_entered_at"])))

    def test_fr10_ai_search(self) -> None:
        """FR-10: AI search rule-based."""
        create_lead(
            self.conn,
            full_name="Hot Lead Search",
            phone="0955555555",
            need="Urgent",
            created_by="test",
            ts=TS,
        )
        self.conn.commit()
        out = ai_search_leads(self.conn, "lead hot uu tien", ts=TS)
        self.assertIn("leads", out)
        self.assertTrue(out.get("answer"))

    def test_fr11_ai_classify(self) -> None:
        """FR-11: AI gợi ý phân loại."""
        row, _, _ = create_lead(
            self.conn,
            full_name="Classify Lead",
            phone="0966666666",
            email="c@test.com",
            need="San pham A",
            product_interest="CRM",
            created_by="test",
            ts=TS,
        )
        self.conn.commit()
        out = ai_classify_suggestion(self.conn, int(row["id"]), ts=TS)
        self.assertIn("suggested_level", out)
        self.assertTrue(out.get("requires_confirm"))

    def test_fr12_ai_summary(self) -> None:
        """FR-12: AI summary."""
        row, _, _ = create_lead(
            self.conn,
            full_name="Summary Lead",
            phone="0977777777",
            need="Can tu van",
            created_by="test",
            ts=TS,
        )
        lid = int(row["id"])
        log_lead_activity(
            self.conn,
            lead_id=lid,
            activity_type="call",
            content="Da goi",
            created_by="test",
            ts=TS,
        )
        self.conn.commit()
        out = ai_summarize_lead(self.conn, lid, ts=TS)
        self.assertTrue(out.get("summary"))
        self.assertGreaterEqual(out.get("activity_count", 0), 1)

    def test_pending_cleanup_status(self) -> None:
        """§8.2: Lead thiếu dữ liệu → pending_cleanup."""
        needs, reasons = lead_needs_cleanup(
            full_name="Zalo user",
            phone="123",
            email="",
            need="",
            product_interest="",
        )
        self.assertTrue(needs)
        self.assertTrue(reasons)
        row, _, _ = create_lead(
            self.conn,
            full_name="Zalo user",
            phone="0908888777",
            email="z@test.com",
            need="",
            product_interest="",
            created_by="test",
            ts=TS,
        )
        self.assertEqual(str(row["status"]), "pending_cleanup")

    def test_inactive_owner_reassign(self) -> None:
        """§8.2: Owner inactive → reassignment."""
        row, _, _ = create_lead(
            self.conn,
            full_name="Reassign Lead",
            phone="0988888888",
            owner_id=1,
            auto_assign=False,
            created_by="test",
            ts=TS,
        )
        lid = int(row["id"])
        self.conn.execute("UPDATE crm_staff SET active = 0 WHERE id = 1")
        self.conn.commit()
        n = reassign_leads_from_inactive_owners(self.conn, ts=TS)
        self.conn.commit()
        self.assertGreaterEqual(n, 1)
        updated = fetch_lead_by_id(self.conn, lid)
        assert updated is not None
        self.assertNotEqual(int(updated["owner_id"]), 1)
        logs = fetch_lead_assignment_logs(self.conn, lid)
        self.assertGreaterEqual(len(logs), 1)

    def test_audit_status_logs(self) -> None:
        """§6/NFR-03: Log trạng thái truy xuất được."""
        row, _, _ = create_lead(
            self.conn,
            full_name="Audit Lead",
            phone="0999999999",
            email="audit@test.com",
            need="Tu van",
            created_by="test",
            ts=TS,
        )
        lid = int(row["id"])
        update_lead(
            self.conn,
            lid,
            status="lost",
            updated_by="admin",
            ts=TS,
            status_note="Khong phu hop",
        )
        self.conn.commit()
        logs = fetch_lead_status_logs(self.conn, lid)
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0]["new_status"], "lost")

    def test_status_transition_valid(self) -> None:
        """§11: Chuyển trạng thái hợp lệ pipeline B2."""
        self.assertTrue(is_status_transition_allowed("first_contact", "lost"))
        self.assertTrue(is_status_transition_allowed("pending_cleanup", "first_contact"))

    def test_status_transition_blocked_missing_data(self) -> None:
        """§11: Không đổi trạng thái khi thiếu dữ liệu (trừ override)."""
        with self.assertRaises(ValueError):
            validate_status_transition(
                "pending_cleanup",
                "first_contact",
                needs_cleanup=True,
                allow_override=False,
            )

    def test_merge_duplicate_leads(self) -> None:
        """Mục 4: Gộp lead trùng vào lead chính."""
        row1, _, _ = create_lead(
            self.conn,
            full_name="Primary Lead",
            phone="0910101010",
            email="primary@test.com",
            need="Tu van",
            product_interest="CRM",
            created_by="test",
            ts=TS,
        )
        row2, _, _ = create_lead(
            self.conn,
            full_name="Dup Lead",
            phone="0910101010",
            email="dup2@test.com",
            need="Khac",
            duplicate_policy="flag",
            created_by="test",
            ts=TS,
        )
        self.conn.commit()
        merged = merge_leads(
            self.conn,
            int(row1["id"]),
            [int(row2["id"])],
            merged_by="admin",
            ts=TS,
            reason="Test merge",
        )
        self.assertEqual(int(merged["id"]), int(row1["id"]))
        dup = fetch_lead_by_id(self.conn, int(row2["id"]))
        assert dup is not None
        self.assertEqual(int(dup["is_duplicate"]), 1)
        acts = fetch_lead_activities(self.conn, int(row1["id"]))
        self.assertGreaterEqual(len(acts), 2)

    def test_lead_config_duplicate_policy(self) -> None:
        """Mục 4: Cấu hình policy dedup."""
        cfg = save_lead_config(
            self.conn,
            config={"duplicate_policy": "reject"},
            updated_by="admin",
            ts=TS,
        )
        self.conn.commit()
        self.assertEqual(cfg["duplicate_policy"], "reject")
        loaded = fetch_lead_config(self.conn)
        self.assertEqual(loaded["duplicate_policy"], "reject")

    def test_fetch_new_assigned_leads_notifications(self) -> None:
        row1, _, _ = create_lead(
            self.conn,
            full_name="Chua gan",
            phone="0901000001",
            email="",
            source="manual",
            auto_assign=False,
            created_by="test",
            ts=TS,
        )
        row2, _, _ = create_lead(
            self.conn,
            full_name="Da gan",
            phone="0901000002",
            email="",
            source="facebook",
            auto_assign=False,
            created_by="test",
            ts=TS,
        )
        self.conn.execute(
            "UPDATE crm_leads SET owner_id = 5 WHERE id = ?",
            (int(row2["id"]),),
        )
        self.conn.commit()
        self.assertEqual(fetch_max_lead_id(self.conn), int(row2["id"]))
        new_rows = fetch_new_assigned_leads(self.conn, after_id=int(row1["id"]))
        self.assertEqual(len(new_rows), 1)
        self.assertEqual(int(new_rows[0]["id"]), int(row2["id"]))
        self.assertEqual(fetch_new_assigned_leads(self.conn, after_id=int(row2["id"])), [])

    def test_fetch_new_facebook_leads_for_admin_notifications(self) -> None:
        row1, _, _ = create_lead(
            self.conn,
            full_name="FB chua gan",
            phone="0901000010",
            email="",
            source="facebook",
            auto_assign=False,
            created_by="webhook:facebook",
            ts=TS,
        )
        row2, _, _ = create_lead(
            self.conn,
            full_name="Manual chua gan",
            phone="0901000011",
            email="",
            source="manual",
            auto_assign=False,
            created_by="test",
            ts=TS,
        )
        self.conn.commit()
        new_rows = fetch_new_assigned_leads(self.conn, after_id=int(row1["id"]) - 1)
        self.assertEqual(new_rows, [])
        self.conn.execute(
            "UPDATE crm_leads SET owner_id = 5 WHERE id = ?",
            (int(row1["id"]),),
        )
        self.conn.commit()
        new_rows = fetch_new_assigned_leads(self.conn, after_id=int(row1["id"]) - 1)
        ids = {int(r["id"]) for r in new_rows}
        self.assertIn(int(row1["id"]), ids)
        self.assertNotIn(int(row2["id"]), ids)

    def test_fetch_duplicate_facebook_leads_for_admin_notifications(self) -> None:
        row1, _, _ = create_lead(
            self.conn,
            full_name="FB goc",
            phone="0901000020",
            email="",
            source="facebook",
            auto_assign=False,
            created_by="webhook:facebook",
            ts=TS,
        )
        row2, _, _ = create_lead(
            self.conn,
            full_name="FB trung",
            phone="0901000020",
            email="",
            source="facebook",
            auto_assign=False,
            created_by="webhook:facebook",
            ts=TS,
        )
        self.conn.execute(
            "UPDATE crm_leads SET owner_id = 5 WHERE id = ?",
            (int(row1["id"]),),
        )
        self.conn.commit()
        new_rows = fetch_new_assigned_leads(self.conn, after_id=int(row1["id"]) - 1)
        ids = {int(r["id"]) for r in new_rows}
        self.assertIn(int(row1["id"]), ids)
        self.assertNotIn(int(row2["id"]), ids)
        self.assertEqual(int(row2["is_duplicate"]), 1)

    def test_delete_lead_removes_record(self) -> None:
        row, _, _ = create_lead(
            self.conn,
            full_name="To Delete",
            phone="0901000099",
            email="",
            source="manual",
            created_by="test",
            ts=TS,
        )
        lid = int(row["id"])
        log_lead_activity(
            self.conn,
            lead_id=lid,
            activity_type="note",
            content="test activity",
            created_by="test",
            ts=TS,
        )
        self.conn.commit()
        result = delete_lead(self.conn, lid, deleted_by="admin")
        self.assertEqual(result["deleted_id"], lid)
        self.assertIsNone(fetch_lead_by_id(self.conn, lid))
        cnt = self.conn.execute(
            "SELECT COUNT(*) AS c FROM crm_lead_activities WHERE lead_id = ?",
            (lid,),
        ).fetchone()
        self.assertEqual(int(cnt["c"]), 0)

    def test_delete_lead_blocks_converted_without_force(self) -> None:
        row, _, _ = create_lead(
            self.conn,
            full_name="Converted",
            phone="0901000088",
            email="",
            source="manual",
            created_by="test",
            ts=TS,
        )
        lid = int(row["id"])
        self.conn.execute(
            "UPDATE crm_leads SET converted_case_id = 99, converted_customer_id = 88 WHERE id = ?",
            (lid,),
        )
        self.conn.commit()
        with self.assertRaises(ValueError):
            delete_lead(self.conn, lid, deleted_by="admin", force=False)
        delete_lead(self.conn, lid, deleted_by="admin", force=True)
        self.assertIsNone(fetch_lead_by_id(self.conn, lid))

    def test_fetch_leads_sort_by_received_at_desc(self) -> None:
        """Danh sách sắp giảm dần theo ngày đổ về (ingested_at / created_at)."""
        row1, _, _ = create_lead(
            self.conn,
            full_name="Older FB",
            phone="0902000001",
            email="",
            source="facebook",
            created_by="test",
            ts="2026-06-10 08:00:00",
            meta={"ingested_at": "2026-06-10T08:00:00Z"},
        )
        row2, _, _ = create_lead(
            self.conn,
            full_name="Newer FB",
            phone="0902000002",
            email="",
            source="facebook",
            created_by="test",
            ts="2026-06-10 08:00:00",
            meta={"ingested_at": "2026-06-11T10:00:00Z"},
        )
        self.conn.commit()
        rows = fetch_leads(self.conn, limit=10)
        ids = [int(r["id"]) for r in rows]
        self.assertIn(int(row1["id"]), ids)
        self.assertIn(int(row2["id"]), ids)
        self.assertLess(ids.index(int(row2["id"])), ids.index(int(row1["id"])))

    def test_lead_pipeline_alert_and_facebook_times(self) -> None:
        alert, msg = lead_pipeline_alert(
            {"facebook_leadgen_id": "lg1", "awaiting_facebook_graph": True},
            source="facebook",
            owner_id=None,
            is_duplicate=False,
            created_by="webhook:facebook",
        )
        self.assertTrue(alert)
        self.assertIn("Graph API", msg)

        row, _, _ = create_lead(
            self.conn,
            full_name="FB timed",
            phone="0903000001",
            email="",
            source="facebook",
            auto_assign=False,
            meta={
                "facebook_leadgen_id": "lg99",
                "facebook_created_time": "2026-06-11T08:30:00+0000",
                "ingested_at": "2026-06-11 08:31:00",
            },
            created_by="webhook:facebook",
            ts=TS,
        )
        self.conn.execute(
            "UPDATE crm_leads SET owner_id = 3 WHERE id = ?",
            (int(row["id"]),),
        )
        self.conn.execute(
            """
            INSERT INTO crm_lead_assignment_logs
                (lead_id, from_user_id, to_user_id, reason, created_by, created_at)
            VALUES (?, NULL, 3, 'test', 'admin', ?)
            """,
            (int(row["id"]), "2026-06-11 08:32:00"),
        )
        self.conn.commit()
        out = lead_row_to_dict(fetch_lead_by_id(self.conn, int(row["id"])), self.conn)
        self.assertEqual(out["received_at"], "2026-06-11 08:30:00")
        self.assertEqual(out["facebook_received_at"], "2026-06-11 08:30:00")
        self.assertEqual(out["assigned_at"], "2026-06-11 08:32:00")
        self.assertFalse(out["pipeline_alert"])

    def test_lead_received_at_manual_fallback_created_at(self) -> None:
        """Lead nhập tay / webform không có meta → received_at = created_at."""
        row, _, _ = create_lead(
            self.conn,
            full_name="Manual lead",
            phone="0904000001",
            email="",
            source="manual",
            created_by="admin",
            ts="2026-06-12 14:00:00",
        )
        self.conn.commit()
        out = lead_row_to_dict(fetch_lead_by_id(self.conn, int(row["id"])), self.conn)
        self.assertEqual(out["received_at"], "2026-06-12 14:00:00")
        self.assertEqual(out["facebook_received_at"], out["received_at"])

        row_zalo, _, _ = create_lead(
            self.conn,
            full_name="Zalo lead",
            phone="0904000002",
            email="",
            source="zalo",
            created_by="webhook:zalo",
            ts="2026-06-12 14:00:00",
            meta={"ingested_at": "2026-06-12T09:15:00Z"},
        )
        self.conn.commit()
        out_z = lead_row_to_dict(fetch_lead_by_id(self.conn, int(row_zalo["id"])), self.conn)
        self.assertEqual(out_z["received_at"], "2026-06-12 09:15:00")

    def test_create_lead_auto_ingest_sets_ingested_at(self) -> None:
        """Webhook / system:ingest tự ghi meta.ingested_at; nhập tay thì không."""
        row_sys, _, _ = create_lead(
            self.conn,
            full_name="Form web",
            phone="0905000001",
            email="",
            source="website",
            created_by="system:ingest",
            ts="2026-06-15 10:00:00",
            meta={"ingest_channel": "website_form", "ingest_site": "landing-ptt"},
        )
        out_sys = lead_row_to_dict(fetch_lead_by_id(self.conn, int(row_sys["id"])), self.conn)
        self.assertEqual(out_sys["meta"].get("ingested_at"), "2026-06-15 10:00:00")
        self.assertEqual(out_sys["meta"].get("ingest_channel"), "website_form")
        self.assertEqual(out_sys["received_at"], "2026-06-15 10:00:00")

        row_wh, _, _ = create_lead(
            self.conn,
            full_name="Webhook generic",
            phone="0905000002",
            email="",
            source="api",
            created_by="webhook:generic",
            ts="2026-06-15 11:00:00",
        )
        out_wh = lead_row_to_dict(fetch_lead_by_id(self.conn, int(row_wh["id"])), self.conn)
        self.assertEqual(out_wh["meta"].get("ingested_at"), "2026-06-15 11:00:00")

        row_manual, _, _ = create_lead(
            self.conn,
            full_name="Manual",
            phone="0905000003",
            email="",
            source="manual",
            created_by="admin",
            ts="2026-06-15 12:00:00",
        )
        out_manual = lead_row_to_dict(fetch_lead_by_id(self.conn, int(row_manual["id"])), self.conn)
        self.assertNotIn("ingested_at", out_manual["meta"])
        self.assertEqual(out_manual["received_at"], "2026-06-15 12:00:00")

        row_fb, _, _ = create_lead(
            self.conn,
            full_name="FB keep meta",
            phone="0905000004",
            email="",
            source="facebook",
            created_by="webhook:facebook",
            ts="2026-06-15 13:00:00",
            meta={"ingested_at": "2026-06-01 08:00:00"},
        )
        out_fb = lead_row_to_dict(fetch_lead_by_id(self.conn, int(row_fb["id"])), self.conn)
        self.assertEqual(out_fb["meta"].get("ingested_at"), "2026-06-01 08:00:00")

    def test_lead_pipeline_alert_unassigned_manual(self) -> None:
        alert, msg = lead_pipeline_alert(
            {},
            source="manual",
            owner_id=None,
            is_duplicate=False,
        )
        self.assertTrue(alert)
        self.assertIn("Chưa gán owner", msg)

        alert_dup, _ = lead_pipeline_alert(
            {},
            source="manual",
            owner_id=None,
            is_duplicate=True,
        )
        self.assertFalse(alert_dup)


if __name__ == "__main__":
    unittest.main()
