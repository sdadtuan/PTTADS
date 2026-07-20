"""Keyword cluster management (P2 Research depth)."""
from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import Any


def _ts() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")


def list_clusters(conn: sqlite3.Connection, customer_id: int) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT c.*,
               (
                   SELECT COUNT(*) FROM seo_keywords k
                   WHERE k.customer_id = c.customer_id AND k.cluster_id = c.id AND k.status = 'active'
               ) AS keyword_count
        FROM seo_keyword_clusters c
        WHERE c.customer_id = ? AND c.status = 'active'
        ORDER BY c.name ASC, c.id ASC
        """,
        (customer_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def create_cluster(conn: sqlite3.Connection, customer_id: int, payload: dict[str, Any]) -> int:
    name = str(payload.get("name") or "").strip()
    if not name:
        raise ValueError("Thiếu tên cluster")
    ts = _ts()
    cur = conn.execute(
        """
        INSERT INTO seo_keyword_clusters (
            customer_id, name, intent, notes, status, created_at, updated_at
        ) VALUES (?,?,?,?,?,?,?)
        """,
        (
            customer_id,
            name,
            str(payload.get("intent") or "informational"),
            str(payload.get("notes") or ""),
            "active",
            ts,
            ts,
        ),
    )
    conn.commit()
    return int(cur.lastrowid)


def update_cluster(conn: sqlite3.Connection, cluster_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    row = conn.execute(
        "SELECT * FROM seo_keyword_clusters WHERE id = ?", (cluster_id,)
    ).fetchone()
    if row is None:
        raise ValueError("Cluster không tồn tại")
    current = dict(row)
    conn.execute(
        """
        UPDATE seo_keyword_clusters
        SET name=?, intent=?, notes=?, updated_at=?
        WHERE id=?
        """,
        (
            str(payload.get("name") or current["name"]),
            str(payload.get("intent") or current["intent"]),
            str(payload.get("notes") or current["notes"]),
            _ts(),
            cluster_id,
        ),
    )
    conn.commit()
    out = conn.execute("SELECT * FROM seo_keyword_clusters WHERE id = ?", (cluster_id,)).fetchone()
    return dict(out) if out else {}


def assign_keyword_to_cluster(
    conn: sqlite3.Connection,
    customer_id: int,
    keyword_id: int,
    cluster_id: int | None,
) -> None:
    conn.execute(
        """
        UPDATE seo_keywords SET cluster_id = ?
        WHERE id = ? AND customer_id = ?
        """,
        (cluster_id, keyword_id, customer_id),
    )
    conn.commit()


def delete_cluster(conn: sqlite3.Connection, cluster_id: int) -> bool:
    conn.execute(
        "UPDATE seo_keywords SET cluster_id = NULL WHERE cluster_id = ?", (cluster_id,)
    )
    cur = conn.execute(
        "UPDATE seo_keyword_clusters SET status = 'archived', updated_at = ? WHERE id = ?",
        (_ts(), cluster_id),
    )
    conn.commit()
    return int(cur.rowcount or 0) > 0
