"""Enterprise backlog tables — PG source of truth + SQLite mirror for local/tests."""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any


def _enterprise_ddl_path() -> Path:
    return Path(__file__).resolve().parents[1] / "deploy" / "sql" / "seo_aeo_enterprise.sql"


def ensure_enterprise_pg_schema(conn: Any) -> None:
    from ptt_seo.pg_schema import _split_sql

    ddl = _enterprise_ddl_path().read_text(encoding="utf-8")
    with conn.cursor() as cur:
        for stmt in _split_sql(ddl):
            if stmt.strip():
                cur.execute(stmt)
    conn.commit()


def ensure_enterprise_schema(conn: sqlite3.Connection) -> None:
    """SQLite mirror for dev/tests (not added to frozen schema.py)."""
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS seo_entities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER NOT NULL,
            entity_name TEXT NOT NULL DEFAULT '',
            entity_type TEXT NOT NULL DEFAULT 'category',
            same_as_json TEXT NOT NULL DEFAULT '[]',
            confidence_score REAL,
            notes TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT ''
        );
        CREATE INDEX IF NOT EXISTS idx_seo_entities_customer ON seo_entities (customer_id, entity_type);

        CREATE TABLE IF NOT EXISTS seo_entity_links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER NOT NULL,
            source_entity_id INTEGER NOT NULL,
            target_entity_id INTEGER NOT NULL,
            link_type TEXT NOT NULL DEFAULT 'related',
            weight REAL NOT NULL DEFAULT 1.0,
            created_at TEXT NOT NULL DEFAULT '',
            UNIQUE (customer_id, source_entity_id, target_entity_id, link_type)
        );

        CREATE TABLE IF NOT EXISTS seo_pages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER NOT NULL,
            url TEXT NOT NULL DEFAULT '',
            title TEXT NOT NULL DEFAULT '',
            slug TEXT NOT NULL DEFAULT '',
            content_type TEXT NOT NULL DEFAULT '',
            schema_type TEXT NOT NULL DEFAULT '',
            primary_keyword_id INTEGER,
            primary_entity_id INTEGER,
            status TEXT NOT NULL DEFAULT 'unknown',
            last_crawled_at TEXT,
            created_at TEXT NOT NULL DEFAULT '',
            UNIQUE (customer_id, url)
        );

        CREATE TABLE IF NOT EXISTS seo_rank_tracked_keywords (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER NOT NULL,
            keyword_id INTEGER,
            phrase TEXT NOT NULL DEFAULT '',
            target_url TEXT NOT NULL DEFAULT '',
            locale TEXT NOT NULL DEFAULT 'vi-VN',
            status TEXT NOT NULL DEFAULT 'active',
            created_at TEXT NOT NULL DEFAULT '',
            UNIQUE (customer_id, phrase, locale)
        );

        CREATE TABLE IF NOT EXISTS seo_rank_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tracked_keyword_id INTEGER NOT NULL,
            snapshot_date TEXT NOT NULL,
            position REAL,
            url_found TEXT NOT NULL DEFAULT '',
            source TEXT NOT NULL DEFAULT 'manual',
            created_at TEXT NOT NULL DEFAULT '',
            UNIQUE (tracked_keyword_id, snapshot_date, source)
        );

        CREATE TABLE IF NOT EXISTS seo_cms_targets (
            customer_id INTEGER PRIMARY KEY,
            cms_type TEXT NOT NULL DEFAULT 'webhook',
            base_url TEXT NOT NULL DEFAULT '',
            auth_json TEXT NOT NULL DEFAULT '{}',
            active INTEGER NOT NULL DEFAULT 1,
            updated_at TEXT NOT NULL DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS seo_cms_publish_jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER NOT NULL,
            content_id INTEGER NOT NULL,
            cms_type TEXT NOT NULL DEFAULT 'webhook',
            status TEXT NOT NULL DEFAULT 'pending',
            remote_url TEXT NOT NULL DEFAULT '',
            payload_json TEXT NOT NULL DEFAULT '{}',
            response_json TEXT NOT NULL DEFAULT '{}',
            error_message TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT '',
            finished_at TEXT
        );
        """
    )
    conn.commit()
