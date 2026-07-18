"""Client channel account token vault helpers (Phase 2 M1)."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

logger = logging.getLogger(__name__)

TOKEN_STATUSES = frozenset({"unknown", "valid", "expiring", "expired", "revoked"})


def vault_columns_ready() -> bool:
    try:
        from ptt_jobs.db import pg_available, pg_connection

        if not pg_available():
            return False
        with pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT COUNT(*) FROM information_schema.columns
                    WHERE table_schema = 'public'
                      AND table_name = 'client_channel_accounts'
                      AND column_name = 'access_token_encrypted'
                    """
                )
                return int(cur.fetchone()[0] or 0) >= 1
    except Exception as exc:
        logger.debug("vault_columns_ready: %s", exc)
        return False


def _parse_expires(value: Any) -> datetime | None:
    if value is None or value == "":
        return None
    if hasattr(value, "isoformat"):
        dt = value
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt
    text = str(value).strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(text[:25])
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return None


def compute_token_status(
    *,
    has_token: bool,
    token_status: str | None,
    token_expires_at: datetime | None,
    revoked: bool = False,
) -> str:
    if revoked or (token_status or "").lower() == "revoked":
        return "revoked"
    if not has_token:
        return "unknown"
    if token_expires_at:
        now = datetime.now(timezone.utc)
        if token_expires_at < now:
            return "expired"
        if token_expires_at < now + timedelta(days=7):
            return "expiring"
    return "valid"


def public_channel_account(row: dict[str, Any]) -> dict[str, Any]:
    enc = row.get("access_token_encrypted")
    cred = str(row.get("credential_ref") or "").strip()
    has_token = bool(enc) or bool(cred)
    expires = _parse_expires(row.get("token_expires_at"))
    status = compute_token_status(
        has_token=has_token,
        token_status=str(row.get("token_status") or ""),
        token_expires_at=expires,
        revoked=str(row.get("token_status") or "").lower() == "revoked",
    )
    out = {
        "id": str(row.get("id") or ""),
        "channel": row.get("channel"),
        "external_account_id": row.get("external_account_id"),
        "display_name": row.get("display_name"),
        "status": row.get("status"),
        "credential_ref": cred or None,
        "has_token": has_token,
        "token_status": status,
        "token_expires_at": expires.isoformat() if expires else None,
        "last_token_refresh_at": row.get("last_token_refresh_at"),
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
    }
    meta = row.get("meta")
    if isinstance(meta, dict):
        pixel = str(meta.get("pixel_id") or meta.get("meta_pixel_id") or "").strip()
        out["pixel_id"] = pixel or None
        out["pixel_configured"] = bool(pixel)
    elif meta:
        out["pixel_id"] = None
        out["pixel_configured"] = False
    return out
