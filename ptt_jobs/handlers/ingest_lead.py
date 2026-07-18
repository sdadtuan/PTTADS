"""Ingest normalized lead into SQLite CRM."""
from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timezone
from typing import Any

from ptt_channel.mappers import normalized_lead_to_legacy
from ptt_jobs.config import sqlite_db_path
from ptt_jobs.events import emit_domain_event
from ptt_jobs.store import JOB_STATUS_DEAD, mark_job_done, mark_job_failed

logger = logging.getLogger(__name__)


def _utc_ts() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _default_source(channel: str) -> str:
    ch = (channel or "").lower()
    if ch in {"meta", "facebook"}:
        return "facebook"
    return ch or "webhook"


def process_ingest_lead_payload(
    payload: dict[str, Any],
    *,
    correlation_id: str | None = None,
) -> dict[str, Any]:
    lead_dict = payload.get("lead") if isinstance(payload.get("lead"), dict) else payload
    channel = str(payload.get("channel") or lead_dict.get("channel") or "meta")
    client_id = str(payload.get("client_id") or lead_dict.get("client_id") or "")

    legacy_item = normalized_lead_to_legacy(lead_dict)
    if client_id and client_id not in {"unknown", ""}:
        meta = legacy_item.setdefault("meta", {})
        if isinstance(meta, dict):
            meta["agency_client_id"] = client_id

    source = _default_source(channel)
    db_path = sqlite_db_path()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        from crm_lead_webhooks import ingest_webhook_leads

        result = ingest_webhook_leads(
            conn,
            [legacy_item],
            default_source=source,
            created_by="ptt_worker",
            ts=_utc_ts(),
            webhook_slug=f"v1_{channel}",
        )
        conn.commit()

        for lead_id in result.get("created_ids") or []:
            emit_domain_event(
                "LeadCreated",
                "lead",
                str(lead_id),
                {
                    "lead_id": lead_id,
                    "channel": channel,
                    "client_id": client_id or None,
                    "external_lead_id": lead_dict.get("external_lead_id"),
                },
                correlation_id=correlation_id,
            )
            if client_id and client_id not in {"", "unknown"}:
                try:
                    from ptt_meta.capi_dispatch import enqueue_capi_lead_dispatch

                    enqueue_capi_lead_dispatch(
                        lead_id=int(lead_id),
                        client_id=client_id,
                        external_lead_id=str(lead_dict.get("external_lead_id") or "") or None,
                        correlation_id=correlation_id,
                    )
                except Exception as exc:
                    logger.debug("capi enqueue after ingest skipped: %s", exc)

        try:
            from ptt_crm.lead_sync import sync_after_ingest

            sync_after_ingest(list(result.get("created_ids") or []))
        except Exception as exc:
            logger.warning("post-ingest lead sync skipped: %s", exc)

        return {
            "ok": True,
            "created_count": result.get("created_count", 0),
            "created_ids": result.get("created_ids", []),
            "skipped": result.get("skipped", []),
            "results": result.get("results"),
        }
    except Exception as exc:
        conn.rollback()
        logger.exception("ingest_lead failed: %s", exc)
        return {"ok": False, "error": str(exc)}
    finally:
        conn.close()


def run_ingest_lead_job(job: dict[str, Any]) -> None:
    job_id = str(job["id"])
    payload = job.get("payload") or {}
    if isinstance(payload, str):
        import json

        payload = json.loads(payload)

    correlation_id = job.get("correlation_id")
    attempts = int(job.get("attempts") or 1)
    max_attempts = int(job.get("max_attempts") or 5)

    outcome = process_ingest_lead_payload(payload, correlation_id=correlation_id)
    if outcome.get("ok"):
        mark_job_done(job_id)
        emit_domain_event(
            "JobCompleted",
            "job",
            job_id,
            {
                "job_id": job_id,
                "job_type": "ingest_lead",
                "status": "done",
                "correlation_id": correlation_id,
                "created_count": outcome.get("created_count", 0),
            },
            correlation_id=correlation_id,
        )
        return

    error = str(outcome.get("error") or "ingest failed")
    status = mark_job_failed(job_id, error, attempts=attempts, max_attempts=max_attempts)
    if status == JOB_STATUS_DEAD:
        emit_domain_event(
            "JobDead",
            "job",
            job_id,
            {
                "job_id": job_id,
                "job_type": "ingest_lead",
                "last_error": error,
                "correlation_id": correlation_id,
            },
            correlation_id=correlation_id,
        )
