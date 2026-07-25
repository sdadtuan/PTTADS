"""Zalo form lead poll worker (Wave Z2)."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from crm_lead_store import normalize_email, normalize_phone
from ptt_crm.lead_ingest_pg import ingest_legacy_item_pg, shadow_sync_created
from ptt_jobs.db import json_dumps, pg_connection
from ptt_zalo.ads_api import zalo_ads_stub_mode
from ptt_zalo.form_api import fetch_form_leads, form_lead_poll_enabled, normalize_form_lead_row
from ptt_zalo.token_vault import resolve_zalo_access_token

logger = logging.getLogger(__name__)


def pg_zalo_leads_ready() -> bool:
    try:
        from ptt_crm.pg_schema import pg_zalo_leads_ready as _ready

        return _ready()
    except Exception as exc:
        logger.debug("pg_zalo_leads_ready: %s", exc)
        return False


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _utc_ts() -> str:
    return _utc_now().replace(microsecond=0).isoformat()


def log_zalo_lead_event(
    *,
    lead_id: int | None,
    client_id: str | None,
    event_type: str,
    payload: dict[str, Any] | None = None,
) -> None:
    if not pg_zalo_leads_ready():
        return
    with pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO zalo_lead_events (lead_id, client_id, event_type, payload_json)
                VALUES (%s, %s::uuid, %s, %s::jsonb)
                """,
                [
                    lead_id,
                    client_id,
                    event_type[:32],
                    json_dumps(payload or {}),
                ],
            )
        conn.commit()


def find_phone_dedup_24h(*, client_id: str, phone: str) -> int | None:
    ph = normalize_phone(phone)
    if not ph or not client_id:
        return None
    with pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT sqlite_lead_id
                FROM crm_leads
                WHERE agency_client_id = %s::uuid
                  AND lower(COALESCE(channel, '')) = 'zalo'
                  AND COALESCE(is_duplicate, FALSE) IS NOT TRUE
                  AND created_at >= NOW() - INTERVAL '24 hours'
                  AND (
                    CASE
                      WHEN regexp_replace(phone, '[^0-9]', '', 'g') ~ '^84'
                      THEN '0' || substring(regexp_replace(phone, '[^0-9]', '', 'g') from 3)
                      ELSE regexp_replace(phone, '[^0-9]', '', 'g')
                    END
                  ) = %s
                ORDER BY created_at DESC
                LIMIT 1
                """,
                [client_id, ph],
            )
            row = cur.fetchone()
            return int(row[0]) if row else None


def get_cursor(*, client_id: str, oa_id: str, form_id: str) -> dict[str, Any] | None:
    with pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id::text, last_form_data_id, last_polled_at::text, last_status, last_error
                FROM zalo_lead_form_sync_cursor
                WHERE client_id = %s::uuid AND oa_id = %s AND form_id = %s
                LIMIT 1
                """,
                [client_id, oa_id, form_id],
            )
            row = cur.fetchone()
            if not row:
                return None
            cols = [d[0] for d in cur.description]
            return dict(zip(cols, row))


