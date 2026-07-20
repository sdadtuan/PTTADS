"""SEO/AEO projects linked to service lifecycle."""
from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import Any

from ptt_seo.constants import project_type_for_slug


def _ts() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")


def ensure_project_for_lifecycle(
    conn: sqlite3.Connection,
    *,
    customer_id: int,
    lifecycle_id: int,
    service_slug: str,
    name: str = "",
) -> int:
    row = conn.execute(
        "SELECT id FROM seo_projects WHERE lifecycle_id = ?",
        (lifecycle_id,),
    ).fetchone()
    if row is not None:
        return int(row["id"])
    cur = conn.execute(
        """
        INSERT INTO seo_projects (
            customer_id, lifecycle_id, name, project_type, status, created_at, updated_at
        ) VALUES (?,?,?,?,?,?,?)
        """,
        (
            customer_id,
            lifecycle_id,
            name or f"SEO/AEO #{lifecycle_id}",
            project_type_for_slug(service_slug),
            "active",
            _ts(),
            _ts(),
        ),
    )
    conn.commit()
    return int(cur.lastrowid)


def get_project_by_lifecycle(conn: sqlite3.Connection, lifecycle_id: int) -> dict[str, Any] | None:
    row = conn.execute(
        "SELECT * FROM seo_projects WHERE lifecycle_id = ?",
        (lifecycle_id,),
    ).fetchone()
    return dict(row) if row else None


def count_projects_for_customer(conn: sqlite3.Connection, customer_id: int) -> int:
    row = conn.execute(
        "SELECT COUNT(*) AS c FROM seo_projects WHERE customer_id = ? AND status = 'active'",
        (customer_id,),
    ).fetchone()
    return int(row["c"] or 0) if row else 0
