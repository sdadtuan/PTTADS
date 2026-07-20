"""Tests — PG ingest rules snapshot (Phase 2 cutover)."""
from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from crm_facebook_config import merge_facebook_config
from crm_lead_auto_assign import config_with_only
from crm_lead_rules import save_lead_config
from crm_lead_store import ensure_lead_schema
from crm_re_projects import ensure_re_projects_schema
from ptt_crm.lead_ingest_config import (
    _hydrate_rules_conn_from_snapshot,
    fetch_facebook_config_for_ingest,
    open_ingest_rules_conn,
    snapshot_has_rules,
    sync_ingest_rules_from_sqlite,
)

TS = "2026-06-05 12:00:00"
FB_CFG = {
    "enabled": True,
    "page_id": "page_123",
    "form_ids": ["form_abc"],
    "auto_optimize": True,
    "auto_assign": True,
}


class TestIngestRulesSnapshot(unittest.TestCase):
    def _seed_sqlite(self, db: Path) -> None:
        conn = sqlite3.connect(db)
        conn.row_factory = sqlite3.Row
        ensure_re_projects_schema(conn)
        ensure_lead_schema(conn)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS crm_staff (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                notes TEXT NOT NULL DEFAULT '',
                active INTEGER NOT NULL DEFAULT 1,
                sales_level TEXT NOT NULL DEFAULT 'b',
                internal_code TEXT NOT NULL DEFAULT ''
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS crm_assignment_state (
                pool_key TEXT PRIMARY KEY,
                last_staff_id INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        conn.execute(
            "INSERT INTO crm_staff (name, notes, active, sales_level) VALUES (?, ?, 1, ?)",
            ("NV FB", "q.7 facebook", "b"),
        )
        save_lead_config(
            conn,
            config={
                "assign_config": config_with_only("skill_based", "round_robin"),
                "facebook_config": FB_CFG,
            },
            updated_by="test",
            ts=TS,
        )
        conn.commit()
        conn.close()

    def test_snapshot_has_rules(self) -> None:
        self.assertFalse(snapshot_has_rules(None))
        self.assertTrue(snapshot_has_rules({"lead_config": {"facebook_config": FB_CFG}}))

    def test_hydrate_and_fetch_facebook_config(self) -> None:
        snap = {
            "lead_config": {
                "assign_config": config_with_only("skill_based"),
                "facebook_config": FB_CFG,
            },
            "staff_rows": [{"id": 1, "name": "NV", "notes": "q.7", "active": 1, "sales_level": "b", "internal_code": ""}],
            "assignment_state": [],
            "staff_assign_scope": [],
            "catalog_services": [],
            "catalog_industries": [],
            "staff_workload": {},
        }
        conn = _hydrate_rules_conn_from_snapshot(snap)
        try:
            fb = fetch_facebook_config_for_ingest(conn)
            self.assertTrue(merge_facebook_config(fb).get("enabled"))
            row = conn.execute("SELECT COUNT(*) AS c FROM crm_staff").fetchone()
            self.assertEqual(int(row["c"]), 1)
        finally:
            conn.close()

    @patch("ptt_crm.lead_ingest_config.pg_ingest_rules_ready", return_value=True)
    @patch("ptt_crm.lead_ingest_config.fetch_pg_ingest_rules_snapshot")
    @patch("ptt_crm.config.ingest_rules_source", return_value="pg")
    def test_open_ingest_rules_conn_from_pg(
        self,
        _src: unittest.mock.MagicMock,
        mock_fetch: unittest.mock.MagicMock,
        _ready: unittest.mock.MagicMock,
    ) -> None:
        mock_fetch.return_value = {
            "lead_config": {"facebook_config": FB_CFG},
            "staff_rows": [],
            "assignment_state": [],
            "staff_assign_scope": [],
            "catalog_services": [],
            "catalog_industries": [],
            "staff_workload": {},
        }
        conn = open_ingest_rules_conn()
        try:
            row = conn.execute(
                "SELECT config_json FROM crm_lead_settings WHERE config_key = 'global'"
            ).fetchone()
            cfg = json.loads(row["config_json"])
            self.assertTrue(cfg.get("facebook_config", {}).get("enabled"))
        finally:
            conn.close()

    @patch("ptt_crm.lead_ingest_config.pg_connection")
    @patch("ptt_crm.lead_ingest_config.pg_ingest_rules_ready", return_value=True)
    @patch("ptt_crm.lead_ingest_config._collect_staff_workload_from_pg", return_value={})
    def test_sync_from_sqlite_writes_pg(
        self,
        _wl: unittest.mock.MagicMock,
        _ready: unittest.mock.MagicMock,
        mock_pg: unittest.mock.MagicMock,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "rules.db"
            self._seed_sqlite(db)
            captured: dict[str, str] = {}

            class FakeCursor:
                def __enter__(self):
                    return self

                def __exit__(self, *_a):
                    return False

                def execute(self, sql, params=None):
                    if "UPDATE crm_ingest_rules_snapshot" in sql and params:
                        captured["lead_config"] = params[0]

            class FakeConn:
                def __enter__(self):
                    return self

                def __exit__(self, *_a):
                    return False

                def cursor(self):
                    return FakeCursor()

                def commit(self):
                    return None

            mock_pg.return_value = FakeConn()
            with patch("ptt_jobs.config.sqlite_db_path", return_value=str(db)):
                out = sync_ingest_rules_from_sqlite(sqlite_path=str(db))
            self.assertTrue(out.get("ok"))
            cfg = json.loads(captured["lead_config"])
            self.assertTrue(cfg.get("facebook_config", {}).get("enabled"))


if __name__ == "__main__":
    unittest.main()
