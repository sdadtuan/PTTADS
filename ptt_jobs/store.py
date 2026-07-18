"""Job queue persistence (PostgreSQL)."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from ptt_jobs.db import PgUnavailableError, json_dumps, pg_connection

logger = logging.getLogger(__name__)

JOB_STATUS_PENDING = "pending"
JOB_STATUS_RUNNING = "running"
JOB_STATUS_DONE = "done"
JOB_STATUS_FAILED = "failed"
JOB_STATUS_DEAD = "dead"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _row_to_dict(row: tuple, columns: list[str]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for idx, col in enumerate(columns):
        val = row[idx]
        if isinstance(val, UUID):
            val = str(val)
        elif isinstance(val, datetime):
            val = val.isoformat()
        out[col] = val
    return out


_JOB_COLUMNS = [
    "id",
    "job_type",
    "payload",
    "status",
    "idempotency_key",
    "correlation_id",
    "client_id",
    "attempts",
    "max_attempts",
    "last_error",
    "scheduled_at",
    "started_at",
    "finished_at",
    "created_at",
    "updated_at",
]


def enqueue_job_record(
    *,
    job_type: str,
    payload: dict[str, Any],
    idempotency_key: str,
    correlation_id: str | None = None,
    client_id: str | None = None,
    max_attempts: int = 5,
) -> dict[str, Any]:
    """Insert job or return existing row for idempotency_key."""
    with pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO job_queue (
                    job_type, payload, idempotency_key,
                    correlation_id, client_id, max_attempts, status
                )
                VALUES (%s, %s::jsonb, %s, %s, %s::uuid, %s, %s)
                ON CONFLICT (idempotency_key) DO NOTHING
                RETURNING id, job_type, status, idempotency_key, correlation_id
                """,
                (
                    job_type,
                    json_dumps(payload),
                    idempotency_key,
                    correlation_id,
                    client_id if client_id else None,
                    max_attempts,
                    JOB_STATUS_PENDING,
                ),
            )
            row = cur.fetchone()
            if row:
                conn.commit()
                job_id = str(row[0])
                job_type = row[1]
                correlation_id = row[4]
                try:
                    from ptt_jobs.broker import notify_job_enqueued

                    notify_job_enqueued(
                        job_id=job_id,
                        job_type=job_type,
                        correlation_id=str(correlation_id) if correlation_id else None,
                    )
                except Exception:
                    logger.debug("job notify skipped", exc_info=True)
                return {
                    "id": job_id,
                    "job_type": job_type,
                    "status": row[2],
                    "idempotency_key": row[3],
                    "correlation_id": correlation_id,
                    "created": True,
                }
            cur.execute(
                """
                SELECT id, job_type, status, idempotency_key, correlation_id
                FROM job_queue WHERE idempotency_key = %s
                """,
                (idempotency_key,),
            )
            existing = cur.fetchone()
            conn.commit()
            if not existing:
                raise RuntimeError("Failed to enqueue or fetch job")
            return {
                "id": str(existing[0]),
                "job_type": existing[1],
                "status": existing[2],
                "idempotency_key": existing[3],
                "correlation_id": existing[4],
                "created": False,
            }


def claim_next_job() -> dict[str, Any] | None:
    with pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE job_queue
                SET status = %s,
                    started_at = NOW(),
                    attempts = attempts + 1,
                    updated_at = NOW()
                WHERE id = (
                    SELECT id FROM job_queue
                    WHERE status IN (%s, %s)
                      AND scheduled_at <= NOW()
                      AND attempts < max_attempts
                    ORDER BY scheduled_at ASC, created_at ASC
                    FOR UPDATE SKIP LOCKED
                    LIMIT 1
                )
                RETURNING id, job_type, payload, status, idempotency_key,
                          correlation_id, client_id, attempts, max_attempts
                """,
                (JOB_STATUS_RUNNING, JOB_STATUS_PENDING, JOB_STATUS_FAILED),
            )
            row = cur.fetchone()
            if not row:
                conn.commit()
                return None
            cols = [
                "id",
                "job_type",
                "payload",
                "status",
                "idempotency_key",
                "correlation_id",
                "client_id",
                "attempts",
                "max_attempts",
            ]
            job = _row_to_dict(row, cols)
            if isinstance(job.get("payload"), str):
                import json

                job["payload"] = json.loads(job["payload"])
            conn.commit()
            return job


def mark_job_done(job_id: str) -> None:
    with pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE job_queue
                SET status = %s, finished_at = NOW(), updated_at = NOW(), last_error = NULL
                WHERE id = %s::uuid
                """,
                (JOB_STATUS_DONE, job_id),
            )
            conn.commit()


