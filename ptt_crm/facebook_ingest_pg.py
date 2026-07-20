"""Facebook lead business logic with PostgreSQL-primary write (Phase 2)."""
from __future__ import annotations

import json
import logging
import sqlite3
from typing import Any

from crm_facebook_config import matches_facebook_source
from crm_facebook_leads import (
    _facebook_pending_placeholder_email,
    optimize_facebook_lead_item,
)
from crm_lead_store import (
    LEAD_LEVEL_LABELS,
    assign_lead_owner,
    classify_level,
    find_duplicate_matches,
    lead_needs_cleanup,
    normalize_email,
    normalize_phone,
    normalize_source,
    normalize_status,
    validate_lead_contacts,
)
from crm_lead_care_pipeline import CARE_STAGE_KEYS
from ptt_crm.lead_ingest_pg import (
    _external_lead_id,
    _normalize_uuid,
    fetch_pg_lead_by_id,
    find_pg_contact_duplicates,
    find_pg_lead_by_external,
    insert_pg_lead_record,
    next_prod_lead_id,
    update_pg_lead_fields,
)
from ptt_crm.lead_ingest_config import fetch_facebook_config_for_ingest, open_ingest_rules_conn
from ptt_jobs.db import json_dumps, pg_connection

logger = logging.getLogger(__name__)


def open_sqlite_config_conn() -> sqlite3.Connection:
    """Deprecated alias — use open_ingest_rules_conn()."""
    return open_ingest_rules_conn()


