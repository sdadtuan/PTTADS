"""Job handler — email_journey_trigger_events (EM-12)."""
from __future__ import annotations

import logging
from typing import Any

from ptt_email.triggers import process_pending_trigger_events
from ptt_jobs.store import mark_job_done, mark_job_failed

logger = logging.getLogger(__name__)


def run_email_journey_trigger_events_job(job: dict[str, Any]) -> None:
    job_id = str(job["id"])
    try:
        outcome = process_pending_trigger_events()
        if outcome.get("ok"):
            mark_job_done(job_id)
            return
        mark_job_failed(
            job_id,
            str(outcome.get("error") or "journey_trigger_events_failed"),
            attempts=int(job.get("attempts") or 1),
            max_attempts=int(job.get("max_attempts") or 5),
        )
    except Exception as exc:
        logger.exception("email_journey_trigger_events failed: %s", exc)
        mark_job_failed(
            job_id,
            str(exc),
            attempts=int(job.get("attempts") or 1),
            max_attempts=int(job.get("max_attempts") or 5),
        )
