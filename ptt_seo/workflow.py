"""Content workflow approvals (Spec 6.11 Phase 2)."""
from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import Any

from ptt_seo.constants import APPROVAL_STAGES


def _ts() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")


def log_audit(
    conn: sqlite3.Connection,
    *,
    customer_id: int | None,
    entity_type: str,
    entity_id: int,
    action: str,
    actor_id: str = "",
    payload: dict[str, Any] | None = None,
) -> None:
    import json

    conn.execute(
        """
        INSERT INTO seo_audit_log (customer_id, entity_type, entity_id, action, actor_id, payload_json, created_at)
        VALUES (?,?,?,?,?,?,?)
        """,
        (
            customer_id,
            entity_type,
            entity_id,
            action,
            actor_id,
            json.dumps(payload or {}, ensure_ascii=False),
            _ts(),
        ),
    )


def record_approval(
    conn: sqlite3.Connection,
    *,
    content_id: int,
    stage: str,
    status: str,
    actor_id: str = "",
    notes: str = "",
) -> int:
    cur = conn.execute(
        """
        INSERT INTO seo_content_approvals (content_id, stage, status, actor_id, notes, created_at)
        VALUES (?,?,?,?,?,?)
        """,
        (content_id, stage, status, actor_id, notes, _ts()),
    )
    return int(cur.lastrowid)


def list_approvals(conn: sqlite3.Connection, content_id: int) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT * FROM seo_content_approvals
        WHERE content_id = ? ORDER BY id ASC
        """,
        (content_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def approval_timeline(conn: sqlite3.Connection, content_id: int) -> list[dict[str, Any]]:
    """Latest status per approval stage for UI timeline."""
    timeline: list[dict[str, Any]] = []
    for stage in APPROVAL_STAGES:
        row = conn.execute(
            """
            SELECT * FROM seo_content_approvals
            WHERE content_id = ? AND stage = ?
            ORDER BY id DESC LIMIT 1
            """,
            (content_id, stage),
        ).fetchone()
        timeline.append(
            {
                "stage": stage,
                "status": dict(row)["status"] if row else "pending",
                "notes": dict(row)["notes"] if row else "",
                "actor_id": dict(row)["actor_id"] if row else "",
                "created_at": dict(row)["created_at"] if row else None,
            }
        )
    return timeline
