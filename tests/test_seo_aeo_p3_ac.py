"""Tests for P3a–c — task deep link, assignee picker, cron auth."""
from __future__ import annotations

import os
import sqlite3
import unittest
from unittest.mock import patch

from ptt_seo import schema as seo_schema
from ptt_seo.cron import run_daily_cron, run_weekly_cron, seo_cron_local_allowed, seo_cron_secret_ok
from ptt_seo.p2_schema import ensure_p2_schema
from ptt_seo.technical import create_issue, list_issues, update_issue
from ptt_seo.technical_tasks import (
    create_task_for_issue,
    enrich_issues,
    list_assignee_staff,
    task_workflow_url,
)


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
        CREATE TABLE crm_staff (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL DEFAULT '',
            job_title TEXT NOT NULL DEFAULT '',
            department TEXT NOT NULL DEFAULT '',
            active INTEGER NOT NULL DEFAULT 1
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


class TestP3TaskDeepLink(unittest.TestCase):
    def test_task_workflow_url(self) -> None:
        url = task_workflow_url(42, 7)
        self.assertEqual(url, "/crm/service-delivery/42#task-card-7")

    def test_enrich_issues_backfills_lifecycle(self) -> None:
        crm = _mem_crm_conn()
        seo = _mem_seo_conn()
        crm.execute("INSERT INTO crm_customers (name) VALUES ('Acme')")
        crm.execute(
            "INSERT INTO crm_service_lifecycle (customer_id, service_slug) VALUES (1, 'dich-vu-seo-tong-the')"
        )
        crm.commit()
        iid = create_issue(seo, 1, {"url": "https://x.com", "issue_type": "404", "severity": "high"})
        out = create_task_for_issue(crm, seo, iid)
        seo.execute("UPDATE seo_technical_issues SET lifecycle_id = NULL WHERE id = ?", (iid,))
        seo.commit()
        rows = enrich_issues(crm, list_issues(seo, 1))
        self.assertEqual(len(rows), 1)
        self.assertIn("task_url", rows[0])
        self.assertIn("#task-card-", rows[0]["task_url"])
        self.assertEqual(rows[0]["lifecycle_id"], out["lifecycle_id"])

    def test_existing_task_backfills_lifecycle(self) -> None:
        crm = _mem_crm_conn()
        seo = _mem_seo_conn()
        crm.execute("INSERT INTO crm_customers (name) VALUES ('X')")
        crm.execute(
            "INSERT INTO crm_service_lifecycle (customer_id, service_slug) VALUES (1, 'dich-vu-aeo')"
        )
        crm.commit()
        iid = create_issue(seo, 1, {"url": "https://a.com", "issue_type": "dup", "severity": "high"})
        first = create_task_for_issue(crm, seo, iid)
        seo.execute("UPDATE seo_technical_issues SET lifecycle_id = NULL WHERE id = ?", (iid,))
        seo.commit()
        second = create_task_for_issue(crm, seo, iid)
        self.assertTrue(second.get("existing"))
        self.assertIsNotNone(second.get("task_url"))
        self.assertEqual(second["task_id"], first["task_id"])


class TestP3Assignees(unittest.TestCase):
    def test_list_assignee_staff_active_only(self) -> None:
        crm = _mem_crm_conn()
        crm.execute("INSERT INTO crm_staff (name, active) VALUES ('Alice', 1), ('Bob', 0)")
        crm.commit()
        staff = list_assignee_staff(crm)
        self.assertEqual(len(staff), 1)
        self.assertEqual(staff[0]["name"], "Alice")

    def test_update_issue_clear_assignee(self) -> None:
        seo = _mem_seo_conn()
        iid = create_issue(seo, 1, {"url": "https://z.com", "severity": "low"})
        update_issue(seo, iid, {"assignee_id": 5})
        item = update_issue(seo, iid, {"assignee_id": None})
        self.assertIsNone(item.get("assignee_id"))


class TestP3Cron(unittest.TestCase):
    def test_cron_secret_ok(self) -> None:
        with patch.dict(os.environ, {"PTT_SEO_CRON_SECRET": "test-secret"}, clear=False):
            self.assertTrue(seo_cron_secret_ok("Bearer test-secret"))
            self.assertFalse(seo_cron_secret_ok("Bearer wrong"))
            self.assertFalse(seo_cron_secret_ok(None))

    def test_cron_local_allowed(self) -> None:
        self.assertTrue(seo_cron_local_allowed("127.0.0.1", "localhost:8002"))
        with patch.dict(os.environ, {"PTT_SEO_CRON_ALLOW_LOCAL": "0"}, clear=False):
            self.assertFalse(seo_cron_local_allowed("127.0.0.1", "localhost"))

    @patch.dict(os.environ, {"PTT_GSC_SYNC_ENABLED": "0", "PTT_GA4_SYNC_ENABLED": "0"}, clear=False)
    @patch("ptt_seo.db.crm_connection")
    @patch("ptt_seo.db.seo_write")
    @patch("ptt_seo.report_schedule.run_due_schedules")
    def test_run_daily_cron_skips_sync(self, mock_due, mock_seo_write, mock_crm) -> None:
        mock_due.return_value = {"ok": True, "processed": 0}
        mock_seo_write.return_value.__enter__ = lambda s: sqlite3.connect(":memory:")
        mock_seo_write.return_value.__exit__ = lambda s, *a: None
        mock_crm.return_value.__enter__ = lambda s: sqlite3.connect(":memory:")
        mock_crm.return_value.__exit__ = lambda s, *a: None
        out = run_daily_cron(days=7)
        self.assertTrue(out["ok"])
        self.assertTrue(out["jobs"]["gsc"].get("skipped"))
        self.assertTrue(out["jobs"]["ga4"].get("skipped"))

    @patch.dict(
        os.environ,
        {
            "PTT_FRESHNESS_SCAN_ENABLED": "0",
            "PTT_SERP_SCHEDULE_ENABLED": "0",
            "PTT_CWV_ENABLED": "0",
            "PTT_AEO_SCHEDULE_ENABLED": "0",
            "PTT_CRAWL_REMINDER_ENABLED": "0",
            "PTT_CRAWL_CONNECTOR_ENABLED": "0",
            "PTT_RANK_LIVE_ENABLED": "0",
        },
        clear=False,
    )
    def test_run_weekly_cron_disabled(self) -> None:
        out = run_weekly_cron()
        self.assertTrue(out["ok"])
        self.assertTrue(out["jobs"]["freshness"].get("skipped"))
        self.assertTrue(out["jobs"]["serp_capture"].get("skipped"))
        self.assertTrue(out["jobs"]["cwv_capture"].get("skipped"))
        self.assertTrue(out["jobs"]["aeo_schedule"].get("skipped"))
        self.assertTrue(out["jobs"]["crawl_reminder"].get("skipped"))


if __name__ == "__main__":
    unittest.main()
