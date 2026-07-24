"""Job handler — meta_clickhouse_export (B14)."""
from __future__ import annotations

import logging
from typing import Any

from ptt_meta.warehouse_export import export_meta_facts_range, export_meta_facts_to_clickhouse
from ptt_jobs.store import mark_job_done, mark_job_failed

logger = logging.getLogger(__name__)


def run_meta_clickhouse_export_job(job: dict[str, Any]) -> None:
    job_id = str(job["id"])
    payload = job.get("payload") or {}
    fact_date = payload.get("fact_date")
    client_id = payload.get("client_id")
    days = int(payload.get("days") or 0)
    attempts = int(job.get("attempts") or 1)
    max_attempts = int(job.get("max_attempts") or 5)

    try:
        if days > 1:
            outcome = export_meta_facts_range(days=days, client_id=client_id, skip_if_no_ch=False)
        else:
            outcome = export_meta_facts_to_clickhouse(
                fact_date=str(fact_date) if fact_date else None,
                client_id=str(client_id) if client_id else None,
                skip_if_no_ch=False,
            )
    except Exception as exc:
        logger.exception("meta_clickhouse_export failed job_id=%s", job_id)
        mark_job_failed(job_id, str(exc), attempts=attempts, max_attempts=max_attempts)
        return

    if outcome.get("ok") or outcome.get("skipped"):
        mark_job_done(job_id)
        logger.info("meta_clickhouse_export done job_id=%s outcome=%s", job_id, outcome)
        return

    mark_job_failed(
        job_id,
        str(outcome.get("error") or "meta_clickhouse_export_failed"),
        attempts=attempts,
        max_attempts=max_attempts,
    )
