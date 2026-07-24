"""Meta CAPI dispatch — Lead events async pilot (Phase 2 M5)."""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import sqlite3
from datetime import datetime, timezone
from typing import Any

from ptt_jobs.db import json_dumps, pg_connection
from ptt_meta.graph_capi import send_pixel_events
from ptt_meta.token_vault import resolve_meta_access_token

logger = logging.getLogger(__name__)

_CAPI_EVENT_LEAD = "Lead"
_CAPI_EVENT_PURCHASE = "Purchase"
_ACTION_SOURCE = "system_generated"


def _truthy(name: str, default: str = "0") -> bool:
    return os.environ.get(name, default).strip().lower() in {"1", "true", "yes", "on"}


def capi_dispatch_enabled() -> bool:
    return _truthy("PTT_CAPI_ENABLED", "0")


def capi_stub_mode() -> bool:
    return _truthy("PTT_CAPI_STUB", "0")


def capi_purchase_stub_enabled() -> bool:
    return _truthy("PTT_CAPI_PURCHASE_STUB", "0")


def capi_test_event_code() -> str:
    return (os.environ.get("PTT_CAPI_TEST_EVENT_CODE") or "").strip()


def pilot_client_ids() -> frozenset[str]:
    raw = (os.environ.get("PTT_CAPI_PILOT_CLIENTS") or "").strip()
    if not raw:
        return frozenset()
    return frozenset(x.strip().lower() for x in raw.split(",") if x.strip())


def pg_capi_ready() -> bool:
    try:
        from ptt_jobs.db import pg_available

        if not pg_available():
            return False
        with pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT COUNT(*) FROM information_schema.tables
                    WHERE table_schema = 'public' AND table_name = 'capi_event_log'
                    """
                )
                return int(cur.fetchone()[0] or 0) >= 1
    except Exception as exc:
        logger.debug("pg_capi_ready: %s", exc)
        return False


def client_allowed_for_capi(client_id: str | None) -> bool:
    if not client_id:
        return False
    pilots = pilot_client_ids()
    if not pilots:
        return True
    return str(client_id).strip().lower() in pilots


def _sha256_normalized(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def hash_email(raw: str | None) -> str | None:
    from crm_lead_store import normalize_email

    email = normalize_email(raw)
    if not email:
        return None
    return _sha256_normalized(email)


def hash_phone(raw: str | None) -> str | None:
    from crm_lead_store import normalize_phone

    phone = normalize_phone(raw)
    if not phone:
        return None
    digits = re.sub(r"\D", "", phone)
    if digits.startswith("0"):
        digits = "84" + digits[1:]
    elif not digits.startswith("84"):
        digits = "84" + digits.lstrip("0")
    if len(digits) < 8:
        return None
    return _sha256_normalized(digits)


def lead_event_id(*, lead_id: int, client_id: str, external_id: str = "") -> str:
    """B9 event_id — leadgen_* when Meta external id present, else legacy ptt-lead-*."""
    ext = str(external_id or "").strip()
    if ext and ext != str(lead_id):
        return f"leadgen_{ext}"
    return f"ptt-lead-{client_id}-{lead_id}"


def legacy_lead_event_ids(*, lead_id: int, client_id: str, external_id: str = "") -> list[str]:
    """Backward-compat dedupe keys for migrated Lead event_id format."""
    primary = lead_event_id(lead_id=lead_id, client_id=client_id, external_id=external_id)
    if primary.startswith("leadgen_"):
        return [f"ptt-lead-{client_id}-{lead_id}"]
    return []


def build_lead_event(
    *,
    lead_id: int,
    client_id: str,
    event_time: int | None = None,
    email: str = "",
    phone: str = "",
    external_id: str = "",
    event_source_url: str = "",
    custom_data: dict[str, Any] | None = None,
    event_id_override: str | None = None,
) -> dict[str, Any]:
    user_data: dict[str, Any] = {}
    em = hash_email(email)
    ph = hash_phone(phone)
    if em:
        user_data["em"] = [em]
    if ph:
        user_data["ph"] = [ph]
    ext = str(external_id or lead_id).strip()
    if ext:
        user_data["external_id"] = _sha256_normalized(ext)

    event_id = event_id_override or lead_event_id(
        lead_id=lead_id,
        client_id=client_id,
        external_id=str(external_id or ""),
    )

    evt: dict[str, Any] = {
        "event_name": _CAPI_EVENT_LEAD,
        "event_time": event_time or int(datetime.now(timezone.utc).timestamp()),
        "event_id": event_id,
        "action_source": _ACTION_SOURCE,
        "user_data": user_data,
    }
    if event_source_url.strip():
        evt["event_source_url"] = event_source_url.strip()
    if custom_data:
        evt["custom_data"] = custom_data
    return evt


def _parse_meta_json(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


def resolve_capi_config(client_id: str) -> dict[str, Any] | None:
    """Pixel + token from Meta channel account meta JSONB (US-M5-03)."""
    global_pixel = (os.environ.get("PTT_META_PIXEL_ID") or os.environ.get("META_PIXEL_ID") or "").strip()
    global_token = (os.environ.get("PTT_META_ACCESS_TOKEN") or os.environ.get("META_ACCESS_TOKEN") or "").strip()

    with pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, external_account_id, access_token_encrypted, credential_ref, meta
                FROM client_channel_accounts
                WHERE client_id = %s::uuid
                  AND channel = 'meta'
                  AND status = 'active'
                ORDER BY updated_at DESC
                LIMIT 1
                """,
                (client_id,),
            )
            row = cur.fetchone()

    if row:
        cols = ["id", "external_account_id", "access_token_encrypted", "credential_ref", "meta"]
        account = dict(zip(cols, row))
        meta = _parse_meta_json(account.get("meta"))
        pixel_id = str(meta.get("pixel_id") or meta.get("meta_pixel_id") or global_pixel).strip()
        try:
            from ptt_meta.meta_pixels import meta_pixels_enabled, resolve_primary_pixel_id

            if meta_pixels_enabled():
                primary = resolve_primary_pixel_id(str(account.get("id") or ""))
                if primary:
                    pixel_id = primary
        except Exception:
            pass
        token = resolve_meta_access_token(account) or global_token
        if pixel_id and token:
            return {
                "pixel_id": pixel_id,
                "access_token": token,
                "channel_account_id": str(account.get("id") or ""),
                "external_account_id": str(account.get("external_account_id") or ""),
            }

    if global_pixel and global_token:
        return {"pixel_id": global_pixel, "access_token": global_token}

    return None


