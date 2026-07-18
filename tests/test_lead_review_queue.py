"""Lead Phải tra soát — quá hạn B2 chưa Liên hệ OK."""
from __future__ import annotations

import sqlite3
import unittest
from datetime import datetime, timedelta

from crm_lead_care_pipeline import CONTACT_OK_CARE_STATUS, ensure_lead_care_pipeline_schema
from crm_lead_review_queue import (
    is_lead_in_review_queue,
    lead_b2_overdue_for_review,
    normalize_b2_contact_deadline_hours,
    queue_lead_for_review,
    release_lead_from_review_queue,
    sync_b2_review_queue,
)
from crm_lead_rules import save_lead_config
from crm_lead_store import create_lead, ensure_lead_schema, fetch_lead_by_id, lead_row_to_dict, log_lead_activity
from crm_re_projects import ensure_re_projects_schema


TS = "2026-06-01 10:00:00"
ASSIGNED = "2026-06-01 08:00:00"


class LeadReviewQueueTest(unittest.TestCase):
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
                active INTEGER NOT NULL DEFAULT 1
            );
            CREATE TABLE IF NOT EXISTS crm_staff (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                active INTEGER NOT NULL DEFAULT 1,
                internal_code TEXT NOT NULL DEFAULT '',
                department_id INTEGER,
                notes TEXT NOT NULL DEFAULT '',
                sales_level TEXT NOT NULL DEFAULT ''
            );
            INSERT INTO crm_departments (id, code, name, active) VALUES (1, 'kd', 'KD', 1);
            INSERT INTO crm_staff (id, name, active, internal_code, department_id)
            VALUES (1, 'AM A', 1, 'NV-01', 1), (2, 'AM B', 1, 'NV-02', 1);
            """
        )
        save_lead_config(
            self.conn,
            config={"b2_review_queue_enabled": True, "b2_contact_deadline_hours": 24},
            updated_by="test",
            ts=TS,
        )
        self.conn.commit()

    def tearDown(self) -> None:
        self.conn.close()

    def _create_assigned_lead(self, *, assigned_at: str = ASSIGNED) -> int:
        import json

        row, _, _ = create_lead(
            self.conn,
            full_name="Review Lead",
            phone="0902000001",
            email="",
            status="new",
            owner_id=1,
            created_by="test",
            ts=assigned_at,
            meta={"auto_assigned_at": assigned_at},
        )
        lid = int(row["id"])
        self.conn.commit()
        return lid

    def test_normalize_deadline_hours_default(self) -> None:
        self.assertEqual(normalize_b2_contact_deadline_hours(None), 24)
        self.assertEqual(normalize_b2_contact_deadline_hours(48), 48)
        self.assertEqual(normalize_b2_contact_deadline_hours(999), 168)

    def test_sync_queues_overdue_lead_without_contact_ok(self) -> None:
        lid = self._create_assigned_lead()
        now_ts = (
            datetime.strptime(ASSIGNED, "%Y-%m-%d %H:%M:%S") + timedelta(hours=25)
        ).strftime("%Y-%m-%d %H:%M:%S")
        summary = sync_b2_review_queue(self.conn, ts=now_ts, actor="test")
        self.conn.commit()
        self.assertEqual(summary["queued"], 1)
        lead = fetch_lead_by_id(self.conn, lid)
        assert lead is not None
        self.assertIsNone(lead["owner_id"])
        out = lead_row_to_dict(lead, self.conn)
        self.assertTrue(out["review_queue"]["active"])

    def test_sync_skips_when_contact_ok_report_exists(self) -> None:
        lid = self._create_assigned_lead()
        log_lead_activity(
            self.conn,
            lead_id=lid,
            activity_type="call",
            content="Da lien he",
            care_contact_type="goi_dien",
            care_status=CONTACT_OK_CARE_STATUS,
            care_stage_key="first_contact",
            created_by="test",
            ts="2026-06-01 09:00:00",
        )
        now_ts = (
            datetime.strptime(ASSIGNED, "%Y-%m-%d %H:%M:%S") + timedelta(hours=25)
        ).strftime("%Y-%m-%d %H:%M:%S")
        summary = sync_b2_review_queue(self.conn, ts=now_ts, actor="test")
        self.assertEqual(summary["queued"], 0)
        lead = fetch_lead_by_id(self.conn, lid)
        assert lead is not None
        self.assertEqual(int(lead["owner_id"]), 1)

    def test_release_auto_assigns_new_owner(self) -> None:
        lid = self._create_assigned_lead()
        queue_lead_for_review(
            self.conn,
            lid,
            ts=TS,
            actor="test",
            previous_owner_id=1,
            assigned_at=ASSIGNED,
            deadline_hours=24,
        )
        self.conn.commit()
        row = release_lead_from_review_queue(
            self.conn,
            lid,
            mode="auto",
            actor="gdkd",
            ts="2026-06-01 12:00:00",
        )
        self.conn.commit()
        self.assertIsNotNone(row["owner_id"])
        self.assertNotEqual(int(row["owner_id"]), 1)
        meta = lead_row_to_dict(row, self.conn)
        self.assertFalse(meta["review_queue"]["active"])

    def test_lead_b2_overdue_respects_hours(self) -> None:
        lid = self._create_assigned_lead()
        lead = fetch_lead_by_id(self.conn, lid)
        assert lead is not None
        assigned_dt = datetime.strptime(ASSIGNED, "%Y-%m-%d %H:%M:%S")
        self.assertFalse(
            lead_b2_overdue_for_review(
                lead,
                deadline_hours=24,
                now=assigned_dt + timedelta(hours=23),
            )
        )
        self.assertTrue(
            lead_b2_overdue_for_review(
                lead,
                deadline_hours=24,
                now=assigned_dt + timedelta(hours=24),
            )
        )


if __name__ == "__main__":
    unittest.main()
