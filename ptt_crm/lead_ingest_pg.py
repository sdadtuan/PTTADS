"""PostgreSQL-primary lead ingest for worker (Phase 2 — no SQLite OLTP commit)."""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from typing import Any

from crm_lead_store import normalize_email, normalize_phone
from ptt_crm.lead_sync import _normalize_uuid, _parse_meta, _parse_ts, upsert_pg_lead
from ptt_jobs.db import json_dumps, pg_available, pg_connection

logger = logging.getLogger(__name__)

_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.I,
)


def _utc_ts() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _default_source(channel: str) -> str:
    ch = (channel or "").lower()
    if ch in {"meta", "facebook"}:
        return "facebook"
    return ch or "webhook"


def _external_lead_id(item: dict[str, Any], channel: str) -> str | None:
    meta = item.get("meta") if isinstance(item.get("meta"), dict) else {}
    ch = (channel or "").lower()
    if ch in {"meta", "facebook"}:
        ext = str(meta.get("facebook_leadgen_id") or item.get("external_lead_id") or "").strip()
        return ext or None
    if ch == "zalo":
        ext = str(meta.get("zalo_lead_id") or item.get("external_lead_id") or "").strip()
        return ext or None
    ext = str(item.get("external_lead_id") or meta.get("external_lead_id") or "").strip()
    return ext or None


def _parse_pg_meta(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return dict(raw)
    try:
        meta = json.loads(raw or "{}")
    except (json.JSONDecodeError, TypeError):
        meta = {}
    return meta if isinstance(meta, dict) else {}


def _pg_phone_norm_expr(column: str = "phone") -> str:
    return f"""
        CASE
            WHEN regexp_replace({column}, '[^0-9]', '', 'g') ~ '^84'
            THEN '0' || substring(regexp_replace({column}, '[^0-9]', '', 'g') from 3)
            ELSE regexp_replace({column}, '[^0-9]', '', 'g')
        END
    """


def fetch_pg_lead_by_id(lead_id: int) -> dict[str, Any] | None:
    with pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT sqlite_lead_id, full_name, phone, email, status, source,
                       owner_id, is_duplicate, meta_json, agency_client_id,
                       channel, external_lead_id, campaign_id, received_at, created_at
                FROM crm_leads
                WHERE sqlite_lead_id = %s
                LIMIT 1
                """,
                (int(lead_id),),
            )
            row = cur.fetchone()
            if not row:
                return None
            cols = [d[0] for d in cur.description]
            return dict(zip(cols, row))


def find_pg_contact_duplicates(
    *,
    phone: str = "",
    email: str = "",
    exclude_id: int | None = None,
) -> list[dict[str, Any]]:
    ph = normalize_phone(phone)
    em = normalize_email(email)
    if not ph and not em:
        return []
    clauses = ["COALESCE(is_duplicate, FALSE) IS NOT TRUE"]
    params: list[Any] = []
    sub: list[str] = []
    if ph:
        sub.append(f"{_pg_phone_norm_expr()} = %s")
        params.append(ph)
    if em:
        sub.append("lower(trim(email)) = %s")
        params.append(em)
    clauses.append("(" + " OR ".join(sub) + ")")
    if exclude_id:
        clauses.append("sqlite_lead_id <> %s")
        params.append(int(exclude_id))
    with pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT sqlite_lead_id, full_name, phone, email, owner_id, is_duplicate, meta_json
                FROM crm_leads
                WHERE {' AND '.join(clauses)}
                ORDER BY sqlite_lead_id ASC
                LIMIT 5
                """,
                params,
            )
            rows = cur.fetchall()
            cols = [d[0] for d in cur.description]
            out: list[dict[str, Any]] = []
            for row in rows:
                rec = dict(zip(cols, row))
                rec["lead_id"] = int(rec["sqlite_lead_id"])
                out.append(rec)
            return out