def upsert_cursor(
    *,
    client_id: str,
    oa_id: str,
    form_id: str,
    last_form_data_id: str | None,
    status: str,
    error: str | None = None,
) -> None:
    with pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO zalo_lead_form_sync_cursor (
                    client_id, oa_id, form_id, last_form_data_id, last_polled_at, last_status, last_error, updated_at
                ) VALUES (%s::uuid, %s, %s, %s, NOW(), %s, %s, NOW())
                ON CONFLICT (client_id, oa_id, form_id)
                DO UPDATE SET
                    last_form_data_id = COALESCE(EXCLUDED.last_form_data_id, zalo_lead_form_sync_cursor.last_form_data_id),
                    last_polled_at = NOW(),
                    last_status = EXCLUDED.last_status,
                    last_error = EXCLUDED.last_error,
                    updated_at = NOW()
                """,
                [client_id, oa_id, form_id, last_form_data_id, status[:16], error],
            )
        conn.commit()


def _parse_form_ids(meta: Any) -> list[str]:
    if isinstance(meta, str):
        try:
            meta = json.loads(meta)
        except json.JSONDecodeError:
            meta = {}
    if not isinstance(meta, dict):
        return []
    raw = meta.get("form_ids")
    if not isinstance(raw, list):
        return []
    return [str(x).strip() for x in raw if str(x).strip()]


def _load_poll_targets(*, client_id: str | None = None, form_id: str | None = None) -> list[dict[str, Any]]:
    from ptt_agency.clients import load_channel_account_for_sync

    rows = load_channel_account_for_sync(client_id, channel="zalo")
    out: list[dict[str, Any]] = []
    for row in rows:
        if str(row.get("status") or "") == "revoked":
            continue
        meta = row.get("meta") or {}
        form_ids = _parse_form_ids(meta)
        if not form_ids:
            continue
        oa_id = str(row.get("external_account_id") or meta.get("oa_id") or "").strip()
        if not oa_id:
            continue
        for fid in form_ids:
            if form_id and fid != form_id:
                continue
            out.append(
                {
                    "client_id": str(row["client_id"]),
                    "channel_account_id": str(row["id"]),
                    "oa_id": oa_id,
                    "form_id": fid,
                    "account": {
                        "id": str(row["id"]),
                        "client_id": str(row["client_id"]),
                        "external_account_id": oa_id,
                        "meta": meta,
                        "access_token_encrypted": row.get("access_token_encrypted"),
                        "credential_ref": row.get("credential_ref"),
                        "token_status": row.get("token_status"),
                    },
                }
            )
    return out


def form_row_to_legacy_item(row: dict[str, Any], *, client_id: str, form_id: str, oa_id: str) -> dict[str, Any]:
    form_data_id = str(row.get("form_data_id") or "").strip()
    return {
        "full_name": row.get("full_name") or row.get("phone") or row.get("email") or "Lead Zalo",
        "phone": row.get("phone") or "",
        "email": row.get("email") or "",
        "source": "zalo",
        "external_lead_id": form_data_id,
        "meta": {
            "zalo_lead_id": form_data_id,
            "form_id": form_id,
            "oa_id": oa_id,
            "agency_client_id": client_id,
            "ingest_channel": "zalo_form_poll",
            "form_data_id": form_data_id,
        },
    }


def ingest_form_lead(
    row: dict[str, Any],
    *,
    client_id: str,
    form_id: str,
    oa_id: str,
) -> dict[str, Any]:
    item = form_row_to_legacy_item(row, client_id=client_id, form_id=form_id, oa_id=oa_id)
    phone = str(item.get("phone") or "")
    email = str(item.get("email") or "")
    form_data_id = str(item.get("meta", {}).get("form_data_id") or "")

    log_zalo_lead_event(
        lead_id=None,
        client_id=client_id,
        event_type="received",
        payload={"form_id": form_id, "oa_id": oa_id, "form_data_id": form_data_id},
    )

    if not normalize_phone(phone) and not normalize_email(email):
        log_zalo_lead_event(
            lead_id=None,
            client_id=client_id,
            event_type="failed",
            payload={"reason": "missing_contact", "form_data_id": form_data_id},
        )
        return {"status": "skipped", "message": "Thiếu phone/email", "form_data_id": form_data_id}

    dup_id = find_phone_dedup_24h(client_id=client_id, phone=phone)
    if dup_id:
        log_zalo_lead_event(
            lead_id=dup_id,
            client_id=client_id,
            event_type="deduped",
            payload={"form_data_id": form_data_id, "matched_lead_id": dup_id, "rule": "BR-ZALO-02"},
        )
        return {
            "status": "duplicate",
            "lead_id": dup_id,
            "form_data_id": form_data_id,
            "message": "BR-ZALO-02 phone+client+24h",
        }

    out = ingest_legacy_item_pg(
        item,
        channel="zalo",
        client_id=client_id,
        default_source="zalo",
        ts=_utc_ts(),
    )
    lead_id = out.get("lead_id")
    if lead_id:
        shadow_sync_created([int(lead_id)])
        log_zalo_lead_event(
            lead_id=int(lead_id),
            client_id=client_id,
            event_type="pushed_crm",
            payload={"form_data_id": form_data_id, "ingest_status": out.get("status")},
        )
    elif out.get("status") == "duplicate_seen":
        log_zalo_lead_event(
            lead_id=int(out["lead_id"]) if out.get("lead_id") else None,
            client_id=client_id,
            event_type="deduped",
            payload={"form_data_id": form_data_id, "external_dedup": True},
        )
    else:
        log_zalo_lead_event(
            lead_id=None,
            client_id=client_id,
            event_type="failed",
            payload={"form_data_id": form_data_id, "result": out},
        )
    return out


def poll_form_once(
    target: dict[str, Any],
    *,
    force: bool = False,
) -> dict[str, Any]:
    client_id = target["client_id"]
    oa_id = target["oa_id"]
    form_id = target["form_id"]
    account = target["account"]

    cursor = get_cursor(client_id=client_id, oa_id=oa_id, form_id=form_id)
    after_id = None if force else (cursor.get("last_form_data_id") if cursor else None)

    token = resolve_zalo_access_token(account)
    if not token and not zalo_ads_stub_mode():
        upsert_cursor(
            client_id=client_id,
            oa_id=oa_id,
            form_id=form_id,
            last_form_data_id=cursor.get("last_form_data_id") if cursor else None,
            status="error",
            error="missing_token",
        )
        return {"ok": False, "error": "missing_token", "form_id": form_id}

    rows, err = fetch_form_leads(
        oa_id=oa_id,
        form_id=form_id,
        access_token=token or "",
        after_form_data_id=after_id,
    )
    if err:
        upsert_cursor(
            client_id=client_id,
            oa_id=oa_id,
            form_id=form_id,
            last_form_data_id=cursor.get("last_form_data_id") if cursor else None,
            status="error",
            error=err,
        )
        return {"ok": False, "error": err, "form_id": form_id}

    ingested = 0
    deduped = 0
    skipped = 0
    last_id = after_id
    for raw in rows:
        row = normalize_form_lead_row(raw, form_id=form_id, oa_id=oa_id)
        fid = str(row.get("form_data_id") or "").strip()
        if not fid:
            skipped += 1
            continue
        if after_id and fid <= after_id:
            continue
        result = ingest_form_lead(row, client_id=client_id, form_id=form_id, oa_id=oa_id)
        status = result.get("status")
        if status in {"created_assigned", "created_unassigned"}:
            ingested += 1
        elif status in {"duplicate", "duplicate_seen"}:
            deduped += 1
        else:
            skipped += 1
        last_id = fid

    if rows and last_id and last_id != after_id:
        upsert_cursor(
            client_id=client_id,
            oa_id=oa_id,
            form_id=form_id,
            last_form_data_id=last_id,
            status="ok",
            error=None,
        )
    elif not rows:
        upsert_cursor(
            client_id=client_id,
            oa_id=oa_id,
            form_id=form_id,
            last_form_data_id=after_id,
            status="ok",
            error=None,
        )

    return {
        "ok": True,
        "form_id": form_id,
        "oa_id": oa_id,
        "client_id": client_id,
        "fetched": len(rows),
        "ingested": ingested,
        "deduped": deduped,
        "skipped": skipped,
        "last_form_data_id": last_id,
    }


def poll_zalo_form_leads(
    *,
    client_id: str | None = None,
    form_id: str | None = None,
    oa_id: str | None = None,
    force: bool = False,
) -> dict[str, Any]:
    if not form_lead_poll_enabled() and not zalo_ads_stub_mode():
        return {"ok": False, "skipped": True, "reason": "form_poll_disabled"}
    if not pg_zalo_leads_ready():
        return {"ok": False, "error": "pg_zalo_leads_not_ready"}

    targets = _load_poll_targets(client_id=client_id, form_id=form_id)
    if oa_id:
        targets = [t for t in targets if t["oa_id"] == oa_id]
    if not targets:
        return {"ok": True, "skipped": True, "reason": "no_active_forms", "polled": 0}

    results: list[dict[str, Any]] = []
    failures = 0
    for target in targets:
        try:
            results.append(poll_form_once(target, force=force))
        except Exception as exc:
            failures += 1
            logger.exception("poll form failed client=%s form=%s: %s", target.get("client_id"), target.get("form_id"), exc)
            results.append({"ok": False, "error": str(exc), "form_id": target.get("form_id")})

    ok_count = sum(1 for r in results if r.get("ok"))
    return {
        "ok": failures == 0,
        "polled": len(results),
        "ok_count": ok_count,
        "failures": failures,
        "results": results,
    }
