"""Job handler — SEO content freshness scan (Phase 4B)."""
from __future__ import annotations

import json
import logging
from typing import Any

from ptt_jobs.store import mark_job_done, mark_job_failed
from ptt_seo.freshness import process_seo_freshness_scan_payload

logger = logging.getLogger(__name__)


def run_seo_freshness_scan_job(job: dict[str, Any]) -> None:
    job_id = str(job["id"])
    payload = job.get("payload") or {}
    if isinstance(payload, str):
        payload = json.loads(payload)

    attempts = int(job.get("attempts") or 1)
    max_attempts = int(job.get("max_attempts") or 5)

    outcome = process_seo_freshness_scan_payload(payload)
    if outcome.get("ok"):
        mark_job_done(job_id)
        logger.info("seo_freshness_scan done job_id=%s outcome=%s", job_id, outcome)
        return

    error = str(outcome.get("error") or "seo freshness scan failed")
    mark_job_failed(job_id, error, attempts=attempts, max_attempts=max_attempts)
