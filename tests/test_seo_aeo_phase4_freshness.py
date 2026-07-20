"""Tests for SEO/AEO Phase 4B — Content Freshness."""
from __future__ import annotations


import os
import unittest

if os.environ.get("PTT_RUN_FLASK_TESTS") != "1":
    raise unittest.SkipTest(
        "Flask HTTP removed — set PTT_RUN_FLASK_TESTS=1 to run integration tests"
    )
import os
import sqlite3
import unittest
from datetime import date, timedelta
from unittest.mock import patch

from ptt_seo import schema as seo_schema
from ptt_seo.connectors.freshness_signals import traffic_delta_pct
from ptt_seo.db import SeoDB
from ptt_seo.freshness import (
    compute_decay_score,
    freshness_sync_enabled,
    process_seo_freshness_scan_payload,
    refresh_priority,
    score_content_item,
)


def _mem_db() -> SeoDB:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    seo_schema.ensure_schema(conn)
    return SeoDB(conn, "sqlite")


class TestDecayScore(unittest.TestCase):
    def test_old_content_with_traffic_drop(self) -> None:
        score = compute_decay_score(
            age_days=200,
            traffic_delta_pct=-35.0,
            gsc_clicks_current=5,
            gsc_clicks_previous=20,
            workflow_status="published",
        )
        self.assertGreaterEqual(score, 60.0)

    def test_non_scoreable_status_zero(self) -> None:
        score = compute_decay_score(
            age_days=365,
            traffic_delta_pct=-50.0,
            gsc_clicks_current=1,
            gsc_clicks_previous=100,
            workflow_status="in_writing",
        )
        self.assertEqual(score, 0.0)

    def test_fresh_published_low_score(self) -> None:
        score = compute_decay_score(
            age_days=7,
            traffic_delta_pct=10.0,
            gsc_clicks_current=50,
            gsc_clicks_previous=45,
            workflow_status="monitoring",
        )
        self.assertLess(score, 40.0)


class TestRefreshPriority(unittest.TestCase):
    def test_bands(self) -> None:
        self.assertEqual(refresh_priority(85), "urgent")
        self.assertEqual(refresh_priority(65), "high")
        self.assertEqual(refresh_priority(45), "medium")
        self.assertEqual(refresh_priority(10), "low")


class TestTrafficDelta(unittest.TestCase):
    def test_delta_pct(self) -> None:
        self.assertEqual(traffic_delta_pct(70, 100), -30.0)
        self.assertIsNone(traffic_delta_pct(10, 0))


class TestScoreContentItem(unittest.TestCase):
    def test_scores_and_persists(self) -> None:
        db = _mem_db()
        conn = db
        old = (date.today() - timedelta(days=200)).isoformat()
        conn.execute(
            """

            INSERT INTO seo_content (
                customer_id, title, slug, workflow_status, publish_date, created_at, updated_at,
                brief_json, outline_json, body_html, content_type, intent, funnel_stage
            ) VALUES (1, 'Old post', '/blog/old', 'published', ?, ?, ?, '{}', '{}', '', 'blog', '', '')
            """,
            (old, old, old),
        )
        conn.execute(
            """
            INSERT INTO seo_gsc_daily_stats (
                customer_id, stat_date, query, page, clicks, impressions, created_at
            ) VALUES (1, date('now', '-3 days'), '', '/blog/old', 5, 100, datetime('now'))
            """
        )
        conn.execute(
            """
            INSERT INTO seo_gsc_daily_stats (
                customer_id, stat_date, query, page, clicks, impressions, created_at
            ) VALUES (1, date('now', '-35 days'), '', '/blog/old', 30, 200, datetime('now'))
            """
        )
        conn.commit()

        out = score_content_item(conn, 1, 1)
        self.assertTrue(out.get("ok"))
        self.assertGreater(out.get("decay_score", 0), 0)
        row = conn.execute(
            "SELECT decay_score FROM seo_content_freshness WHERE content_id = 1"
        ).fetchone()
        self.assertIsNotNone(row)


class TestApplyRefreshFlags(unittest.TestCase):
    def test_transitions_high_decay(self) -> None:
        db = _mem_db()
        conn = db
        conn.execute(
            """
            INSERT INTO seo_content (
                customer_id, title, workflow_status, created_at, updated_at,
                brief_json, outline_json, body_html, content_type, intent, funnel_stage, slug
            ) VALUES (1, 'Stale', 'published', datetime('now'), datetime('now'), '{}', '{}', '', 'blog', '', '', '')
            """
        )
        conn.commit()
        cid = int(conn.execute("SELECT id FROM seo_content").fetchone()["id"])
        conn.execute(
            """
            INSERT INTO seo_content_freshness (
                customer_id, content_id, decay_score, age_days, signals_json,
                refresh_priority, last_scored_at
            ) VALUES (1, ?, 75, 200, '{}', 'high', datetime('now'))
            """,
            (cid,),
        )
        conn.commit()
        from ptt_seo.freshness import apply_refresh_flags

        n = apply_refresh_flags(conn, 1, threshold=60.0)
        self.assertEqual(n, 1)
        st = conn.execute("SELECT workflow_status FROM seo_content WHERE id = ?", (cid,)).fetchone()
        self.assertEqual(st["workflow_status"], "refresh_required")


class TestFreshnessBatch(unittest.TestCase):
    def test_sync_enabled_flag(self) -> None:
        with patch.dict(os.environ, {"PTT_FRESHNESS_SCAN_ENABLED": "1"}, clear=False):
            self.assertTrue(freshness_sync_enabled())
        with patch.dict(os.environ, {"PTT_FRESHNESS_SCAN_ENABLED": "0"}, clear=False):
            self.assertFalse(freshness_sync_enabled())

    @patch.dict(os.environ, {"PTT_FRESHNESS_SCAN_ENABLED": "0"}, clear=False)
    def test_scan_all_skipped(self) -> None:
        from ptt_seo.freshness import scan_all_freshness_customers

        out = scan_all_freshness_customers()
        self.assertTrue(out.get("skipped"))

    @patch("ptt_seo.freshness.score_customer_content")
    def test_process_payload_single(self, mock_score) -> None:
        mock_score.return_value = {"ok": True, "scored": 2}
        out = process_seo_freshness_scan_payload({"customer_id": 3})
        self.assertTrue(out["ok"])
        mock_score.assert_called_once_with(3)


if __name__ == "__main__":
    unittest.main()
