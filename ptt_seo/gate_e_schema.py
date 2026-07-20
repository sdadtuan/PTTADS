"""Gate E schema — OKR/KPI tree, crawl schedules, GA4 revenue columns."""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any


def _gate_e_ddl_path() -> Path:
    return Path(__file__).resolve().parents[1] / "deploy" / "sql" / "seo_aeo_gate_e.sql"


def _sqlite_has_column(conn: sqlite3.Connection, table: str, column: str) -> bool:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return any(str(r[1]) == column for r in rows)


def ensure_gate_e_pg_schema(conn: Any) -> None:
    from ptt_seo.pg_schema import _split_sql

    ddl = _gate_e_ddl_path().read_text(encoding="utf-8")
    with conn.cursor() as cur:
        for stmt in _split_sql(ddl):
            if stmt.strip():
                cur.execute(stmt)
    conn.commit()


def ensure_gate_e_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS seo_strategy_goals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER NOT NULL,
            title TEXT NOT NULL DEFAULT '',
            description TEXT NOT NULL DEFAULT '',
            period TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'active',
            sort_order INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT ''
        );
        CREATE INDEX IF NOT EXISTS idx_seo_strategy_goals_customer
            ON seo_strategy_goals (customer_id, status);

        CREATE TABLE IF NOT EXISTS seo_strategy_kpis (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER NOT NULL,
            goal_id INTEGER NOT NULL,
            initiative_id INTEGER,
            metric_key TEXT NOT NULL DEFAULT '',
            metric_label TEXT NOT NULL DEFAULT '',
            target_value REAL,
            current_value REAL,
            unit TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL DEFAULT ''
        );
        CREATE INDEX IF NOT EXISTS idx_seo_strategy_kpis_goal ON seo_strategy_kpis (goal_id);

        CREATE TABLE IF NOT EXISTS seo_crawl_schedules (
            customer_id INTEGER PRIMARY KEY,
            frequency_days INTEGER NOT NULL DEFAULT 30,
            webhook_secret TEXT NOT NULL DEFAULT '',
            last_ingest_at TEXT,
            active INTEGER NOT NULL DEFAULT 1,
            updated_at TEXT NOT NULL DEFAULT ''
        );
        """
    )
    if not _sqlite_has_column(conn, "seo_initiatives", "goal_id"):
        conn.execute("ALTER TABLE seo_initiatives ADD COLUMN goal_id INTEGER")
    if not _sqlite_has_column(conn, "seo_ga4_daily_stats", "conversions"):
        conn.execute("ALTER TABLE seo_ga4_daily_stats ADD COLUMN conversions REAL NOT NULL DEFAULT 0")
    if not _sqlite_has_column(conn, "seo_ga4_daily_stats", "revenue"):
        conn.execute("ALTER TABLE seo_ga4_daily_stats ADD COLUMN revenue REAL NOT NULL DEFAULT 0")
    conn.commit()
