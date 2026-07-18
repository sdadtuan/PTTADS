"""Domain events outbox read/write helpers."""
from __future__ import annotations

import logging
from typing import Any

from ptt_jobs.db import PgUnavailableError, pg_connection

logger = logging.getLogger(__name__)


def list_domain_events(
    *,
    event_type: str | None = None,
    limit: int = 50,
    unpublished_only: bool = False,
) -> list[dict[str, Any]]:
    lim = max(1, min(int(limit), 200))
    clauses: list[str] = []
    params: list[Any] = []
    if event_type:
        clauses.append("event_type = %s")
        params.append(event_type)
    if unpublished_only:
        clauses.append("published_at IS NULL")
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    with pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT id, event_type, aggregate_type, aggregate_id,
                       payload, correlation_id, published_at, created_at
                FROM domain_events
                {where}
                ORDER BY created_at DESC
                LIMIT %s
                """,
                [*params, lim],
            )
            cols = [d[0] for d in cur.description]
            return [_row_to_dict(row, cols) for row in cur.fetchall()]


def fetch_unpublished_events(*, limit: int = 50) -> list[dict[str, Any]]:
    return list_domain_events(limit=limit, unpublished_only=True)


def mark_event_published(event_id: str) -> bool:
    with pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE domain_events
                SET published_at = NOW()
                WHERE id = %s::uuid AND published_at IS NULL
                """,
                (event_id,),
            )
            conn.commit()
            return cur.rowcount > 0


def event_stats() -> dict[str, int]:
    try:
        with pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        COUNT(*) FILTER (WHERE published_at IS NULL) AS unpublished,
                        COUNT(*) FILTER (WHERE event_type = 'LeadCreated') AS lead_created,
                        COUNT(*) FILTER (WHERE event_type = 'JobDead') AS job_dead,
                        COUNT(*) AS total
                    FROM domain_events
                    """
                )
                row = cur.fetchone()
                if not row:
                    return {"unpublished": 0, "lead_created": 0, "job_dead": 0, "total": 0}
                return {
                    "unpublished": int(row[0] or 0),
                    "lead_created": int(row[1] or 0),
                    "job_dead": int(row[2] or 0),
                    "total": int(row[3] or 0),
                }
    except PgUnavailableError:
        return {"unpublished": 0, "lead_created": 0, "job_dead": 0, "total": 0}


def _row_to_dict(row: tuple, columns: list[str]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for idx, col in enumerate(columns):
        val = row[idx]
        if col == "payload":
            out[col] = val if isinstance(val, (dict, list)) else val
        elif val is not None and hasattr(val, "isoformat"):
            out[col] = val.isoformat()
        elif val is not None:
            out[col] = str(val)
        else:
            out[col] = val
    return out
