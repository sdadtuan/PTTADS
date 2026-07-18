"""Job handler — Meta token refresh + expiry alerts (Phase 2 M1-03)."""
from __future__ import annotations

import json
import logging
from typing import Any

from ptt_meta.token_refresh import sync_meta_token_refresh
from ptt_jobs.store import mark_job_done, mark_job_failed

logger = logging.getLogger(__name__)


def process_meta_token_refresh_payload(payload: dict[str, Any]) -> dict[str, Any]:
    dry_run = bool(payload.get("dry_run"))
    force = bool(payload.get("force"))
    return sync_meta_token_refresh(dry_run=dry_run, force=force)


def run_meta_token_refresh_job(job: dict[str, Any]) -> None:
    job_id = str(job["id"])
    payload = job.get("payload") or {}
    if isinstance(payload, str):
        payload = json.loads(payload)

    attempts = int(job.get("attempts") or 1)
    max_attempts = int(job.get("max_attempts") or 5)

    outcome = process_meta_token_refresh_payload(payload)
    if outcome.get("ok") or outcome.get("skipped"):
        mark_job_done(job_id)
        logger.info("meta_token_refresh done job_id=%s outcome=%s", job_id, outcome)
        return

    error = str(outcome.get("error") or outcome.get("reason") or "meta token refresh failed")
    if outcome.get("refresh_failed"):
        error = f"{error}; refresh_failed={outcome.get('refresh_failed')}"
    mark_job_failed(job_id, error, attempts=attempts, max_attempts=max_attempts)
