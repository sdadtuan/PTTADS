"""Tests for P2 Enterprise depth — RBAC §9, charts, research, Slack extensions."""
from __future__ import annotations

import os
import sqlite3
import unittest
from datetime import date, timedelta
from unittest.mock import patch

from admin_page_permissions import position_can
from ptt_seo import rbac as seo_rbac
from ptt_seo import schema as seo_schema
from ptt_seo.clusters import assign_keyword_to_cluster, create_cluster, list_clusters
from ptt_seo.enterprise_schema import ensure_enterprise_schema
from ptt_seo.pages import list_pages, sync_pages_from_gsc, upsert_page
from ptt_seo.report import dashboard
from ptt_seo.research_schema import ensure_research_schema
from ptt_seo.serp_stub import capture_serp_snapshot, list_serp_snapshots
from ptt_seo.slack_notify import SLACK_ALERT_TYPES, notify_slack_for_alert
from ptt_seo.technical import create_issue


class _MockDeps:
    def __init__(self, grants: dict[str, frozenset[str]]) -> None:
        self._grants = grants

    def admin_section_can(self, section: str, action: str) -> bool:
        return position_can(self._grants, section, action)


def _mem_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE crm_customers (id INTEGER PRIMARY KEY, name TEXT DEFAULT '', company TEXT DEFAULT '');
        """
    )
    seo_schema.ensure_schema(conn)
    ensure_enterprise_schema(conn)
    ensure_research_schema(conn)
    conn.execute("INSERT INTO crm_customers (name) VALUES ('Test Co')")
    conn.commit()
    return conn


class TestRbacSectionKeys(unittest.TestCase):
    def test_writer_has_write_not_approve(self) -> None:
        grants = {
            "crm_seo_aeo": frozenset({"view"}),
            "crm_seo_aeo_write": frozenset({"view", "edit", "create"}),
        }
        deps = _MockDeps(grants)
        self.assertTrue(seo_rbac.can_write(deps, "edit"))
        self.assertFalse(seo_rbac.can_approve(deps))

    def test_technical_section_isolated(self) -> None:
        grants = {
            "crm_seo_aeo": frozenset({"view"}),
            "crm_seo_aeo_technical": frozenset({"view", "edit", "create"}),
        }
        deps = _MockDeps(grants)
        self.assertTrue(seo_rbac.can_technical(deps, "edit"))
        self.assertFalse(seo_rbac.can_settings(deps, "configure"))

    def test_settings_and_reports_sections(self) -> None:
        grants = {
            "crm_seo_aeo": frozenset({"view"}),
            "crm_seo_aeo_settings": frozenset({"view", "configure"}),
            "crm_seo_aeo_reports": frozenset({"view", "export"}),
        }
        deps = _MockDeps(grants)
        self.assertTrue(seo_rbac.can_settings(deps, "configure"))
        self.assertTrue(seo_rbac.can_reports(deps, "export"))
        caps = seo_rbac.ui_caps(deps)
        self.assertTrue(caps["can_seo_configure"])
        self.assertTrue(caps["can_seo_export"])
        self.assertFalse(caps["can_seo_technical"])


class TestReportsCharts(unittest.TestCase):
    def test_executive_includes_gsc_trend(self) -> None:
        conn = _mem_conn()
        today = date.today()
        for i in range(3):
            d = (today - timedelta(days=i)).isoformat()
            conn.execute(
                """
                INSERT INTO seo_gsc_daily_stats (
                    customer_id, stat_date, query, page, clicks, impressions, created_at
                ) VALUES (1, ?, 'kw', 'https://example.com/', ?, 100, '2026-07-19')
                """,
                (d, 10 + i),
            )
        conn.commit()
        data = dashboard(conn, customer_id=1, dashboard_type="executive")
        self.assertIn("gsc_trend", data)
        self.assertGreaterEqual(len(data["gsc_trend"]), 1)

    def test_content_dashboard_chart(self) -> None:
        conn = _mem_conn()
        conn.execute(
            """
            INSERT INTO seo_content (
                customer_id, title, slug, workflow_status, created_at, updated_at
            ) VALUES (1, 'A', 'a', 'draft', '2026-07-19', '2026-07-19')
            """
        )
        conn.commit()
        data = dashboard(conn, customer_id=1, dashboard_type="content")
        self.assertIn("content_chart", data)
        self.assertTrue(any(c["label"] == "draft" for c in data["content_chart"]))

    def test_technical_severity_chart(self) -> None:
        conn = _mem_conn()
        create_issue(conn, 1, {"url": "https://x.com", "severity": "critical"})
        create_issue(conn, 1, {"url": "https://y.com", "severity": "high"})
        data = dashboard(conn, customer_id=1, dashboard_type="technical")
        labels = {c["label"] for c in data["severity_chart"]}
        self.assertIn("critical", labels)
        self.assertIn("high", labels)


class TestResearchDepth(unittest.TestCase):
    def test_cluster_crud_and_assign(self) -> None:
        conn = _mem_conn()
        cid = create_cluster(conn, 1, {"name": "Brand terms", "intent": "commercial"})
        clusters = list_clusters(conn, 1)
        self.assertEqual(len(clusters), 1)
        self.assertEqual(clusters[0]["keyword_count"], 0)
        conn.execute(
            """
            INSERT INTO seo_keywords (customer_id, phrase, volume, difficulty, status, created_at)
            VALUES (1, 'ptt ads', 100, 40, 'active', '2026-07-19')
            """
        )
        conn.commit()
        kw_id = int(conn.execute("SELECT id FROM seo_keywords LIMIT 1").fetchone()["id"])
        assign_keyword_to_cluster(conn, 1, kw_id, cid)
        clusters = list_clusters(conn, 1)
        self.assertEqual(clusters[0]["keyword_count"], 1)

    def test_serp_stub_capture(self) -> None:
        conn = _mem_conn()
        snap = capture_serp_snapshot(conn, 1, phrase="seo agency hcm")
        self.assertEqual(snap["source"], "stub")
        self.assertEqual(len(snap["results"]), 3)
        rows = list_serp_snapshots(conn, 1)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["phrase"], "seo agency hcm")

    def test_pages_sync_from_gsc(self) -> None:
        conn = _mem_conn()
        recent = date.today().isoformat()
        conn.execute(
            """
            INSERT INTO seo_gsc_daily_stats (
                customer_id, stat_date, query, page, clicks, impressions, created_at
            ) VALUES (1, ?, 'kw', 'https://client.com/blog/a', 5, 50, '2026-07-19')
            """,
            (recent,),
        )
        conn.commit()
        out = sync_pages_from_gsc(conn, 1, days=90)
        self.assertTrue(out["ok"])
        self.assertEqual(out["synced"], 1)
        pages = list_pages(conn, 1)
        self.assertEqual(len(pages), 1)
        self.assertIn("client.com", pages[0]["url"])

    def test_pages_upsert(self) -> None:
        conn = _mem_conn()
        pid = upsert_page(conn, 1, "https://example.com/about", title="About us")
        self.assertGreater(pid, 0)
        pid2 = upsert_page(conn, 1, "https://example.com/about", title="About PTT")
        self.assertEqual(pid, pid2)
        pages = list_pages(conn, 1)
        self.assertEqual(pages[0]["title"], "About PTT")


class TestSlackAlertTypes(unittest.TestCase):
    def test_new_alert_types_registered(self) -> None:
        self.assertIn("sync_failed", SLACK_ALERT_TYPES)
        self.assertIn("freshness_urgent", SLACK_ALERT_TYPES)

    @patch.dict(os.environ, {"PTT_SEO_SLACK_WEBHOOK": "https://hooks.example.com/x"}, clear=False)
    @patch("ptt_seo.slack_notify.post_seo_slack")
    def test_sync_failed_slack(self, mock_post) -> None:
        mock_post.return_value = {"ok": True}
        out = notify_slack_for_alert(
            alert_type="sync_failed",
            message="GSC sync failed",
            link="/crm/seo/automations",
        )
        self.assertIsNotNone(out)
        mock_post.assert_called_once()
        self.assertIn("GSC sync failed", mock_post.call_args[0][0])

    @patch.dict(os.environ, {"PTT_SEO_SLACK_WEBHOOK": "https://hooks.example.com/x"}, clear=False)
    @patch("ptt_seo.slack_notify.post_seo_slack")
    def test_freshness_urgent_slack(self, mock_post) -> None:
        mock_post.return_value = {"ok": True}
        out = notify_slack_for_alert(
            alert_type="freshness_urgent",
            message="3 pages urgent refresh",
            link="/crm/seo/content",
        )
        self.assertIsNotNone(out)
        mock_post.assert_called_once()
        self.assertIn(":fire:", mock_post.call_args[0][0])


if __name__ == "__main__":
    unittest.main()
