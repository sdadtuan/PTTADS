"""Job handler — evaluate meta_alerts after insights sync (B8)."""
from __future__ import annotations

import json
import logging
from typing import Any

from ptt_meta.alerts import evaluate_meta_alerts
from ptt_jobs.store import mark_job_done, mark_job_failed

logger = logging.getLogger(__name__)


def process_meta_alerts_eval_payload(payload: dict[str, Any]) -> dict[str, Any]:
    client_id = payload.get("client_id")
    performance_date = payload.get("performance_date") or payload.get("target_date")
    return evaluate_meta_alerts(
        client_id=str(client_id) if client_id else None,
        performance_date=performance_date,
    )


def run_meta_alerts_eval_job(job: dict[str, Any]) -> None:
    job_id = str(job["id"])
    payload = job.get("payload") or {}
    if isinstance(payload, str):
        payload = json.loads(payload)

    attempts = int(job.get("attempts") or 1)
    max_attempts = int(job.get("max_attempts") or 5)

    outcome = process_meta_alerts_eval_payload(payload)
    if outcome.get("ok") or outcome.get("skipped"):
        mark_job_done(job_id)
        logger.info("meta_alerts_eval done job_id=%s outcome=%s", job_id, outcome)
        return

    error = str(outcome.get("error") or "meta alerts eval failed")
    mark_job_failed(job_id, error, attempts=attempts, max_attempts=max_attempts)
