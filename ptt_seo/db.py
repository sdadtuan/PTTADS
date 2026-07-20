"""SEO/AEO database layer — SQLite legacy + PostgreSQL cutover (Phase 3.5)."""
from __future__ import annotations

import os
import re
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Literal

SeoBackend = Literal["sqlite", "pg"]

_DATE_NOW = re.compile(
    r"date\s*\(\s*'now'\s*,\s*'-(\d+)\s+days'\s*\)",
    re.IGNORECASE,
)
_DATETIME_NOW = re.compile(
    r"datetime\s*\(\s*'now'\s*,\s*'-(\d+)\s+days'\s*\)",
    re.IGNORECASE,
)


def seo_db_mode() -> str:
    return os.environ.get("SEO_AEO_DB", "sqlite").strip().lower() or "sqlite"


def seo_uses_pg() -> bool:
    return seo_db_mode() in {"pg", "dual"}


def seo_write_dual() -> bool:
    return seo_db_mode() == "dual"


def _sqlite_path() -> Path:
    raw = os.environ.get("PTT_SQLITE_PATH", "ptt.db").strip()
    p = Path(raw)
    if p.is_absolute():
        return p
    return Path(__file__).resolve().parents[1] / p


def _adapt_sql(sql: str, backend: SeoBackend) -> str:
    if backend == "sqlite":
        return sql
    out = sql.replace("?", "%s")
    out = _DATE_NOW.sub(r"(CURRENT_DATE - \1 * INTERVAL '1 day')", out)
    out = _DATETIME_NOW.sub(r"(NOW() - \1 * INTERVAL '1 day')", out)
    upper = out.strip().upper()
    if (
        upper.startswith("INSERT")
        and "RETURNING" not in upper
        and "ON CONFLICT" not in upper
    ):
        out = out.rstrip().rstrip(";") + " RETURNING id"
    return out


class SeoResult:
    def __init__(self, cursor: Any, backend: SeoBackend, insert_id: int | None = None) -> None:
        self._cursor = cursor
        self._backend = backend
        self._insert_id = insert_id

    @property
    def lastrowid(self) -> int | None:
        if self._insert_id is not None:
            return self._insert_id
        lid = getattr(self._cursor, "lastrowid", None)
        return int(lid) if lid else None

    def fetchone(self) -> Any:
        row = self._cursor.fetchone()
        if row is None:
            return None
        return dict(row) if self._backend == "pg" else row

    def fetchall(self) -> list[Any]:
        rows = self._cursor.fetchall()
        if self._backend == "pg":
            return [dict(r) for r in rows]
        return rows


class SeoDB:
    """Duck-type wrapper for SEO domain SQL (SQLite or PostgreSQL)."""

    def __init__(self, conn: Any, backend: SeoBackend) -> None:
        self._conn = conn
        self.backend = backend

    def execute(self, sql: str, params: tuple[Any, ...] | list[Any] = ()) -> SeoResult:
        adapted = _adapt_sql(sql, self.backend)
        params = tuple(params)
        if self.backend == "pg":
            cur = self._conn.cursor()
            cur.execute(adapted, params)
            insert_id: int | None = None
            if adapted.strip().upper().startswith("INSERT") and "RETURNING" in adapted.upper():
                row = cur.fetchone()
                if row:
                    insert_id = int(row["id"] if isinstance(row, dict) else row[0])
            return SeoResult(cur, "pg", insert_id=insert_id)
        return SeoResult(self._conn.execute(adapted, params), "sqlite")

    def commit(self) -> None:
        self._conn.commit()


class DualSeoDB:
    """Write both SQLite + PG; reads use PG result (pilot mode — run backfill first)."""

    def __init__(self, sqlite_db: SeoDB, pg_db: SeoDB) -> None:
        self._sqlite = sqlite_db
        self._pg = pg_db
        self.backend: SeoBackend = "pg"

    def execute(self, sql: str, params: tuple[Any, ...] | list[Any] = ()) -> SeoResult:
        self._sqlite.execute(sql, params)
        return self._pg.execute(sql, params)

    def commit(self) -> None:
        self._sqlite.commit()
        self._pg.commit()


