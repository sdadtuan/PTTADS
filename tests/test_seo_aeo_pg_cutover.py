"""Tests for SEO/AEO Phase 3.5 — PostgreSQL cutover layer."""
from __future__ import annotations

import os
import sqlite3
import unittest
from contextlib import contextmanager
from unittest.mock import patch

from ptt_seo import schema as seo_schema
from ptt_seo.client_settings import get_settings, upsert_settings
from ptt_seo.db import SeoDB, seo_db_mode, seo_read, seo_write
from ptt_seo.research import create_keyword, list_keywords


def _mem_sqlite() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    seo_schema.ensure_schema(conn)
    return conn


class TestSeoDBLayer(unittest.TestCase):
    def test_seo_db_sqlite_wrapper(self) -> None:
        conn = _mem_sqlite()
        db = SeoDB(conn, "sqlite")
        db.execute(
            "INSERT INTO seo_client_settings (customer_id, domains_json, updated_at) VALUES (?,?,?)",
            (1, "[]", "2026-01-01"),
        )
        db.commit()
        row = db.execute("SELECT customer_id FROM seo_client_settings WHERE customer_id = ?", (1,)).fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(int(row["customer_id"]), 1)

    def test_seo_read_context_sqlite_default(self) -> None:
        prev = os.environ.get("SEO_AEO_DB")
        os.environ["SEO_AEO_DB"] = "sqlite"
        try:
            import sqlite3
            from unittest.mock import patch

            from ptt_seo import schema as seo_schema
            from ptt_seo.db import SeoDB, seo_read

            mem = sqlite3.connect(":memory:")
            mem.row_factory = sqlite3.Row
            seo_schema.ensure_schema(mem)

            @contextmanager
            def fake_sqlite():
                yield mem

            with patch("ptt_seo.db._sqlite_raw", fake_sqlite):
                with seo_read() as conn:
                    conn.execute(
                        "INSERT INTO seo_keywords (customer_id, phrase, created_at) VALUES (?,?,?)",
                        (88001, "test-read-ctx", "2026-01-01"),
                    )
                    conn.commit()
                    rows = list_keywords(conn, 88001)
                    self.assertEqual(len(rows), 1)
        finally:
            if prev is None:
                os.environ.pop("SEO_AEO_DB", None)
            else:
                os.environ["SEO_AEO_DB"] = prev

    def test_settings_roundtrip_sqlite_via_seo_write(self) -> None:
        prev = os.environ.get("SEO_AEO_DB")
        os.environ["SEO_AEO_DB"] = "sqlite"
        try:
            with seo_write() as conn:
                upsert_settings(conn, 42, {"domains": ["example.com"], "industry": "SaaS"})
                s = get_settings(conn, 42)
            self.assertEqual(s["domains"], ["example.com"])
            self.assertEqual(s["industry"], "SaaS")
        finally:
            if prev is None:
                os.environ.pop("SEO_AEO_DB", None)
            else:
                os.environ["SEO_AEO_DB"] = prev


class TestPgCutoverOptional(unittest.TestCase):
    """Run against real PG when DATABASE_URL is available."""

    def setUp(self) -> None:
        try:
            from ptt_jobs.db import pg_available

            self.pg_ok = pg_available()
        except Exception:
            self.pg_ok = False

    @unittest.skipUnless(
        os.environ.get("SEO_AEO_PG_TEST") == "1",
        "Set SEO_AEO_PG_TEST=1 and DATABASE_URL to run PG integration tests",
    )
    def test_pg_keyword_roundtrip(self) -> None:
        if not self.pg_ok:
            self.skipTest("PostgreSQL unavailable")
        prev = os.environ.get("SEO_AEO_DB")
        os.environ["SEO_AEO_DB"] = "pg"
        try:
            with seo_write() as conn:
                kid = create_keyword(conn, 9999, {"phrase": "pg cutover test"})
                self.assertGreater(kid, 0)
                rows = list_keywords(conn, 9999)
                self.assertTrue(any(r["phrase"] == "pg cutover test" for r in rows))
                conn.execute("DELETE FROM seo_keywords WHERE customer_id = ?", (9999,))
                conn.commit()
        finally:
            if prev is None:
                os.environ.pop("SEO_AEO_DB", None)
            else:
                os.environ["SEO_AEO_DB"] = prev


class TestModeEnv(unittest.TestCase):
    def test_default_mode_sqlite(self) -> None:
        prev = os.environ.pop("SEO_AEO_DB", None)
        try:
            self.assertEqual(seo_db_mode(), "sqlite")
        finally:
            if prev:
                os.environ["SEO_AEO_DB"] = prev


if __name__ == "__main__":
    unittest.main()
