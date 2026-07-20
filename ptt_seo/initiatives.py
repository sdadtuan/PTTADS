"""Strategy initiatives / roadmap (module 6.2 — Phase 1 basic)."""
from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import Any


def _ts() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")


def list_initiatives(
    conn: sqlite3.Connection,
    customer_id: int,
    *,
    lifecycle_id: int | None = None,
    roadmap_bucket: str | None = None,
) -> list[dict[str, Any]]:
    sql = "SELECT * FROM seo_initiatives WHERE customer_id = ?"
    params: list[Any] = [customer_id]
    if lifecycle_id is not None:
        sql += " AND lifecycle_id = ?"
        params.append(lifecycle_id)
    if roadmap_bucket:
        sql += " AND roadmap_bucket = ?"
        params.append(roadmap_bucket)
    sql += " ORDER BY id DESC"
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def create_initiative(conn: sqlite3.Connection, customer_id: int, payload: dict[str, Any]) -> int:
    cur = conn.execute(
        """
        INSERT INTO seo_initiatives (
            customer_id, project_id, lifecycle_id, title, description,
            impact, effort, roadmap_bucket, status, owner_staff_id, deadline, created_at
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            customer_id,
            payload.get("project_id"),
            payload.get("lifecycle_id"),
            str(payload.get("title") or "").strip(),
            str(payload.get("description") or ""),
            str(payload.get("impact") or "medium"),
            str(payload.get("effort") or "medium"),
            str(payload.get("roadmap_bucket") or "30d"),
            str(payload.get("status") or "planned"),
            payload.get("owner_staff_id"),
            payload.get("deadline"),
            _ts(),
        ),
    )
    conn.commit()
    return int(cur.lastrowid)


def count_initiatives_by_status(conn: sqlite3.Connection, customer_id: int) -> dict[str, int]:
    rows = conn.execute(
        """
        SELECT status, COUNT(*) AS c FROM seo_initiatives
        WHERE customer_id = ? GROUP BY status
        """,
        (customer_id,),
    ).fetchall()
    return {str(r["status"]): int(r["c"]) for r in rows}


def list_all_initiatives(
    crm_conn: sqlite3.Connection,
    seo_conn: sqlite3.Connection,
    *,
    status: str | None = None,
    roadmap_bucket: str | None = None,
) -> list[dict[str, Any]]:
    sql = "SELECT * FROM seo_initiatives WHERE 1=1"
    params: list[Any] = []
    if status:
        sql += " AND status = ?"
        params.append(status)
    if roadmap_bucket:
        sql += " AND roadmap_bucket = ?"
        params.append(roadmap_bucket)
    sql += " ORDER BY CASE WHEN deadline IS NULL OR deadline = '' THEN 1 ELSE 0 END, deadline ASC, id DESC"
    rows = [dict(r) for r in seo_conn.execute(sql, params).fetchall()]
    name_cache: dict[int, dict[str, str]] = {}
    for item in rows:
        cid = int(item["customer_id"])
        if cid not in name_cache:
            row = crm_conn.execute(
                "SELECT name, company FROM crm_customers WHERE id = ?",
                (cid,),
            ).fetchone()
            name_cache[cid] = {
                "customer_name": (row["name"] if row else "") or "",
                "customer_company": (row["company"] if row else "") or "",
            }
        item.update(name_cache[cid])
    return rows
