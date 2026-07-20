"""Gate B — brand settings, SERP schedule, pipeline transitions, brief assignee."""
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
from ptt_seo.client_settings import get_settings, upsert_settings
from ptt_seo.constants import CONTENT_TRANSITIONS, CONTENT_STATUS_LABELS
from ptt_seo.content import create_content, create_content_from_research, get_content, transition_status
from ptt_seo.research import create_keyword
from ptt_seo.research_schema import ensure_research_schema
from ptt_seo.serp_schedule import capture_serp_all_customers, capture_serp_for_customer


def _mem_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """

        CREATE TABLE crm_customers (id INTEGER PRIMARY KEY, name TEXT DEFAULT '');
        """
    )
    seo_schema.ensure_schema(conn)
    ensure_research_schema(conn)
    conn.execute("INSERT INTO crm_customers (name) VALUES ('Acme')")
    conn.commit()
    return conn


class TestGateBBrandSettings(unittest.TestCase):
    def test_upsert_and_read_brand_guidelines(self) -> None:
        conn = _mem_conn()
        upsert_settings(
            conn,
            1,
            {
                "brand_guidelines": {
                    "company_name": "Client X",
                    "report_title_prefix": "Monthly SEO",
                    "primary_color": "#059669",
                    "report_footer": "Confidential",
                    "hide_agency_branding": True,
                }
            },
        )
        settings = get_settings(conn, 1)
        brand = settings["brand_guidelines"]
        self.assertEqual(brand["company_name"], "Client X")
        self.assertEqual(brand["primary_color"], "#059669")
        self.assertTrue(brand["hide_agency_branding"])


class TestGateBSerpSchedule(unittest.TestCase):
    def test_capture_top_keywords_for_customer(self) -> None:
        conn = _mem_conn()
        create_keyword(conn, 1, {"phrase": "low opp", "volume": 10, "opportunity_score": 1})
        create_keyword(conn, 1, {"phrase": "high opp", "volume": 500, "opportunity_score": 90})
        conn.execute("UPDATE seo_keywords SET status = 'active' WHERE customer_id = 1")
        conn.commit()

        result = capture_serp_for_customer(conn, 1, limit=1)
        self.assertEqual(result["customer_id"], 1)
        self.assertEqual(result["captured"], 1)
        self.assertEqual(result["snapshots"][0]["phrase"], "high opp")

    def test_capture_all_customers(self) -> None:
        conn = _mem_conn()
        create_keyword(conn, 1, {"phrase": "kw a", "volume": 100})
        conn.execute("UPDATE seo_keywords SET status = 'active' WHERE customer_id = 1")
        conn.commit()
        out = capture_serp_all_customers(conn, per_customer_limit=2)
        self.assertTrue(out["ok"])
        self.assertEqual(out["customers"], 1)
        self.assertGreaterEqual(out["snapshots_captured"], 1)


class TestGateBPipelineTransitions(unittest.TestCase):
    def test_allowed_transitions_from_constants(self) -> None:
        self.assertIn("in_writing", CONTENT_TRANSITIONS.get("brief_ready", ()))
        self.assertEqual(CONTENT_STATUS_LABELS.get("in_writing"), "Đang viết")

    def test_transition_status_moves_card(self) -> None:
        conn = _mem_conn()
        cid = create_content(conn, {"customer_id": 1, "title": "Post", "workflow_status": "brief_ready"})
        item = transition_status(conn, cid, "in_writing")
        self.assertEqual(item["workflow_status"], "in_writing")
        loaded = get_content(conn, cid)
        assert loaded is not None
        self.assertEqual(loaded["workflow_status"], "in_writing")


class TestGateBBriefAssignee(unittest.TestCase):
    def test_create_from_research_with_owner(self) -> None:
        conn = _mem_conn()
        kid = create_keyword(conn, 1, {"phrase": "local seo", "intent": "commercial", "volume": 200})
        cid = create_content_from_research(
            conn,
            1,
            keyword_id=kid,
            owner_staff_id=42,
            due_date="2026-08-01",
        )
        item = get_content(conn, cid)
        assert item is not None
        self.assertEqual(item["owner_staff_id"], 42)
        self.assertEqual(item["due_date"], "2026-08-01")
        self.assertEqual(item["workflow_status"], "brief_ready")


class TestGateBApiPipeline(unittest.TestCase):
    def setUp(self) -> None:
        from app import app

        self.client = app.test_client()

    @patch("app._admin_logged_in", return_value=True)
    @patch("app._ensure_crm_session_html", return_value=None)
    def test_pipeline_includes_allowed_transitions(self, _sess, _auth) -> None:
        conn = _mem_conn()
        create_content(conn, {"customer_id": 1, "title": "Kanban", "workflow_status": "brief_ready"})
        conn.commit()

        with patch("blueprints.seo_aeo.seo_read") as mock_read:
            mock_read.return_value.__enter__ = lambda s: conn
            mock_read.return_value.__exit__ = lambda s, *a: None
            resp = self.client.get("/api/v1/seo/content/pipeline?customer_id=1")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        board = data["board"]
        brief_items = board.get("brief_ready") or []
        self.assertTrue(brief_items)
        transitions = brief_items[0].get("allowed_transitions") or []
        values = [t["value"] for t in transitions]
        self.assertIn("in_writing", values)


if __name__ == "__main__":
    unittest.main()
