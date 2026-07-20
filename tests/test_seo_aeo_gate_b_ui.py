"""Gate B — Spec parity UI tests."""
from __future__ import annotations


import os
import unittest

if os.environ.get("PTT_RUN_FLASK_TESTS") != "1":
    raise unittest.SkipTest(
        "Flask HTTP removed — set PTT_RUN_FLASK_TESTS=1 to run integration tests"
    )
import sqlite3
import unittest
from unittest.mock import patch

from ptt_seo import schema as seo_schema
from ptt_seo.clusters import create_cluster
from ptt_seo.constants import PIPELINE_COLUMNS
from ptt_seo.content import create_content, pipeline_board, preview_research_brief
from ptt_seo.research import create_keyword, list_keywords
from ptt_seo.research_schema import ensure_research_schema


def _mem_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """

        CREATE TABLE crm_customers (id INTEGER PRIMARY KEY, name TEXT DEFAULT '');
        CREATE TABLE crm_service_lifecycle (
            id INTEGER PRIMARY KEY, customer_id INTEGER, service_slug TEXT,
            stage TEXT, status TEXT
        );
        """
    )
    seo_schema.ensure_schema(conn)
    ensure_research_schema(conn)
    import crm_svc_tasks

    crm_svc_tasks.ensure_schema(conn)
    conn.execute("INSERT INTO crm_customers (name) VALUES ('Acme')")
    conn.commit()
    return conn


class TestGateBKanbanColumns(unittest.TestCase):
    def test_review_stages_split(self) -> None:
        cols = [c[0] for c in PIPELINE_COLUMNS]
        self.assertIn("seo_review", cols)
        self.assertIn("aeo_review", cols)
        self.assertIn("technical_review", cols)
        self.assertIn("client_review", cols)
        self.assertNotIn("review", cols)

    def test_pipeline_board_maps_review_columns(self) -> None:
        conn = _mem_conn()
        create_content(conn, {"customer_id": 1, "title": "A", "workflow_status": "seo_review"})
        create_content(conn, {"customer_id": 1, "title": "B", "workflow_status": "aeo_review"})
        board = pipeline_board(conn, 1)
        self.assertEqual(len(board["seo_review"]), 1)
        self.assertEqual(len(board["aeo_review"]), 1)


class TestGateBKeywordFilters(unittest.TestCase):
    def test_filter_by_intent_and_cluster(self) -> None:
        conn = _mem_conn()
        cid = create_cluster(conn, 1, {"name": "Brand", "intent": "commercial"})
        create_keyword(conn, 1, {"phrase": "seo agency", "intent": "commercial", "volume": 100})
        create_keyword(conn, 1, {"phrase": "what is seo", "intent": "informational", "volume": 50})
        conn.execute("UPDATE seo_keywords SET cluster_id = ? WHERE phrase = 'seo agency'", (cid,))
        conn.commit()
        rows = list_keywords(conn, 1, intent="commercial", cluster_id=cid)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["phrase"], "seo agency")
        self.assertEqual(rows[0]["cluster_name"], "Brand")


class TestGateBBriefPreview(unittest.TestCase):
    def test_preview_template_brief(self) -> None:
        conn = _mem_conn()
        kid = create_keyword(conn, 1, {"phrase": "local seo", "intent": "commercial", "volume": 200})
        preview = preview_research_brief(conn, 1, keyword_id=kid, use_ai=False)
        self.assertIn("local seo", preview["title"])
        self.assertEqual(preview["source"], "template")
        self.assertIn("sections", preview["brief"])


class TestGateBLegacyRedirect(unittest.TestCase):
    def setUp(self) -> None:
        from app import app

        self.client = app.test_client()

    @patch("app._admin_logged_in", return_value=True)
    @patch("app._ensure_crm_session_html", return_value=None)
    def test_crm_aeo_redirects_301(self, _sess, _auth) -> None:
        resp = self.client.get("/crm/aeo?customer_id=5", follow_redirects=False)
        self.assertEqual(resp.status_code, 301)
        self.assertIn("/crm/seo/aeo", resp.headers.get("Location", ""))
        self.assertIn("customer_id=5", resp.headers.get("Location", ""))


class TestGateBUiMarkup(unittest.TestCase):
    def setUp(self) -> None:
        from app import app

        self.client = app.test_client()

    @patch("app._admin_logged_in", return_value=True)
    @patch("app._ensure_crm_session_html", return_value=None)
    @patch("ptt_seo.hub.customer_workspace")
    def test_client_settings_brand_fieldset(self, mock_ws, _sess, _auth) -> None:
        mock_ws.return_value = {
            "customer": {"id": 1, "name": "Acme", "company": ""},
            "settings": {
                "domains": [],
                "markets": [],
                "contract_tier": "standard",
                "brand_guidelines": {},
            },
            "lifecycles": [],
            "initiatives": [],
            "overview": {
                "keywords": 0,
                "content_pipeline": 0,
                "technical_issues": 0,
                "aeo_coverage_pct": 0,
                "opportunities": [],
            },
            "metrics": {},
            "tab_badges": {},
        }
        resp = self.client.get("/crm/seo/clients/1?tab=settings")
        self.assertEqual(resp.status_code, 200)
        html = resp.get_data(as_text=True)
        self.assertIn("seo-brand-fieldset", html)
        self.assertIn("brand_company_name", html)

    @patch("app._admin_logged_in", return_value=True)
    @patch("app._ensure_crm_session_html", return_value=None)
    def test_research_brief_assignee_select(self, _sess, _auth) -> None:
        resp = self.client.get("/crm/seo/research")
        self.assertEqual(resp.status_code, 200)
        html = resp.get_data(as_text=True)
        self.assertIn("seo-brief-assignee", html)


if __name__ == "__main__":
    unittest.main()
