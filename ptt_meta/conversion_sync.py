"""B9 conversion backfill — scan recent leads and enqueue/dispatch CAPI conversion events."""
from __future__ import annotations

import logging
import os
from typing import Any

from ptt_jobs.db import pg_connection
from ptt_meta.capi_dispatch import (
    capi_dispatch_enabled,
    capi_stub_mode,
    find_capi_log_dedup,
    load_lead_for_capi,
    pg_capi_ready,
)
from ptt_meta.conversion_rules import (
    ConversionDispatchIntent,
    evaluate_conversion_rules,
    normalize_lead,
    summarize_intents,
)

logger = logging.getLogger(__name__)


def _truthy(name: str, default: str = "0") -> bool:
    return os.environ.get(name, default).strip().lower() in {"1", "true", "yes", "on"}


def conversion_sync_enabled() -> bool:
    return _truthy("PTT_META_CONVERSION_SYNC_ENABLED", "1") and (
        capi_dispatch_enabled() or capi_stub_mode()
    )


def list_leads_for_conversion_sync(
    *,
    client_id: str | None = None,
    lookback_hours: int = 72,
    limit: int = 500,
) -> list[dict[str, Any]]:
    """Leads updated within lookback window with agency client binding."""
    hours = max(1, min(int(lookback_hours), 24 * 14))
    max_rows = max(1, min(int(limit), 2000))
    clauses = [
        "agency_client_id IS NOT NULL",
        "updated_at >= NOW() - (%s || ' hours')::interval",
    ]
    params: list[Any] = [str(hours)]
    if client_id:
        clauses.append("agency_client_id = %s::uuid")
        params.append(client_id)
    params.append(max_rows)

    with pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT sqlite_lead_id, agency_client_id::text, status, channel,
                       external_lead_id, campaign_id, meta_json, updated_at
                FROM crm_leads
                WHERE {' AND '.join(clauses)}
                ORDER BY updated_at DESC
                LIMIT %s
                """,
                params,
            )
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]


def intent_already_sent(intent: ConversionDispatchIntent) -> bool:
    if intent.get("skipped") or not intent.get("event_id"):
        return False
    client_id = str(intent.get("client_id") or "")
    event_name = str(intent.get("event_name") or "")
    event_id = str(intent.get("event_id") or "")
    if not client_id or not event_name or not event_id:
        return False
    existing = find_capi_log_dedup(client_id, event_name, event_id)
    return bool(existing and existing.get("status") == "sent")


def enqueue_conversion_intent(intent: ConversionDispatchIntent) -> dict[str, Any] | None:
    """Enqueue capi_dispatch with conversion_intent payload."""
    if intent.get("skipped"):
        return None
    client_id = str(intent.get("client_id") or "")
    event_id = str(intent.get("event_id") or "")
    event_name = str(intent.get("event_name") or "")
    lead_id = intent.get("lead_id")
    if not client_id or not event_id or not event_name:
        return None
    try:
        from ptt_jobs.enqueue import enqueue_job

        idem = f"capi:conv:{client_id}:{event_name}:{event_id}"
        return enqueue_job(
            "capi_dispatch",
            {
                "conversion_intent": intent,
                "client_id": client_id,
                "lead_id": lead_id,
            },
            idem,
            client_id=client_id,
        )
    except Exception as exc:
        logger.debug("conversion enqueue skipped lead_id=%s: %s", lead_id, exc)
        return None


def process_conversion_intents(
    intents: list[ConversionDispatchIntent],
    *,
    mode: str = "enqueue",
) -> dict[str, Any]:
    """Apply dispatch/enqueue for evaluated intents with capi_event_log dedupe."""
    results: list[dict[str, Any]] = []
    enqueued = 0
    dispatched = 0
    deduped = 0
    skipped = 0

    for intent in intents:
        if intent.get("skipped"):
            skipped += 1
            results.append({"ok": True, "skipped": True, "reason": intent.get("reason")})
            continue
        if intent_already_sent(intent):
            deduped += 1
            results.append(
                {
                    "ok": True,
                    "skipped": True,
                    "reason": "dedup",
                    "event_id": intent.get("event_id"),
                }
            )
            continue

        if mode == "dispatch":
            from ptt_meta.capi_dispatch import dispatch_conversion_intent

            out = dispatch_conversion_intent(intent)
            results.append(out)
            if out.get("ok") and not out.get("skipped"):
                dispatched += 1
            elif out.get("skipped"):
                skipped += 1
            continue

        job = enqueue_conversion_intent(intent)
        if job:
            enqueued += 1
            results.append({"ok": True, "enqueued": True, "job_id": job.get("id")})
        else:
            skipped += 1
            results.append({"ok": True, "skipped": True, "reason": "enqueue_unavailable"})

    summary = summarize_intents(intents)
    summary.update(
        {
            "enqueued": enqueued,
            "dispatched": dispatched,
            "deduped": deduped,
            "skipped_results": skipped,
            "results": results,
        }
    )
    return summary


def process_conversion_eval_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Evaluate rules for a single lead status transition (Nest hook / job)."""
    lead_id = int(payload.get("lead_id") or 0)
    client_id = str(payload.get("client_id") or "").strip()
    old_status = payload.get("old_status")
    new_status = payload.get("new_status")
    mode = str(payload.get("mode") or "dispatch").strip().lower()

    if not lead_id:
        return {"ok": False, "error": "lead_id required"}

    lead = load_lead_for_capi(lead_id)
    if not lead:
        return {"ok": False, "error": "lead_not_found", "lead_id": lead_id}

    if client_id:
        lead["agency_client_id"] = client_id
        lead["client_id"] = client_id

    intents = evaluate_conversion_rules(lead, old_status, new_status)
    out = process_conversion_intents(intents, mode=mode if mode in {"enqueue", "dispatch"} else "dispatch")
    out["lead_id"] = lead_id
    out["client_id"] = client_id or normalize_lead(lead).get("client_id")
    return out