def load_sqlite_lead(lead_id: int) -> dict[str, Any] | None:
    from ptt_jobs.config import sqlite_db_path

    conn = sqlite3.connect(sqlite_db_path())
    conn.row_factory = sqlite3.Row
    try:
        from crm_lead_store import fetch_lead_by_id

        row = fetch_lead_by_id(conn, lead_id)
        if not row:
            return None
        return dict(row)
    finally:
        conn.close()


def load_pg_lead(lead_id: int) -> dict[str, Any] | None:
    """Load lead from PG crm_leads (Nest write / shadow path)."""
    try:
        with pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT sqlite_lead_id, full_name, phone, email, status, source,
                           channel, external_lead_id, meta_json, agency_client_id::text,
                           campaign_id, updated_at
                    FROM crm_leads
                    WHERE sqlite_lead_id = %s
                    LIMIT 1
                    """,
                    (int(lead_id),),
                )
                row = cur.fetchone()
        if not row:
            return None
        meta = _parse_meta_json(row[8])
        return {
            "id": int(row[0]),
            "full_name": row[1] or "",
            "phone": row[2] or "",
            "email": row[3] or "",
            "status": row[4] or "",
            "source": row[5] or "",
            "channel": row[6] or "",
            "external_id": row[7] or "",
            "external_lead_id": row[7] or "",
            "agency_client_id": row[9] or "",
            "client_id": row[9] or "",
            "campaign_id": row[10] or "",
            "updated_at": row[11],
            "landing_url": meta.get("landing_url") or meta.get("source_url") or "",
            "meta_json": meta,
        }
    except Exception as exc:
        logger.debug("load_pg_lead %s: %s", lead_id, exc)
        return None


def load_lead_for_capi(lead_id: int) -> dict[str, Any] | None:
    """SQLite shadow first, then PG OLTP fallback."""
    lead = load_sqlite_lead(lead_id)
    if lead:
        return lead
    return load_pg_lead(lead_id)


def _payload_hash(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def find_capi_log(client_id: str, event_id: str, event_name: str) -> dict[str, Any] | None:
    with pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, status, error_message, sent_at, created_at
                FROM capi_event_log
                WHERE client_id = %s::uuid AND event_id = %s AND event_name = %s
                LIMIT 1
                """,
                (client_id, event_id, event_name),
            )
            row = cur.fetchone()
            if not row:
                return None
            cols = [d[0] for d in cur.description]
            out = dict(zip(cols, row))
            out["id"] = str(out["id"])
            return out


