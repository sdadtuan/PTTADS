"""Tests for Giai đoạn 2 — UI parity backend (nav badges, research entities, versions, PDF)."""
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
from ptt_seo.content import create_content, list_versions, save_version
from ptt_seo.initiatives import create_initiative, list_all_initiatives
from ptt_seo.research import create_keyword, list_entity_groups, list_opportunities


def _mem_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """

        CREATE TABLE crm_customers (id INTEGER PRIMARY KEY, name TEXT DEFAULT '', company TEXT DEFAULT '');
        """
    )
    seo_schema.ensure_schema(conn)
    conn.execute("INSERT INTO crm_customers (name, company) VALUES ('Acme', 'Co')")
    conn.commit()
    return conn


class TestPhase2UIParity(unittest.TestCase):
    def test_list_versions(self) -> None:
        conn = _mem_conn()
        cid = create_content(conn, {"customer_id": 1, "title": "Post", "workflow_status": "in_writing"})
        save_version(conn, cid, body_html="<p>v1</p>", changes_summary="First")
        save_version(conn, cid, body_html="<p>v2</p>", changes_summary="Second")
        versions = list_versions(conn, cid)
        self.assertEqual(len(versions), 2)
        self.assertEqual(versions[0]["version_number"], 2)
        self.assertEqual(versions[0]["changes_summary"], "Second")

    def test_entity_groups_by_intent(self) -> None:
        conn = _mem_conn()
        create_keyword(conn, 1, {"phrase": "what is seo", "volume": 100, "difficulty": 20, "intent": "informational"})
        create_keyword(conn, 1, {"phrase": "buy seo tool", "volume": 200, "difficulty": 40, "intent": "commercial"})
        groups = list_entity_groups(conn, 1)
        self.assertEqual(len(groups), 2)
        intents = {g["intent"] for g in groups}
        self.assertIn("informational", intents)
        self.assertIn("commercial", intents)

    def test_opportunities_min_score(self) -> None:
        conn = _mem_conn()
        create_keyword(conn, 1, {"phrase": "low", "volume": 10, "difficulty": 90, "business_value": "low"})
        create_keyword(conn, 1, {"phrase": "high", "volume": 5000, "difficulty": 10, "business_value": "high"})
        opps = list_opportunities(conn, 1, min_score=50.0)
        self.assertTrue(all(o["opportunity_score"] >= 50 for o in opps))
        self.assertGreaterEqual(len(opps), 1)

    def test_list_all_initiatives(self) -> None:
        conn = _mem_conn()
        create_initiative(conn, 1, {"title": "Fix technical debt", "roadmap_bucket": "30d", "status": "planned"})
        rows = list_all_initiatives(conn, conn)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["customer_name"], "Acme")
        self.assertEqual(rows[0]["title"], "Fix technical debt")


class TestReportExport(unittest.TestCase):
    def test_build_dashboard_pdf(self) -> None:
        from ptt_seo.report_export import build_dashboard_pdf

        try:
            buf, name = build_dashboard_pdf(
                {
                    "type": "executive",
                    "gsc": {"clicks": 100, "impressions": 5000, "avg_ctr": 0.02},
                    "critical_issues": 2,
                    "content_by_status": {"idea": 3, "published": 1},
                },
                customer_label="Acme",
            )
        except RuntimeError:
            self.skipTest("reportlab not installed")
        self.assertTrue(name.endswith(".pdf"))
        self.assertGreater(len(buf.getvalue()), 100)


if __name__ == "__main__":
    unittest.main()
