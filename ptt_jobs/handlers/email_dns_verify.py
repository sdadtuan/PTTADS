"""Job handler — email_dns_verify (Wave 2)."""
from __future__ import annotations

import logging
from typing import Any

from ptt_email.dns_verify import verify_and_persist
from ptt_jobs.store import mark_job_done, mark_job_failed

logger = logging.getLogger(__name__)


def run_email_dns_verify_job(job: dict[str, Any]) -> None:
    job_id = str(job["id"])
    payload = job.get("payload") or {}
    domain_id = str(payload.get("domain_id") or "").strip()
    if not domain_id:
        mark_job_failed(job_id, "missing domain_id", attempts=int(job.get("attempts") or 1), max_attempts=int(job.get("max_attempts") or 5))
        return
    try:
        outcome = verify_and_persist(domain_id, actor=str(payload.get("actor") or "worker"))
        if outcome.get("ok"):
            mark_job_done(job_id)
            return
        mark_job_failed(job_id, str(outcome.get("error") or "verify_failed"), attempts=int(job.get("attempts") or 1), max_attempts=int(job.get("max_attempts") or 5))
    except Exception as exc:
        logger.exception("email_dns_verify: %s", exc)
        mark_job_failed(job_id, str(exc), attempts=int(job.get("attempts") or 1), max_attempts=int(job.get("max_attempts") or 5))
