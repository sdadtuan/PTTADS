"""B12 — Meta ad_id ↔ CRM creative asset registry."""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

LINK_SOURCES = frozenset({"manual", "campaign_write", "graph_sync"})
APPROVED_CREATIVE_STATUS = "approved"


def registry_enabled() -> bool:
    return os.environ.get("PTT_META_CREATIVE_REGISTRY_ENABLED", "0").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def normalize_link_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(row.get("id") or ""),
        "client_id": str(row.get("client_id") or ""),
        "creative_submission_id": str(row.get("creative_submission_id") or ""),
        "external_ad_id": str(row.get("external_ad_id") or "").strip(),
        "external_adset_id": (str(row["external_adset_id"]).strip() if row.get("external_adset_id") else None),
        "external_campaign_id": (
            str(row["external_campaign_id"]).strip() if row.get("external_campaign_id") else None
        ),
        "external_creative_id": (
            str(row["external_creative_id"]).strip() if row.get("external_creative_id") else None
        ),
        "link_source": str(row.get("link_source") or "manual"),
        "is_active": bool(row.get("is_active", True)),
        "linked_by": row.get("linked_by"),
        "note": row.get("note"),
        "creative_title": row.get("creative_title"),
        "creative_status": row.get("creative_status"),
        "creative_asset_url": row.get("creative_asset_url"),
        "creative_version": row.get("creative_version"),
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
    }


def validate_link_payload(payload: dict[str, Any], *, require_approved: bool = True) -> tuple[dict[str, Any], list[str]]:
    errors: list[str] = []
    client_id = str(payload.get("client_id") or "").strip()
    creative_id = str(payload.get("creative_submission_id") or payload.get("creative_id") or "").strip()
    external_ad_id = str(payload.get("external_ad_id") or "").strip()
    if not client_id:
        errors.append("client_id_required")
    if not creative_id:
        errors.append("creative_submission_id_required")
    if not external_ad_id:
        errors.append("external_ad_id_required")
    link_source = str(payload.get("link_source") or "manual").strip().lower()
    if link_source not in LINK_SOURCES:
        errors.append("invalid_link_source")
    creative_status = str(payload.get("creative_status") or "").strip().lower()
    if require_approved and creative_status and creative_status != APPROVED_CREATIVE_STATUS:
        errors.append("creative_not_approved")
    if payload.get("creative_client_id") and str(payload["creative_client_id"]).strip() != client_id:
        errors.append("creative_client_mismatch")
    normalized = {
        "client_id": client_id,
        "creative_submission_id": creative_id,
        "external_ad_id": external_ad_id,
        "external_adset_id": str(payload.get("external_adset_id") or "").strip() or None,
        "external_campaign_id": str(payload.get("external_campaign_id") or "").strip() or None,
        "external_creative_id": str(payload.get("external_creative_id") or "").strip() or None,
        "link_source": link_source,
        "linked_by": payload.get("linked_by"),
        "note": payload.get("note"),
    }
    return normalized, errors


def build_upsert_plan(existing_active_id: str | None, payload: dict[str, Any]) -> dict[str, Any]:
    """Return plan for repository: deactivate previous active link for same ad."""
    return {
        "deactivate_link_id": existing_active_id,
        "insert": payload,
        "replaced": existing_active_id is not None,
    }


def list_links_filters(params: dict[str, Any]) -> dict[str, Any]:
    return {
        "client_id": str(params.get("client_id") or "").strip() or None,
        "external_ad_id": str(params.get("external_ad_id") or "").strip() or None,
        "external_campaign_id": str(params.get("external_campaign_id") or "").strip() or None,
        "creative_submission_id": str(params.get("creative_submission_id") or "").strip() or None,
        "active_only": str(params.get("active_only", "1")).strip().lower() not in {"0", "false", "no"},
        "limit": min(max(int(params.get("limit") or 200), 1), 1000),
    }


