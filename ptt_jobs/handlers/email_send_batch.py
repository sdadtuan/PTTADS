"""Job handler — email_send_batch (EM-6)."""
from __future__ import annotations

import logging
from typing import Any

from ptt_email.sender import send_batch
from ptt_jobs.store import mark_job_done, mark_job_failed

logger = logging.getLogger(__name__)


def run_email_send_batch_job(job: dict[str, Any]) -> None:
    job_id = str(job["id"])
    payload = job.get("payload") or {}
    campaign_id = str(payload.get("campaign_id") or "").strip() or None
    client_id = str(payload.get("client_id") or "").strip() or None
    batch_size = payload.get("batch_size")

    try:
        outcome = send_batch(
            campaign_id=campaign_id,
            client_id=client_id,
            batch_size=int(batch_size) if batch_size else None,
        )
        if outcome.get("ok") or outcome.get("skipped"):
            mark_job_done(job_id)
            return
        mark_job_failed(
            job_id,
            str(outcome.get("error") or "send_batch_failed"),
            attempts=int(job.get("attempts") or 1),
            max_attempts=int(job.get("max_attempts") or 5),
        )
    except Exception as exc:
        logger.exception("email_send_batch failed: %s", exc)
        mark_job_failed(
            job_id,
            str(exc),
            attempts=int(job.get("attempts") or 1),
            max_attempts=int(job.get("max_attempts") or 5),
        )
