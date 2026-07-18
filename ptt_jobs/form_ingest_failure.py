"""Form landing ingest failure handling — P0-08 (no silent fail)."""
from __future__ import annotations

import hashlib
import json
import logging
import sqlite3
from datetime import datetime, timezone
from typing import Any

from ptt_jobs.config import jobs_enabled, jobs_sync_fallback, sqlite_db_path
from ptt_jobs.db import pg_available

logger = logging.getLogger(__name__)


def build_form_idempotency_key(fields: dict[str, Any]) -> str:
    key_src = "|".join(
        [
            str(fields.get("phone") or "").strip(),
            str(fields.get("email") or "").strip(),
            str(fields.get("full_name") or "").strip(),
        ]
    )
    return "form:" + hashlib.sha256(key_src.encode("utf-8")).hexdigest()[:48]


def ensure_spillover_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS form_ingest_spillover (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            idempotency_key TEXT,
            payload TEXT NOT NULL,
            error TEXT,
            created_at TEXT NOT NULL,
            resolved_at TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_form_ingest_spillover_open
        ON form_ingest_spillover (created_at DESC)
        WHERE resolved_at IS NULL
        """
    )


def record_form_ingest_spillover(*, fields: dict[str, Any], error: str) -> int | None:
    """Persist failed form payload locally when queue unavailable."""
    idem = build_form_idempotency_key(fields)
    payload = {**fields, "error": error, "idempotency_key": idem}
    ts = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    conn = sqlite3.connect(sqlite_db_path())
    try:
        ensure_spillover_table(conn)
        cur = conn.execute(
            """
            INSERT INTO form_ingest_spillover (idempotency_key, payload, error, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (idem, json.dumps(payload, ensure_ascii=False), error[:2000], ts),
        )
        conn.commit()
        return int(cur.lastrowid or 0) or None
    finally:
        conn.close()


def notify_form_ingest_dead(*, job_id: str, payload: dict[str, Any], error: str) -> None:
    from ptt_agency.notifications import notify_agency_ops

    phone = str(payload.get("phone") or "")
    name = str(payload.get("full_name") or "")
    notify_agency_ops(
        recipient_id="admin",
        title="Form ingest DLQ",
        body=f"Job {job_id} dead — {name} {phone} — {error[:200]}",
        category="dlq",
        link_url="/crm/agency/ingest",
        meta={"job_id": job_id, "job_type": "form_ingest", "error": error[:500]},
        email_env="PTT_FORM_INGEST_ALERT_EMAIL",
        email_fallback_env="PTT_AGENCY_SLA_ALERT_EMAIL",
        slack_prefix=":rotating_light: [Form DLQ]",
    )


def enqueue_form_ingest_failure(**fields: Any) -> dict[str, Any]:
    """
    Queue retry job when PG available; sync retry or SQLite spillover otherwise.
    Never swallow errors silently (spec FR-TR-04 / P0-08).
    """
    error = str(fields.pop("error", "") or "form ingest failed")
    payload = dict(fields)
    payload["error"] = error
    idem = build_form_idempotency_key(payload)

    if jobs_enabled() and pg_available():
        try:
            from ptt_jobs.enqueue import enqueue_job

            job = enqueue_job("form_ingest", payload, idem)
            logger.warning(
                "form ingest queued for retry job_id=%s idem=%s error=%s",
                job.get("id"),
                idem,
                error,
            )
            return {"mode": "queue", "job": job, "idempotency_key": idem}
        except Exception as exc:
            logger.exception("form ingest enqueue failed: %s", exc)

    if jobs_sync_fallback():
        try:
            from ptt_jobs.handlers.form_ingest import process_form_ingest_payload

            outcome = process_form_ingest_payload(payload)
            if outcome.get("ok"):
                logger.info("form ingest sync fallback recovered lead_id=%s", outcome.get("lead_id"))
                return {"mode": "sync", "ok": True, "lead_id": outcome.get("lead_id")}
            error = str(outcome.get("error") or error)
        except Exception as exc:
            error = str(exc)
            logger.exception("form ingest sync fallback failed: %s", exc)

    spill_id = record_form_ingest_spillover(fields=payload, error=error)
    logger.error(
        "form ingest spillover id=%s idem=%s error=%s",
        spill_id,
        idem,
        error,
    )
    try:
        notify_form_ingest_dead(job_id=f"spillover:{spill_id or idem}", payload=payload, error=error)
    except Exception as exc:
        logger.warning("form ingest dead notify failed: %s", exc)
    return {
        "mode": "spillover",
        "ok": False,
        "spillover_id": spill_id,
        "idempotency_key": idem,
        "error": error,
    }


def spillover_stats() -> dict[str, int]:
    """Count open/total form ingest spillover rows (SQLite)."""
    conn = sqlite3.connect(sqlite_db_path())
    conn.row_factory = sqlite3.Row
    try:
        ensure_spillover_table(conn)
        open_row = conn.execute(
            "SELECT COUNT(*) AS c FROM form_ingest_spillover WHERE resolved_at IS NULL"
        ).fetchone()
        total_row = conn.execute("SELECT COUNT(*) AS c FROM form_ingest_spillover").fetchone()
        return {
            "open": int(open_row["c"] if open_row else 0),
            "total": int(total_row["c"] if total_row else 0),
        }
    finally:
        conn.close()


def list_form_ingest_spillover(*, limit: int = 50, open_only: bool = True) -> list[dict[str, Any]]:
    conn = sqlite3.connect(sqlite_db_path())
    conn.row_factory = sqlite3.Row
    try:
        ensure_spillover_table(conn)
        sql = """
            SELECT id, idempotency_key, payload, error, created_at, resolved_at
            FROM form_ingest_spillover
        """
        params: list[Any] = []
        if open_only:
            sql += " WHERE resolved_at IS NULL"
        sql += " ORDER BY created_at DESC LIMIT ?"
        params.append(max(1, min(int(limit), 200)))
        rows = conn.execute(sql, params).fetchall()
        out: list[dict[str, Any]] = []
        for row in rows:
            payload_raw = row["payload"] or "{}"
            try:
                payload = json.loads(payload_raw)
            except json.JSONDecodeError:
                payload = {"raw": payload_raw}
            out.append(
                {
                    "id": int(row["id"]),
                    "idempotency_key": row["idempotency_key"],
                    "payload": payload,
                    "error": row["error"],
                    "created_at": row["created_at"],
                    "resolved_at": row["resolved_at"],
                    "phone": str(payload.get("phone") or ""),
                    "full_name": str(payload.get("full_name") or ""),
                }
            )
        return out
    finally:
        conn.close()


def _mark_spillover_resolved(spillover_id: int) -> None:
    ts = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    conn = sqlite3.connect(sqlite_db_path())
    try:
        ensure_spillover_table(conn)
        conn.execute(
            "UPDATE form_ingest_spillover SET resolved_at = ? WHERE id = ? AND resolved_at IS NULL",
            (ts, int(spillover_id)),
        )
        conn.commit()
    finally:
        conn.close()


def replay_form_ingest_spillover(spillover_id: int) -> dict[str, Any]:
    """Re-process a spillover row — queue, sync fallback, or fail again."""
    conn = sqlite3.connect(sqlite_db_path())
    conn.row_factory = sqlite3.Row
    try:
        ensure_spillover_table(conn)
        row = conn.execute(
            """
            SELECT id, payload, error, resolved_at
            FROM form_ingest_spillover
            WHERE id = ?
            """,
            (int(spillover_id),),
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        return {"ok": False, "error": "not_found"}
    if row["resolved_at"]:
        return {"ok": False, "error": "already_resolved", "resolved_at": row["resolved_at"]}

    try:
        payload = json.loads(row["payload"] or "{}")
    except json.JSONDecodeError:
        payload = {}
    payload.pop("error", None)
    payload.pop("idempotency_key", None)

    if jobs_enabled() and pg_available():
        try:
            from ptt_jobs.enqueue import enqueue_job

            idem = build_form_idempotency_key(payload)
            job = enqueue_job("form_ingest", payload, idem)
            _mark_spillover_resolved(int(spillover_id))
            return {"ok": True, "mode": "queue", "job": job, "spillover_id": int(spillover_id)}
        except Exception as exc:
            logger.exception("spillover replay enqueue failed id=%s: %s", spillover_id, exc)

    if jobs_sync_fallback():
        try:
            from ptt_jobs.handlers.form_ingest import process_form_ingest_payload

            outcome = process_form_ingest_payload(payload)
            if outcome.get("ok"):
                _mark_spillover_resolved(int(spillover_id))
                return {
                    "ok": True,
                    "mode": "sync",
                    "lead_id": outcome.get("lead_id"),
                    "spillover_id": int(spillover_id),
                }
            return {
                "ok": False,
                "mode": "sync",
                "error": str(outcome.get("error") or "sync failed"),
                "spillover_id": int(spillover_id),
            }
        except Exception as exc:
            return {"ok": False, "mode": "sync", "error": str(exc), "spillover_id": int(spillover_id)}

    return {"ok": False, "error": "queue_unavailable", "spillover_id": int(spillover_id)}