def upsert_ad_creative_link(
    *,
    payload: dict[str, Any],
    linked_by: str | None = None,
    stub: bool = False,
) -> dict[str, Any]:
    """Validate and upsert link. Uses PG when available; stub for local tests."""
    normalized, errors = validate_link_payload({**payload, "linked_by": linked_by})
    if errors:
        return {"ok": False, "errors": errors}

    if stub or not registry_enabled():
        row = normalize_link_row(
            {
                **normalized,
                "id": "stub-link-1",
                "is_active": True,
                "creative_title": payload.get("creative_title") or "Stub Creative",
                "creative_status": APPROVED_CREATIVE_STATUS,
                "creative_asset_url": payload.get("creative_asset_url"),
                "creative_version": payload.get("creative_version") or 1,
                "created_at": _now_iso(),
                "updated_at": _now_iso(),
            }
        )
        return {"ok": True, "stub": True, "link": row, "replaced": False}

    try:
        from ptt_jobs.db import pg_available, pg_connection
    except Exception as exc:
        logger.warning("creative registry PG unavailable: %s", exc)
        return {"ok": False, "error": "pg_unavailable"}

    if not pg_available():
        return {"ok": False, "error": "pg_unavailable"}

    try:
        from ptt_crm.pg_schema import pg_meta_ad_creative_links_ready

        if not pg_meta_ad_creative_links_ready():
            return {
                "ok": False,
                "error": "meta_ad_creative_links_not_ready",
                "hint": "./scripts/apply_pg_ddl_v9_meta_creative_registry.sh",
            }
    except Exception:
        return {"ok": False, "error": "meta_ad_creative_links_not_ready"}

    with pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT cs.id::text, cs.client_id::text, cs.status, cs.title, cs.asset_url, cs.version
                FROM creative_submissions cs
                WHERE cs.id = %s::uuid
                LIMIT 1
                """,
                (normalized["creative_submission_id"],),
            )
            creative = cur.fetchone()
            if not creative:
                return {"ok": False, "error": "creative_not_found"}
            creative_row = {
                "creative_client_id": str(creative[1]),
                "creative_status": str(creative[2]),
                "creative_title": str(creative[3]),
                "creative_asset_url": creative[4],
                "creative_version": creative[5],
            }
            normalized, errors = validate_link_payload({**payload, **creative_row, "linked_by": linked_by})
            if errors:
                return {"ok": False, "errors": errors}

            cur.execute(
                """
                SELECT id::text FROM meta_ad_creative_links
                WHERE client_id = %s::uuid AND external_ad_id = %s AND is_active IS TRUE
                LIMIT 1
                """,
                (normalized["client_id"], normalized["external_ad_id"]),
            )
            existing = cur.fetchone()
            replaced = existing is not None
            if existing:
                cur.execute(
                    """
                    UPDATE meta_ad_creative_links
                    SET is_active = FALSE, updated_at = NOW()
                    WHERE id = %s::uuid
                    """,
                    (existing[0],),
                )

            cur.execute(
                """
                INSERT INTO meta_ad_creative_links (
                  client_id, creative_submission_id, external_ad_id, external_adset_id,
                  external_campaign_id, external_creative_id, link_source, linked_by, note
                ) VALUES (
                  %s::uuid, %s::uuid, %s, %s, %s, %s, %s, %s, %s
                )
                RETURNING id::text, client_id::text, creative_submission_id::text,
                          external_ad_id, external_adset_id, external_campaign_id,
                          external_creative_id, link_source, is_active, linked_by, note,
                          created_at, updated_at
                """,
                (
                    normalized["client_id"],
                    normalized["creative_submission_id"],
                    normalized["external_ad_id"],
                    normalized["external_adset_id"],
                    normalized["external_campaign_id"],
                    normalized["external_creative_id"],
                    normalized["link_source"],
                    linked_by,
                    normalized.get("note"),
                ),
            )
            inserted = cur.fetchone()
        conn.commit()

    row = normalize_link_row(
        {
            "id": inserted[0],
            "client_id": inserted[1],
            "creative_submission_id": inserted[2],
            "external_ad_id": inserted[3],
            "external_adset_id": inserted[4],
            "external_campaign_id": inserted[5],
            "external_creative_id": inserted[6],
            "link_source": inserted[7],
            "is_active": inserted[8],
            "linked_by": inserted[9],
            "note": inserted[10],
            "creative_title": creative_row["creative_title"],
            "creative_status": creative_row["creative_status"],
            "creative_asset_url": creative_row["creative_asset_url"],
            "creative_version": creative_row["creative_version"],
            "created_at": inserted[11],
            "updated_at": inserted[12],
        }
    )
    return {"ok": True, "link": row, "replaced": replaced}


def resolve_creative_for_ad(
    *,
    client_id: str,
    external_ad_id: str,
    stub: bool = False,
) -> dict[str, Any]:
    ad_id = external_ad_id.strip()
    cid = client_id.strip()
    if not cid or not ad_id:
        return {"ok": False, "error": "client_id_and_external_ad_id_required"}

    if stub or not registry_enabled():
        return {
            "ok": True,
            "stub": True,
            "found": False,
            "external_ad_id": ad_id,
            "client_id": cid,
            "link": None,
        }

    try:
        from ptt_jobs.db import pg_available, pg_connection
        from ptt_crm.pg_schema import pg_meta_ad_creative_links_ready
    except Exception:
        return {"ok": False, "error": "pg_unavailable"}

    if not pg_available() or not pg_meta_ad_creative_links_ready():
        return {"ok": False, "error": "meta_ad_creative_links_not_ready"}

    with pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT l.id::text, l.client_id::text, l.creative_submission_id::text,
                       l.external_ad_id, l.external_adset_id, l.external_campaign_id,
                       l.external_creative_id, l.link_source, l.is_active, l.linked_by, l.note,
                       l.created_at, l.updated_at,
                       cs.title, cs.status, cs.asset_url, cs.version
                FROM meta_ad_creative_links l
                JOIN creative_submissions cs ON cs.id = l.creative_submission_id
                WHERE l.client_id = %s::uuid AND l.external_ad_id = %s AND l.is_active IS TRUE
                LIMIT 1
                """,
                (cid, ad_id),
            )
            row = cur.fetchone()

    if not row:
        return {"ok": True, "found": False, "external_ad_id": ad_id, "client_id": cid, "link": None}

    link = normalize_link_row(
        {
            "id": row[0],
            "client_id": row[1],
            "creative_submission_id": row[2],
            "external_ad_id": row[3],
            "external_adset_id": row[4],
            "external_campaign_id": row[5],
            "external_creative_id": row[6],
            "link_source": row[7],
            "is_active": row[8],
            "linked_by": row[9],
            "note": row[10],
            "created_at": row[11],
            "updated_at": row[12],
            "creative_title": row[13],
            "creative_status": row[14],
            "creative_asset_url": row[15],
            "creative_version": row[16],
        }
    )
    return {"ok": True, "found": True, "external_ad_id": ad_id, "client_id": cid, "link": link}
