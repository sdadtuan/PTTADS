"""Gate E — OKR tree, crawl connector, CWV UI API, entity autolink, CMS auto-publish, rank SOV, attribution, a11y helpers."""
from __future__ import annotations

import json
import os
import sqlite3
import unittest
from unittest.mock import patch

from ptt_seo import schema as seo_schema
from ptt_seo.attribution import (
    organic_attribution_summary,
    organic_revenue_total,
    top_organic_landing_pages,
)
from ptt_seo.clusters import create_cluster
from ptt_seo.content import create_content
from ptt_seo.crawl_connector import ingest_crawl_payload, upsert_crawl_schedule, verify_crawl_secret
from ptt_seo.cms_publish import cms_auto_publish_enabled, maybe_auto_publish, upsert_cms_target
from ptt_seo.cwv import cwv_summary, insert_cwv_snapshot, list_cwv_snapshots
from ptt_seo.enterprise_schema import ensure_enterprise_schema
from ptt_seo.entity_autolink import autolink_all
from ptt_seo.gate_d_schema import ensure_gate_d_schema
from ptt_seo.gate_e_schema import ensure_gate_e_schema
from ptt_seo.initiatives import create_initiative
from ptt_seo.rank_live import capture_ranks_for_customer, share_of_voice
from ptt_seo.rank_tracker import add_tracked_keyword, record_snapshot
from ptt_seo.research_schema import ensure_research_schema
from ptt_seo.strategy_okr import create_goal, create_kpi, okr_tree, refresh_kpi_metrics


def _mem_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("CREATE TABLE crm_customers (id INTEGER PRIMARY KEY, name TEXT DEFAULT '');")
    seo_schema.ensure_schema(conn)
    ensure_research_schema(conn)
    ensure_enterprise_schema(conn)
    ensure_gate_d_schema(conn)
    ensure_gate_e_schema(conn)
    conn.execute("INSERT INTO crm_customers (name) VALUES ('Acme')")
    conn.commit()
    return conn


class TestGateEOkr(unittest.TestCase):
    def test_okr_tree_goal_kpi_initiative(self) -> None:
        conn = _mem_conn()
        gid = create_goal(conn, 1, {"title": "Grow organic traffic", "period": "Q3-2026"})
        create_kpi(
            conn,
            1,
            {"goal_id": gid, "metric_label": "GSC Clicks", "metric_key": "gsc_clicks", "target_value": 1000},
        )
        iid = create_initiative(conn, 1, {"title": "Fix technical SEO", "status": "planned"})
        from ptt_seo.strategy_okr import link_initiative_to_goal

        link_initiative_to_goal(conn, 1, iid, gid)
        tree = okr_tree(conn, 1)
        self.assertEqual(len(tree["goals"]), 1)
        self.assertEqual(len(tree["goals"][0]["kpis"]), 1)
        self.assertEqual(len(tree["goals"][0]["initiatives"]), 1)


class TestGateECrawlConnector(unittest.TestCase):
    def test_webhook_ingest(self) -> None:
        conn = _mem_conn()
        sched = upsert_crawl_schedule(conn, 1, {"frequency_days": 14})
        secret = sched["webhook_secret"]
        self.assertTrue(verify_crawl_secret(conn, 1, secret))
        csv_text = "url,issue_type,severity,description\nhttps://a.com/x,broken_link,high,404\n"
        result = ingest_crawl_payload(conn, 1, csv_text=csv_text)
        self.assertEqual(result["rows_imported"], 1)
        row = conn.execute("SELECT COUNT(*) AS c FROM seo_technical_issues WHERE customer_id = 1").fetchone()
        self.assertEqual(int(row["c"]), 1)


