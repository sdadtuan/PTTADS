"""Job handler — hourly conversion backfill (B9)."""
from __future__ import annotations

import json
import logging
from typing import Any

from ptt_meta.conversion_sync import run_conversion_sync
from ptt_jobs.store import mark_job_done, mark_job_failed

logger = logging.getLogger(__name__)


def process_meta_conversion_sync_payload(payload: dict[str, Any]) -> dict[str, Any]:
    client_id = payload.get("client_id")
    lookback = payload.get("lookback_hours") or payload.get("lookback") or 72
    limit = payload.get("limit") or 500
    return run_conversion_sync(
        client_id=str(client_id) if client_id else None,
        lookback_hours=int(lookback),
        limit=int(limit),
    )


def run_meta_conversion_sync_job(job: dict[str, Any]) -> None:
    job_id = str(job["id"])
    payload = job.get("payload") or {}
    if isinstance(payload, str):
        payload = json.loads(payload)

    attempts = int(job.get("attempts") or 1)
    max_attempts = int(job.get("max_attempts") or 5)

    outcome = process_meta_conversion_sync_payload(payload)
    if outcome.get("ok") or outcome.get("skipped"):
        mark_job_done(job_id)
        logger.info("meta_conversion_sync done job_id=%s outcome=%s", job_id, outcome)
        return

    error = str(outcome.get("error") or "meta conversion sync failed")
    mark_job_failed(job_id, error, attempts=attempts, max_attempts=max_attempts)
