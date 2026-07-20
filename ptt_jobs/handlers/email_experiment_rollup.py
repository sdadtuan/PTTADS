"""Job handler — email_experiment_rollup (EM-12)."""
from __future__ import annotations

import logging
from typing import Any

from ptt_email.experiments import rollup_experiment_metrics
from ptt_jobs.store import mark_job_done, mark_job_failed

logger = logging.getLogger(__name__)


def run_email_experiment_rollup_job(job: dict[str, Any]) -> None:
    job_id = str(job["id"])
    payload = job.get("payload") or {}
    experiment_id = str(payload.get("experiment_id") or "").strip()
    if not experiment_id:
        mark_job_failed(job_id, "missing experiment_id", attempts=1, max_attempts=1)
        return
    try:
        outcome = rollup_experiment_metrics(experiment_id)
        if outcome.get("ok"):
            mark_job_done(job_id)
            return
        mark_job_failed(
            job_id,
            str(outcome.get("error") or "experiment_rollup_failed"),
            attempts=int(job.get("attempts") or 1),
            max_attempts=int(job.get("max_attempts") or 5),
        )
    except Exception as exc:
        logger.exception("email_experiment_rollup failed: %s", exc)
        mark_job_failed(
            job_id,
            str(exc),
            attempts=int(job.get("attempts") or 1),
            max_attempts=int(job.get("max_attempts") or 5),
        )
