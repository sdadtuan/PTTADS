"""Tests for SEO/AEO Phase 4A — AEO Console v2 (PG-first cutover)."""
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
import warnings
from contextlib import contextmanager
from unittest.mock import patch

from ptt_seo.db import SeoDB
from ptt_seo.schema import ensure_schema


def _seo_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    ensure_schema(conn)
    conn.executescript(
        """

        CREATE TABLE IF NOT EXISTS seo_ai_mentions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER NOT NULL,
            question_id INTEGER,
            platform TEXT NOT NULL DEFAULT 'anthropic_sim',
            query_text TEXT NOT NULL DEFAULT '',
            source_url TEXT NOT NULL DEFAULT '',
            citation_status TEXT NOT NULL DEFAULT 'absent',
            brand_visible INTEGER NOT NULL DEFAULT 0,
            gap_notes TEXT NOT NULL DEFAULT '',
            ai_response TEXT NOT NULL DEFAULT '',
            legacy_scan_id INTEGER,
            detected_at TEXT NOT NULL DEFAULT ''
        );
        """
    )
    return conn


class TestAeoCoverage(unittest.TestCase):
    @patch("ptt_seo.aeo.seo_read")
    def test_aeo_coverage_empty(self, mock_read) -> None:
        seo = _seo_conn()

        @contextmanager
        def fake_read():
            yield SeoDB(seo, "sqlite")

        mock_read.side_effect = fake_read
        from ptt_seo.aeo import aeo_coverage_summary

        out = aeo_coverage_summary(1)
        self.assertEqual(out["total"], 0)
        self.assertEqual(out["coverage_pct"], 0.0)

    @patch("ptt_seo.aeo.seo_read")
    def test_aeo_coverage_with_visible_queries(self, mock_read) -> None:
        seo = _seo_conn()
        from ptt_seo.aeo_store import add_aeo_question, insert_mention

        db = SeoDB(seo, "sqlite")
        q1 = add_aeo_question(db, 1, "q1?", "Brand")
        q2 = add_aeo_question(db, 1, "q2?", "Brand")
        insert_mention(
            db,
            customer_id=1,
            question_id=q1,
            query_text="q1?",
            scan={"brand_visible": True, "gap_notes": "", "ai_response": "r1", "detected_at": "2026-07-18"},
        )
        insert_mention(
            db,
            customer_id=1,
            question_id=q2,
            query_text="q2?",
            scan={"brand_visible": False, "gap_notes": "gap", "ai_response": "r2", "detected_at": "2026-07-17"},
        )

        @contextmanager
        def fake_read():
            yield SeoDB(seo, "sqlite")

        mock_read.side_effect = fake_read
        from ptt_seo.aeo import aeo_coverage_summary

        out = aeo_coverage_summary(1)
        self.assertEqual(out["total"], 2)
        self.assertEqual(out["visible"], 1)
        self.assertEqual(out["coverage_pct"], 50.0)


class TestAeoScanStub(unittest.TestCase):
    @patch.dict(os.environ, {"PTT_AEO_SCAN_STUB": "1", "SEO_AEO_DB": "sqlite"})
    @patch("ptt_seo.connectors.aeo_scan.seo_write")
    @patch("ptt_seo.connectors.aeo_scan.seo_read")
    def test_stub_scan_writes_mention(self, mock_read, mock_write) -> None:
        seo = _seo_conn()
        from ptt_seo.aeo_store import add_aeo_question

        db = SeoDB(seo, "sqlite")
        qid = add_aeo_question(db, 1, "seo agency?", "PTTADS")

        @contextmanager
        def fake_read():
            yield SeoDB(seo, "sqlite")

        @contextmanager
        def fake_write():
            yield SeoDB(seo, "sqlite")

        mock_read.side_effect = fake_read
        mock_write.side_effect = fake_write

        from ptt_seo.connectors.aeo_scan import scan_query

        out = scan_query(1, qid)
        self.assertTrue(out.get("ok"))
        row = seo.execute("SELECT COUNT(*) AS c FROM seo_ai_mentions WHERE customer_id = 1").fetchone()
        self.assertEqual(int(row["c"]), 1)

    @patch.dict(os.environ, {"PTT_AEO_SCAN_STUB": "1"})
    @patch("ptt_seo.aeo.list_aeo_queries")
    @patch("ptt_seo.connectors.aeo_scan.scan_query")
    def test_batch_scan(self, mock_scan, mock_list) -> None:
        from ptt_seo.connectors.aeo_scan import scan_customer_batch

        mock_list.return_value = [{"id": 1}, {"id": 2}]
        mock_scan.side_effect = [{"ok": True}, {"ok": False, "error": "fail"}]
        out = scan_customer_batch(1)
        self.assertFalse(out["ok"])
        self.assertEqual(out["scanned"], 2)
        self.assertEqual(out["ok_count"], 1)


class TestAeoScanPayload(unittest.TestCase):
    @patch.dict(os.environ, {"PTT_AEO_SCAN_STUB": "1"})
    @patch("ptt_seo.connectors.aeo_scan.scan_customer_batch")
    def test_process_payload(self, mock_batch) -> None:
        mock_batch.return_value = {"ok": True, "scanned": 1}
        from ptt_seo.connectors.aeo_scan import process_seo_aeo_scan_payload

        out = process_seo_aeo_scan_payload({"customer_id": 5})
        self.assertTrue(out["ok"])
        mock_batch.assert_called_once()


class TestCitationStatus(unittest.TestCase):
    def test_citation_mapping(self) -> None:
        from ptt_seo.aeo_store import citation_status

        self.assertEqual(citation_status(True, ""), "cited")
        self.assertEqual(citation_status(True, "gap"), "mentioned")
        self.assertEqual(citation_status(False, "gap"), "absent")


class TestAeoStubMode(unittest.TestCase):
    def test_stub_flag(self) -> None:
        from ptt_seo.connectors.aeo_scan import aeo_stub_mode

        with patch.dict(os.environ, {"PTT_AEO_SCAN_STUB": "1"}):
            self.assertTrue(aeo_stub_mode())
        with patch.dict(os.environ, {"PTT_AEO_SCAN_STUB": "0"}):
            self.assertFalse(aeo_stub_mode())


class TestCrmAeoDeprecated(unittest.TestCase):
    def test_list_queries_deprecation(self) -> None:
        with patch("ptt_seo.aeo.list_aeo_queries", return_value=[]):
            import crm_aeo

            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                crm_aeo.list_queries(None, 1)
            self.assertTrue(any("deprecated" in str(w.message).lower() for w in caught))


if __name__ == "__main__":
    unittest.main()
