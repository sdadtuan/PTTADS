"""Job handler — weekly daily_performance archive (B9)."""
from __future__ import annotations

import json
import logging
from typing import Any

from ptt_meta.insights_archive import archive_daily_performance
from ptt_jobs.store import mark_job_done, mark_job_failed

logger = logging.getLogger(__name__)


def process_meta_insights_archive_payload(payload: dict[str, Any]) -> dict[str, Any]:
    dry_run = payload.get("dry_run", True)
    if isinstance(dry_run, str):
        dry_run = dry_run.strip().lower() not in {"0", "false", "no"}
    client_id = payload.get("client_id")
    limit = payload.get("limit") or 5000
    return archive_daily_performance(
        dry_run=bool(dry_run),
        client_id=str(client_id) if client_id else None,
        limit=int(limit),
    )


def run_meta_insights_archive_job(job: dict[str, Any]) -> None:
    job_id = str(job["id"])
    payload = job.get("payload") or {}
    if isinstance(payload, str):
        payload = json.loads(payload)

    attempts = int(job.get("attempts") or 1)
    max_attempts = int(job.get("max_attempts") or 5)

    outcome = process_meta_insights_archive_payload(payload)
    if outcome.get("ok") or outcome.get("skipped"):
        mark_job_done(job_id)
        logger.info("meta_insights_archive done job_id=%s outcome=%s", job_id, outcome)
        return

    error = str(outcome.get("error") or "meta insights archive failed")
    mark_job_failed(job_id, error, attempts=attempts, max_attempts=max_attempts)
