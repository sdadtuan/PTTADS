"""Job handler: Zalo Ads insights sync (Wave Z1)."""
from __future__ import annotations

import json
import logging
from typing import Any

from ptt_zalo.insights_sync import sync_zalo_insights
from ptt_jobs.store import mark_job_done, mark_job_failed

logger = logging.getLogger(__name__)


def _maybe_enqueue_zalo_alerts_eval(payload: dict[str, Any], outcome: dict[str, Any]) -> None:
    try:
        from ptt_zalo.alerts import zalo_alerts_enabled
        from ptt_jobs.store import enqueue_job

        if not zalo_alerts_enabled():
            return
        if not (outcome.get("ok") or outcome.get("skipped")):
            return
        client_id = str(payload.get("client_id") or "").strip()
        target_date = outcome.get("performance_date") or payload.get("target_date")
        cid_part = client_id or "all"
        date_key = str(target_date or "latest")[:10]
        idem = f"zalo_alerts_eval:{cid_part}:{date_key}"
        enqueue_job(
            job_type="zalo_alerts_eval",
            payload={
                "client_id": client_id or None,
                "target_date": target_date,
                "mode": "dispatch",
            },
            idempotency_key=idem,
            client_id=client_id or None,
        )
    except Exception as exc:
        logger.warning("zalo_alerts_eval enqueue skipped: %s", exc)


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
        _maybe_enqueue_zalo_alerts_eval(payload, outcome)
        mark_job_done(job_id)
        logger.info("zalo_insights_sync done job_id=%s outcome=%s", job_id, outcome)
        return

    error = str(outcome.get("error") or outcome.get("reason") or "zalo insights sync failed")
    if outcome.get("accounts_failed"):
        error = f"{error}; failures={outcome.get('accounts_failed')}"
    mark_job_failed(job_id, error, attempts=attempts, max_attempts=max_attempts)
