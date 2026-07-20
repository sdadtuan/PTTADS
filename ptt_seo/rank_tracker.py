"""Rank tracker — tracked keywords + position snapshots."""
from __future__ import annotations

import csv
import io
import sqlite3
from datetime import datetime
from typing import Any


def _ts() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")


def list_tracked_keywords(conn: sqlite3.Connection, customer_id: int) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT t.*,
               (
                   SELECT s.position FROM seo_rank_snapshots s
                   WHERE s.tracked_keyword_id = t.id
                   ORDER BY s.snapshot_date DESC, s.id DESC LIMIT 1
               ) AS latest_position,
               (
                   SELECT s.snapshot_date FROM seo_rank_snapshots s
                   WHERE s.tracked_keyword_id = t.id
                   ORDER BY s.snapshot_date DESC, s.id DESC LIMIT 1
               ) AS latest_date
        FROM seo_rank_tracked_keywords t
        WHERE t.customer_id = ? AND t.status = 'active'
        ORDER BY t.phrase ASC
        """,
        (customer_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def add_tracked_keyword(conn: sqlite3.Connection, customer_id: int, payload: dict[str, Any]) -> int:
    phrase = str(payload.get("phrase") or "").strip()
    if not phrase:
        raise ValueError("Thiếu phrase")
    cur = conn.execute(
        """
        INSERT INTO seo_rank_tracked_keywords (
            customer_id, keyword_id, phrase, target_url, locale, status, created_at
        ) VALUES (?,?,?,?,?,?,?)
        """,
        (
            customer_id,
            payload.get("keyword_id"),
            phrase,
            str(payload.get("target_url") or ""),
            str(payload.get("locale") or "vi-VN"),
            "active",
            _ts(),
        ),
    )
    conn.commit()
    return int(cur.lastrowid)


def record_snapshot(
    conn: sqlite3.Connection,
    tracked_keyword_id: int,
    *,
    snapshot_date: str,
    position: float | None,
    url_found: str = "",
    source: str = "manual",
) -> int:
    cur = conn.execute(
        """
        INSERT INTO seo_rank_snapshots (
            tracked_keyword_id, snapshot_date, position, url_found, source, created_at
        ) VALUES (?,?,?,?,?,?)
        ON CONFLICT(tracked_keyword_id, snapshot_date, source)
        DO UPDATE SET position = excluded.position, url_found = excluded.url_found
        """,
        (tracked_keyword_id, snapshot_date, position, url_found, source, _ts()),
    )
    conn.commit()
    return int(cur.lastrowid)


def import_rank_csv(conn: sqlite3.Connection, customer_id: int, csv_text: str) -> dict[str, int]:
    reader = csv.DictReader(io.StringIO(csv_text))
    tracked = 0
    snapshots = 0
    for row in reader:
        phrase = (row.get("phrase") or row.get("keyword") or "").strip()
        if not phrase:
            continue
        existing = conn.execute(
            """
            SELECT id FROM seo_rank_tracked_keywords
            WHERE customer_id = ? AND phrase = ? AND locale = 'vi-VN'
            """,
            (customer_id, phrase),
        ).fetchone()
        if existing:
            tid = int(existing["id"])
        else:
            tid = add_tracked_keyword(conn, customer_id, {"phrase": phrase})
            tracked += 1
        snap_date = (row.get("date") or row.get("snapshot_date") or _ts()[:10]).strip()
        pos_raw = row.get("position") or row.get("rank")
        position = float(pos_raw) if pos_raw not in (None, "") else None
        record_snapshot(
            conn,
            tid,
            snapshot_date=snap_date,
            position=position,
            url_found=str(row.get("url") or row.get("url_found") or ""),
            source=str(row.get("source") or "import"),
        )
        snapshots += 1
    return {"tracked_added": tracked, "snapshots": snapshots}


def position_history(conn: sqlite3.Connection, tracked_keyword_id: int, *, limit: int = 90) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT snapshot_date, position, url_found, source
        FROM seo_rank_snapshots
        WHERE tracked_keyword_id = ?
        ORDER BY snapshot_date ASC
        LIMIT ?
        """,
        (tracked_keyword_id, limit),
    ).fetchall()
    return [dict(r) for r in rows]
