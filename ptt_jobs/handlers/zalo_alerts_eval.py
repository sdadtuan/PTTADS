"""Job handler — evaluate Zalo alerts after insights sync (Z3)."""
from __future__ import annotations

import json
import logging
from typing import Any

from ptt_jobs.store import mark_job_done, mark_job_failed
from ptt_zalo.alerts import evaluate_zalo_alerts

logger = logging.getLogger(__name__)


def process_zalo_alerts_eval_payload(payload: dict[str, Any]) -> dict[str, Any]:
    client_id = str(payload.get("client_id") or "").strip() or None
    target_date = payload.get("target_date") or payload.get("performance_date")
    return evaluate_zalo_alerts(client_id=client_id, performance_date=target_date)


def run_zalo_alerts_eval_job(job: dict[str, Any]) -> None:
    job_id = str(job["id"])
    payload = job.get("payload") or {}
    if isinstance(payload, str):
        payload = json.loads(payload)

    attempts = int(job.get("attempts") or 1)
    max_attempts = int(job.get("max_attempts") or 5)

    outcome = process_zalo_alerts_eval_payload(payload)
    if outcome.get("ok") or outcome.get("skipped"):
        mark_job_done(job_id)
        logger.info("zalo_alerts_eval done job_id=%s outcome=%s", job_id, outcome)
        return

    error = str(outcome.get("error") or "zalo alerts eval failed")
    mark_job_failed(job_id, error, attempts=attempts, max_attempts=max_attempts)
