"""B13 — Meta ops webhooks: account disabled + ad disapproved alerts."""
from __future__ import annotations

import logging
import os
from datetime import date, datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

OPS_ALERT_TYPES = frozenset({"meta_account_disabled", "ad_disapproved"})
ACCOUNT_DISABLED_FIELDS = frozenset({"account_update", "ad_account", "advertiser_account"})
AD_STATUS_FIELDS = frozenset({"ads", "ad", "with_issues_ad_objects"})
ACTIVE_ACCOUNT_STATUSES = frozenset({"active", "1", "enabled"})


def ops_webhooks_enabled() -> bool:
    return os.environ.get("PTT_META_OPS_WEBHOOKS", "0").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _today() -> date:
    return datetime.now(timezone.utc).date()


def dedupe_key(
    alert_type: str,
    client_id: str,
    external_campaign_id: str | None,
    performance_date: date | None = None,
) -> str:
    camp = (external_campaign_id or "").strip() or "_"
    day = (performance_date or _today()).isoformat()
    return f"{alert_type}:{client_id}:{camp}:{day}"


def is_account_disabled_status(status: Any) -> bool:
    if status is None:
        return False
    text = str(status).strip().lower()
    if not text:
        return False
    if text in ACTIVE_ACCOUNT_STATUSES:
        return False
    if text in {"disabled", "2", "disabled_account", "deactivated", "closed"}:
        return True
    return text not in ACTIVE_ACCOUNT_STATUSES and text.isdigit() and text != "1"


def is_ad_disapproved_status(status: Any) -> bool:
    return str(status or "").strip().upper() == "DISAPPROVED"


def normalize_ad_account_id(raw: Any) -> str:
    text = str(raw or "").strip()
    if not text:
        return ""
    digits = "".join(ch for ch in text if ch.isdigit())
    if text.startswith("act_"):
        return text
    if digits:
        return f"act_{digits}"
    return text


def parse_ops_webhook_changes(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract B13 ops events from a Meta webhook payload."""
    events: list[dict[str, Any]] = []
    entries = payload.get("entry")
    if not isinstance(entries, list):
        return events

    for entry in entries:
        if not isinstance(entry, dict):
            continue
        entry_id = entry.get("id")
        changes = entry.get("changes")
        if not isinstance(changes, list):
            continue
        for change in changes:
            if not isinstance(change, dict):
                continue
            field = str(change.get("field") or "").strip().lower()
            value = change.get("value")
            if not isinstance(value, dict):
                value = {}

            if field in ACCOUNT_DISABLED_FIELDS or (
                payload.get("object") == "ad_account" and field not in AD_STATUS_FIELDS
            ):
                account_id = normalize_ad_account_id(
                    value.get("account_id") or value.get("ad_account_id") or entry_id
                )
                status = value.get("account_status") or value.get("status") or value.get("event")
                if account_id and is_account_disabled_status(status):
                    events.append(
                        {
                            "event_type": "meta_account_disabled",
                            "external_account_id": account_id,
                            "external_ad_id": None,
                            "external_campaign_id": None,
                            "account_status": str(status),
                            "disable_reason": value.get("disable_reason") or value.get("reason"),
                            "field": field or "account_update",
                        }
                    )
                continue

            if field in AD_STATUS_FIELDS:
                ad_id = str(value.get("ad_id") or value.get("id") or "").strip()
                effective = value.get("effective_status") or value.get("status")
                if ad_id and is_ad_disapproved_status(effective):
                    events.append(
                        {
                            "event_type": "ad_disapproved",
                            "external_account_id": normalize_ad_account_id(
                                value.get("account_id") or value.get("ad_account_id") or entry_id
                            )
                            or None,
                            "external_ad_id": ad_id,
                            "external_campaign_id": str(
                                value.get("campaign_id") or value.get("external_campaign_id") or ""
                            ).strip()
                            or None,
                            "effective_status": str(effective),
                            "field": field,
                        }
                    )

    return events


def insert_ops_alert(
    *,
    client_id: str,
    alert_type: str,
    message: str,
    external_campaign_id: str | None = None,
    severity: str = "danger",
) -> dict[str, Any]:
    if alert_type not in OPS_ALERT_TYPES:
        return {"ok": False, "error": "invalid_alert_type"}

    try:
        from ptt_crm.pg_schema import pg_meta_alerts_ready
        from ptt_jobs.db import pg_available, pg_connection

        if not pg_available() or not pg_meta_alerts_ready():
            return {"ok": False, "error": "meta_alerts_not_ready"}
    except Exception as exc:
        logger.warning("insert_ops_alert pg check failed: %s", exc)
        return {"ok": False, "error": "meta_alerts_not_ready"}

    key = dedupe_key(alert_type, client_id, external_campaign_id)
    with pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO meta_alerts (
                    client_id, channel, external_campaign_id, alert_type, severity,
                    metric_value, threshold_value, message, performance_date, dedupe_key
                ) VALUES (
                    %s::uuid, 'meta', %s, %s, %s,
                    NULL, NULL, %s, %s, %s
                )
                ON CONFLICT (dedupe_key) DO NOTHING
                RETURNING id::text
                """,
                (
                    client_id,
                    external_campaign_id,
                    alert_type,
                    severity,
                    message,
                    _today(),
                    key,
                ),
            )
            row = cur.fetchone()
        conn.commit()

    if row:
        return {"ok": True, "created": True, "alert_id": str(row[0]), "dedupe_key": key}
    return {"ok": True, "created": False, "dedupe_key": key, "idempotent": True}


