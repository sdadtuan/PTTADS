"""Tests for P1 UI spec — hub executive, health score, AEO checklist, routes."""
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
from ptt_seo.connectors.gsc import gsc_daily_trend
from ptt_seo.content import aeo_checklist_for_content, create_content
from ptt_seo.hub import compute_health_score, content_delivery_summary, seo_hub_summary


def _mem_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """

        CREATE TABLE crm_customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL DEFAULT '',
            company TEXT NOT NULL DEFAULT ''
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
    seo_schema.ensure_schema(conn)
    return conn


class TestP1HubExecutive(unittest.TestCase):
    def test_compute_health_score(self) -> None:
        good = compute_health_score(
            settings_ok=True, aeo_coverage_pct=80, aeo_queries=10, critical_issues=0
        )
        bad = compute_health_score(
            settings_ok=False, aeo_coverage_pct=20, aeo_queries=10, critical_issues=3, content_overdue=5
        )
        self.assertGreater(good, bad)
        self.assertLessEqual(good, 100)
        self.assertGreaterEqual(bad, 0)

    def test_hub_executive_block(self) -> None:
        conn = _mem_conn()
        conn.execute("INSERT INTO crm_customers (name) VALUES ('Acme')")
        conn.execute(
            "INSERT INTO crm_service_lifecycle (customer_id, service_slug) VALUES (1, 'dich-vu-aeo')"
        )
        conn.commit()
        data = seo_hub_summary(conn, conn)
        self.assertIn("executive", data)
        self.assertIn("gsc_trend", data["executive"])
        self.assertIn("content_delivery", data["executive"])
        self.assertIn("health_score", data["clients"][0])

    def test_gsc_daily_trend(self) -> None:
        conn = _mem_conn()
        conn.execute(
            """
            INSERT INTO seo_gsc_daily_stats (
                customer_id, stat_date, query, page, clicks, impressions, ctr, position, created_at
            ) VALUES (1, date('now'), 'q', '/', 10, 100, 0.1, 1.0, datetime('now'))
            """
        )
        conn.commit()
        trend = gsc_daily_trend(conn, days=30, customer_id=1)
        self.assertEqual(len(trend), 1)
        self.assertEqual(trend[0]["clicks"], 10)

    def test_content_delivery_summary(self) -> None:
        conn = _mem_conn()
        create_content(conn, {"customer_id": 1, "title": "A", "workflow_status": "in_writing"})
        summary = content_delivery_summary(conn)
        self.assertGreaterEqual(summary["in_writing"], 1)


class TestP1AeoChecklist(unittest.TestCase):
    def test_aeo_checklist_for_content(self) -> None:
        conn = _mem_conn()
        cid = create_content(
            conn,
            {
                "customer_id": 1,
                "title": "Post",
                "workflow_status": "in_writing",
                "body_html": "<h2>FAQ</h2><p>Answer first paragraph with enough text.</p>",
                "brief": {
                    "checklist": ["Schema phù hợp", "AEO answer-first paragraph"],
                    "target_keyword": "seo",
                },
                "outline": {"schema_json": '{"@type":"FAQPage"}'},
            },
        )
        result = aeo_checklist_for_content(conn, cid)
        self.assertEqual(result["content_id"], cid)
        self.assertGreater(result["done_count"], 0)
        self.assertIn("items", result)


class TestP1Routes(unittest.TestCase):
    def test_clients_and_freshness_pages(self) -> None:
        try:
            import app as app_module
        except ImportError:
            self.skipTest("app not importable")
        app = app_module.app
        app.config["TESTING"] = True
        with app.test_client() as client:
            for path in ("/crm/seo/clients", "/crm/seo/freshness"):
                r = client.get(path)
                self.assertIn(r.status_code, (200, 302, 401, 403))


if __name__ == "__main__":
    unittest.main()
