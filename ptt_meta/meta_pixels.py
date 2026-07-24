"""Meta multi-pixel registry (B11) — CRUD + primary pixel resolution for CAPI."""
from __future__ import annotations

import logging
import os
from typing import Any

from ptt_jobs.db import pg_connection

logger = logging.getLogger(__name__)


def _truthy(name: str, default: str = "0") -> bool:
    return os.environ.get(name, default).strip().lower() in {"1", "true", "yes", "on"}


def meta_pixels_enabled() -> bool:
    return _truthy("PTT_META_PIXELS_ENABLED", "0")


def pg_meta_pixels_ready() -> bool:
    try:
        from ptt_crm.pg_schema import pg_meta_pixels_ready as _ready

        return _ready()
    except Exception:
        return False


def list_pixels(*, client_id: str | None = None, channel_account_id: str | None = None) -> dict[str, Any]:
    if not meta_pixels_enabled():
        return {"ok": True, "disabled": True, "pixels": []}
    if not pg_meta_pixels_ready():
        return {"ok": False, "error": "meta_pixels_not_ready", "hint": "./scripts/apply_pg_ddl_v7_meta_advanced.sh"}

    clauses = ["1=1"]
    values: list[Any] = []
    if channel_account_id:
        clauses.append("mp.client_channel_account_id = %s::uuid")
        values.append(channel_account_id)
    if client_id:
        clauses.append("cca.client_id = %s::uuid")
        values.append(client_id)

    with pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT mp.id::text, mp.client_channel_account_id::text, cca.client_id::text,
                       mp.pixel_id, mp.label, mp.is_primary, mp.capi_enabled, mp.created_at
                FROM meta_pixels mp
                JOIN client_channel_accounts cca ON cca.id = mp.client_channel_account_id
                WHERE {' AND '.join(clauses)}
                ORDER BY mp.is_primary DESC, mp.created_at ASC
                """,
                values,
            )
            rows = cur.fetchall()

    pixels = [
        {
            "id": r[0],
            "client_channel_account_id": r[1],
            "client_id": r[2],
            "pixel_id": r[3],
            "label": r[4],
            "is_primary": bool(r[5]),
            "capi_enabled": bool(r[6]),
            "created_at": r[7].isoformat() if r[7] else None,
        }
        for r in rows
    ]
    return {"ok": True, "pixels": pixels, "count": len(pixels)}


def create_pixel(
    *,
    client_channel_account_id: str,
    pixel_id: str,
    label: str = "",
    is_primary: bool = False,
    capi_enabled: bool = True,
) -> dict[str, Any]:
    if not meta_pixels_enabled():
        return {"ok": True, "disabled": True}
    if not pg_meta_pixels_ready():
        return {"ok": False, "error": "meta_pixels_not_ready"}

    pixel_id = pixel_id.strip()
    if not pixel_id:
        return {"ok": False, "error": "pixel_id_required"}

    with pg_connection() as conn:
        with conn.cursor() as cur:
            if is_primary:
                cur.execute(
                    """
                    UPDATE meta_pixels SET is_primary = FALSE
                    WHERE client_channel_account_id = %s::uuid
                    """,
                    (client_channel_account_id,),
                )
            cur.execute(
                """
                INSERT INTO meta_pixels (
                    client_channel_account_id, pixel_id, label, is_primary, capi_enabled
                ) VALUES (%s::uuid, %s, %s, %s, %s)
                RETURNING id::text, created_at
                """,
                (client_channel_account_id, pixel_id, label.strip(), is_primary, capi_enabled),
            )
            row = cur.fetchone()
        conn.commit()

    return {
        "ok": True,
        "pixel": {
            "id": row[0],
            "client_channel_account_id": client_channel_account_id,
            "pixel_id": pixel_id,
            "label": label.strip(),
            "is_primary": is_primary,
            "capi_enabled": capi_enabled,
            "created_at": row[1].isoformat() if row[1] else None,
        },
    }


def patch_pixel(
    pixel_row_id: str,
    *,
    label: str | None = None,
    is_primary: bool | None = None,
    capi_enabled: bool | None = None,
) -> dict[str, Any]:
    if not meta_pixels_enabled():
        return {"ok": True, "disabled": True}
    if not pg_meta_pixels_ready():
        return {"ok": False, "error": "meta_pixels_not_ready"}

    updates: list[str] = []
    values: list[Any] = []
    if label is not None:
        updates.append("label = %s")
        values.append(label.strip())
    if capi_enabled is not None:
        updates.append("capi_enabled = %s")
        values.append(capi_enabled)
    if is_primary is not None:
        updates.append("is_primary = %s")
        values.append(is_primary)
    if not updates:
        return {"ok": False, "error": "no_updates"}

    with pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT client_channel_account_id::text FROM meta_pixels WHERE id = %s::uuid",
                (pixel_row_id,),
            )
            existing = cur.fetchone()
            if not existing:
                return {"ok": False, "error": "not_found"}
            account_id = existing[0]
            if is_primary:
                cur.execute(
                    "UPDATE meta_pixels SET is_primary = FALSE WHERE client_channel_account_id = %s::uuid",
                    (account_id,),
                )
            values.append(pixel_row_id)
            cur.execute(
                f"UPDATE meta_pixels SET {', '.join(updates)} WHERE id = %s::uuid RETURNING pixel_id, label, is_primary, capi_enabled",
                values,
            )
            row = cur.fetchone()
        conn.commit()

    return {
        "ok": True,
        "pixel": {
            "id": pixel_row_id,
            "client_channel_account_id": account_id,
            "pixel_id": row[0],
            "label": row[1],
            "is_primary": bool(row[2]),
            "capi_enabled": bool(row[3]),
        },
    }


def resolve_primary_pixel_id(client_channel_account_id: str) -> str | None:
    """Return primary pixel_id for CAPI when B11 multi-pixel is enabled."""
    if not meta_pixels_enabled() or not pg_meta_pixels_ready():
        return None
    with pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT pixel_id FROM meta_pixels
                WHERE client_channel_account_id = %s::uuid
                  AND is_primary IS TRUE
                  AND capi_enabled IS TRUE
                ORDER BY created_at ASC
                LIMIT 1
                """,
                (client_channel_account_id,),
            )
            row = cur.fetchone()
    return str(row[0]).strip() if row and row[0] else None
