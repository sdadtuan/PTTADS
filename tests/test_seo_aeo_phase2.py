"""Tests for SEO/AEO Ops Phase 2 — research, content pipeline, workflow."""
from __future__ import annotations


import os
import unittest

if os.environ.get("PTT_RUN_FLASK_TESTS") != "1":
    raise unittest.SkipTest(
        "Flask HTTP removed — set PTT_RUN_FLASK_TESTS=1 to run integration tests"
    )
import sqlite3
import unittest
from unittest.mock import MagicMock, patch

from ptt_seo import schema as seo_schema
from ptt_seo.content import (
    approve_stage,
    create_content,
    create_content_from_research,
    pipeline_board,
    transition_status,
)
from ptt_seo.research import create_keyword, create_question, import_keywords_csv, list_keywords
from ptt_seo.constants import can_transition


def _mem_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """

        CREATE TABLE crm_customers (id INTEGER PRIMARY KEY, name TEXT DEFAULT '');
        """
    )
    seo_schema.ensure_schema(conn)
    conn.execute("INSERT INTO crm_customers (name) VALUES ('Test Co')")
    conn.commit()
    return conn


class TestResearch(unittest.TestCase):
    def test_keyword_opportunity_score(self) -> None:
        conn = _mem_conn()
        kid = create_keyword(
            conn, 1, {"phrase": "seo agency", "volume": 1000, "difficulty": 30, "business_value": "high"}
        )
        rows = list_keywords(conn, 1)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["id"], kid)
        self.assertGreater(rows[0]["opportunity_score"], 0)

    def test_import_csv(self) -> None:
        conn = _mem_conn()
        csv_text = "phrase,volume,difficulty,intent\nseo local,500,40,commercial\n"
        n = import_keywords_csv(conn, 1, csv_text)
        self.assertEqual(n, 1)
        self.assertEqual(len(list_keywords(conn, 1)), 1)

    def test_research_to_content(self) -> None:
        conn = _mem_conn()
        kid = create_keyword(conn, 1, {"phrase": "test kw"})
        cid = create_content_from_research(conn, 1, keyword_id=kid, lifecycle_id=99)
        item = conn.execute("SELECT * FROM seo_content WHERE id = ?", (cid,)).fetchone()
        self.assertIsNotNone(item)
        assert item is not None
        self.assertEqual(item["workflow_status"], "brief_ready")
        self.assertEqual(item["target_keyword_id"], kid)


class TestContentPipeline(unittest.TestCase):
    def test_create_and_pipeline(self) -> None:
        conn = _mem_conn()
        cid = create_content(conn, {"customer_id": 1, "title": "Blog 1", "workflow_status": "idea"})
        board = pipeline_board(conn, 1)
        self.assertEqual(len(board["idea"]), 1)
        self.assertEqual(board["idea"][0]["id"], cid)

    def test_transition_valid(self) -> None:
        conn = _mem_conn()
        cid = create_content(conn, {"customer_id": 1, "title": "X", "workflow_status": "idea"})
        item = transition_status(conn, cid, "brief_ready")
        self.assertEqual(item["workflow_status"], "brief_ready")

    def test_transition_invalid_raises(self) -> None:
        conn = _mem_conn()
        cid = create_content(conn, {"customer_id": 1, "title": "X", "workflow_status": "idea"})
        with self.assertRaises(ValueError):
            transition_status(conn, cid, "published")

    def test_approve_seo_review(self) -> None:
        conn = _mem_conn()
        cid = create_content(conn, {"customer_id": 1, "title": "X", "workflow_status": "seo_review"})
        item = approve_stage(conn, cid, "seo_review", approved=True, actor_id="tester")
        self.assertEqual(item["workflow_status"], "aeo_review")


class TestTransitions(unittest.TestCase):
    def test_can_transition_matrix(self) -> None:
        self.assertTrue(can_transition("idea", "brief_ready"))
        self.assertFalse(can_transition("idea", "published"))


class TestPhase2Blueprint(unittest.TestCase):
    def setUp(self) -> None:
        from app import app

        self.client = app.test_client()

    @patch("app._admin_logged_in", return_value=True)
    @patch("blueprints.seo_aeo._can", return_value=True)
    @patch("blueprints.seo_aeo.deps.ensure_crm_session_html", return_value=None)
    @patch("blueprints.seo_aeo.deps.admin_page_template_kwargs", return_value={})
    def test_research_page(self, _kw: MagicMock, _sess: MagicMock, _can: MagicMock, _auth: MagicMock) -> None:
        resp = self.client.get("/crm/seo/research")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Research Console", resp.data)

    @patch("app._admin_logged_in", return_value=True)
    @patch("blueprints.seo_aeo._can", return_value=True)
    @patch("blueprints.seo_aeo.deps.ensure_crm_session_html", return_value=None)
    @patch("blueprints.seo_aeo.deps.admin_page_template_kwargs", return_value={})
    def test_content_pipeline_page(self, _kw: MagicMock, _sess: MagicMock, _can: MagicMock, _auth: MagicMock) -> None:
        resp = self.client.get("/crm/seo/content")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Content Pipeline", resp.data)

    @patch("blueprints.seo_aeo._can", return_value=True)
    def test_api_pipeline(self, _can: MagicMock) -> None:
        resp = self.client.get("/api/v1/seo/content/pipeline")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("board", resp.get_json())


if __name__ == "__main__":
    unittest.main()