def find_capi_log_dedup(
    client_id: str,
    event_name: str,
    event_id: str,
    *,
    legacy_event_ids: list[str] | None = None,
) -> dict[str, Any] | None:
    """Resolve dedupe log row including legacy Lead event_id keys."""
    existing = find_capi_log(client_id, event_id, event_name)
    if existing:
        return existing
    for legacy_id in legacy_event_ids or []:
        existing = find_capi_log(client_id, legacy_id, event_name)
        if existing:
            return existing
    return None


def insert_capi_log(
    *,
    client_id: str,
    event_name: str,
    event_id: str,
    lead_id: int | None,
    pixel_id: str,
    payload_hash: str,
    status: str,
    meta_response: dict[str, Any] | None = None,
    error_message: str = "",
) -> str | None:
    with pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO capi_event_log (
                    client_id, event_name, event_id, lead_id, pixel_id,
                    payload_hash, status, meta_response, error_message, sent_at
                )
                VALUES (
                    %s::uuid, %s, %s, %s, %s,
                    %s, %s, %s::jsonb, %s,
                    CASE WHEN %s = 'sent' THEN NOW() ELSE NULL END
                )
                ON CONFLICT (client_id, event_id, event_name) DO NOTHING
                RETURNING id
                """,
                (
                    client_id,
                    event_name,
                    event_id,
                    lead_id,
                    pixel_id or None,
                    payload_hash,
                    status,
                    json_dumps(meta_response or {}),
                    error_message or None,
                    status,
                ),
            )
            row = cur.fetchone()
            conn.commit()
            return str(row[0]) if row else None


def update_capi_log(
    log_id: str,
    *,
    status: str,
    meta_response: dict[str, Any] | None = None,
    error_message: str = "",
) -> None:
    with pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE capi_event_log
                SET status = %s,
                    meta_response = COALESCE(%s::jsonb, meta_response),
                    error_message = COALESCE(%s, error_message),
                    sent_at = CASE WHEN %s = 'sent' THEN NOW() ELSE sent_at END
                WHERE id = %s::uuid
                """,
                (
                    status,
                    json_dumps(meta_response) if meta_response is not None else None,
                    error_message or None,
                    status,
                    log_id,
                ),
            )
            conn.commit()


