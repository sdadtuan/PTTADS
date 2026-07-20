"""Job handler — email_journey_tick (EM-11)."""
from __future__ import annotations

import logging
from typing import Any

from ptt_email.journey_engine import tick_due_enrollments
from ptt_jobs.store import mark_job_done, mark_job_failed

logger = logging.getLogger(__name__)


def run_email_journey_tick_job(job: dict[str, Any]) -> None:
    job_id = str(job["id"])
    try:
        outcome = tick_due_enrollments()
        if outcome.get("ok"):
            mark_job_done(job_id)
            return
        mark_job_failed(
            job_id,
            str(outcome.get("error") or "journey_tick_failed"),
            attempts=int(job.get("attempts") or 1),
            max_attempts=int(job.get("max_attempts") or 5),
        )
    except Exception as exc:
        logger.exception("email_journey_tick failed: %s", exc)
        mark_job_failed(
            job_id,
            str(exc),
            attempts=int(job.get("attempts") or 1),
            max_attempts=int(job.get("max_attempts") or 5),
        )