def process_ops_webhook_event(
    event: dict[str, Any],
    *,
    client_id: str,
    stub: bool = False,
) -> dict[str, Any]:
    alert_type = str(event.get("event_type") or "").strip()
    if alert_type == "meta_account_disabled":
        account_id = str(event.get("external_account_id") or "")
        reason = str(event.get("disable_reason") or "account_status_not_active")
        message = f"Meta ad account {account_id} disabled ({reason})"
        if stub or not ops_webhooks_enabled():
            return {
                "ok": True,
                "stub": True,
                "alert_type": alert_type,
                "client_id": client_id,
                "message": message,
            }
        return insert_ops_alert(
            client_id=client_id,
            alert_type=alert_type,
            message=message,
            external_campaign_id=None,
            severity="danger",
        )

    if alert_type == "ad_disapproved":
        ad_id = str(event.get("external_ad_id") or "")
        campaign_id = event.get("external_campaign_id")
        message = f"Meta ad {ad_id} disapproved — review creative/copy"
        if stub or not ops_webhooks_enabled():
            return {
                "ok": True,
                "stub": True,
                "alert_type": alert_type,
                "client_id": client_id,
                "message": message,
            }
        return insert_ops_alert(
            client_id=client_id,
            alert_type=alert_type,
            message=message,
            external_campaign_id=str(campaign_id) if campaign_id else ad_id,
            severity="warning",
        )

    return {"ok": False, "error": "unknown_event_type", "event_type": alert_type}


def process_ops_webhook_payload(
    payload: dict[str, Any],
    *,
    resolve_client_id,
    stub: bool = False,
) -> dict[str, Any]:
    """Process all ops events in a webhook payload.

    resolve_client_id: callable(external_account_id: str | None) -> str | None
    """
    if not stub and not ops_webhooks_enabled():
        return {"ok": True, "skipped": True, "reason": "PTT_META_OPS_WEBHOOKS=0"}

    events = parse_ops_webhook_changes(payload)
    results: list[dict[str, Any]] = []
    created = 0
    for event in events:
        client_id = resolve_client_id(event.get("external_account_id"))
        if not client_id:
            results.append({**event, "ok": False, "error": "client_not_resolved"})
            continue
        outcome = process_ops_webhook_event(event, client_id=client_id, stub=stub)
        if outcome.get("created"):
            created += 1
        results.append({**event, **outcome})

    return {
        "ok": True,
        "events": len(events),
        "created": created,
        "results": results,
    }
