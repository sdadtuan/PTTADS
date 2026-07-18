"""LeadCreated domain_events → CAPI enqueue (Phase 2 P2 #12)."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

logger = logging.getLogger(__name__)


def _parse_payload(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


def fetch_recent_lead_created_events(*, limit: int = 50, since_hours: int = 72) -> list[dict[str, Any]]:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=max(1, since_hours))
    lim = max(1, min(int(limit), 200))
    try:
        from ptt_jobs.db import pg_connection

        with pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, payload, correlation_id, created_at
                    FROM domain_events
                    WHERE event_type = 'LeadCreated'
                      AND created_at >= %s
                    ORDER BY created_at DESC
                    LIMIT %s
                    """,
                    (cutoff, lim),
                )
                cols = [d[0] for d in cur.description]
                return [dict(zip(cols, row)) for row in cur.fetchall()]
    except Exception as exc:
        logger.debug("fetch LeadCreated events: %s", exc)
        return []


def process_lead_created_outbox(
    *,
    batch_size: int = 50,
    since_hours: int = 72,
) -> dict[str, Any]:
    """
    Enqueue capi_dispatch for LeadCreated outbox rows (any publisher path).

    Job idempotency key capi:lead:{client}:{lead_id} prevents duplicate sends.
    """
    from ptt_meta.capi_dispatch import capi_dispatch_enabled, capi_stub_mode, enqueue_capi_lead_dispatch

    if not capi_dispatch_enabled() and not capi_stub_mode():
        return {"ok": True, "skipped": True, "reason": "capi_disabled"}

    events = fetch_recent_lead_created_events(limit=batch_size, since_hours=since_hours)
    enqueued = 0
    skipped = 0
    errors: list[str] = []

    for ev in events:
        payload = _parse_payload(ev.get("payload"))
        lead_id = payload.get("lead_id")
        client_id = str(payload.get("client_id") or "").strip()
        if lead_id is None or not client_id or client_id in {"unknown", ""}:
            skipped += 1
            continue
        try:
            out = enqueue_capi_lead_dispatch(
                lead_id=int(lead_id),
                client_id=client_id,
                external_lead_id=str(payload.get("external_lead_id") or "") or None,
                correlation_id=str(ev.get("correlation_id") or ev.get("id") or "") or None,
            )
            if out:
                enqueued += 1
            else:
                skipped += 1
        except Exception as exc:
            errors.append(f"lead_id={lead_id}:{exc}")
            logger.debug("LeadCreated capi enqueue failed: %s", exc)

    return {
        "ok": len(errors) == 0,
        "scanned": len(events),
        "enqueued": enqueued,
        "skipped": skipped,
        "errors": errors[:5],
    }