def update_pg_lead_fields(
    lead_id: int,
    *,
    full_name: str | None = None,
    phone: str | None = None,
    email: str | None = None,
    status: str | None = None,
    owner_id: int | None = None,
    is_duplicate: bool | None = None,
    meta_json: dict[str, Any] | None = None,
    updated_by: str = "worker",
) -> None:
    sets: list[str] = ["synced_at = NOW()", "sync_version = crm_leads.sync_version + 1"]
    params: list[Any] = []
    if full_name is not None:
        sets.append("full_name = %s")
        params.append(full_name[:500])
    if phone is not None:
        sets.append("phone = %s")
        params.append(phone[:64])
    if email is not None:
        sets.append("email = %s")
        params.append(email[:240])
    if status is not None:
        sets.append("status = %s")
        params.append(status[:64])
    if owner_id is not None:
        sets.append("owner_id = %s")
        params.append(owner_id)
    if is_duplicate is not None:
        sets.append("is_duplicate = %s")
        params.append(bool(is_duplicate))
    if meta_json is not None:
        sets.append("meta_json = %s::jsonb")
        params.append(json_dumps(meta_json))
    sets.append("write_source = %s")
    params.append("worker")
    sets.append("updated_at = NOW()")
    sets.append("updated_by = %s")
    params.append(str(updated_by or "worker")[:120])
    params.append(int(lead_id))
    with pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                UPDATE crm_leads SET {', '.join(sets)}
                WHERE sqlite_lead_id = %s
                """,
                params,
            )
        conn.commit()


def find_pg_lead_by_external(
    *,
    agency_client_id: str | None,
    channel: str,
    external_lead_id: str,
) -> int | None:
    if not external_lead_id:
        return None
    clauses = ["external_lead_id = %s", "COALESCE(is_duplicate, FALSE) IS NOT TRUE"]
    params: list[Any] = [external_lead_id]
    if agency_client_id:
        clauses.append("agency_client_id = %s::uuid")
        params.append(agency_client_id)
    if channel:
        clauses.append("lower(COALESCE(channel, '')) = %s")
        params.append(channel.strip().lower())
    with pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT sqlite_lead_id FROM crm_leads
                WHERE {' AND '.join(clauses)}
                ORDER BY created_at DESC
                LIMIT 1
                """,
                params,
            )
            row = cur.fetchone()
            return int(row[0]) if row else None


def next_prod_lead_id(cur) -> int:
    cur.execute("SELECT nextval('crm_leads_prod_id_seq') AS next_id")
    row = cur.fetchone()
    lead_id = int(row[0] if row else 0)
    if lead_id <= 0 or lead_id >= 900_000_000:
        raise RuntimeError("prod_id_allocator_unavailable")
    return lead_id


def legacy_item_to_pg_record(
    item: dict[str, Any],
    *,
    lead_id: int,
    channel: str,
    client_id: str | None,
    default_source: str,
    ts: str,
) -> dict[str, Any]:
    meta = dict(item.get("meta") if isinstance(item.get("meta"), dict) else {})
    if client_id:
        meta.setdefault("agency_client_id", client_id)
    name = str(item.get("full_name") or "").strip() or str(item.get("phone") or item.get("email") or "Lead")
    phone = str(item.get("phone") or "").strip()
    email = str(item.get("email") or "").strip()
    ext = _external_lead_id(item, channel)
    campaign_id = str(item.get("campaign_id") or meta.get("campaign_id") or "").strip() or None
    parsed_ts = _parse_ts(ts) or _parse_ts(_utc_ts())
    return {
        "sqlite_lead_id": lead_id,
        "full_name": name[:500],
        "phone": phone[:64],
        "email": email[:240],
        "status": str(item.get("status") or "new")[:64],
        "source": str(item.get("source") or default_source)[:64],
        "owner_id": int(item["owner_id"]) if item.get("owner_id") not in (None, "") else None,
        "is_duplicate": False,
        "meta_json": json_dumps(meta),
        "agency_client_id": _normalize_uuid(client_id),
        "channel": (channel or meta.get("channel") or "")[:32],
        "external_lead_id": ext,
        "campaign_id": campaign_id,
        "received_at": parsed_ts,
        "created_at": parsed_ts,
    }


def insert_pg_lead_record(record: dict[str, Any]) -> None:
    upsert_pg_lead(record, write_source="worker")


def ingest_legacy_item_pg(
    item: dict[str, Any],
    *,
    channel: str,
    client_id: str | None,
    default_source: str,
    ts: str,
) -> dict[str, Any]:
    """Insert one lead into PG; return status dict compatible with webhook processors."""
    ext = _external_lead_id(item, channel)
    agency_uuid = _normalize_uuid(client_id)
    if ext:
        existing = find_pg_lead_by_external(
            agency_client_id=agency_uuid,
            channel=channel,
            external_lead_id=ext,
        )
        if existing:
            return {
                "status": "duplicate_seen",
                "lead_id": existing,
                "message": f"Lead external {ext} đã tồn tại (PG #{existing})",
            }

    name = str(item.get("full_name") or "").strip()
    phone = str(item.get("phone") or "").strip()
    email = str(item.get("email") or "").strip()
    if not name:
        name = phone or email or "Lead webhook"
    if not normalize_phone(phone) and not normalize_email(email):
        if not ext:
            return {"status": "skipped", "message": "Thiếu phone/email", "full_name": name}

    with pg_connection() as conn:
        with conn.cursor() as cur:
            lead_id = next_prod_lead_id(cur)
    record = legacy_item_to_pg_record(
        item,
        lead_id=lead_id,
        channel=channel,
        client_id=client_id,
        default_source=default_source,
        ts=ts,
    )
    insert_pg_lead_record(record)
    status = "created_unassigned" if record.get("owner_id") is None else "created_assigned"
    return {
        "status": status,
        "lead_id": lead_id,
        "full_name": record["full_name"],
        "external_lead_id": ext,
    }


