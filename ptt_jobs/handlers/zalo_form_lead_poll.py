"""Job handler: Zalo form lead poll (Wave Z2)."""
from __future__ import annotations

import json
import logging
from typing import Any

from ptt_jobs.store import mark_job_done, mark_job_failed
from ptt_zalo.form_lead_poll import poll_zalo_form_leads

logger = logging.getLogger(__name__)


def process_zalo_form_lead_poll_payload(payload: dict[str, Any]) -> dict[str, Any]:
    client_id = str(payload.get("client_id") or "").strip() or None
    form_id = str(payload.get("form_id") or "").strip() or None
    oa_id = str(payload.get("oa_id") or "").strip() or None
    force = bool(payload.get("force", False))
    return poll_zalo_form_leads(client_id=client_id, form_id=form_id, oa_id=oa_id, force=force)


def run_zalo_form_lead_poll_job(job: dict[str, Any]) -> None:
    job_id = str(job["id"])
    payload = job.get("payload") or {}
    if isinstance(payload, str):
        payload = json.loads(payload)

    attempts = int(job.get("attempts") or 1)
    max_attempts = int(job.get("max_attempts") or 5)

    outcome = process_zalo_form_lead_poll_payload(payload)
    if outcome.get("ok") or outcome.get("skipped"):
        mark_job_done(job_id)
        logger.info("zalo_form_lead_poll done job_id=%s outcome=%s", job_id, outcome)
        return

    error = str(outcome.get("error") or outcome.get("reason") or "zalo form lead poll failed")
    if outcome.get("failures"):
        error = f"{error}; failures={outcome.get('failures')}"
    mark_job_failed(job_id, error, attempts=attempts, max_attempts=max_attempts)
