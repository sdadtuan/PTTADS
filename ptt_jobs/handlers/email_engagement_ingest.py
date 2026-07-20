"""Job handler — email_engagement_ingest (EM-6)."""
from __future__ import annotations

import logging
from typing import Any

from ptt_email.engagement_ingest import ingest_events
from ptt_jobs.store import mark_job_done, mark_job_failed

logger = logging.getLogger(__name__)


def run_email_engagement_ingest_job(job: dict[str, Any]) -> None:
    job_id = str(job["id"])
    payload = job.get("payload") or {}
    events = payload.get("events") or []
    client_id = str(payload.get("client_id") or "").strip()

    if not isinstance(events, list) or not events:
        mark_job_done(job_id)
        return

    try:
        outcome = ingest_events(events, client_id=client_id)
        if outcome.get("ok"):
            mark_job_done(job_id)
            return
        mark_job_failed(
            job_id,
            str(outcome.get("error") or "ingest_failed"),
            attempts=int(job.get("attempts") or 1),
            max_attempts=int(job.get("max_attempts") or 5),
        )
    except Exception as exc:
        logger.exception("email_engagement_ingest failed: %s", exc)
        mark_job_failed(
            job_id,
            str(exc),
            attempts=int(job.get("attempts") or 1),
            max_attempts=int(job.get("max_attempts") or 5),
        )
