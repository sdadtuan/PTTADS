"""Job handler — email_campaign_prepare (EM-6)."""
from __future__ import annotations

import logging
from typing import Any

from ptt_email.campaign_prepare import prepare_campaign
from ptt_jobs.store import mark_job_done, mark_job_failed

logger = logging.getLogger(__name__)


def run_email_campaign_prepare_job(job: dict[str, Any]) -> None:
    job_id = str(job["id"])
    payload = job.get("payload") or {}
    campaign_id = str(payload.get("campaign_id") or "").strip()
    client_id = str(payload.get("client_id") or "").strip() or None
    if not campaign_id:
        mark_job_failed(
            job_id,
            "missing campaign_id",
            attempts=int(job.get("attempts") or 1),
            max_attempts=int(job.get("max_attempts") or 5),
        )
        return

    try:
        outcome = prepare_campaign(campaign_id, client_id=client_id)
        if outcome.get("ok"):
            mark_job_done(job_id)
            return
        if outcome.get("skipped"):
            mark_job_done(job_id)
            return
        mark_job_failed(
            job_id,
            str(outcome.get("error") or "prepare_failed"),
            attempts=int(job.get("attempts") or 1),
            max_attempts=int(job.get("max_attempts") or 5),
        )
    except Exception as exc:
        logger.exception("email_campaign_prepare failed: %s", exc)
        mark_job_failed(
            job_id,
            str(exc),
            attempts=int(job.get("attempts") or 1),
            max_attempts=int(job.get("max_attempts") or 5),
        )