def _parse_meta(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return dict(raw)
    try:
        meta = json.loads(raw or "{}")
    except (json.JSONDecodeError, TypeError):
        meta = {}
    return meta if isinstance(meta, dict) else {}


def _level_label(conn: sqlite3.Connection | None, level_id: str) -> str:
    if conn is not None:
        try:
            from crm_lead_tiers import level_labels_map

            labels = {**LEAD_LEVEL_LABELS, **level_labels_map(conn)}
            return labels.get(level_id, level_id)
        except Exception:
            pass
    return LEAD_LEVEL_LABELS.get(level_id, level_id)


def _pipeline_summary_pg(row: dict[str, Any], conn: sqlite3.Connection) -> dict[str, Any]:
    meta = _parse_meta(row.get("meta_json"))
    level = str(meta.get("lead_level") or "warm")
    score = int(meta.get("lead_score") or 0)
    owner_id = row.get("owner_id")
    owner_name = ""
    if owner_id:
        try:
            staff = conn.execute(
                "SELECT name FROM crm_staff WHERE id = ?",
                (int(owner_id),),
            ).fetchone()
            if staff:
                owner_name = str(staff["name"] or "")
        except sqlite3.Error:
            pass
    return {
        "lead_id": int(row["sqlite_lead_id"]),
        "full_name": str(row.get("full_name") or ""),
        "phone": str(row.get("phone") or ""),
        "email": str(row.get("email") or ""),
        "source": str(row.get("source") or "facebook"),
        "lead_score": score,
        "lead_level": level,
        "lead_level_label": _level_label(conn, level),
        "owner_id": int(owner_id) if owner_id is not None else None,
        "owner_name": owner_name or None,
        "assign_strategy": meta.get("assign_strategy"),
        "is_duplicate": bool(row.get("is_duplicate")),
        "duplicate_of_id": meta.get("duplicate_of_id"),
        "facebook_leadgen_id": meta.get("facebook_leadgen_id") or row.get("external_lead_id"),
        "facebook_page_id": meta.get("facebook_page_id"),
        "facebook_form_id": meta.get("facebook_form_id"),
        "score_breakdown": meta.get("score_breakdown") or [],
        "optimized": bool(meta.get("optimized_at")),
    }


def _ensure_ingested_at_meta(meta: dict[str, Any], *, ts: str, created_by: str) -> None:
    from crm_lead_store import _ensure_ingested_at_meta

    _ensure_ingested_at_meta(meta, ts=ts, created_by=created_by)


def _build_fb_pg_record(
    item: dict[str, Any],
    *,
    lead_id: int,
    channel: str,
    client_id: str | None,
    ts: str,
    created_by: str,
    industry_slug: str,
    config_conn: sqlite3.Connection,
    fb_cfg: dict[str, Any],
    auto_assign: bool,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Score, assign, and build PG upsert payload for a new Facebook lead."""
    from crm_lead_catalog import normalize_industry_slug, normalize_product_interest
    from crm_lead_scoring import score_lead

    meta = dict(item.get("meta") if isinstance(item.get("meta"), dict) else {})
    name = str(item.get("full_name") or "").strip()
    phone = str(item.get("phone") or "").strip()
    email = str(item.get("email") or "").strip()
    region = str(item.get("region") or "")
    product_interest = normalize_product_interest(config_conn, str(item.get("product_interest") or ""))
    need = str(item.get("need") or "")
    industry_key = normalize_industry_slug(config_conn, industry_slug)
    utm_campaign = str(item.get("utm_campaign") or "")

    ph_norm, em_norm = validate_lead_contacts(phone=phone, email=email)
    needs_clean, _clean_reasons = lead_needs_cleanup(
        full_name=name,
        phone=phone,
        email=email,
        need=need,
        product_interest=product_interest,
    )
    st = normalize_status(str(item.get("status") or "new"))
    if needs_clean and st not in ("lost",):
        st = "pending_cleanup"
    elif st not in ("lost", "pending_cleanup"):
        st = "intake" if st not in CARE_STAGE_KEYS else st

    src = normalize_source("facebook")
    meta_obj = dict(meta)
    _ensure_ingested_at_meta(meta_obj, ts=ts, created_by=created_by)
    meta_obj.setdefault("ingest_channel", "facebook_lead_ads")
    meta_obj["industry_slug"] = industry_key
    if utm_campaign:
        meta_obj.setdefault("utm_campaign", utm_campaign)

    score_result = score_lead(
        config_conn,
        source=src,
        phone=phone,
        email=email,
        need=need,
        product_interest=product_interest,
        region=region,
        full_name=name,
        meta=meta_obj,
        activity_count=0,
    )
    meta_obj["score_breakdown"] = score_result["breakdown"]
    meta_obj["score_raw_total"] = score_result["raw_total"]
    meta_obj["score_updated_at"] = ts
    score = int(score_result["score"])
    level = classify_level(score, status=st, conn=config_conn)
    meta_obj["lead_score"] = score
    meta_obj["lead_level"] = level

    dup_matches = find_pg_contact_duplicates(phone=phone, email=email)
    if not dup_matches:
        dup_matches = find_duplicate_matches(config_conn, phone=phone, email=email)

    dup_of: int | None = None
    is_dup = False
    if dup_matches:
        primary_id = int(dup_matches[0].get("lead_id") or dup_matches[0].get("sqlite_lead_id") or 0)
        if primary_id:
            dup_of = primary_id
            is_dup = True
            meta_obj["duplicate_of_id"] = primary_id

    final_owner = item.get("owner_id")
    assign_strategy = ""
    if final_owner in (None, "") and auto_assign and not is_dup:
        final_owner, _owner_name, assign_strategy = assign_lead_owner(
            config_conn,
            region=region,
            product_interest=product_interest,
            industry_slug=industry_key,
            lead_level=level,
            lead_score=score,
            source=src,
            need=need,
        )
        if assign_strategy and final_owner:
            meta_obj["assign_strategy"] = assign_strategy
            meta_obj["auto_assigned_at"] = ts
        elif auto_assign and not is_dup:
            meta_obj["assign_failed"] = True
            meta_obj["assign_failed_at"] = ts
            if assign_strategy == "no_scope_staff":
                meta_obj["assign_failed_reason"] = "Không có AM phụ trách ngành × dịch vụ này"
            else:
                meta_obj["assign_failed_reason"] = (
                    "Không tìm được nhân viên phù hợp"
                    if assign_strategy in ("", "none")
                    else f"Phân công thất bại ({assign_strategy})"
                )

    ext = _external_lead_id(item, channel) or str(meta_obj.get("facebook_leadgen_id") or "").strip() or None
    campaign_id = str(item.get("campaign_id") or meta_obj.get("campaign_id") or "").strip() or None
    from ptt_crm.lead_sync import _parse_ts

    parsed_ts = _parse_ts(ts)
    record = {
        "sqlite_lead_id": lead_id,
        "full_name": name[:500] or phone or email or "Lead Facebook",
        "phone": phone[:64],
        "email": email[:240],
        "status": st[:64],
        "source": src[:64],
        "owner_id": int(final_owner) if final_owner not in (None, "") else None,
        "is_duplicate": is_dup,
        "meta_json": json_dumps(meta_obj),
        "agency_client_id": _normalize_uuid(client_id),
        "channel": (channel or meta_obj.get("channel") or "meta")[:32],
        "external_lead_id": ext,
        "campaign_id": campaign_id,
        "received_at": parsed_ts,
        "created_at": parsed_ts,
    }
    summary_extra = {
        "dup_matches": dup_matches,
        "dup_of": dup_of,
        "is_dup": is_dup,
        "score": score,
        "level": level,
        "placeholder_meta": meta_obj,
    }
    return record, summary_extra


def enrich_pg_facebook_placeholder(
    existing_id: int,
    item: dict[str, Any],
    *,
    created_by: str,
    ts: str,
    fb_cfg: dict[str, Any],
    config_conn: sqlite3.Connection,
) -> dict[str, Any] | None:
    row = fetch_pg_lead_by_id(existing_id)
    if row is None:
        return None
    meta = _parse_meta(row.get("meta_json"))
    if not meta.get("awaiting_facebook_graph"):
        return None

    phone = str(item.get("phone") or "").strip()
    email = str(item.get("email") or "").strip()
    if email.endswith("@pending.ptt"):
        email = ""
    if not normalize_phone(phone) and not normalize_email(email):
        return None

    name = str(item.get("full_name") or "").strip() or str(row.get("full_name") or "")
    meta.pop("awaiting_facebook_graph", None)
    meta["facebook_enriched_at"] = ts
    meta.setdefault("ingest_channel", "facebook_lead_ads")
    item_meta = item.get("meta") if isinstance(item.get("meta"), dict) else {}
    for key in ("facebook_form_id", "facebook_page_id", "raw_field_data", "facebook_created_time"):
        if item_meta.get(key) is not None:
            meta[key] = item_meta[key]

    update_pg_lead_fields(
        existing_id,
        full_name=name[:500],
        phone=phone[:64],
        email=email[:240],
        meta_json=meta,
        updated_by=created_by[:120],
    )
    refreshed = fetch_pg_lead_by_id(existing_id)
    if refreshed is None:
        return None
    summary = _pipeline_summary_pg(refreshed, config_conn)
    summary["status"] = "enriched"
    summary["message"] = "Đã bổ sung dữ liệu lead Facebook từ Graph API."

    if not summary.get("owner_id") and fb_cfg.get("auto_assign", True):
        owner_id, _owner_name, strategy = assign_lead_owner(
            config_conn,
            region=str(item.get("region") or refreshed.get("region") or ""),
            product_interest=str(item.get("product_interest") or meta.get("product_interest") or ""),
            industry_slug=str(meta.get("industry_slug") or ""),
            lead_level=str(summary.get("lead_level") or ""),
            lead_score=int(summary.get("lead_score") or 0),
            source="facebook",
            need=str(item.get("need") or ""),
        )
        if owner_id:
            meta.pop("assign_failed", None)
            meta.pop("assign_failed_at", None)
            meta.pop("assign_failed_reason", None)
            meta["assign_strategy"] = strategy
            meta["auto_assigned_at"] = ts
            update_pg_lead_fields(
                existing_id,
                owner_id=int(owner_id),
                meta_json=meta,
                updated_by=created_by[:120],
            )
            refreshed = fetch_pg_lead_by_id(existing_id) or refreshed
            summary = _pipeline_summary_pg(refreshed, config_conn)
            summary["status"] = "created_assigned"
            summary["message"] = f"Đã bổ sung + gán {summary.get('owner_name') or owner_id}."
    return summary


def process_facebook_lead_item_pg(
    item: dict[str, Any],
    *,
    channel: str,
    client_id: str | None,
    created_by: str,
    ts: str,
    webhook_slug: str | None = None,
    auto_assign: bool | None = None,
    fb_cfg: dict[str, Any] | None = None,
    skip_source_filter: bool = False,
    config_conn: sqlite3.Connection | None = None,
) -> dict[str, Any]:
    """Mirror process_facebook_lead_item — writes only to PostgreSQL."""
    _ = webhook_slug
    owns_conn = config_conn is None
    conn_ro = config_conn or open_ingest_rules_conn()
    try:
        cfg = fb_cfg if fb_cfg is not None else fetch_facebook_config_for_ingest(conn_ro)
        meta_pre = item.get("meta") if isinstance(item.get("meta"), dict) else {}
        form_id_pre = str(meta_pre.get("facebook_form_id") or item.get("facebook_form_id") or "").strip()

        from crm_lead_product_model_p3 import resolve_facebook_industry_slug

        industry_slug = resolve_facebook_industry_slug(conn_ro, item, webhook_slug=webhook_slug)

        if not skip_source_filter:
            ok, reason = matches_facebook_source(item, cfg)
            if not ok:
                return {
                    "status": "filtered_out",
                    "message": reason,
                    "full_name": item.get("full_name"),
                    "facebook_form_id": form_id_pre,
                }

        if cfg.get("auto_optimize", True):
            item = optimize_facebook_lead_item(item)

        meta = item.get("meta") if isinstance(item.get("meta"), dict) else {}
        leadgen_id = str(meta.get("facebook_leadgen_id") or "").strip()
        agency_uuid = _normalize_uuid(client_id)
        ch = (channel or "meta").strip().lower()

        if leadgen_id:
            existing = find_pg_lead_by_external(
                agency_client_id=agency_uuid,
                channel=ch,
                external_lead_id=leadgen_id,
            )
            if existing:
                enriched = enrich_pg_facebook_placeholder(
                    int(existing),
                    item,
                    created_by=created_by,
                    ts=ts,
                    fb_cfg=cfg,
                    config_conn=conn_ro,
                )
                if enriched:
                    return enriched
                row = fetch_pg_lead_by_id(int(existing))
                if row:
                    update_pg_lead_fields(int(existing), updated_by=created_by[:120])
                    summary = _pipeline_summary_pg(row, conn_ro)
                    summary["status"] = "duplicate_seen"
                    summary["repeat_webhook"] = True
                    summary["message"] = (
                        f"Lead Facebook #{leadgen_id} đã có (PG #{existing}) — Meta gửi webhook lặp."
                    )
                    return summary

        name = str(item.get("full_name") or "").strip()
        phone = str(item.get("phone") or "").strip()
        email = str(item.get("email") or "").strip()
        if not name:
            name = phone or email or "Lead Facebook"
        meta_obj = dict(meta)
        meta_obj.setdefault("ingest_channel", "facebook_lead_ads")
        meta_obj["ingested_at"] = ts
        placeholder = False
        if not normalize_phone(phone) and not normalize_email(email):
            if not leadgen_id:
                return {
                    "status": "skipped",
                    "message": "Thiếu SĐT hoặc email hợp lệ.",
                    "full_name": name,
                    "facebook_leadgen_id": leadgen_id or None,
                }
            email = _facebook_pending_placeholder_email(leadgen_id)
            meta_obj["awaiting_facebook_graph"] = True
            meta_obj["facebook_leadgen_id"] = leadgen_id
            placeholder = True

        do_assign = cfg.get("auto_assign", True) if auto_assign is None else bool(auto_assign)
        item_for_record = dict(item)
        item_for_record["full_name"] = name
        item_for_record["phone"] = phone
        item_for_record["email"] = email
        item_for_record["meta"] = meta_obj
        if client_id and client_id not in {"", "unknown"}:
            meta_obj.setdefault("agency_client_id", client_id)

        try:
            with pg_connection() as pg:
                with pg.cursor() as cur:
                    lead_id = next_prod_lead_id(cur)
            record, extra = _build_fb_pg_record(
                item_for_record,
                lead_id=lead_id,
                channel=ch,
                client_id=client_id,
                ts=ts,
                created_by=created_by,
                industry_slug=industry_slug,
                config_conn=conn_ro,
                fb_cfg=cfg,
                auto_assign=do_assign,
            )
            if leadgen_id:
                record["external_lead_id"] = leadgen_id
                meta_parsed = _parse_meta(record["meta_json"])
                meta_parsed["facebook_leadgen_id"] = leadgen_id
                record["meta_json"] = json_dumps(meta_parsed)
            insert_pg_lead_record(record)
        except ValueError as exc:
            return {
                "status": "error",
                "message": str(exc),
                "full_name": name,
                "facebook_leadgen_id": leadgen_id or None,
            }

        row = fetch_pg_lead_by_id(lead_id) or record
        summary = _pipeline_summary_pg(row if isinstance(row, dict) else record, conn_ro)
        dup_matches = extra.get("dup_matches") or []
        if dup_matches:
            summary["status"] = "duplicate_linked"
            primary = dup_matches[0].get("lead_id") or dup_matches[0].get("sqlite_lead_id")
            summary["message"] = f"Trùng phone/email — liên kết lead #{primary or ''}."
        elif extra.get("is_dup"):
            summary["status"] = "duplicate_linked"
            summary["message"] = "Lead trùng SĐT/email — vẫn lưu bản ghi Facebook mới (đánh dấu trùng)."
        elif summary.get("owner_id"):
            summary["status"] = "created_assigned"
            summary["message"] = (
                (f"Lead placeholder — chờ Graph API · " if placeholder else "")
                + f"Tối ưu → chấm {summary['lead_score']}đ → "
                + f"{summary.get('lead_level_label') or summary['lead_level']} → "
                + f"gán {summary.get('owner_name') or summary['owner_id']} "
                + f"({summary.get('assign_strategy') or 'auto'})."
            )
        else:
            summary["status"] = "created_unassigned"
            summary["message"] = (
                (f"Lead placeholder — chờ Graph API · " if placeholder else "")
                + f"Tối ưu → chấm {summary['lead_score']}đ → "
                + f"{summary.get('lead_level_label') or summary['lead_level']} "
                + "— chưa gán NV."
            )
        if placeholder or meta_obj.get("awaiting_facebook_graph"):
            summary["awaiting_facebook_graph"] = True
        summary["industry_slug"] = industry_slug
        return summary
    finally:
        if owns_conn:
            conn_ro.close()
