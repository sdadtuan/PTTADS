"""Pipeline chăm sóc lead 8 bước — tiến độ & hoàn thành bước."""
from __future__ import annotations

import sqlite3
import unittest

from crm_lead_care_pipeline import (
    CARE_STAGE_KEYS,
    care_pipeline_state,
    complete_lead_care_stage,
    ensure_lead_care_pipeline_schema,
)
from crm_lead_store import (
    activity_row_to_dict,
    create_lead,
    ensure_lead_schema,
    fetch_lead_by_id,
    lead_row_to_dict,
    log_lead_activity,
)
from crm_re_projects import ensure_re_projects_schema


TS = "2026-05-25 10:00:00"


class LeadCarePipelineTest(unittest.TestCase):
    def setUp(self) -> None:
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        ensure_re_projects_schema(self.conn)
        ensure_lead_schema(self.conn)
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS crm_assignment_state (
                pool_key TEXT PRIMARY KEY,
                last_staff_id INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS crm_departments (
                id INTEGER PRIMARY KEY,
                code TEXT NOT NULL DEFAULT '',
                name TEXT NOT NULL,
                active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT '',
                updated_at TEXT NOT NULL DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS crm_staff (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                active INTEGER NOT NULL DEFAULT 1,
                internal_code TEXT NOT NULL DEFAULT '',
                department_id INTEGER
            );
            INSERT INTO crm_departments (id, code, name, active) VALUES (1, 'kd', 'KD', 1);
            INSERT INTO crm_staff (id, name, active, internal_code, department_id)
            VALUES (1, 'NV A', 1, 'NV-01', 1);
            """
        )
        self.conn.commit()

    def tearDown(self) -> None:
        self.conn.close()

    def test_complete_stage_advances_and_marks_done(self) -> None:
        row, _, _ = create_lead(
            self.conn,
            full_name="Pipe Lead",
            phone="0901000001",
            email="",
            status="new",
            owner_id=1,
            created_by="test",
            ts=TS,
        )
        lid = int(row["id"])
        self.conn.commit()
        out = complete_lead_care_stage(
            self.conn,
            lead_id=lid,
            stage_key="intake",
            note="Phân loại Hot",
            created_by="test",
            ts="2026-05-25 10:05:00",
        )
        self.conn.commit()
        d = dict(out)
        self.assertEqual(str(d["care_stage_current"]), "first_contact")
        done = care_pipeline_state(
            status=str(d["status"]),
            care_stage_current=str(d["care_stage_current"]),
            care_stages_done_json=str(d["care_stages_done_json"]),
        )
        self.assertIn("intake", done["stages_done"])
        self.assertEqual(done["current_stage_key"], "first_contact")

    def test_complete_first_contact_updates_status(self) -> None:
        row, _, _ = create_lead(
            self.conn,
            full_name="Contact Lead",
            phone="0901000002",
            email="",
            need="Tu van",
            status="new",
            owner_id=1,
            created_by="test",
            ts=TS,
        )
        lid = int(row["id"])
        complete_lead_care_stage(
            self.conn,
            lead_id=lid,
            stage_key="intake",
            created_by="test",
            ts="2026-05-25 10:05:00",
        )
        complete_lead_care_stage(
            self.conn,
            lead_id=lid,
            stage_key="first_contact",
            created_by="test",
            ts="2026-05-25 10:10:00",
        )
        self.conn.commit()
        lead = fetch_lead_by_id(self.conn, lid)
        assert lead is not None
        self.assertEqual(str(lead["status"]), "qualify")
        self.assertEqual(str(lead["care_stage_current"]), "qualify")

    def test_cannot_skip_stage(self) -> None:
        row, _, _ = create_lead(
            self.conn,
            full_name="Skip Lead",
            phone="0901000003",
            email="",
            status="new",
            owner_id=1,
            created_by="test",
            ts=TS,
        )
        lid = int(row["id"])
        with self.assertRaises(ValueError):
            complete_lead_care_stage(
                self.conn,
                lead_id=lid,
                stage_key="qualify",
                created_by="test",
                ts=TS,
            )

    def test_lead_row_includes_care_pipeline(self) -> None:
        row, _, _ = create_lead(
            self.conn,
            full_name="Dict Lead",
            phone="0901000004",
            email="",
            status="new",
            owner_id=1,
            created_by="test",
            ts=TS,
        )
        lid = int(row["id"])
        self.conn.commit()
        lead = fetch_lead_by_id(self.conn, lid)
        out = lead_row_to_dict(lead, self.conn)
        pipe = out.get("care_pipeline") or {}
        self.assertEqual(pipe.get("current_stage_key"), "intake")
        self.assertEqual(len(pipe.get("stages") or []), len(CARE_STAGE_KEYS))

    def test_care_report_activity_stores_stage_key(self) -> None:
        row, _, _ = create_lead(
            self.conn,
            full_name="Report Lead",
            phone="0901000005",
            email="",
            status="new",
            owner_id=1,
            created_by="test",
            ts=TS,
        )
        lid = int(row["id"])
        act = log_lead_activity(
            self.conn,
            lead_id=lid,
            activity_type="call",
            content="Đã gọi lần 1",
            care_contact_type="phone",
            care_status="contacted",
            care_stage_key="intake",
            created_by="test",
            ts="2026-05-25 10:05:00",
        )
        self.conn.commit()
        out = activity_row_to_dict(act)
        self.assertEqual(out.get("care_stage_key"), "intake")
        self.assertEqual(out.get("care_stage_label"), "Tiếp nhận & phân loại")

    def test_care_report_syncs_status_to_current_stage(self) -> None:
        row, _, _ = create_lead(
            self.conn,
            full_name="Sync Lead",
            phone="0901000006",
            email="",
            need="Tu van",
            status="new",
            owner_id=1,
            created_by="test",
            ts=TS,
        )
        lid = int(row["id"])
        complete_lead_care_stage(
            self.conn,
            lead_id=lid,
            stage_key="intake",
            created_by="test",
            ts="2026-05-25 10:05:00",
        )
        self.conn.commit()
        log_lead_activity(
            self.conn,
            lead_id=lid,
            activity_type="call",
            content="Goi lan 1",
            care_contact_type="goi_dien",
            care_status="da_lien_he_thanh_cong",
            care_stage_key="first_contact",
            created_by="test",
            ts="2026-05-25 10:10:00",
        )
        self.conn.commit()
        lead = fetch_lead_by_id(self.conn, lid)
        assert lead is not None
        self.assertEqual(str(lead["status"]), "first_contact")
        out = lead_row_to_dict(lead, self.conn)
        self.assertEqual(out.get("status_label"), "Liên hệ lần đầu")


if __name__ == "__main__":
    unittest.main()
