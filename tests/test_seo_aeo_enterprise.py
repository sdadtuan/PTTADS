"""Tests for SEO/AEO enterprise backlog (Phase 3 enterprise)."""
from __future__ import annotations

import sqlite3
import unittest
from unittest.mock import patch

from ptt_seo import schema as seo_schema
from ptt_seo.cms_publish import queue_publish, upsert_cms_target
from ptt_seo.content import create_content
from ptt_seo.enterprise_schema import ensure_enterprise_schema
from ptt_seo.entities import create_entity, create_entity_link, entity_graph, seed_entities_from_keywords
from ptt_seo.rank_tracker import add_tracked_keyword, import_rank_csv, list_tracked_keywords
from ptt_seo.research import create_keyword
from ptt_seo.bi_clickhouse import collect_daily_facts


def _mem_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("CREATE TABLE crm_customers (id INTEGER PRIMARY KEY, name TEXT DEFAULT '');")
    seo_schema.ensure_schema(conn)
    ensure_enterprise_schema(conn)
    conn.execute("INSERT INTO crm_customers (name) VALUES ('Test')")
    conn.commit()
    return conn


class TestEntities(unittest.TestCase):
    def test_entity_graph(self) -> None:
        conn = _mem_conn()
        a = create_entity(conn, 1, {"entity_name": "Brand X", "entity_type": "brand"})
        b = create_entity(conn, 1, {"entity_name": "Product Y", "entity_type": "product"})
        create_entity_link(conn, 1, {"source_entity_id": a, "target_entity_id": b, "link_type": "owns"})
        graph = entity_graph(conn, 1)
        self.assertEqual(graph["entity_count"], 2)
        self.assertEqual(graph["link_count"], 1)

    def test_seed_from_keywords(self) -> None:
        conn = _mem_conn()
        create_keyword(conn, 1, {"phrase": "seo tips", "intent": "informational"})
        n = seed_entities_from_keywords(conn, 1)
        self.assertGreaterEqual(n, 1)


class TestRankTracker(unittest.TestCase):
    def test_import_csv(self) -> None:
        conn = _mem_conn()
        csv_text = "phrase,position,date\nseo agency,5,2026-07-01\n"
        result = import_rank_csv(conn, 1, csv_text)
        self.assertEqual(result["snapshots"], 1)
        tracked = list_tracked_keywords(conn, 1)
        self.assertEqual(len(tracked), 1)
        self.assertEqual(tracked[0]["latest_position"], 5.0)

    def test_add_tracked(self) -> None:
        conn = _mem_conn()
        tid = add_tracked_keyword(conn, 1, {"phrase": "local seo"})
        self.assertGreater(tid, 0)


class TestCmsPublish(unittest.TestCase):
    def test_dry_run_queue(self) -> None:
        conn = _mem_conn()
        cid = create_content(conn, {"customer_id": 1, "title": "Post", "workflow_status": "approved", "body_html": "<p>Hi</p>"})
        upsert_cms_target(conn, 1, {"cms_type": "webhook", "base_url": "https://example.com/hook", "active": True})
        result = queue_publish(conn, cid, dry_run=True)
        self.assertTrue(result.get("dry_run"))
        self.assertEqual(result.get("status"), "sent")
        self.assertIn("payload", result)

    @patch("ptt_seo.cms_publish.urllib.request.urlopen")
    def test_test_webhook(self, mock_urlopen) -> None:
        conn = _mem_conn()
        upsert_cms_target(
            conn,
            1,
            {
                "cms_type": "webhook",
                "base_url": "https://example.com/hook",
                "active": True,
                "auth": {"bearer_token": "secret"},
            },
        )
        mock_resp = mock_urlopen.return_value.__enter__.return_value
        mock_resp.read.return_value = b'{"ok":true,"url":"https://example.com/blog/test"}'
        from ptt_seo.cms_publish import test_cms_webhook

        result = test_cms_webhook(conn, 1)
        self.assertTrue(result["ok"])
        self.assertIn("example.com", result["remote_url"])


class TestCmsPilotConfig(unittest.TestCase):
    def test_pilot_target_payload(self) -> None:
        from ptt_seo.cms_pilot import default_pilot_webhook_url, pilot_target_payload

        with patch.dict(
            "os.environ",
            {"PTT_SEO_CMS_PILOT_WEBHOOK_URL": "http://localhost:9999/hook"},
            clear=False,
        ):
            p = pilot_target_payload()
            self.assertEqual(p["base_url"], "http://localhost:9999/hook")
            self.assertTrue(p["active"])


class TestBiFacts(unittest.TestCase):
    def test_collect_daily_facts(self) -> None:
        conn = _mem_conn()
        create_content(conn, {"customer_id": 1, "title": "Pub", "workflow_status": "published"})
        facts = collect_daily_facts(conn)
        self.assertTrue(any(f["metric_name"] == "content_published" for f in facts))


class TestEnterpriseFlag(unittest.TestCase):
    def test_flag_default_on(self) -> None:
        from ptt_seo.enterprise import enterprise_enabled

        with patch.dict("os.environ", {}, clear=False):
            self.assertTrue(enterprise_enabled())


if __name__ == "__main__":
    unittest.main()
