"""Job handler — sync PostgreSQL crm_leads → SQLite shadow (Phase 2 W2)."""
from __future__ import annotations

import json
import logging
from typing import Any

from ptt_crm.lead_shadow_sync import (
    sync_shadow_full,
    sync_shadow_incremental,
    sync_shadow_lead_ids,
)
from ptt_jobs.store import mark_job_done, mark_job_failed

logger = logging.getLogger(__name__)


def process_sync_lead_shadow_payload(payload: dict[str, Any]) -> dict[str, Any]:
    mode = str(payload.get("mode") or "incremental").strip().lower()
    if mode == "ids":
        ids = payload.get("lead_ids") or []
        return sync_shadow_lead_ids([int(x) for x in ids])
    if mode == "full":
        return sync_shadow_full(
            batch_size=int(payload.get("batch_size") or 500),
            max_batches=int(payload.get("max_batches") or 100),
        )
    return sync_shadow_incremental(batch_size=int(payload.get("batch_size") or 200))


def run_sync_lead_shadow_job(job: dict[str, Any]) -> None:
    job_id = str(job["id"])
    payload = job.get("payload") or {}
    if isinstance(payload, str):
        payload = json.loads(payload)

    attempts = int(job.get("attempts") or 1)
    max_attempts = int(job.get("max_attempts") or 5)

    outcome = process_sync_lead_shadow_payload(payload)
    if outcome.get("ok"):
        mark_job_done(job_id)
        logger.info("sync_lead_shadow done job_id=%s outcome=%s", job_id, outcome)
        return

    error = str(outcome.get("error") or outcome.get("reason") or "shadow sync failed")
    mark_job_failed(job_id, error, attempts=attempts, max_attempts=max_attempts)
