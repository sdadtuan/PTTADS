"""Form landing ingest via job queue."""
from __future__ import annotations

import sqlite3
from typing import Any


def process_form_ingest_payload(payload: dict[str, Any]) -> dict[str, Any]:
    from ptt_jobs.config import sqlite_db_path

    conn = sqlite3.connect(sqlite_db_path())
    conn.row_factory = sqlite3.Row
    try:
        from datetime import datetime, timezone

        from ptt_crm.form_lead_ingest import ingest_lead_from_form

        ts = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        lead_id = ingest_lead_from_form(
            conn,
            full_name=str(payload.get("full_name") or ""),
            phone=str(payload.get("phone") or ""),
            email=str(payload.get("email") or ""),
            need=str(payload.get("need") or ""),
            source=str(payload.get("source") or "website"),
            region=str(payload.get("region") or ""),
            product_interest=str(payload.get("product_interest") or ""),
            utm_campaign=str(payload.get("utm_campaign") or ""),
            ts=ts,
            _from_worker=True,
        )
        conn.commit()
        if lead_id:
            return {"ok": True, "lead_id": lead_id}
        return {"ok": False, "error": payload.get("error") or "ingest returned none"}
    except Exception as exc:
        conn.rollback()
        return {"ok": False, "error": str(exc)}
    finally:
        conn.close()


def run_form_ingest_job(job: dict[str, Any]) -> None:
    from ptt_jobs.handlers.ingest_lead import run_ingest_lead_job  # noqa: F401
    from ptt_jobs.store import JOB_STATUS_DEAD, mark_job_done, mark_job_failed

    job_id = str(job["id"])
    payload = job.get("payload") or {}
    if isinstance(payload, str):
        import json

        payload = json.loads(payload)
    attempts = int(job.get("attempts") or 1)
    max_attempts = int(job.get("max_attempts") or 5)
    outcome = process_form_ingest_payload(payload)
    if outcome.get("ok"):
        mark_job_done(job_id)
        return
    status = mark_job_failed(
        job_id,
        str(outcome.get("error") or "form ingest failed"),
        attempts=attempts,
        max_attempts=max_attempts,
    )
    if status == JOB_STATUS_DEAD:
        import logging

        logging.getLogger(__name__).error("form_ingest dead job_id=%s", job_id)
        try:
            from ptt_jobs.form_ingest_failure import notify_form_ingest_dead

            notify_form_ingest_dead(
                job_id=job_id,
                payload=payload if isinstance(payload, dict) else {},
                error=str(outcome.get("error") or "form ingest failed"),
            )
        except Exception as exc:
            logging.getLogger(__name__).warning("form_ingest dead notify failed: %s", exc)