def capi_stats(*, client_id: str | None = None, hours: int = 24) -> dict[str, Any]:
    """Observability summary — default 24h; pass hours=168 for 7d tracking health."""
    if not pg_capi_ready():
        return {"ok": False, "error": "capi_log_not_ready"}

    window_hours = max(1, min(int(hours), 24 * 90))
    clauses = ["created_at >= NOW() - (%s || ' hours')::interval"]
    params: list[Any] = [str(window_hours)]
    if client_id:
        clauses.append("client_id = %s::uuid")
        params.append(client_id)

    with pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT status, COUNT(*)::int
                FROM capi_event_log
                WHERE {' AND '.join(clauses)}
                GROUP BY status
                """,
                params,
            )
            by_status = {str(row[0]): int(row[1]) for row in cur.fetchall()}
            cur.execute(
                f"""
                SELECT AVG(EXTRACT(EPOCH FROM (sent_at - created_at)) * 1000)::float AS avg_ms
                FROM capi_event_log
                WHERE status = 'sent'
                  AND sent_at IS NOT NULL
                  AND {' AND '.join(clauses)}
                """,
                params,
            )
            avg_row = cur.fetchone()
            avg_latency_ms = avg_row[0] if avg_row else None

    total = sum(by_status.values())
    sent = by_status.get("sent", 0)
    failed = by_status.get("failed", 0)
    skipped = by_status.get("skipped", 0)
    pending = by_status.get("pending", 0)
    attempted = sent + failed
    error_rate = round(failed / attempted * 100, 2) if attempted else 0.0
    window_days = round(window_hours / 24, 2) if window_hours >= 24 else None

    return {
        "ok": True,
        "hours": window_hours,
        "window_days": window_days,
        "total": total,
        "by_status": by_status,
        "sent": sent,
        "failed": failed,
        "skipped": skipped,
        "pending": pending,
        "attempted": attempted,
        "error_rate_pct": error_rate,
        "fail_rate_pct": error_rate,
        "match_rate_pct": round(sent / attempted * 100, 2) if attempted else None,
        "match_hint_pct": round(sent / attempted * 100, 2) if attempted else None,
        "avg_latency_ms": round(float(avg_latency_ms), 2)
        if avg_latency_ms is not None and float(avg_latency_ms) >= 0
        else None,
    }


def _dispatch_capi_event(
    *,
    client_id: str,
    event: dict[str, Any],
    lead_id: int | None = None,
    correlation_id: str | None = None,
    legacy_event_ids: list[str] | None = None,
) -> dict[str, Any]:
    """Shared CAPI send path for Lead + conversion events."""
    if not capi_dispatch_enabled() and not capi_stub_mode():
        return {"ok": True, "skipped": True, "reason": "PTT_CAPI_ENABLED disabled"}

    if not pg_capi_ready():
        return {"ok": False, "error": "capi_log_not_ready"}

    if not client_allowed_for_capi(client_id):
        return {"ok": True, "skipped": True, "reason": "client_not_in_pilot"}

    config = resolve_capi_config(client_id)
    if not config:
        return {"ok": True, "skipped": True, "reason": "missing_pixel_or_token"}

    event_name = str(event.get("event_name") or "").strip()
    if not event_name:
        return {"ok": False, "error": "event_name required"}

    event_id = str(event.get("event_id") or "").strip()
    if not event_id:
        return {"ok": False, "error": "event_id required"}

    payload = dict(event)
    if correlation_id and isinstance(payload.get("custom_data"), dict):
        payload["custom_data"] = {**payload["custom_data"], "correlation_id": correlation_id}
    elif correlation_id:
        payload["custom_data"] = {"correlation_id": correlation_id}

    payload_hash = _payload_hash(payload)

    existing = find_capi_log_dedup(
        client_id,
        event_name,
        event_id,
        legacy_event_ids=legacy_event_ids,
    )
    if existing and existing.get("status") == "sent":
        return {
            "ok": True,
            "skipped": True,
            "reason": "dedup",
            "event_id": event_id,
            "event_name": event_name,
            "log_status": existing.get("status"),
        }

    log_id: str | None = None
    if existing and existing.get("status") in {"failed", "pending", "skipped"}:
        log_id = str(existing.get("id") or "")
    else:
        log_id = insert_capi_log(
            client_id=client_id,
            event_name=event_name,
            event_id=event_id,
            lead_id=lead_id,
            pixel_id=str(config["pixel_id"]),
            payload_hash=payload_hash,
            status="pending",
        )
        if not log_id:
            existing = find_capi_log_dedup(
                client_id,
                event_name,
                event_id,
                legacy_event_ids=legacy_event_ids,
            )
            if existing and existing.get("status") == "sent":
                return {
                    "ok": True,
                    "skipped": True,
                    "reason": "dedup_race",
                    "event_id": event_id,
                    "event_name": event_name,
                    "log_status": existing.get("status"),
                }
            log_id = str((existing or {}).get("id") or "")

    if not log_id:
        return {"ok": False, "error": "capi_log_unavailable", "event_id": event_id}

    if capi_stub_mode():
        stub_resp = {
            "events_received": 1,
            "stub": True,
            "pixel_id": config["pixel_id"],
            "event_name": event_name,
        }
        update_capi_log(log_id, status="sent", meta_response=stub_resp)
        return {
            "ok": True,
            "stub": True,
            "event_id": event_id,
            "event_name": event_name,
            "log_id": log_id,
            "events_received": 1,
        }

    outcome = send_pixel_events(
        pixel_id=str(config["pixel_id"]),
        access_token=str(config["access_token"]),
        events=[payload],
        test_event_code=capi_test_event_code(),
    )
    err = outcome.get("_graph_error")
    if err:
        update_capi_log(
            log_id,
            status="failed",
            meta_response=outcome.get("_graph_response") or {"error": err},
            error_message=str(err),
        )
        logger.warning(
            "capi dispatch failed client_id=%s event_name=%s event_id=%s err=%s",
            client_id,
            event_name,
            event_id,
            err,
        )
        return {
            "ok": False,
            "error": str(err),
            "event_id": event_id,
            "event_name": event_name,
            "log_id": log_id,
        }

    update_capi_log(log_id, status="sent", meta_response=outcome)
    events_received = outcome.get("events_received")
    logger.info(
        "capi dispatch sent client_id=%s event_name=%s event_id=%s received=%s",
        client_id,
        event_name,
        event_id,
        events_received,
    )
    return {
        "ok": True,
        "event_id": event_id,
        "event_name": event_name,
        "log_id": log_id,
        "events_received": events_received,
        "fbtrace_id": outcome.get("fbtrace_id"),
    }


def dispatch_conversion_capi(
    *,
    client_id: str,
    event: dict[str, Any],
    lead_id: int | None = None,
    correlation_id: str | None = None,
) -> dict[str, Any]:
    """Send arbitrary Meta CAPI event (B9 conversion rules pipeline)."""
    return _dispatch_capi_event(
        client_id=client_id,
        event=event,
        lead_id=lead_id,
        correlation_id=correlation_id,
    )


def dispatch_conversion_intent(intent: dict[str, Any]) -> dict[str, Any]:
    """Bridge from ptt_meta.conversion_rules evaluate output."""
    if intent.get("skipped"):
        return {
            "ok": True,
            "skipped": True,
            "reason": intent.get("reason") or "intent_skipped",
            "event_name": intent.get("event_name"),
        }
    event = intent.get("event")
    if not isinstance(event, dict):
        return {"ok": False, "error": "intent_missing_event"}
    return dispatch_conversion_capi(
        client_id=str(intent.get("client_id") or ""),
        event=event,
        lead_id=int(intent["lead_id"]) if intent.get("lead_id") is not None else None,
    )


def dispatch_lead_capi(
    *,
    lead_id: int,
    client_id: str,
    external_lead_id: str | None = None,
    correlation_id: str | None = None,
) -> dict[str, Any]:
    """
    Send Lead event to Meta CAPI. Non-blocking caller; logs to capi_event_log.
    """
    lead = load_lead_for_capi(lead_id)
    if not lead:
        return {"ok": False, "error": "lead_not_found", "lead_id": lead_id}

    external = str(external_lead_id or lead.get("external_id") or lead.get("external_lead_id") or "")
    event = build_lead_event(
        lead_id=lead_id,
        client_id=client_id,
        email=str(lead.get("email") or ""),
        phone=str(lead.get("phone") or ""),
        external_id=external or str(lead_id),
        event_source_url=str(lead.get("landing_url") or lead.get("source_url") or ""),
        custom_data={
            "lead_id": lead_id,
            "client_id": client_id,
            "correlation_id": correlation_id,
        },
    )
    return _dispatch_capi_event(
        client_id=client_id,
        event=event,
        lead_id=lead_id,
        correlation_id=correlation_id,
        legacy_event_ids=legacy_lead_event_ids(
            lead_id=lead_id,
            client_id=client_id,
            external_id=external,
        ),
    )


def build_purchase_event(
    *,
    lead_id: int,
    client_id: str,
    value: float = 0.0,
    currency: str = "VND",
    event_time: int | None = None,
) -> dict[str, Any]:
    """Purchase CAPI stub — optional pilot (PTT_CAPI_PURCHASE_STUB=1)."""
    return {
        "event_name": _CAPI_EVENT_PURCHASE,
        "event_time": event_time or int(datetime.now(timezone.utc).timestamp()),
        "event_id": f"ptt-purchase-{client_id}-{lead_id}",
        "action_source": _ACTION_SOURCE,
        "user_data": {"external_id": [_sha256_normalized(str(lead_id))]},
        "custom_data": {
            "value": round(float(value or 0), 2),
            "currency": currency or "VND",
            "lead_id": lead_id,
            "client_id": client_id,
            "stub": True,
        },
    }


def dispatch_purchase_capi_stub(
    *,
    lead_id: int,
    client_id: str,
    value: float = 0.0,
    currency: str = "VND",
) -> dict[str, Any]:
    """Log-only Purchase stub — does not call Graph unless stub mode sends."""
    if not capi_purchase_stub_enabled():
        return {"ok": True, "skipped": True, "reason": "PTT_CAPI_PURCHASE_STUB disabled"}
    if not pg_capi_ready():
        return {"ok": False, "error": "capi_log_not_ready"}
    config = resolve_capi_config(client_id)
    if not config:
        return {"ok": True, "skipped": True, "reason": "missing_pixel_or_token"}
    event = build_purchase_event(
        lead_id=lead_id,
        client_id=client_id,
        value=value,
        currency=currency,
    )
    event_id = str(event["event_id"])
    log_id = insert_capi_log(
        client_id=client_id,
        event_name=_CAPI_EVENT_PURCHASE,
        event_id=event_id,
        lead_id=lead_id,
        pixel_id=str(config["pixel_id"]),
        payload_hash=_payload_hash(event),
        status="skipped" if not capi_stub_mode() else "sent",
    )
    if capi_stub_mode():
        update_capi_log(log_id or "", status="sent", meta_response={"stub": True, "purchase": True})
    return {"ok": True, "stub": True, "event_id": event_id, "log_id": log_id}


def get_capi_log_row(log_id: str) -> dict[str, Any] | None:
    """Load a single capi_event_log row for replay/retry."""
    if not pg_capi_ready():
        return None
    text = str(log_id or "").strip()
    if not text:
        return None
    with pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id::text, client_id::text, event_name, event_id,
                       lead_id, status, error_message
                FROM capi_event_log
                WHERE id = $1::uuid
                """,
                [text],
            )
            row = cur.fetchone()
            if not row:
                return None
            cols = [d[0] for d in cur.description]
            return dict(zip(cols, row))


