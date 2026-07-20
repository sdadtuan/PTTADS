"""Job handler — email_campaign_schedule_due (EM-10)."""
from __future__ import annotations

import logging
from typing import Any

from ptt_email.campaign_schedule import run_due_scheduled_campaigns
from ptt_jobs.store import mark_job_done, mark_job_failed

logger = logging.getLogger(__name__)


def run_email_campaign_schedule_due_job(job: dict[str, Any]) -> None:
    job_id = str(job["id"])
    try:
        outcome = run_due_scheduled_campaigns()
        if outcome.get("ok"):
            mark_job_done(job_id)
            return
        mark_job_failed(
            job_id,
            str(outcome.get("error") or "schedule_due_failed"),
            attempts=int(job.get("attempts") or 1),
            max_attempts=int(job.get("max_attempts") or 5),
        )
    except Exception as exc:
        logger.exception("email_campaign_schedule_due failed: %s", exc)
        mark_job_failed(
            job_id,
            str(exc),
            attempts=int(job.get("attempts") or 1),
            max_attempts=int(job.get("max_attempts") or 5),
        )
