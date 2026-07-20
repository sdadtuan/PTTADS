"""Tests for SEO/AEO Phase 4 — GA4 OAuth (PG-only integrations)."""
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
from contextlib import contextmanager
from unittest.mock import patch

from ptt_seo import schema as seo_schema
from ptt_seo.connectors.ga4_api import fetch_daily_metrics, ga4_stub_mode
from ptt_seo.connectors.ga4_oauth import build_oauth_state, parse_oauth_state
from ptt_seo.connectors.ga4_sync import (
    ga4_sync_enabled,
    process_seo_ga4_sync_payload,
    sync_all_ga4_customers,
    sync_ga4_for_customer,
)
from ptt_seo.db import SeoDB


def _mem_db() -> SeoDB:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    seo_schema.ensure_schema(conn)
    return SeoDB(conn, "sqlite")


@contextmanager
def _fake_pg(db: SeoDB):
    yield db


class TestGa4OAuthState(unittest.TestCase):
    def test_state_roundtrip(self) -> None:
        state = build_oauth_state(customer_id=42, property_id="123456789")
        parsed = parse_oauth_state(state)
        self.assertEqual(parsed["customer_id"], 42)
        self.assertEqual(parsed["property_id"], "123456789")


class TestGa4ApiStub(unittest.TestCase):
    def test_stub_rows(self) -> None:
        with patch.dict(os.environ, {"PTT_GA4_SYNC_STUB": "1"}):
            self.assertTrue(ga4_stub_mode())
            from datetime import date

            rows = fetch_daily_metrics(
                "stub",
                "123456789",
                start_date=date(2026, 7, 1),
                end_date=date(2026, 7, 2),
            )
            self.assertGreaterEqual(len(rows), 1)
            self.assertIn("sessions", rows[0])
            self.assertIn("conversions", rows[0])
            self.assertIn("revenue", rows[0])
            organic = [r for r in rows if "organic" in (r.get("source_medium") or "")]
            self.assertTrue(any(r.get("revenue", 0) > 0 for r in organic))


class TestGa4SyncStub(unittest.TestCase):
    @patch.dict(os.environ, {"PTT_GA4_SYNC_STUB": "1"})
    @patch("ptt_seo.integrations.seo_pg_only")
    @patch("ptt_seo.connectors.ga4_sync.seo_pg_only")
    @patch("ptt_seo.connectors.ga4_sync.patch_integrations")
    @patch("ptt_seo.connectors.ga4_sync.get_ga4_integration")
    @patch("ptt_seo.connectors.ga4_sync.resolve_ga4_refresh_token")
    def test_sync_stub_writes_stats(
        self,
        mock_refresh,
        mock_get_ga4,
        mock_patch,
        mock_sync_pg,
        mock_int_pg,
    ) -> None:
        db = _mem_db()

        @contextmanager
        def fake_pg():
            yield db

        mock_sync_pg.side_effect = fake_pg
        mock_int_pg.side_effect = fake_pg
        mock_refresh.return_value = None
        mock_get_ga4.return_value = {"property_id": "123456789", "status": "connected"}
        mock_patch.return_value = {}

        outcome = sync_ga4_for_customer(1, days=7)
        self.assertTrue(outcome.get("ok"))
        row = db.execute(
            "SELECT COUNT(*) AS c FROM seo_ga4_daily_stats WHERE customer_id = ?", (1,)
        ).fetchone()
        self.assertGreater(int(row["c"]), 0)
        rev = db.execute(
            """

            SELECT COALESCE(SUM(revenue), 0) AS r FROM seo_ga4_daily_stats
            WHERE customer_id = ? AND source_medium LIKE '%organic%'
            """,
            (1,),
        ).fetchone()
        self.assertGreater(float(rev["r"]), 0)

    @patch.dict(os.environ, {"PTT_GA4_SYNC_STUB": "1"})
    @patch("ptt_seo.connectors.ga4_sync.sync_ga4_for_customer")
    def test_process_payload(self, mock_sync) -> None:
        mock_sync.return_value = {"ok": True, "rows_imported": 2}
        out = process_seo_ga4_sync_payload({"customer_id": 5, "days": 28})
        self.assertTrue(out["ok"])
        mock_sync.assert_called_once()


class TestGa4BatchSync(unittest.TestCase):
    def test_ga4_sync_enabled_flag(self) -> None:
        with patch.dict(os.environ, {"PTT_GA4_SYNC_ENABLED": "1"}, clear=False):
            self.assertTrue(ga4_sync_enabled())
        with patch.dict(os.environ, {"PTT_GA4_SYNC_ENABLED": "0"}, clear=False):
            self.assertFalse(ga4_sync_enabled())

    @patch.dict(os.environ, {"PTT_GA4_SYNC_ENABLED": "0", "PTT_GA4_SYNC_STUB": "0"}, clear=False)
    def test_sync_all_skipped_when_disabled(self) -> None:
        out = sync_all_ga4_customers()
        self.assertTrue(out.get("skipped"))
        self.assertEqual(out.get("reason"), "PTT_GA4_SYNC_ENABLED=0")

    @patch.dict(os.environ, {"PTT_GA4_SYNC_ENABLED": "1", "PTT_GA4_SYNC_STUB": "0"}, clear=False)
    @patch("ptt_seo.connectors.ga4_sync.list_ga4_connected_customer_ids")
    def test_sync_all_no_customers(self, mock_list) -> None:
        mock_list.return_value = []
        out = sync_all_ga4_customers()
        self.assertTrue(out.get("skipped"))
        self.assertEqual(out.get("reason"), "no_ga4_connected_customers")

    @patch.dict(os.environ, {"PTT_GA4_SYNC_ENABLED": "1", "PTT_GA4_SYNC_STUB": "1"}, clear=False)
    @patch("ptt_seo.connectors.ga4_sync.sync_ga4_for_customer")
    @patch("ptt_seo.connectors.ga4_sync.list_ga4_connected_customer_ids")
    def test_sync_all_batch(self, mock_list, mock_sync) -> None:
        mock_list.return_value = [1, 2]
        mock_sync.side_effect = [{"ok": True, "rows_imported": 3}, {"ok": False, "error": "fail"}]
        out = sync_all_ga4_customers(days=14)
        self.assertFalse(out["ok"])
        self.assertEqual(out["customers"], 2)
        self.assertEqual(out["ok_count"], 1)
        self.assertEqual(out["failed"], 1)
        self.assertEqual(mock_sync.call_count, 2)


if __name__ == "__main__":
    unittest.main()