def list_flushable_capi_logs(
    *,
    client_id: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Rows eligible for manual flush/retry (pending or failed)."""
    if not pg_capi_ready():
        return []
    max_rows = max(1, min(int(limit), 200))
    values: list[Any] = [max_rows]
    client_clause = ""
    if client_id:
        client_clause = " AND client_id = $2::uuid"
        values.append(client_id)
    with pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT id::text, client_id::text, event_name, event_id,
                       lead_id, status, error_message
                FROM capi_event_log
                WHERE status IN ('pending', 'failed')
                {client_clause}
                ORDER BY created_at ASC
                LIMIT $1
                """,
                values,
            )
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]


def replay_capi_event_from_log(row: dict[str, Any]) -> dict[str, Any] | None:
    """Rebuild CAPI payload for retry using stored log row metadata."""
    event_name = str(row.get("event_name") or "").strip()
    event_id = str(row.get("event_id") or "").strip()
    client_id = str(row.get("client_id") or "").strip()
    lead_raw = row.get("lead_id")
    lead_id = int(lead_raw) if lead_raw is not None else None
    if not event_name or not event_id or not client_id:
        return None

    if event_name == _CAPI_EVENT_LEAD:
        if not lead_id:
            return None
        lead = load_lead_for_capi(lead_id)
        if not lead:
            return None
        external = str(lead.get("external_id") or lead.get("external_lead_id") or "")
        event = build_lead_event(
            lead_id=lead_id,
            client_id=client_id,
            email=str(lead.get("email") or ""),
            phone=str(lead.get("phone") or ""),
            external_id=external or str(lead_id),
            event_source_url=str(lead.get("landing_url") or lead.get("source_url") or ""),
            custom_data={"lead_id": lead_id, "client_id": client_id, "replay": True},
            event_id_override=event_id,
        )
        return event

    if not lead_id:
        return None
    lead = load_lead_for_capi(lead_id)
    if not lead:
        return None
    try:
        from ptt_meta.conversion_rules import build_conversion_event, normalize_lead

        norm = normalize_lead({**lead, "agency_client_id": client_id})
        rule = {
            "id": "replay",
            "client_id": None,
            "lead_status": norm.get("status") or "",
            "event_name": event_name,
            "enabled": True,
            "require_meta_attribution": False,
            "value_vnd": 0,
            "notes": "replay",
        }
        event = build_conversion_event(norm, rule)
        event["event_id"] = event_id
        return event
    except Exception as exc:
        logger.debug("replay_capi_event_from_log failed id=%s: %s", row.get("id"), exc)
        return None