def run_conversion_sync(
    *,
    client_id: str | None = None,
    lookback_hours: int = 72,
    limit: int = 500,
) -> dict[str, Any]:
    """Hourly backfill — evaluate current status for recently updated leads."""
    if not conversion_sync_enabled():
        return {"ok": True, "skipped": True, "reason": "conversion_sync_disabled"}
    if not pg_capi_ready():
        return {"ok": False, "error": "capi_log_not_ready"}

    rows = list_leads_for_conversion_sync(
        client_id=client_id,
        lookback_hours=lookback_hours,
        limit=limit,
    )
    processed = 0
    total_enqueued = 0
    total_deduped = 0
    lead_results: list[dict[str, Any]] = []

    for row in rows:
        lead_id = int(row.get("sqlite_lead_id") or 0)
        if not lead_id:
            continue
        lead = load_lead_for_capi(lead_id) or row
        lead["id"] = lead_id
        lead["agency_client_id"] = row.get("agency_client_id")
        lead["client_id"] = row.get("agency_client_id")
        status = row.get("status")
        intents = evaluate_conversion_rules(lead, None, status, force=True)
        out = process_conversion_intents(intents, mode="enqueue")
        processed += 1
        total_enqueued += int(out.get("enqueued") or 0)
        total_deduped += int(out.get("deduped") or 0)
        if out.get("dispatch_count", 0) or out.get("enqueued") or out.get("deduped"):
            lead_results.append(
                {
                    "lead_id": lead_id,
                    "client_id": row.get("agency_client_id"),
                    "status": status,
                    "enqueued": out.get("enqueued"),
                    "deduped": out.get("deduped"),
                }
            )

    return {
        "ok": True,
        "client_id": client_id,
        "lookback_hours": lookback_hours,
        "leads_scanned": len(rows),
        "leads_processed": processed,
        "enqueued": total_enqueued,
        "deduped": total_deduped,
        "samples": lead_results[:20],
    }
