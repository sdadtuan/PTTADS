"""Apply PostgreSQL schema seo_aeo (Phase 3.5)."""
from __future__ import annotations

from pathlib import Path
from typing import Any


def _ddl_path() -> Path:
    return Path(__file__).resolve().parents[1] / "deploy" / "sql" / "seo_aeo_pg_schema.sql"


def ensure_pg_schema(conn: Any) -> None:
    ddl = _ddl_path().read_text(encoding="utf-8")
    with conn.cursor() as cur:
        cur.execute("CREATE SCHEMA IF NOT EXISTS seo_aeo")
        for stmt in _split_sql(ddl):
            if stmt.strip():
                cur.execute(stmt)
    conn.commit()
    _migrate_aeo_cutover(conn)
    from ptt_seo.enterprise_schema import ensure_enterprise_pg_schema

    ensure_enterprise_pg_schema(conn)
    from ptt_seo.p2_schema import ensure_p2_pg_schema

    ensure_p2_pg_schema(conn)
    from ptt_seo.research_schema import ensure_research_pg_schema

    ensure_research_pg_schema(conn)


def _migrate_aeo_cutover(conn: Any) -> None:
    """Add AEO cutover columns to existing seo_questions (idempotent)."""
    additions = [
        ("legacy_aeo_query_id", "INTEGER"),
        ("brand_name", "TEXT NOT NULL DEFAULT ''"),
        ("lifecycle_id", "INTEGER"),
        ("notes", "TEXT NOT NULL DEFAULT ''"),
    ]
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT column_name FROM information_schema.columns
            WHERE table_schema = 'seo_aeo' AND table_name = 'seo_questions'
            """
        )
        existing = {r["column_name"] if isinstance(r, dict) else r[0] for r in cur.fetchall()}
        for name, ddl in additions:
            if name not in existing:
                cur.execute(f"ALTER TABLE seo_aeo.seo_questions ADD COLUMN {name} {ddl}")
        cur.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_seo_questions_legacy_aeo
            ON seo_aeo.seo_questions (legacy_aeo_query_id)
            WHERE legacy_aeo_query_id IS NOT NULL
            """
        )
    conn.commit()


def pg_seo_ready(conn: Any) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = 'seo_aeo' AND table_name = 'seo_client_settings'
            """
        )
        return cur.fetchone() is not None


def _split_sql(text: str) -> list[str]:
    parts: list[str] = []
    buf: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("--"):
            continue
        buf.append(line)
        if stripped.endswith(";"):
            parts.append("\n".join(buf))
            buf = []
    if buf:
        parts.append("\n".join(buf))
    return parts
