"""SEO integrations — GSC OAuth tokens stored in PG integrations_json (Phase 4)."""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from ptt_seo.db import seo_pg_only


def _ts() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")


def _loads(raw: Any) -> dict[str, Any]:
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return raw
    try:
        data = json.loads(raw or "{}")
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        return {}


def get_integrations(customer_id: int) -> dict[str, Any]:
    with seo_pg_only() as conn:
        row = conn.execute(
            "SELECT integrations_json FROM seo_client_settings WHERE customer_id = ?",
            (customer_id,),
        ).fetchone()
    if row is None:
        return {}
    return _loads(row["integrations_json"])


def patch_integrations(customer_id: int, patch: dict[str, Any]) -> dict[str, Any]:
    current = get_integrations(customer_id)
    merged = {**current, **patch}
    with seo_pg_only() as conn:
        conn.execute(
            """
            INSERT INTO seo_client_settings (customer_id, integrations_json, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(customer_id) DO UPDATE SET
                integrations_json = excluded.integrations_json,
                updated_at = excluded.updated_at
            """,
            (customer_id, json.dumps(merged, ensure_ascii=False), _ts()),
        )
        conn.commit()
    return merged


def get_gsc_integration(customer_id: int) -> dict[str, Any]:
    return dict(get_integrations(customer_id).get("gsc") or {})


def gsc_public_status(customer_id: int) -> dict[str, Any]:
    gsc = get_gsc_integration(customer_id)
    return {
        "connected": bool(gsc.get("refresh_token_encrypted") or gsc.get("refresh_token")),
        "site_url": gsc.get("site_url") or "",
        "status": gsc.get("status") or "disconnected",
        "connected_at": gsc.get("connected_at"),
        "last_sync_at": gsc.get("last_sync_at"),
        "last_sync_status": gsc.get("last_sync_status"),
    }


def get_ga4_integration(customer_id: int) -> dict[str, Any]:
    return dict(get_integrations(customer_id).get("ga4") or {})


def ga4_public_status(customer_id: int) -> dict[str, Any]:
    ga4 = get_ga4_integration(customer_id)
    return {
        "connected": bool(ga4.get("refresh_token_encrypted") or ga4.get("refresh_token")),
        "property_id": ga4.get("property_id") or "",
        "status": ga4.get("status") or "disconnected",
        "connected_at": ga4.get("connected_at"),
        "last_sync_at": ga4.get("last_sync_at"),
        "last_sync_status": ga4.get("last_sync_status"),
    }
