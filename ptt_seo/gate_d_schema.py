"""Gate D schema — CWV snapshots, crawl import log."""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any


def _gate_d_ddl_path() -> Path:
    return Path(__file__).resolve().parents[1] / "deploy" / "sql" / "seo_aeo_gate_d.sql"


def ensure_gate_d_pg_schema(conn: Any) -> None:
    from ptt_seo.pg_schema import _split_sql

    ddl = _gate_d_ddl_path().read_text(encoding="utf-8")
    with conn.cursor() as cur:
        for stmt in _split_sql(ddl):
            if stmt.strip():
                cur.execute(stmt)
    conn.commit()


def ensure_gate_d_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS seo_cwv_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER NOT NULL,
            url TEXT NOT NULL DEFAULT '',
            lcp_ms REAL,
            cls REAL,
            inp_ms REAL,
            performance_score REAL,
            cwv_rating TEXT NOT NULL DEFAULT 'unknown',
            source TEXT NOT NULL DEFAULT 'pagespeed',
            checked_at TEXT NOT NULL DEFAULT ''
        );
        CREATE INDEX IF NOT EXISTS idx_seo_cwv_customer ON seo_cwv_snapshots (customer_id, checked_at);

        CREATE TABLE IF NOT EXISTS seo_crawl_import_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER NOT NULL,
            rows_imported INTEGER NOT NULL DEFAULT 0,
            imported_at TEXT NOT NULL DEFAULT ''
        );
        CREATE INDEX IF NOT EXISTS idx_seo_crawl_log_customer ON seo_crawl_import_log (customer_id, imported_at);
        """
    )
    conn.commit()
