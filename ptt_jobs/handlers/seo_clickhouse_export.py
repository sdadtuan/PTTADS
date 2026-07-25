"""Job handler — seo_clickhouse_export (Phase 6 / Gate D BI)."""
from __future__ import annotations

import logging
from typing import Any

from ptt_jobs.store import mark_job_done, mark_job_failed
from ptt_seo.bi_clickhouse import export_seo_facts_to_clickhouse
from ptt_seo.db import seo_read

logger = logging.getLogger(__name__)


def run_seo_clickhouse_export_job(job: dict[str, Any]) -> None:
    job_id = str(job["id"])
    payload = job.get("payload") or {}
    fact_date = payload.get("fact_date")
    try:
        with seo_read() as conn:
            outcome = export_seo_facts_to_clickhouse(conn, fact_date=fact_date, skip_if_no_ch=False)
        if outcome.get("ok") or outcome.get("skipped"):
            mark_job_done(job_id)
            return
        mark_job_failed(
            job_id,
            str(outcome.get("error") or "export_failed"),
            attempts=int(job.get("attempts") or 1),
            max_attempts=int(job.get("max_attempts") or 5),
        )
    except Exception as exc:
        logger.exception("seo_clickhouse_export: %s", exc)
        mark_job_failed(
            job_id,
            str(exc),
            attempts=int(job.get("attempts") or 1),
            max_attempts=int(job.get("max_attempts") or 5),
        )
