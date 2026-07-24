"""Job handler — lead status → conversion rules eval (B9)."""
from __future__ import annotations

import json
import logging
from typing import Any

from ptt_meta.conversion_sync import process_conversion_eval_payload
from ptt_jobs.store import mark_job_done, mark_job_failed

logger = logging.getLogger(__name__)


def run_meta_conversion_eval_job(job: dict[str, Any]) -> None:
    job_id = str(job["id"])
    payload = job.get("payload") or {}
    if isinstance(payload, str):
        payload = json.loads(payload)

    attempts = int(job.get("attempts") or 1)
    max_attempts = int(job.get("max_attempts") or 5)

    outcome = process_conversion_eval_payload(payload)
    if outcome.get("ok") or outcome.get("skipped"):
        mark_job_done(job_id)
        logger.info("meta_conversion_eval done job_id=%s outcome=%s", job_id, outcome)
        return

    error = str(outcome.get("error") or "meta conversion eval failed")
    mark_job_failed(job_id, error, attempts=attempts, max_attempts=max_attempts)