def mark_job_failed(job_id: str, error: str, *, attempts: int, max_attempts: int) -> str:
    """Mark failed with retry or dead. Returns final status."""
    if attempts >= max_attempts:
        status = JOB_STATUS_DEAD
        scheduled = None
    else:
        status = JOB_STATUS_FAILED
        backoff_sec = min(300, 2**attempts * 5)
        scheduled = _utc_now() + timedelta(seconds=backoff_sec)

    with pg_connection() as conn:
        with conn.cursor() as cur:
            if scheduled:
                cur.execute(
                    """
                    UPDATE job_queue
                    SET status = %s, last_error = %s, scheduled_at = %s,
                        updated_at = NOW(), started_at = NULL
                    WHERE id = %s::uuid
                    """,
                    (status, error[:4000], scheduled, job_id),
                )
            else:
                cur.execute(
                    """
                    UPDATE job_queue
                    SET status = %s, last_error = %s, finished_at = NOW(),
                        updated_at = NOW()
                    WHERE id = %s::uuid
                    """,
                    (status, error[:4000], job_id),
                )
            conn.commit()
    return status


def get_job_by_id(job_id: str) -> dict[str, Any] | None:
    with pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT j.id, j.job_type, j.payload, j.status, j.idempotency_key, j.correlation_id,
                       j.client_id, j.attempts, j.max_attempts, j.last_error, j.scheduled_at,
                       j.started_at, j.finished_at, j.created_at, j.updated_at,
                       c.code AS client_code,
                       COALESCE(j.payload->>'channel', j.payload->'lead'->>'channel', '') AS channel
                FROM job_queue j
                LEFT JOIN clients c ON c.id = j.client_id
                WHERE j.id = %s::uuid
                """,
                (job_id,),
            )
            row = cur.fetchone()
            if not row:
                return None
            cols = [d[0] for d in cur.description]
            job = {cols[i]: row[i] for i in range(len(cols))}
            for k in ("id", "client_id"):
                if job.get(k) is not None:
                    job[k] = str(job[k])
            for k in ("scheduled_at", "started_at", "finished_at", "created_at", "updated_at"):
                if job.get(k) is not None and hasattr(job[k], "isoformat"):
                    job[k] = job[k].isoformat()
            if isinstance(job.get("payload"), str):
                import json

                job["payload"] = json.loads(job["payload"])
            return job


def replay_job(job_id: str) -> dict[str, Any] | None:
    with pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE job_queue
                SET status = %s, scheduled_at = NOW(), started_at = NULL,
                    finished_at = NULL, last_error = NULL, updated_at = NOW()
                WHERE id = %s::uuid AND status = %s
                RETURNING id, status
                """,
                (JOB_STATUS_PENDING, job_id, JOB_STATUS_DEAD),
            )
            row = cur.fetchone()
            conn.commit()
            if not row:
                return None
            return {"id": str(row[0]), "status": row[1], "replayed": True}


def job_stats() -> dict[str, int]:
    with pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT status, COUNT(*)::int FROM job_queue
                GROUP BY status
                """
            )
            stats = {str(r[0]): int(r[1]) for r in cur.fetchall()}
    for key in (JOB_STATUS_PENDING, JOB_STATUS_RUNNING, JOB_STATUS_DONE, JOB_STATUS_FAILED, JOB_STATUS_DEAD):
        stats.setdefault(key, 0)
    return stats


def list_jobs(
    *,
    status: str | None = None,
    job_type: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict[str, Any]]:
    clauses = ["1=1"]
    params: list[Any] = []
    if status:
        clauses.append("status = %s")
        params.append(status)
    if job_type:
        clauses.append("job_type = %s")
        params.append(job_type)
    params.extend([limit, offset])
    with pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT j.id, j.job_type, j.status, j.idempotency_key, j.correlation_id,
                       j.attempts, j.max_attempts, j.last_error, j.scheduled_at, j.finished_at,
                       j.created_at, j.client_id, c.code AS client_code,
                       COALESCE(j.payload->>'channel', j.payload->'lead'->>'channel', '') AS channel
                FROM job_queue j
                LEFT JOIN clients c ON c.id = j.client_id
                WHERE {' AND '.join(clauses)}
                ORDER BY j.created_at DESC
                LIMIT %s OFFSET %s
                """,
                params,
            )
            rows = []
            cols = [d[0] for d in cur.description]
            for row in cur.fetchall():
                item = {cols[i]: row[i] for i in range(len(cols))}
                for k in ("id", "client_id"):
                    if item.get(k) is not None:
                        item[k] = str(item[k])
                for k in ("scheduled_at", "finished_at", "created_at"):
                    if item.get(k) is not None and hasattr(item[k], "isoformat"):
                        item[k] = item[k].isoformat()
                rows.append(item)
            return rows
