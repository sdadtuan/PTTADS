"""SEO page inventory — sync from GSC stats (P2 Research depth)."""
from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import Any
from urllib.parse import urlparse


def _ts() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")


def list_pages(conn: sqlite3.Connection, customer_id: int, *, limit: int = 500) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT * FROM seo_pages
        WHERE customer_id = ?
        ORDER BY url ASC
        LIMIT ?
        """,
        (customer_id, limit),
    ).fetchall()
    return [dict(r) for r in rows]


def upsert_page(conn: sqlite3.Connection, customer_id: int, url: str, **fields: Any) -> int:
    url = url.strip()
    if not url:
        raise ValueError("Thiếu URL")
    parsed = urlparse(url)
    slug = (parsed.path or "/").strip("/") or "/"
    existing = conn.execute(
        "SELECT id FROM seo_pages WHERE customer_id = ? AND url = ?",
        (customer_id, url),
    ).fetchone()
    title = str(fields.get("title") or slug)
    if existing:
        conn.execute(
            """
            UPDATE seo_pages SET title=?, slug=?, status=?, last_crawled_at=?
            WHERE id=?
            """,
            (
                title,
                slug,
                str(fields.get("status") or "indexed"),
                fields.get("last_crawled_at") or _ts(),
                int(existing["id"]),
            ),
        )
        conn.commit()
        return int(existing["id"])
    cur = conn.execute(
        """
        INSERT INTO seo_pages (
            customer_id, url, title, slug, content_type, schema_type, status, last_crawled_at, created_at
        ) VALUES (?,?,?,?,?,?,?,?,?)
        """,
        (
            customer_id,
            url,
            title,
            slug,
            str(fields.get("content_type") or "page"),
            str(fields.get("schema_type") or ""),
            str(fields.get("status") or "indexed"),
            fields.get("last_crawled_at") or _ts(),
            _ts(),
        ),
    )
    conn.commit()
    return int(cur.lastrowid)


def sync_pages_from_gsc(conn: sqlite3.Connection, customer_id: int, *, days: int = 90) -> dict[str, Any]:
    """Import distinct pages from seo_gsc_daily_stats."""
    rows = conn.execute(
        """
        SELECT DISTINCT page FROM seo_gsc_daily_stats
        WHERE customer_id = ? AND page IS NOT NULL AND page != ''
          AND stat_date >= date('now', ?)
        """,
        (customer_id, f"-{int(days)} days"),
    ).fetchall()
    count = 0
    for r in rows:
        page = str(r["page"] or "").strip()
        if not page:
            continue
        upsert_page(conn, customer_id, page)
        count += 1
    return {"ok": True, "synced": count, "source": "gsc"}