def ingest_webhook_leads_pg(
    items: list[dict[str, Any]],
    *,
    channel: str,
    client_id: str | None,
    default_source: str,
    created_by: str,
    ts: str,
    webhook_slug: str | None = None,
) -> dict[str, Any]:
    """PG-primary ingest — mirrors ingest_webhook_leads result shape."""
    source = default_source or _default_source(channel)
    results: list[dict[str, Any]] = []
    for raw in items:
        item = dict(raw)
        if webhook_slug:
            meta = item.setdefault("meta", {})
            if isinstance(meta, dict):
                meta.setdefault("webhook_slug", webhook_slug)
        if client_id and client_id not in {"", "unknown"}:
            meta = item.setdefault("meta", {})
            if isinstance(meta, dict):
                meta.setdefault("agency_client_id", client_id)
        try:
            if source == "facebook":
                from ptt_crm.facebook_ingest_pg import process_facebook_lead_item_pg

                out = process_facebook_lead_item_pg(
                    item,
                    channel=channel,
                    client_id=client_id,
                    created_by=created_by,
                    ts=ts,
                    webhook_slug=webhook_slug,
                )
            else:
                out = ingest_legacy_item_pg(
                    item,
                    channel=channel,
                    client_id=client_id,
                    default_source=source,
                    ts=ts,
                )
            results.append(out)
        except Exception as exc:
            logger.exception("pg ingest item failed: %s", exc)
            results.append({"status": "error", "message": str(exc), "item": item.get("full_name")})

    created_statuses = {"created_assigned", "created_unassigned", "duplicate_linked"}
    if source == "facebook":
        created_statuses = {"created_assigned", "created_unassigned"}
    created = [r for r in results if r.get("status") in created_statuses]
    return {
        "created_ids": [int(r["lead_id"]) for r in created if r.get("lead_id")],
        "created_count": len(created),
        "skipped": [r for r in results if r.get("status") not in created_statuses],
        "results": results,
    }


def shadow_sync_created(lead_ids: list[int]) -> None:
    if not lead_ids:
        return
    from ptt_crm.config import lead_shadow_sync_enabled

    if not lead_shadow_sync_enabled():
        return
    try:
        from ptt_crm.lead_shadow_sync import sync_shadow_lead_ids

        sync_shadow_lead_ids(lead_ids)
    except Exception as exc:
        logger.warning("shadow sync after pg ingest: %s", exc)


def process_ingest_lead_payload_pg(
    payload: dict[str, Any],
    *,
    correlation_id: str | None = None,
) -> dict[str, Any]:
    if not pg_available():
        return {"ok": False, "error": "pg_unavailable_for_primary_write"}

    lead_dict = payload.get("lead") if isinstance(payload.get("lead"), dict) else payload
    channel = str(payload.get("channel") or lead_dict.get("channel") or "meta")
    client_id = str(payload.get("client_id") or lead_dict.get("client_id") or "").strip()
    client_id_norm = client_id if client_id not in {"", "unknown"} else None

    from ptt_channel.mappers import normalized_lead_to_legacy

    legacy_item = normalized_lead_to_legacy(lead_dict)
    if client_id_norm:
        meta = legacy_item.setdefault("meta", {})
        if isinstance(meta, dict):
            meta["agency_client_id"] = client_id_norm

    source = _default_source(channel)
    ts = _utc_ts()

    result = ingest_webhook_leads_pg(
        [legacy_item],
        channel=channel,
        client_id=client_id_norm,
        default_source=source,
        created_by="ptt_worker",
        ts=ts,
        webhook_slug=f"v1_{channel}",
    )

    created_ids = list(result.get("created_ids") or [])
    shadow_sync_created(created_ids)

    from ptt_jobs.events import emit_domain_event

    for lead_id in created_ids:
        emit_domain_event(
            "LeadCreated",
            "lead",
            str(lead_id),
            {
                "lead_id": lead_id,
                "channel": channel,
                "client_id": client_id_norm,
                "external_lead_id": lead_dict.get("external_lead_id"),
                "write_path": "pg_primary",
            },
            correlation_id=correlation_id,
        )
        if client_id_norm:
            try:
                from ptt_meta.capi_dispatch import enqueue_capi_lead_dispatch

                enqueue_capi_lead_dispatch(
                    lead_id=int(lead_id),
                    client_id=client_id_norm,
                    external_lead_id=str(lead_dict.get("external_lead_id") or "") or None,
                    correlation_id=correlation_id,
                )
            except Exception as exc:
                logger.debug("capi enqueue skipped: %s", exc)

    return {
        "ok": True,
        "created_count": result.get("created_count", 0),
        "created_ids": created_ids,
        "skipped": result.get("skipped", []),
        "results": result.get("results"),
        "write_path": "pg_primary",
    }
