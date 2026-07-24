"""Job handler — Meta insights → daily_performance (Phase 2 M2)."""
from __future__ import annotations

import json
import logging
from typing import Any

from ptt_meta.insights_sync import sync_meta_insights
from ptt_jobs.store import mark_job_done, mark_job_failed

logger = logging.getLogger(__name__)


def _maybe_enqueue_meta_alerts_eval(payload: dict[str, Any], outcome: dict[str, Any]) -> None:
    try:
        from ptt_meta.alerts import meta_alerts_enabled
        from ptt_jobs.store import enqueue_job_record

        if not meta_alerts_enabled():
            return
        client_id = payload.get("client_id") or outcome.get("client_id")
        perf_date = (
            payload.get("target_date")
            or payload.get("performance_date")
            or outcome.get("performance_date")
        )
        date_key = str(perf_date)[:10] if perf_date else "latest"
        cid_part = str(client_id) if client_id else "all"
        idem = f"meta_alerts_eval:{cid_part}:{date_key}"
        enqueue_job_record(
            job_type="meta_alerts_eval",
            payload={
                "client_id": client_id,
                "performance_date": perf_date,
            },
            idempotency_key=idem,
            client_id=str(client_id) if client_id else None,
        )
    except Exception as exc:
        logger.warning("meta_alerts_eval enqueue skipped: %s", exc)


def process_meta_insights_sync_payload(payload: dict[str, Any]) -> dict[str, Any]:
    target_date = payload.get("target_date") or payload.get("performance_date")
    client_id = payload.get("client_id")
    compute_metrics = payload.get("compute_metrics", True)
    return sync_meta_insights(
        target_date=target_date,
        client_id=str(client_id) if client_id else None,
        compute_metrics=bool(compute_metrics),
    )


def run_meta_insights_sync_job(job: dict[str, Any]) -> None:
    job_id = str(job["id"])
    payload = job.get("payload") or {}
    if isinstance(payload, str):
        payload = json.loads(payload)

    attempts = int(job.get("attempts") or 1)
    max_attempts = int(job.get("max_attempts") or 5)

    outcome = process_meta_insights_sync_payload(payload)
    if outcome.get("ok") or outcome.get("skipped"):
        mark_job_done(job_id)
        logger.info("meta_insights_sync done job_id=%s outcome=%s", job_id, outcome)
        _maybe_enqueue_meta_alerts_eval(payload, outcome)
        return

    error = str(outcome.get("error") or outcome.get("reason") or "meta insights sync failed")
    if outcome.get("accounts_failed"):
        error = f"{error}; failures={outcome.get('accounts_failed')}"
    mark_job_failed(job_id, error, attempts=attempts, max_attempts=max_attempts)
