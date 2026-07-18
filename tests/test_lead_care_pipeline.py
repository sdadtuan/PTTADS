"""Pipeline chăm sóc lead B2-only — tiến độ & gate pre-sales."""
from __future__ import annotations

import sqlite3
import unittest

from crm_lead_care_pipeline import (
    CARE_STAGE_KEYS,
    CONTACT_OK_CARE_STATUS,
    admin_backfill_presales_care_gate,
    care_pipeline_state,
    complete_lead_care_stage,
    ensure_lead_care_pipeline_schema,
    list_leads_needing_presales_care_backfill,
    presales_care_gate_state,
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


def _seed_care_report(
    conn: sqlite3.Connection,
    lead_id: int,
    stage_key: str,
    *,
    care_status: str = CONTACT_OK_CARE_STATUS,
    ts: str = TS,
    created_by: str = "test",
) -> None:
    log_lead_activity(
        conn,
        lead_id=lead_id,
        activity_type="call",
        content="Báo cáo chăm sóc test",
        care_contact_type="goi_dien",
        care_status=care_status,
        care_stage_key=stage_key,
        created_by=created_by,
        ts=ts,
    )


class LeadCarePipelineTest(unittest.TestCase):
    def setUp(self) -> None:
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        ensure_re_projects_schema(self.conn)
        ensure_lead_schema(self.conn)
        ensure_lead_care_pipeline_schema(self.conn)
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

    def test_new_lead_starts_at_b2(self) -> None:
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
        self.conn.commit()
        d = lead_row_to_dict(fetch_lead_by_id(self.conn, int(row["id"])), self.conn)
        pipe = d.get("care_pipeline") or {}
        self.assertEqual(pipe.get("current_stage_key"), "first_contact")
        self.assertEqual(len(pipe.get("stages") or []), len(CARE_STAGE_KEYS))

    def test_complete_b2_marks_done_and_updates_status(self) -> None:
        row, _, _ = create_lead(
            self.conn,
            full_name="B2 Lead",
            phone="0901000002",
            email="",
            status="new",
            owner_id=1,
            created_by="test",
            ts=TS,
        )
        lid = int(row["id"])
        _seed_care_report(self.conn, lid, "first_contact", ts="2026-05-25 10:04:00")
        out = complete_lead_care_stage(
            self.conn,
            lead_id=lid,
            stage_key="first_contact",
            note="Da lien he lan dau",
            created_by="test",
            ts="2026-05-25 10:05:00",
        )
        self.conn.commit()
        d = dict(out)
        self.assertEqual(str(d["care_stage_current"]), "first_contact")
        self.assertEqual(str(d["status"]), "first_contact")
        done = care_pipeline_state(
            status=str(d["status"]),
            care_stage_current=str(d["care_stage_current"]),
            care_stages_done_json=str(d["care_stages_done_json"]),
        )
        self.assertIn("first_contact", done["stages_done"])
        self.assertTrue(done["all_complete"])

    def test_cannot_complete_invalid_stage(self) -> None:
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
                note="Skip step",
                created_by="test",
                ts=TS,
            )

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
            care_stage_key="first_contact",
            created_by="test",
            ts="2026-05-25 10:05:00",
        )
        self.conn.commit()
        out = activity_row_to_dict(act)
        self.assertEqual(out.get("care_stage_key"), "first_contact")
        self.assertEqual(out.get("care_stage_label"), "Liên hệ lần đầu")

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
        log_lead_activity(
            self.conn,
            lead_id=lid,
            activity_type="call",
            content="Goi lan 1",
            care_contact_type="goi_dien",
            care_status=CONTACT_OK_CARE_STATUS,
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

    def test_complete_requires_care_report(self) -> None:
        row, _, _ = create_lead(
            self.conn,
            full_name="No Report",
            phone="0901000007",
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
                stage_key="first_contact",
                note="Co note nhung khong co bao cao",
                created_by="test",
                ts=TS,
            )

    def test_complete_requires_contact_ok_report(self) -> None:
        row, _, _ = create_lead(
            self.conn,
            full_name="No Contact OK",
            phone="0901000011",
            email="",
            status="new",
            owner_id=1,
            created_by="test",
            ts=TS,
        )
        lid = int(row["id"])
        _seed_care_report(
            self.conn,
            lid,
            "first_contact",
            care_status="khong_nghe_may",
        )
        with self.assertRaises(ValueError) as ctx:
            complete_lead_care_stage(
                self.conn,
                lead_id=lid,
                stage_key="first_contact",
                note="Chua lien he duoc",
                created_by="test",
                ts=TS,
            )
        self.assertIn("Liên hệ OK", str(ctx.exception))

    def test_complete_requires_note(self) -> None:
        row, _, _ = create_lead(
            self.conn,
            full_name="No Note",
            phone="0901000008",
            email="",
            status="new",
            owner_id=1,
            created_by="test",
            ts=TS,
        )
        lid = int(row["id"])
        _seed_care_report(self.conn, lid, "first_contact")
        with self.assertRaises(ValueError):
            complete_lead_care_stage(
                self.conn,
                lead_id=lid,
                stage_key="first_contact",
                note="ab",
                created_by="test",
                ts=TS,
            )

    def test_presales_care_gate_requires_b2(self) -> None:
        row, _, _ = create_lead(
            self.conn,
            full_name="Gate Lead",
            phone="0901000009",
            email="",
            status="new",
            owner_id=1,
            created_by="test",
            ts=TS,
        )
        lid = int(row["id"])
        gate = presales_care_gate_state(
            care_stage_current="first_contact",
            care_stages_done_json="{}",
        )
        self.assertFalse(gate["complete"])
        self.assertEqual(len(gate["missing_keys"]), 1)
        _seed_care_report(self.conn, lid, "first_contact", ts="2026-05-25 10:09:00")
        complete_lead_care_stage(
            self.conn,
            lead_id=lid,
            stage_key="first_contact",
            note="Xong B2",
            created_by="test",
            ts="2026-05-25 10:10:00",
        )
        lead = fetch_lead_by_id(self.conn, lid)
        assert lead is not None
        gate2 = presales_care_gate_state(
            care_stage_current=str(lead["care_stage_current"]),
            care_stages_done_json=str(lead["care_stages_done_json"]),
        )
        self.assertTrue(gate2["complete"])

    def test_admin_backfill_presales_care_gate(self) -> None:
        from crm_lead_presales import ensure_schema as ensure_presales_schema

        row, _, _ = create_lead(
            self.conn,
            full_name="Legacy Lead",
            phone="0901000010",
            email="",
            status="new",
            owner_id=1,
            created_by="test",
            ts=TS,
        )
        lid = int(row["id"])
        ensure_presales_schema(self.conn)
        self.conn.execute(
            """
            INSERT INTO crm_lead_presales
                (lead_id, service_slug, stage, status, stage_entered_at, notes, created_at, updated_at)
            VALUES (?, 'dich-vu-aeo', 'consult', 'active', ?, '', ?, ?)
            """,
            (lid, TS, TS, TS),
        )
        self.conn.commit()
        pending = list_leads_needing_presales_care_backfill(self.conn, lead_id=lid)
        self.assertEqual(len(pending), 1)
        summary = admin_backfill_presales_care_gate(
            self.conn,
            lid,
            note="Director approved legacy backfill",
            created_by="admin-test",
            ts=TS,
        )
        self.assertFalse(summary.get("skipped"))
        self.assertTrue(summary.get("gate_complete"))
        self.assertEqual(len(summary.get("stages_marked") or []), 1)
        lead = fetch_lead_by_id(self.conn, lid)
        assert lead is not None
        gate = presales_care_gate_state(
            care_stage_current=str(lead["care_stage_current"]),
            care_stages_done_json=str(lead["care_stages_done_json"]),
        )
        self.assertTrue(gate["complete"])


if __name__ == "__main__":
    unittest.main()
