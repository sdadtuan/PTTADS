"""P2 schema — technical task link + report schedules (SQLite tests + PG apply)."""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any


def _p2_ddl_path() -> Path:
    return Path(__file__).resolve().parents[1] / "deploy" / "sql" / "seo_aeo_p2.sql"


def _p3df_ddl_path() -> Path:
    return Path(__file__).resolve().parents[1] / "deploy" / "sql" / "seo_aeo_p3df.sql"


def ensure_p3df_pg_schema(conn: Any) -> None:
    from ptt_seo.pg_schema import _split_sql

    ddl = _p3df_ddl_path().read_text(encoding="utf-8")
    with conn.cursor() as cur:
        for stmt in _split_sql(ddl):
            if stmt.strip():
                cur.execute(stmt)
    conn.commit()


def ensure_p2_pg_schema(conn: Any) -> None:
    from ptt_seo.pg_schema import _split_sql

    ddl = _p2_ddl_path().read_text(encoding="utf-8")
    with conn.cursor() as cur:
        for stmt in _split_sql(ddl):
            if stmt.strip():
                cur.execute(stmt)
    conn.commit()
    ensure_p3df_pg_schema(conn)
    from ptt_seo.p3_schema import ensure_p3_gate_c_pg_schema

    ensure_p3_gate_c_pg_schema(conn)


def ensure_p2_schema(conn: sqlite3.Connection) -> None:
    cols = {r[1] for r in conn.execute("PRAGMA table_info(seo_technical_issues)").fetchall()}
    if "crm_task_id" not in cols:
        conn.execute("ALTER TABLE seo_technical_issues ADD COLUMN crm_task_id INTEGER")
    if "lifecycle_id" not in cols:
        conn.execute("ALTER TABLE seo_technical_issues ADD COLUMN lifecycle_id INTEGER")
    sched_cols = {r[1] for r in conn.execute("PRAGMA table_info(seo_report_schedules)").fetchall()}
    if sched_cols and "cc_emails_json" not in sched_cols:
        conn.execute("ALTER TABLE seo_report_schedules ADD COLUMN cc_emails_json TEXT NOT NULL DEFAULT '[]'")
    if sched_cols and "bcc_emails_json" not in sched_cols:
        conn.execute("ALTER TABLE seo_report_schedules ADD COLUMN bcc_emails_json TEXT NOT NULL DEFAULT '[]'")
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS seo_report_schedules (
            id                      INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id             INTEGER NOT NULL,
            dashboard_type          TEXT NOT NULL DEFAULT 'executive',
            cadence                 TEXT NOT NULL DEFAULT 'weekly',
            day_of_week             INTEGER NOT NULL DEFAULT 0,
            day_of_month            INTEGER NOT NULL DEFAULT 1,
            recipient_emails_json   TEXT NOT NULL DEFAULT '[]',
            cc_emails_json          TEXT NOT NULL DEFAULT '[]',
            bcc_emails_json         TEXT NOT NULL DEFAULT '[]',
            active                  INTEGER NOT NULL DEFAULT 1,
            last_sent_at            TEXT,
            next_run_at             TEXT,
            created_at              TEXT NOT NULL DEFAULT '',
            updated_at              TEXT NOT NULL DEFAULT ''
        );
        CREATE INDEX IF NOT EXISTS idx_seo_report_schedules_due
            ON seo_report_schedules (active, next_run_at);

        CREATE TABLE IF NOT EXISTS seo_report_schedule_runs (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            schedule_id     INTEGER NOT NULL,
            status          TEXT NOT NULL DEFAULT 'pending',
            error_message   TEXT NOT NULL DEFAULT '',
            sent_at         TEXT,
            created_at      TEXT NOT NULL DEFAULT ''
        );
        """
    )
    from ptt_seo.p3_schema import ensure_p3_gate_c_schema

    ensure_p3_gate_c_schema(conn)
