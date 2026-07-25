"""Job handler — zalo_form_poll_sla (Prod-S3)."""
from __future__ import annotations

import json
import logging
from typing import Any

from ptt_jobs.store import mark_job_done, mark_job_failed
from ptt_zalo.form_poll_sla import evaluate_form_poll_sla

logger = logging.getLogger(__name__)


def process_zalo_form_poll_sla_payload(payload: dict[str, Any]) -> dict[str, Any]:
    client_id = str(payload.get("client_id") or "").strip() or None
    dry_run = bool(payload.get("dry_run"))
    return evaluate_form_poll_sla(client_id=client_id, dry_run=dry_run)


def run_zalo_form_poll_sla_job(job: dict[str, Any]) -> None:
    job_id = str(job["id"])
    payload = job.get("payload") or {}
    if isinstance(payload, str):
        payload = json.loads(payload)

    attempts = int(job.get("attempts") or 1)
    max_attempts = int(job.get("max_attempts") or 5)

    outcome = process_zalo_form_poll_sla_payload(payload)
    if outcome.get("ok") or outcome.get("skipped"):
        mark_job_done(job_id)
        logger.info("zalo_form_poll_sla done job_id=%s outcome=%s", job_id, outcome)
        return

    error = str(outcome.get("error") or "zalo form poll sla failed")
    mark_job_failed(job_id, error, attempts=attempts, max_attempts=max_attempts)
