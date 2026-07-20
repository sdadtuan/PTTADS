"""Job handler — email_deliverability_scan (Wave 2)."""
from __future__ import annotations

import logging
from typing import Any

from ptt_email.deliverability import run_deliverability_scan
from ptt_jobs.store import mark_job_done, mark_job_failed

logger = logging.getLogger(__name__)


def run_email_deliverability_scan_job(job: dict[str, Any]) -> None:
    job_id = str(job["id"])
    payload = job.get("payload") or {}
    hours = int(payload.get("hours") or 24)
    try:
        outcome = run_deliverability_scan(hours=hours)
        if outcome.get("ok"):
            mark_job_done(job_id)
            return
        mark_job_failed(job_id, "scan_failed", attempts=int(job.get("attempts") or 1), max_attempts=int(job.get("max_attempts") or 5))
    except Exception as exc:
        logger.exception("email_deliverability_scan: %s", exc)
        mark_job_failed(job_id, str(exc), attempts=int(job.get("attempts") or 1), max_attempts=int(job.get("max_attempts") or 5))