class TestGateECwvApi(unittest.TestCase):
    def test_cwv_list_and_summary(self) -> None:
        conn = _mem_conn()
        insert_cwv_snapshot(
            conn,
            1,
            {
                "url": "https://example.com/",
                "lcp_ms": 2000.0,
                "cls": 0.04,
                "inp_ms": 150.0,
                "performance_score": 88.0,
                "cwv_rating": "pass",
                "source": "stub",
            },
        )
        snaps = list_cwv_snapshots(conn, 1)
        self.assertEqual(len(snaps), 1)
        summary = cwv_summary(conn, 1)
        self.assertEqual(summary["pass_count"], 1)
        self.assertEqual(summary["pass_rate_pct"], 100.0)


class TestGateEEntityAutolink(unittest.TestCase):
    def test_autolink_clusters(self) -> None:
        conn = _mem_conn()
        create_cluster(conn, 1, {"name": "SEO Tools"})
        create_cluster(conn, 1, {"name": "Content Marketing"})
        result = autolink_all(conn, 1)
        self.assertGreaterEqual(result["entities_created"], 2)
        self.assertGreaterEqual(result["links_created"], 1)


class TestGateECmsAutoPublish(unittest.TestCase):
    @patch.dict(os.environ, {"PTT_SEO_CMS_AUTO_PUBLISH": "1"}, clear=False)
    def test_auto_publish_on_enabled(self) -> None:
        conn = _mem_conn()
        self.assertTrue(cms_auto_publish_enabled())
        upsert_cms_target(conn, 1, {"cms_type": "webhook", "base_url": "https://cms.example/hook", "active": True})
        cid = create_content(conn, {"customer_id": 1, "title": "Post A", "content_type": "blog"})
        with patch("ptt_seo.cms_publish.queue_publish") as mock_pub:
            mock_pub.return_value = {"job_id": 1, "status": "sent"}
            result = maybe_auto_publish(conn, cid)
            self.assertIsNotNone(result)
            mock_pub.assert_called_once()


class TestGateERankSov(unittest.TestCase):
    def test_share_of_voice(self) -> None:
        conn = _mem_conn()
        tid1 = add_tracked_keyword(conn, 1, {"phrase": "seo agency"})
        tid2 = add_tracked_keyword(conn, 1, {"phrase": "aeo platform"})
        record_snapshot(conn, tid1, snapshot_date="2026-07-01", position=3, source="stub")
        record_snapshot(conn, tid2, snapshot_date="2026-07-01", position=15, source="stub")
        sov = share_of_voice(conn, 1, top_n=10)
        self.assertEqual(sov["tracked"], 2)
        self.assertEqual(sov["in_top_n"], 1)
        self.assertEqual(sov["sov_pct"], 50.0)

    @patch.dict(os.environ, {"PTT_SERP_PROVIDER": "stub"}, clear=False)
    def test_capture_ranks_stub(self) -> None:
        conn = _mem_conn()
        conn.execute(
            "INSERT INTO seo_client_settings (customer_id, domains_json) VALUES (1, ?)",
            (json.dumps(["example.com"]),),
        )
        conn.commit()
        add_tracked_keyword(conn, 1, {"phrase": "test kw"})
        result = capture_ranks_for_customer(conn, 1, domain_hint="example.com")
        self.assertEqual(result["captured"], 1)


class TestGateEAttribution(unittest.TestCase):
    def test_organic_revenue(self) -> None:
        conn = _mem_conn()
        conn.execute(
            """
            INSERT INTO seo_ga4_daily_stats (
                customer_id, stat_date, landing_page, source_medium,
                sessions, users, pageviews, conversions, revenue, created_at
            ) VALUES (1, date('now'), '/blog', 'google / organic', 100, 80, 200, 5, 1500.5, '2026-07-01')
            """
        )
        conn.commit()
        self.assertEqual(organic_revenue_total(conn, 1), 1500.5)
        summary = organic_attribution_summary(conn, 1)
        self.assertEqual(summary["revenue"], 1500.5)
        self.assertEqual(summary["sessions"], 100)
        self.assertEqual(summary["conversion_rate"], 0.05)
        pages = top_organic_landing_pages(conn, 1)
        self.assertEqual(len(pages), 1)
        self.assertEqual(pages[0]["landing_page"], "/blog")


if __name__ == "__main__":
    unittest.main()
