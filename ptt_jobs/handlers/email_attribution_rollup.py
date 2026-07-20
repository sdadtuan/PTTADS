"""Job handler — email_attribution_rollup (Wave 2)."""
from __future__ import annotations

import logging
from typing import Any

from ptt_email.attribution import rollup_daily_metrics
from ptt_jobs.store import mark_job_done, mark_job_failed

logger = logging.getLogger(__name__)


def run_email_attribution_rollup_job(job: dict[str, Any]) -> None:
    job_id = str(job["id"])
    payload = job.get("payload") or {}
    try:
        outcome = rollup_daily_metrics(
            client_id=str(payload.get("client_id") or "").strip() or None,
            metric_date=payload.get("metric_date"),
        )
        if outcome.get("ok"):
            mark_job_done(job_id)
            return
        mark_job_failed(job_id, "rollup_failed", attempts=int(job.get("attempts") or 1), max_attempts=int(job.get("max_attempts") or 5))
    except Exception as exc:
        logger.exception("email_attribution_rollup: %s", exc)
        mark_job_failed(job_id, str(exc), attempts=int(job.get("attempts") or 1), max_attempts=int(job.get("max_attempts") or 5))
