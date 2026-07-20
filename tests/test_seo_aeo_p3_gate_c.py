"""Tests for Gate C P3 backlog — SERP provider, white-label, portal widgets, Temporal."""
from __future__ import annotations

import os
import sqlite3
import unittest
from unittest.mock import patch

from ptt_seo import schema as seo_schema
from ptt_seo.client_settings import upsert_settings
from ptt_seo.enterprise_schema import ensure_enterprise_schema
from ptt_seo.p3_schema import ensure_p3_gate_c_schema
from ptt_seo.portal_widgets import portal_widgets
from ptt_seo.report_branding import brand_config_from_settings
from ptt_seo.research_schema import ensure_research_schema
from ptt_seo.serp_provider import capture_serp_snapshot, effective_provider, fetch_serp_results
from ptt_seo.temporal_bridge import content_temporal_enabled, content_workflow_id


def _mem_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE crm_customers (id INTEGER PRIMARY KEY, name TEXT DEFAULT '', company TEXT DEFAULT '');
        CREATE TABLE seo_portal_client_map (
            client_id TEXT PRIMARY KEY, customer_id INTEGER NOT NULL, active INTEGER NOT NULL DEFAULT 1, created_at TEXT
        );
        """
    )
    seo_schema.ensure_schema(conn)
    ensure_enterprise_schema(conn)
    ensure_research_schema(conn)
    ensure_p3_gate_c_schema(conn)
    conn.execute("INSERT INTO crm_customers (name, company) VALUES ('Acme Co', 'Acme')")
    conn.commit()
    return conn


class TestSerpProvider(unittest.TestCase):
    def test_stub_by_default(self) -> None:
        with patch.dict(os.environ, {"PTT_SERP_PROVIDER": "stub"}, clear=False):
            results, source = fetch_serp_results("seo agency")
            self.assertEqual(source, "stub")
            self.assertGreaterEqual(len(results), 1)

    def test_serpapi_without_key_falls_back_stub(self) -> None:
        with patch.dict(os.environ, {"PTT_SERP_PROVIDER": "serpapi", "SERPAPI_API_KEY": ""}, clear=False):
            self.assertEqual(effective_provider(), "stub")

    @patch("ptt_seo.serp_provider._fetch_serpapi")
    def test_serpapi_capture(self, mock_fetch) -> None:
        mock_fetch.return_value = [
            {"position": 1, "title": "Real", "url": "https://a.com", "snippet": "x"}
        ]
        with patch.dict(os.environ, {"PTT_SERP_PROVIDER": "serpapi", "SERPAPI_API_KEY": "key"}, clear=False):
            conn = _mem_conn()
            snap = capture_serp_snapshot(conn, 1, phrase="test kw")
            self.assertEqual(snap["source"], "serpapi")
            self.assertEqual(snap["results"][0]["title"], "Real")

    def test_capture_persists(self) -> None:
        conn = _mem_conn()
        snap = capture_serp_snapshot(conn, 1, phrase="local test")
        self.assertIn("id", snap)
        self.assertEqual(snap["source"], "stub")


class TestReportBranding(unittest.TestCase):
    def test_brand_from_settings(self) -> None:
        cfg = brand_config_from_settings(
            {
                "brand_guidelines": {
                    "company_name": "Client X",
                    "primary_color": "#ff0000",
                    "hide_agency_branding": True,
                    "report_footer": "Confidential — Client X",
                }
            }
        )
        self.assertEqual(cfg["company_name"], "Client X")
        self.assertEqual(cfg["primary_color"], "#ff0000")
        self.assertTrue(cfg["hide_agency_branding"])

    def test_pdf_with_brand(self) -> None:
        from ptt_seo.report_export import build_dashboard_pdf

        brand = brand_config_from_settings({"brand_guidelines": {"primary_color": "#059669"}})
        buf, name = build_dashboard_pdf(
            {"type": "executive", "gsc": {"clicks": 10}, "critical_issues": 0},
            customer_label="Acme",
            brand=brand,
        )
        self.assertTrue(name.endswith(".pdf"))
        self.assertGreater(buf.getbuffer().nbytes, 100)


class TestPortalWidgets(unittest.TestCase):
    def test_widgets_payload(self) -> None:
        conn = _mem_conn()
        data = portal_widgets(conn, 1)
        self.assertTrue(data["ok"])
        widgets = data["widgets"]
        self.assertIn("gsc_clicks", widgets)
        self.assertIn("critical_issues", widgets)
        self.assertIn("content_in_review", widgets)


class TestTemporalBridge(unittest.TestCase):
    def test_disabled_by_default(self) -> None:
        with patch.dict(os.environ, {"PTT_SEO_CONTENT_TEMPORAL": "0"}, clear=False):
            self.assertFalse(content_temporal_enabled())

    def test_workflow_id_format(self) -> None:
        self.assertEqual(content_workflow_id(42), "seo-content-42")


class TestSeoContentApprovalWorkflow(unittest.IsolatedAsyncioTestCase):
    async def test_approve_signal(self) -> None:
        try:
            from temporalio.testing import WorkflowEnvironment
        except ImportError:
            self.skipTest("temporalio not installed")
        from datetime import timedelta

        from temporalio.worker import Worker

        from ptt_temporal.activities.seo_content import (
            notify_am_seo_content_decision,
            notify_am_seo_content_pending,
        )
        from ptt_temporal.workflows.seo_content_approval import (
            SeoContentApprovalInput,
            SeoContentApprovalWorkflow,
        )

        async with await WorkflowEnvironment.start_time_skipping() as env:
            async with Worker(
                env.client,
                task_queue="test-seo-content",
                workflows=[SeoContentApprovalWorkflow],
                activities=[notify_am_seo_content_pending, notify_am_seo_content_decision],
            ):
                handle = await env.client.start_workflow(
                    SeoContentApprovalWorkflow.run,
                    SeoContentApprovalInput(
                        content_id=9,
                        customer_id=1,
                        client_id="550e8400-e29b-41d4-a716-446655440000",
                        title="Blog post",
                        submitted_by="am@test.local",
                    ),
                    id="test-seo-content-9",
                    task_queue="test-seo-content",
                    execution_timeout=timedelta(minutes=1),
                )
                await handle.signal(
                    SeoContentApprovalWorkflow.approve_content,
                    {"reviewed_by": "client@test.local", "note": "LGTM"},
                )
                result = await handle.result()
                self.assertEqual(result["decision"], "approved")


if __name__ == "__main__":
    unittest.main()
