"""Tests for P2 — technical→CRM task + scheduled reports."""
from __future__ import annotations


import os
import unittest

if os.environ.get("PTT_RUN_FLASK_TESTS") != "1":
    raise unittest.SkipTest(
        "Flask HTTP removed — set PTT_RUN_FLASK_TESTS=1 to run integration tests"
    )
import sqlite3
import unittest
from datetime import date, timedelta

from ptt_seo import schema as seo_schema
from ptt_seo.p2_schema import ensure_p2_schema
from ptt_seo.report_schedule import (
    compute_next_run,
    create_schedule,
    list_due_schedules,
    run_due_schedules,
    run_schedule,
)
from ptt_seo.technical import create_issue
from ptt_seo.technical_tasks import create_task_for_issue, pick_seo_lifecycle


def _mem_crm_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """

        CREATE TABLE crm_customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE crm_service_lifecycle (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER NOT NULL,
            service_slug TEXT NOT NULL DEFAULT '',
            stage TEXT NOT NULL DEFAULT 'delivery',
            status TEXT NOT NULL DEFAULT 'active'
        );
        """
    )
    import crm_svc_tasks

    crm_svc_tasks.ensure_schema(conn)
    return conn


def _mem_seo_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    seo_schema.ensure_schema(conn)
    ensure_p2_schema(conn)
    return conn


class TestTechnicalTaskBridge(unittest.TestCase):
    def test_create_task_for_issue(self) -> None:
        crm = _mem_crm_conn()
        seo = _mem_seo_conn()
        crm.execute("INSERT INTO crm_customers (name) VALUES ('Acme')")
        crm.execute(
            "INSERT INTO crm_service_lifecycle (customer_id, service_slug) VALUES (1, 'dich-vu-seo-tong-the')"
        )
        crm.commit()
        iid = create_issue(
            seo,
            1,
            {"url": "https://x.com/bad", "issue_type": "404", "severity": "critical"},
        )
        lc = pick_seo_lifecycle(crm, 1)
        self.assertIsNotNone(lc)
        out = create_task_for_issue(crm, seo, iid)
        self.assertTrue(out["ok"])
        self.assertGreater(out["task_id"], 0)
        row = seo.execute(
            "SELECT crm_task_id, status FROM seo_technical_issues WHERE id = ?", (iid,)
        ).fetchone()
        self.assertEqual(int(row["crm_task_id"]), out["task_id"])
        self.assertEqual(row["status"], "assigned")
        task = crm.execute(
            "SELECT title FROM crm_svc_tasks WHERE id = ?", (out["task_id"],)
        ).fetchone()
        self.assertIn("404", task["title"])

    def test_create_task_idempotent(self) -> None:
        crm = _mem_crm_conn()
        seo = _mem_seo_conn()
        crm.execute("INSERT INTO crm_customers (name) VALUES ('X')")
        crm.execute(
            "INSERT INTO crm_service_lifecycle (customer_id, service_slug) VALUES (1, 'dich-vu-aeo')"
        )
        crm.commit()
        iid = create_issue(seo, 1, {"url": "https://a.com", "issue_type": "dup", "severity": "high"})
        first = create_task_for_issue(crm, seo, iid)
        second = create_task_for_issue(crm, seo, iid)
        self.assertEqual(first["task_id"], second["task_id"])
        self.assertTrue(second.get("existing"))


class TestReportSchedule(unittest.TestCase):
    def test_compute_next_run_weekly(self) -> None:
        monday = date(2026, 7, 20)  # Monday
        nxt = compute_next_run(cadence="weekly", day_of_week=0, from_date=monday)
        self.assertEqual(nxt, (monday + timedelta(days=7)).isoformat())

    def test_create_and_run_schedule_skipped_without_smtp(self) -> None:
        seo = _mem_seo_conn()
        sid = create_schedule(
            seo,
            1,
            {
                "recipient_emails": ["test@example.com"],
                "dashboard_type": "executive",
                "cadence": "weekly",
                "day_of_week": 0,
            },
        )
        seo.execute(
            "UPDATE seo_report_schedules SET next_run_at = ? WHERE id = ?",
            (date.today().isoformat(), sid),
        )
        seo.commit()
        due = list_due_schedules(seo)
        self.assertEqual(len(due), 1)
        result = run_schedule(seo, sid)
        self.assertTrue(result["ok"])
        self.assertIn(result["status"], ("skipped", "sent"))

    def test_run_due_schedules_batch(self) -> None:
        seo = _mem_seo_conn()
        sid = create_schedule(
            seo,
            2,
            {"recipient_emails": ["a@b.com"], "cadence": "monthly", "day_of_month": 1},
        )
        seo.execute(
            "UPDATE seo_report_schedules SET next_run_at = ? WHERE id = ?",
            (date.today().isoformat(), sid),
        )
        seo.commit()
        out = run_due_schedules(seo)
        self.assertEqual(out["processed"], 1)


if __name__ == "__main__":
    unittest.main()
