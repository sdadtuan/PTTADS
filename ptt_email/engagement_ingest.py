"""Process ESP webhook events into engagement_events + suppression (EM-6)."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from ptt_jobs.db import pg_connection

logger = logging.getLogger(__name__)

SCHEMA = "email_mkt"

EVENT_MAP = {
    "delivered": "delivered",
    "open": "open",
    "click": "click",
    "unsubscribe": "unsubscribe",
    "spamreport": "complaint",
    "complaint": "complaint",
    "bounce": "bounce_hard",
    "dropped": "bounce_hard",
    "deferred": "bounce_soft",
}

SUPPRESSION_EVENTS = {"unsubscribe", "complaint", "bounce_hard"}


def ingest_events(events: list[dict[str, Any]], *, client_id: str = "") -> dict[str, Any]:
    inserted = 0
    suppressed = 0
    skipped = 0

    with pg_connection() as conn:
        with conn.cursor() as cur:
            for raw in events:
                event_type = _normalize_event_type(raw)
                if not event_type:
                    skipped += 1
                    continue
                send_id = _resolve_send_id(cur, raw, client_id)
                if not send_id:
                    skipped += 1
                    continue
                cur.execute(
                    f"""
                    SELECT sq.client_id::text, sq.contact_id::text, ct.email_normalized,
                           sq.campaign_id::text
                    FROM {SCHEMA}.send_queue sq
                    JOIN {SCHEMA}.contacts ct ON ct.id = sq.contact_id
                    WHERE sq.id = %s::uuid
                    """,
                    (send_id,),
                )
                row = cur.fetchone()
                if not row:
                    skipped += 1
                    continue
                evt_client_id, contact_id, email_norm, source_campaign_id = (
                    str(row[0]),
                    str(row[1]),
                    str(row[2]),
                    str(row[3]) if row[3] else None,
                )
                occurred = _parse_ts(raw.get("timestamp") or raw.get("occurred_at"))
                url = str(raw.get("url") or "") or None
                cur.execute(
                    f"""
                    INSERT INTO {SCHEMA}.engagement_events
                      (client_id, send_id, contact_id, event_type, occurred_at, url, raw_payload)
                    VALUES (%s::uuid, %s::uuid, %s::uuid, %s, %s, %s, %s::jsonb)
                    """,
                    (
                        evt_client_id,
                        send_id,
                        contact_id,
                        event_type,
                        occurred,
                        url,
                        _json(raw),
                    ),
                )
                inserted += 1

                if event_type in ("open", "click"):
                    from ptt_email.triggers import record_trigger_event

                    record_trigger_event(
                        client_id=evt_client_id,
                        contact_id=contact_id,
                        event_type=event_type,
                        source_send_id=send_id,
                        source_campaign_id=source_campaign_id,
                    )

                if event_type in SUPPRESSION_EVENTS:
                    reason = {
                        "unsubscribe": "unsubscribe",
                        "complaint": "complaint",
                        "bounce_hard": "hard_bounce",
                    }[event_type]
                    cur.execute(
                        f"""
                        INSERT INTO {SCHEMA}.suppression_entries
                          (client_id, email_normalized, reason, scope, source_send_id, created_by)
                        SELECT %s::uuid, %s, %s, 'client', %s::uuid, 'webhook'
                        WHERE NOT EXISTS (
                          SELECT 1 FROM {SCHEMA}.suppression_entries se
                          WHERE se.email_normalized = %s
                            AND se.client_id = %s::uuid
                            AND se.reason = %s
                            AND se.expires_at IS NULL
                        )
                        """,
                        (
                            evt_client_id,
                            email_norm,
                            reason,
                            send_id,
                            email_norm,
                            evt_client_id,
                            reason,
                        ),
                    )
                    suppressed += 1
                    if event_type == "bounce_hard":
                        cur.execute(
                            f"UPDATE {SCHEMA}.send_queue SET status = 'bounced' WHERE id = %s::uuid",
                            (send_id,),
                        )
        conn.commit()

    return {"ok": True, "inserted": inserted, "suppressed": suppressed, "skipped": skipped}


def _normalize_event_type(raw: dict[str, Any]) -> str | None:
    name = str(raw.get("event") or raw.get("event_type") or raw.get("type") or "").lower()
    if name == "bounce":
        bounce_type = str(raw.get("type") or raw.get("bounce_type") or "hard").lower()
        return "bounce_soft" if bounce_type == "soft" else "bounce_hard"
    return EVENT_MAP.get(name)


def _resolve_send_id(cur: Any, raw: dict[str, Any], client_id: str) -> str | None:
    for key in ("send_id", "ptt_send_id"):
        val = str(raw.get(key) or "").strip()
        if val:
            return val
    custom = raw.get("custom_args") or raw.get("unique_args") or {}
    if isinstance(custom, dict):
        val = str(custom.get("send_id") or "").strip()
        if val:
            return val
    tracking = str(raw.get("tracking_id") or raw.get("sg_message_id") or "").strip()
    if tracking:
        cur.execute(
            f"SELECT id::text FROM {SCHEMA}.send_queue WHERE tracking_id = %s::uuid LIMIT 1",
            (tracking,),
        )
        row = cur.fetchone()
        if row:
            return str(row[0])
    msg_id = str(raw.get("esp_message_id") or raw.get("smtp-id") or "").strip()
    if msg_id:
        cur.execute(
            f"SELECT id::text FROM {SCHEMA}.send_queue WHERE esp_message_id = %s LIMIT 1",
            (msg_id,),
        )
        row = cur.fetchone()
        if row:
            return str(row[0])
    return None


def _parse_ts(value: Any) -> datetime:
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(float(value), tz=timezone.utc)
    text = str(value or "").strip()
    if not text:
        return datetime.now(tz=timezone.utc)
    try:
        if text.isdigit():
            return datetime.fromtimestamp(int(text), tz=timezone.utc)
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return datetime.now(tz=timezone.utc)


def _json(raw: dict[str, Any]) -> str:
    import json

    return json.dumps(raw, ensure_ascii=False, default=str)
