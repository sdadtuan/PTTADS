"""Job handler: Zalo Ads insights sync (Wave Z1)."""
from __future__ import annotations

import json
import logging
from typing import Any

from ptt_zalo.insights_sync import sync_zalo_insights
from ptt_jobs.store import mark_job_done, mark_job_failed

logger = logging.getLogger(__name__)


def process_zalo_insights_sync_payload(payload: dict[str, Any]) -> dict[str, Any]:
    client_id = str(payload.get("client_id") or "").strip() or None
    target_date = payload.get("target_date")
    compute_metrics = bool(payload.get("compute_metrics", True))
    return sync_zalo_insights(
        client_id=client_id,
        target_date=target_date,
        compute_metrics=compute_metrics,
    )


def run_zalo_insights_sync_job(job: dict[str, Any]) -> None:
    job_id = str(job["id"])
    payload = job.get("payload") or {}
    if isinstance(payload, str):
        payload = json.loads(payload)

    attempts = int(job.get("attempts") or 1)
    max_attempts = int(job.get("max_attempts") or 5)

    outcome = process_zalo_insights_sync_payload(payload)
    if outcome.get("ok") or outcome.get("skipped"):
        mark_job_done(job_id)
        logger.info("zalo_insights_sync done job_id=%s outcome=%s", job_id, outcome)
        return

    error = str(outcome.get("error") or outcome.get("reason") or "zalo insights sync failed")
    if outcome.get("accounts_failed"):
        error = f"{error}; failures={outcome.get('accounts_failed')}"
    mark_job_failed(job_id, error, attempts=attempts, max_attempts=max_attempts)