@contextmanager
def _pg_raw() -> Iterator[Any]:
    try:
        import psycopg2.extras
        from ptt_jobs.config import database_url
        from ptt_jobs.db import PgUnavailableError
    except ImportError as exc:
        raise RuntimeError("psycopg2 required for SEO_AEO_DB=pg") from exc

    conn = psycopg2.connect(database_url(), cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        with conn.cursor() as cur:
            cur.execute("SET search_path TO seo_aeo, public")
        conn.commit()
        yield conn
    finally:
        conn.close()


@contextmanager
def _sqlite_raw() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(str(_sqlite_path()))
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


@contextmanager
def seo_read() -> Iterator[SeoDB | DualSeoDB]:
    mode = seo_db_mode()
    if mode in {"pg", "dual"}:
        from ptt_seo.pg_schema import ensure_pg_schema

        with _pg_raw() as conn:
            ensure_pg_schema(conn)
            yield SeoDB(conn, "pg")
    else:
        from ptt_seo.schema import ensure_schema

        with _sqlite_raw() as conn:
            ensure_schema(conn)
            from ptt_seo.enterprise_schema import ensure_enterprise_schema

            ensure_enterprise_schema(conn)
            from ptt_seo.p2_schema import ensure_p2_schema

            ensure_p2_schema(conn)
            from ptt_seo.research_schema import ensure_research_schema

            ensure_research_schema(conn)
            from ptt_seo.gate_e_schema import ensure_gate_e_schema

            ensure_gate_e_schema(conn)
            yield SeoDB(conn, "sqlite")


@contextmanager
def seo_write() -> Iterator[SeoDB | DualSeoDB]:
    mode = seo_db_mode()
    if mode == "dual":
        from ptt_seo.pg_schema import ensure_pg_schema
        from ptt_seo.schema import ensure_schema

        with _sqlite_raw() as sq, _pg_raw() as pg:
            ensure_schema(sq)
            from ptt_seo.enterprise_schema import ensure_enterprise_schema
            from ptt_seo.p2_schema import ensure_p2_schema

            ensure_enterprise_schema(sq)
            ensure_p2_schema(sq)
            from ptt_seo.research_schema import ensure_research_schema

            ensure_research_schema(sq)
            from ptt_seo.gate_e_schema import ensure_gate_e_schema

            ensure_gate_e_schema(sq)
            ensure_pg_schema(pg)
            yield DualSeoDB(SeoDB(sq, "sqlite"), SeoDB(pg, "pg"))
    elif mode == "pg":
        from ptt_seo.pg_schema import ensure_pg_schema

        with _pg_raw() as conn:
            ensure_pg_schema(conn)
            yield SeoDB(conn, "pg")
    else:
        from ptt_seo.schema import ensure_schema

        with _sqlite_raw() as conn:
            ensure_schema(conn)
            from ptt_seo.enterprise_schema import ensure_enterprise_schema

            ensure_enterprise_schema(conn)
            from ptt_seo.p2_schema import ensure_p2_schema

            ensure_p2_schema(conn)
            from ptt_seo.research_schema import ensure_research_schema

            ensure_research_schema(conn)
            from ptt_seo.gate_e_schema import ensure_gate_e_schema

            ensure_gate_e_schema(conn)
            yield SeoDB(conn, "sqlite")


@contextmanager
def crm_connection() -> Iterator[Any]:
    """CRM master data — always SQLite until platform cutover."""
    from crm_http import deps

    conn = deps.get_connection()
    try:
        yield conn
    finally:
        conn.close()


def ensure_seo_storage() -> None:
    """Ensure SEO storage backend schema (SQLite legacy and/or PostgreSQL)."""
    mode = seo_db_mode()
    if mode in {"pg", "dual"}:
        from ptt_seo.pg_schema import ensure_pg_schema

        with _pg_raw() as conn:
            ensure_pg_schema(conn)


@contextmanager
def seo_pg_only() -> Iterator[SeoDB]:
    """Phase 4+ connectors — always PostgreSQL seo_aeo (policy: no new SQLite writes)."""
    from ptt_seo.pg_schema import ensure_pg_schema

    with _pg_raw() as conn:
        ensure_pg_schema(conn)
        yield SeoDB(conn, "pg")
