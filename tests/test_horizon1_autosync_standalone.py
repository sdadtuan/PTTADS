#!/usr/bin/env python3
"""Unit tests — Horizon 1 autosync standalone + crm_sqlite."""
from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ptt_crm.crm_sqlite import crm_connection, crm_ts, db_path, get_connection


class CrmSqliteTests(unittest.TestCase):
    def test_crm_ts_format(self) -> None:
        ts = crm_ts()
        self.assertRegex(ts, r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$")

    def test_db_path_override(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "custom.db"
            with patch.dict(os.environ, {"PTT_DB_PATH": str(p)}, clear=False):
                self.assertEqual(db_path(), p)

    def test_get_connection_opens_sqlite(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "test.db"
            with patch.dict(os.environ, {"PTT_DB_PATH": str(p)}, clear=False):
                conn = get_connection()
                try:
                    conn.execute("SELECT 1")
                finally:
                    conn.close()
                self.assertTrue(p.is_file())

    def test_crm_connection_context(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "ctx.db"
            with patch.dict(os.environ, {"PTT_DB_PATH": str(p)}, clear=False):
                with crm_connection() as conn:
                    conn.execute("CREATE TABLE t (id INTEGER)")
                    conn.commit()


class AutosyncStandaloneTests(unittest.TestCase):
    def test_no_app_import_in_autosync(self) -> None:
        root = Path(__file__).resolve().parents[1]
        text = (root / "crm_facebook_autosync.py").read_text(encoding="utf-8")
        self.assertNotIn("from app import", text)

    def test_gunicorn_guard_respected(self) -> None:
        from crm_facebook_autosync import start_facebook_autosync_worker

        class FakeApp:
            pass

        with patch.dict(os.environ, {"CRM_FACEBOOK_BACKGROUND_IN_GUNICORN": "0"}, clear=False):
            start_facebook_autosync_worker(FakeApp())


if __name__ == "__main__":
    unittest.main()
