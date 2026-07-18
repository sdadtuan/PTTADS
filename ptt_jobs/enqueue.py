"""Enqueue helpers and sync fallback."""
from __future__ import annotations

import logging
from typing import Any

from ptt_jobs.config import jobs_enabled, jobs_sync_fallback, webhook_enqueue_enabled
from ptt_jobs.db import PgUnavailableError, pg_available
from ptt_jobs.handlers.ingest_lead import process_ingest_lead_payload
from ptt_jobs.store import enqueue_job_record

logger = logging.getLogger(__name__)


def enqueue_job(
    job_type: str,
    payload: dict[str, Any],
    idempotency_key: str,
    *,
    correlation_id: str | None = None,
    client_id: str | None = None,
) -> dict[str, Any]:
    return enqueue_job_record(
        job_type=job_type,
        payload=payload,
        idempotency_key=idempotency_key,
        correlation_id=correlation_id,
        client_id=_normalize_client_uuid(client_id),
    )


def enqueue_ingest_leads(
    leads: list[dict[str, Any]],
    *,
    channel: str,
    correlation_id: str | None = None,
    client_id: str = "",
) -> dict[str, Any]:
    """
    Enqueue one job per lead. Falls back to sync ingest when PG unavailable.

    Returns:
        mode: queue | sync
        jobs: list of job records
        ingest: sync ingest summary (when mode=sync)
    """
    if not leads:
        return {"mode": "none", "jobs": [], "ingest": None}

    use_queue = webhook_enqueue_enabled() and jobs_enabled() and pg_available()

    if not use_queue:
        if jobs_sync_fallback():
            logger.info("job queue unavailable — sync ingest %d lead(s)", len(leads))
            ingest = process_leads_sync(leads, channel=channel, correlation_id=correlation_id)
            return {"mode": "sync", "jobs": [], "ingest": ingest}
        raise PgUnavailableError("Job queue unavailable and sync fallback disabled")

    jobs: list[dict[str, Any]] = []
    for lead in leads:
        ext_id = str(lead.get("external_lead_id") or lead.get("idempotency_key") or "")
        idem = str(lead.get("idempotency_key") or f"ingest:{channel}:{ext_id}")
        payload = {
            "lead": lead,
            "channel": channel,
            "client_id": client_id or lead.get("client_id") or "",
        }
        job = enqueue_job(
            "ingest_lead",
            payload,
            idem,
            correlation_id=correlation_id,
            client_id=client_id or str(lead.get("client_id") or "") or None,
        )
        jobs.append(job)
    return {"mode": "queue", "jobs": jobs, "ingest": None}


def process_leads_sync(
    leads: list[dict[str, Any]],
    *,
    channel: str,
    correlation_id: str | None = None,
) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    for lead in leads:
        payload = {"lead": lead, "channel": channel, "client_id": lead.get("client_id") or ""}
        results.append(process_ingest_lead_payload(payload, correlation_id=correlation_id))
    created = sum(r.get("created_count", 0) for r in results)
    return {"results": results, "created_count": created, "lead_count": len(leads)}


def _normalize_client_uuid(client_id: str | None) -> str | None:
    if not client_id or client_id in {"unknown", ""}:
        return None
    # Allow UUID strings; ignore invalid (store as NULL)
    import re

    if re.match(
        r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
        client_id,
        re.I,
    ):
        return client_id
    return None
