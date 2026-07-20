"""Gate C P3 schema migrations."""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any


def _gate_c_ddl_path() -> Path:
    return Path(__file__).resolve().parents[1] / "deploy" / "sql" / "seo_aeo_p3_gate_c.sql"


def ensure_p3_gate_c_pg_schema(conn: Any) -> None:
    from ptt_seo.pg_schema import _split_sql

    ddl = _gate_c_ddl_path().read_text(encoding="utf-8")
    with conn.cursor() as cur:
        for stmt in _split_sql(ddl):
            if stmt.strip():
                cur.execute(stmt)
    conn.commit()


def ensure_p3_gate_c_schema(conn: sqlite3.Connection) -> None:
    cols = {r[1] for r in conn.execute("PRAGMA table_info(seo_content)").fetchall()}
    if "temporal_workflow_id" not in cols:
        conn.execute("ALTER TABLE seo_content ADD COLUMN temporal_workflow_id TEXT NOT NULL DEFAULT ''")
    conn.commit()
