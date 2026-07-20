"""Tests for SEO/AEO Phase 4C — Authority Console."""
from __future__ import annotations


import os
import unittest

if os.environ.get("PTT_RUN_FLASK_TESTS") != "1":
    raise unittest.SkipTest(
        "Flask HTTP removed — set PTT_RUN_FLASK_TESTS=1 to run integration tests"
    )
import sqlite3
import unittest

from ptt_seo import schema as seo_schema
from ptt_seo.authority import (
    _domain_from_url,
    _pick,
    authority_summary,
    import_signals_csv,
    list_signals,
)
from ptt_seo.db import SeoDB


def _mem_db() -> SeoDB:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    seo_schema.ensure_schema(conn)
    return SeoDB(conn, "sqlite")


SAMPLE_CSV = """Referring page URL,Domain rating,Anchor text,Target URL,Status

https://example.com/blog/seo,45,best seo agency,https://client.vn/services,active
https://news.site/article,62,PTTADS,https://client.vn/,active
https://lost.ref/page,30,click here,https://client.vn/old,lost
"""


class TestAuthorityHelpers(unittest.TestCase):
    def test_domain_from_url(self) -> None:
        self.assertEqual(_domain_from_url("https://www.example.com/path"), "example.com")

    def test_pick_flexible_headers(self) -> None:
        row = {"Referring page URL": "https://a.com", "DR": "55"}
        self.assertEqual(_pick(row, ("referring page url",)), "https://a.com")


class TestAuthorityImport(unittest.TestCase):
    def test_import_ahrefs_csv(self) -> None:
        db = _mem_db()
        out = import_signals_csv(db, 1, SAMPLE_CSV, signal_type="backlink")
        self.assertTrue(out.get("ok"))
        self.assertEqual(out.get("rows_imported"), 3)
        rows = list_signals(db, 1)
        self.assertEqual(len(rows), 3)

    def test_upsert_updates_last_seen(self) -> None:
        db = _mem_db()
        import_signals_csv(db, 1, SAMPLE_CSV)
        import_signals_csv(db, 1, SAMPLE_CSV)
        count = db.execute("SELECT COUNT(*) AS c FROM seo_authority_signals WHERE customer_id = 1").fetchone()
        self.assertEqual(int(count["c"]), 3)

    def test_invalid_signal_type(self) -> None:
        db = _mem_db()
        out = import_signals_csv(db, 1, SAMPLE_CSV, signal_type="invalid")
        self.assertFalse(out.get("ok"))


class TestAuthoritySummary(unittest.TestCase):
    def test_summary_counts(self) -> None:
        db = _mem_db()
        import_signals_csv(db, 1, SAMPLE_CSV)
        import_signals_csv(
            db,
            1,
            "Source URL,Target URL\nhttps://cite.org,https://client.vn\n",
            signal_type="citation",
        )
        summary = authority_summary(db, 1)
        self.assertEqual(summary["backlinks_active"], 2)
        self.assertEqual(summary["backlinks_lost"], 1)
        self.assertEqual(summary["citations"], 1)
        self.assertGreater(summary["avg_dr"], 0)


if __name__ == "__main__":
    unittest.main()
