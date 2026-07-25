"""Job handler — webhook_health_check (PROD-H-MON)."""
from __future__ import annotations

import json
import logging
from typing import Any

from ptt_crm.webhook_health import evaluate_webhook_health
from ptt_jobs.store import mark_job_done, mark_job_failed

logger = logging.getLogger(__name__)


def run_webhook_health_check_job(job: dict[str, Any]) -> None:
    job_id = str(job["id"])
    payload = job.get("payload") or {}
    if isinstance(payload, str):
        payload = json.loads(payload)

    dry_run = bool(payload.get("dry_run"))
    outcome = evaluate_webhook_health(dry_run=dry_run)
    if outcome.get("ok") or outcome.get("skipped"):
        mark_job_done(job_id)
        logger.info("webhook_health_check done job_id=%s outcome=%s", job_id, outcome)
        return

    mark_job_failed(
        job_id,
        f"webhook_error_rate={outcome.get('error_rate_pct')}",
        attempts=int(job.get("attempts") or 1),
        max_attempts=int(job.get("max_attempts") or 3),
    )
