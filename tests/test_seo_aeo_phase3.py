"""Tests for SEO/AEO Ops Phase 3 — technical, GSC, reports, automation."""
from __future__ import annotations


import os
import unittest

if os.environ.get("PTT_RUN_FLASK_TESTS") != "1":
    raise unittest.SkipTest(
        "Flask HTTP removed — set PTT_RUN_FLASK_TESTS=1 to run integration tests"
    )
import sqlite3
import unittest

from ptt_seo import schema as seo_schema
from ptt_seo.automation import create_alert, list_alerts, resolve_alert, run_alert_checks
from ptt_seo.connectors.gsc import gsc_summary, import_gsc_csv, list_sync_runs
from ptt_seo.report import dashboard
from ptt_seo.technical import (
    count_open_critical,
    create_issue,
    import_crawl_csv,
    list_issues,
    severity_matrix,
    update_issue,
)


def _mem_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """

        CREATE TABLE crm_customers (id INTEGER PRIMARY KEY, name TEXT DEFAULT '', company TEXT DEFAULT '');
        CREATE TABLE crm_service_lifecycle (
            id INTEGER PRIMARY KEY, customer_id INTEGER, service_slug TEXT, stage TEXT, status TEXT
        );
        """
    )
    seo_schema.ensure_schema(conn)
    conn.execute("INSERT INTO crm_customers (name) VALUES ('Test Co')")
    conn.commit()
    return conn


class TestTechnical(unittest.TestCase):
    def test_create_and_list_issues(self) -> None:
        conn = _mem_conn()
        iid = create_issue(
            conn, 1, {"url": "https://example.com/a", "issue_type": "404", "severity": "critical"}
        )
        rows = list_issues(conn, 1)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["id"], iid)
        self.assertEqual(count_open_critical(conn, 1), 1)

    def test_severity_matrix(self) -> None:
        conn = _mem_conn()
        create_issue(conn, 1, {"url": "https://x.com/1", "severity": "critical"})
        create_issue(conn, 1, {"url": "https://x.com/2", "severity": "high"})
        m = severity_matrix(conn, 1)
        self.assertEqual(m["critical"], 1)
        self.assertEqual(m["high"], 1)

    def test_import_crawl_csv(self) -> None:
        conn = _mem_conn()
        csv_text = "url,issue_type,severity,description\nhttps://a.com,broken_link,high,test\n"
        n = import_crawl_csv(conn, 1, csv_text)
        self.assertEqual(n, 1)
        self.assertEqual(len(list_issues(conn, 1)), 1)

    def test_close_issue(self) -> None:
        conn = _mem_conn()
        iid = create_issue(conn, 1, {"url": "https://b.com", "severity": "low"})
        item = update_issue(conn, iid, {"status": "closed"})
        self.assertEqual(item["status"], "closed")
        self.assertIsNotNone(item.get("resolved_at"))


class TestGscConnector(unittest.TestCase):
    def test_import_gsc_csv(self) -> None:
        conn = _mem_conn()
        csv_text = "Query,Clicks,Impressions,CTR,Position\nseo agency,10,100,10%,5.2\n"
        result = import_gsc_csv(conn, 1, csv_text, stat_date="2026-07-01")
        self.assertTrue(result["ok"])
        self.assertEqual(result["rows_imported"], 1)
        summary = gsc_summary(conn, 1, days=90)
        self.assertEqual(summary["clicks"], 10)
        runs = list_sync_runs(conn, 1)
        self.assertEqual(len(runs), 1)
        self.assertEqual(runs[0]["status"], "done")


class TestReports(unittest.TestCase):
    def test_executive_dashboard(self) -> None:
        conn = _mem_conn()
        create_issue(conn, 1, {"url": "https://c.com", "severity": "critical"})
        import_gsc_csv(conn, 1, "Query,Clicks,Impressions\nkw,5,50\n", stat_date="2026-07-15")
        data = dashboard(conn, customer_id=1, dashboard_type="executive")
        self.assertEqual(data["type"], "executive")
        self.assertEqual(data["critical_issues"], 1)
        self.assertGreaterEqual(data["gsc"]["clicks"], 5)

    def test_executive_dashboard_attribution(self) -> None:
        conn = _mem_conn()
        conn.execute(
            """
            INSERT INTO seo_ga4_daily_stats (
                customer_id, stat_date, landing_page, source_medium,
                sessions, users, pageviews, conversions, revenue, created_at
            ) VALUES (1, date('now'), '/landing', 'google / organic', 50, 40, 100, 4, 800, '2026-07-01')
            """
        )
        conn.commit()
        data = dashboard(conn, customer_id=1, dashboard_type="executive")
        self.assertIn("attribution", data)
        self.assertEqual(data["attribution"]["summary"]["revenue"], 800.0)
        self.assertEqual(len(data["attribution"]["top_pages"]), 1)

    def test_technical_dashboard(self) -> None:
        conn = _mem_conn()
        create_issue(conn, 1, {"url": "https://d.com", "severity": "medium"})
        data = dashboard(conn, customer_id=1, dashboard_type="technical")
        self.assertEqual(data["severity"]["medium"], 1)
        self.assertEqual(len(data["issues"]), 1)


class TestAutomation(unittest.TestCase):
    def test_create_and_resolve_alert(self) -> None:
        conn = _mem_conn()
        aid = create_alert(conn, customer_id=1, alert_type="test", message="Hello")
        self.assertIsNotNone(aid)
        alerts = list_alerts(conn, status="open")
        self.assertEqual(len(alerts), 1)
        assert aid is not None
        resolve_alert(conn, aid)
        self.assertEqual(len(list_alerts(conn, status="open")), 0)

    def test_run_alert_checks_critical(self) -> None:
        conn = _mem_conn()
        create_issue(conn, 1, {"url": "https://e.com", "severity": "critical"})
        created = run_alert_checks(conn)
        types = [c["type"] for c in created]
        self.assertIn("critical_issues", types)


if __name__ == "__main__":
    unittest.main()
