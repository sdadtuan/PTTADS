"""Research P2 schema — SERP snapshots, keyword clusters."""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any


def _ddl_path() -> Path:
    return Path(__file__).resolve().parents[1] / "deploy" / "sql" / "seo_aeo_research_p2.sql"


def ensure_research_pg_schema(conn: Any) -> None:
    from ptt_seo.pg_schema import _split_sql

    ddl = _ddl_path().read_text(encoding="utf-8")
    with conn.cursor() as cur:
        for stmt in _split_sql(ddl):
            if stmt.strip():
                cur.execute(stmt)
    conn.commit()


def ensure_research_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS seo_keyword_clusters (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id     INTEGER NOT NULL,
            name            TEXT NOT NULL DEFAULT '',
            intent          TEXT NOT NULL DEFAULT 'informational',
            notes           TEXT NOT NULL DEFAULT '',
            status          TEXT NOT NULL DEFAULT 'active',
            created_at      TEXT NOT NULL DEFAULT '',
            updated_at      TEXT NOT NULL DEFAULT ''
        );
        CREATE INDEX IF NOT EXISTS idx_seo_clusters_customer ON seo_keyword_clusters (customer_id, status);

        CREATE TABLE IF NOT EXISTS seo_serp_snapshots (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id     INTEGER NOT NULL,
            keyword_id      INTEGER,
            phrase          TEXT NOT NULL DEFAULT '',
            snapshot_date   TEXT NOT NULL DEFAULT '',
            results_json    TEXT NOT NULL DEFAULT '[]',
            source          TEXT NOT NULL DEFAULT 'stub',
            created_at      TEXT NOT NULL DEFAULT ''
        );
        CREATE INDEX IF NOT EXISTS idx_seo_serp_customer_date ON seo_serp_snapshots (customer_id, snapshot_date);
        """
    )
    conn.commit()
