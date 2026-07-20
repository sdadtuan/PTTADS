# crm_aeo.py — DEPRECATED: use ptt_seo.aeo / ptt_seo.aeo_store (PG cutover Phase 4A).
from __future__ import annotations

import sqlite3
import warnings
from typing import Any


def _deprecate(name: str) -> None:
    warnings.warn(
        f"crm_aeo.{name} is deprecated; use ptt_seo.aeo instead",
        DeprecationWarning,
        stacklevel=3,
    )


def ensure_schema(conn: sqlite3.Connection) -> None:
    """Legacy SQLite tables — kept for migration/backfill only."""
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS crm_aeo_queries (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id  INTEGER NOT NULL REFERENCES crm_customers(id) ON DELETE CASCADE,
            lifecycle_id INTEGER REFERENCES crm_service_lifecycle(id) ON DELETE SET NULL,
            query_text   TEXT NOT NULL DEFAULT '',
            brand_name   TEXT NOT NULL DEFAULT '',
            notes        TEXT NOT NULL DEFAULT '',
            created_at   TEXT NOT NULL DEFAULT ''
        );
        CREATE INDEX IF NOT EXISTS idx_aeo_queries_customer ON crm_aeo_queries (customer_id);

        CREATE TABLE IF NOT EXISTS crm_aeo_scans (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            query_id      INTEGER NOT NULL REFERENCES crm_aeo_queries(id) ON DELETE CASCADE,
            ai_response   TEXT NOT NULL DEFAULT '',
            brand_visible INTEGER NOT NULL DEFAULT 0,
            gap_notes     TEXT NOT NULL DEFAULT '',
            created_at    TEXT NOT NULL DEFAULT ''
        );
        CREATE INDEX IF NOT EXISTS idx_aeo_scans_query ON crm_aeo_scans (query_id);

        CREATE TABLE IF NOT EXISTS crm_aeo_content (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            query_id    INTEGER NOT NULL REFERENCES crm_aeo_queries(id) ON DELETE CASCADE,
            qa_text     TEXT NOT NULL DEFAULT '',
            schema_json TEXT NOT NULL DEFAULT '',
            created_at  TEXT NOT NULL DEFAULT ''
        );
        CREATE INDEX IF NOT EXISTS idx_aeo_content_query ON crm_aeo_content (query_id);
    """)


def add_query(
    conn: sqlite3.Connection,
    customer_id: int,
    query_text: str,
    brand_name: str,
    *,
    lifecycle_id: int | None = None,
    notes: str = "",
) -> int:
    _deprecate("add_query")
    from ptt_seo.aeo import add_aeo_query

    return add_aeo_query(
        customer_id, query_text, brand_name, lifecycle_id=lifecycle_id, notes=notes
    )


def list_queries(conn: sqlite3.Connection, customer_id: int) -> list[dict]:
    _deprecate("list_queries")
    from ptt_seo.aeo import list_aeo_queries

    return list_aeo_queries(customer_id)


def delete_query(conn: sqlite3.Connection, query_id: int) -> None:
    _deprecate("delete_query")
    from ptt_seo.aeo import delete_aeo_query

    delete_aeo_query(query_id)


def run_scan(conn: sqlite3.Connection, query_id: int) -> str:
    _deprecate("run_scan")
    from ptt_seo.aeo import run_aeo_scan

    return run_aeo_scan(query_id)


def get_scan_history(conn: sqlite3.Connection, query_id: int) -> list[dict]:
    _deprecate("get_scan_history")
    from ptt_seo.aeo import get_aeo_scan_history

    return get_aeo_scan_history(query_id)


def generate_content(conn: sqlite3.Connection, query_id: int) -> dict:
    _deprecate("generate_content")
    from ptt_seo.aeo import generate_aeo_content

    return generate_aeo_content(query_id) or {}


def get_latest_content(conn: sqlite3.Connection, query_id: int) -> dict | None:
    _deprecate("get_latest_content")
    from ptt_seo.aeo import get_aeo_latest_content

    return get_aeo_latest_content(query_id)
