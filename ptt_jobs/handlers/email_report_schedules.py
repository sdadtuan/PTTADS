"""Job handler — email_report_schedules (Wave 2)."""
from __future__ import annotations

import logging
from typing import Any

from ptt_email.report_schedule import run_due_schedules, run_schedule
from ptt_jobs.store import mark_job_done, mark_job_failed

logger = logging.getLogger(__name__)


def run_email_report_schedules_job(job: dict[str, Any]) -> None:
    job_id = str(job["id"])
    payload = job.get("payload") or {}
    schedule_id = str(payload.get("schedule_id") or "").strip()
    try:
        if schedule_id:
            outcome = run_schedule(schedule_id)
        else:
            outcome = run_due_schedules(as_of=payload.get("as_of"))
        if outcome.get("ok"):
            mark_job_done(job_id)
            return
        mark_job_failed(job_id, str(outcome.get("error") or "report_failed"), attempts=int(job.get("attempts") or 1), max_attempts=int(job.get("max_attempts") or 5))
    except Exception as exc:
        logger.exception("email_report_schedules: %s", exc)
        mark_job_failed(job_id, str(exc), attempts=int(job.get("attempts") or 1), max_attempts=int(job.get("max_attempts") or 5))
