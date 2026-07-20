"""Job handler — SEO scheduled report delivery (P2)."""
from __future__ import annotations

import json
import logging
from typing import Any

from ptt_jobs.store import mark_job_done, mark_job_failed
from ptt_seo.report_schedule import process_seo_report_schedules_payload

logger = logging.getLogger(__name__)


def run_seo_report_schedules_job(job: dict[str, Any]) -> None:
    job_id = str(job["id"])
    payload = job.get("payload") or {}
    if isinstance(payload, str):
        payload = json.loads(payload)

    attempts = int(job.get("attempts") or 1)
    max_attempts = int(job.get("max_attempts") or 5)

    outcome = process_seo_report_schedules_payload(payload)
    if outcome.get("ok"):
        mark_job_done(job_id)
        logger.info("seo_report_schedules done job_id=%s processed=%s", job_id, outcome.get("processed"))
        return

    error = str(outcome.get("error") or "seo report schedules failed")
    mark_job_failed(job_id, error, attempts=attempts, max_attempts=max_attempts)