def flush_pending_capi(
    *,
    client_id: str | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    """Retry pending/failed capi_event_log rows (B9 manual flush / cron drain)."""
    if not capi_dispatch_enabled() and not capi_stub_mode():
        return {"ok": True, "skipped": True, "reason": "PTT_CAPI_ENABLED disabled", "processed": 0}

    rows = list_flushable_capi_logs(client_id=client_id, limit=limit)
    results: list[dict[str, Any]] = []
    sent = 0
    skipped = 0
    failed = 0

    for row in rows:
        event = replay_capi_event_from_log(row)
        if not event:
            skipped += 1
            results.append(
                {
                    "log_id": row.get("id"),
                    "ok": True,
                    "skipped": True,
                    "reason": "replay_unavailable",
                }
            )
            continue
        legacy = None
        if str(event.get("event_name")) == _CAPI_EVENT_LEAD and row.get("lead_id"):
            external = ""
            lead = load_lead_for_capi(int(row["lead_id"]))
            if lead:
                external = str(lead.get("external_id") or lead.get("external_lead_id") or "")
            legacy = legacy_lead_event_ids(
                lead_id=int(row["lead_id"]),
                client_id=str(row.get("client_id") or ""),
                external_id=external,
            )
        out = _dispatch_capi_event(
            client_id=str(row.get("client_id") or ""),
            event=event,
            lead_id=int(row["lead_id"]) if row.get("lead_id") is not None else None,
            legacy_event_ids=legacy,
        )
        out["log_id"] = row.get("id")
        results.append(out)
        if out.get("ok") and not out.get("skipped"):
            sent += 1
        elif out.get("skipped"):
            skipped += 1
        else:
            failed += 1

    return {
        "ok": True,
        "processed": len(results),
        "sent": sent,
        "skipped": skipped,
        "failed": failed,
        "results": results,
    }


def enqueue_capi_lead_dispatch(
    *,
    lead_id: int,
    client_id: str,
    external_lead_id: str | None = None,
    correlation_id: str | None = None,
) -> dict[str, Any] | None:
    """Enqueue async capi_dispatch job — never raises."""
    if not capi_dispatch_enabled() and not capi_stub_mode():
        return None
    if not client_id or not client_allowed_for_capi(client_id):
        return None
    try:
        from ptt_jobs.enqueue import enqueue_job

        idem = f"capi:lead:{client_id}:{lead_id}"
        return enqueue_job(
            "capi_dispatch",
            {
                "lead_id": lead_id,
                "client_id": client_id,
                "external_lead_id": external_lead_id,
                "correlation_id": correlation_id,
            },
            idem,
            correlation_id=correlation_id,
            client_id=client_id,
        )
    except Exception as exc:
        logger.debug("capi enqueue skipped lead_id=%s: %s", lead_id, exc)
        return None


def process_capi_dispatch_payload(payload: dict[str, Any]) -> dict[str, Any]:
    client_id = str(payload.get("client_id") or "").strip()
    correlation_id = str(payload.get("correlation_id") or "") or None

    capi_log_id = str(payload.get("capi_log_id") or "").strip()
    if capi_log_id:
        row = get_capi_log_row(capi_log_id)
        if not row:
            return {"ok": False, "error": "capi_log_not_found", "capi_log_id": capi_log_id}
        event = replay_capi_event_from_log(row)
        if not event:
            return {
                "ok": True,
                "skipped": True,
                "reason": "replay_unavailable",
                "capi_log_id": capi_log_id,
            }
        legacy = None
        if str(event.get("event_name")) == _CAPI_EVENT_LEAD and row.get("lead_id"):
            external = ""
            lead = load_lead_for_capi(int(row["lead_id"]))
            if lead:
                external = str(lead.get("external_id") or lead.get("external_lead_id") or "")
            legacy = legacy_lead_event_ids(
                lead_id=int(row["lead_id"]),
                client_id=str(row.get("client_id") or ""),
                external_id=external,
            )
        return _dispatch_capi_event(
            client_id=str(row.get("client_id") or client_id),
            event=event,
            lead_id=int(row["lead_id"]) if row.get("lead_id") is not None else None,
            correlation_id=correlation_id,
            legacy_event_ids=legacy,
        )

    event = payload.get("event")
    if isinstance(event, dict) and client_id:
        lead_id_raw = payload.get("lead_id")
        lead_id = int(lead_id_raw) if lead_id_raw is not None else None
        return dispatch_conversion_capi(
            client_id=client_id,
            event=event,
            lead_id=lead_id,
            correlation_id=correlation_id,
        )

    intent = payload.get("conversion_intent")
    if isinstance(intent, dict):
        return dispatch_conversion_intent(intent)

    lead_id = int(payload.get("lead_id") or 0)
    if not lead_id or not client_id:
        return {"ok": False, "error": "lead_id and client_id required"}
    return dispatch_lead_capi(
        lead_id=lead_id,
        client_id=client_id,
        external_lead_id=str(payload.get("external_lead_id") or "") or None,
        correlation_id=correlation_id,
    )
