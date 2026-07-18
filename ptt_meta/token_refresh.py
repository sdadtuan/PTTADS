"""Meta long-lived token refresh + expiry alerts (Phase 2 M1-03)."""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any

from ptt_agency.channel_vault import compute_token_status, vault_columns_ready
from ptt_jobs.db import json_dumps, pg_connection
from ptt_meta.graph_tokens import exchange_long_lived_token
from ptt_meta.token_vault import resolve_meta_access_token

logger = logging.getLogger(__name__)


def _truthy(name: str, default: str = "0") -> bool:
    return os.environ.get(name, default).strip().lower() in {"1", "true", "yes", "on"}


def meta_token_refresh_enabled() -> bool:
    return _truthy("PTT_META_TOKEN_REFRESH", "0")


def meta_token_refresh_stub_mode() -> bool:
    return _truthy("PTT_META_TOKEN_REFRESH_STUB", "0")


def refresh_window_days() -> int:
    try:
        return max(1, int(os.environ.get("PTT_META_TOKEN_REFRESH_WINDOW_DAYS", "14")))
    except ValueError:
        return 14


def alert_window_days() -> int:
    try:
        return max(1, int(os.environ.get("PTT_META_TOKEN_ALERT_DAYS", "7")))
    except ValueError:
        return 7


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


def _expires_iso_from_seconds(seconds: int | None) -> str | None:
    if seconds is None or seconds <= 0:
        return None
    return (datetime.now(timezone.utc) + timedelta(seconds=seconds)).isoformat()


def list_meta_accounts_for_maintenance() -> list[dict[str, Any]]:
    """Active Meta accounts with vault columns (includes client code/name)."""
    if not vault_columns_ready():
        return []

    with pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT cca.id, cca.client_id, cca.channel, cca.external_account_id,
                       cca.display_name, cca.credential_ref, cca.access_token_encrypted,
                       cca.token_expires_at, cca.token_status, cca.meta,
                       cca.last_token_refresh_at, cca.status,
                       c.code AS client_code, c.name AS client_name, c.owner_am_id
                FROM client_channel_accounts cca
                JOIN clients c ON c.id = cca.client_id
                WHERE cca.channel = 'meta'
                  AND cca.status = 'active'
                  AND COALESCE(cca.token_status, '') <> 'revoked'
                ORDER BY cca.token_expires_at NULLS LAST, c.code, cca.external_account_id
                """
            )
            cols = [d[0] for d in cur.description]
            rows: list[dict[str, Any]] = []
            for row in cur.fetchall():
                item = dict(zip(cols, row))
                meta = item.get("meta") or {}
                if isinstance(meta, str):
                    try:
                        meta = json.loads(meta)
                    except json.JSONDecodeError:
                        meta = {}
                item["meta"] = meta if isinstance(meta, dict) else {}
                rows.append(item)
            return rows


def _alert_already_sent(row: dict[str, Any], *, expires_at: datetime | None) -> bool:
    meta = row.get("meta") or {}
    if not isinstance(meta, dict):
        return False
    sent_for = str(meta.get("token_expiry_alert_for") or "").strip()
    if not expires_at or not sent_for:
        return False
    target = expires_at.isoformat()[:19]
    return sent_for[:19] == target


def _mark_alert_sent(account_id: str, *, expires_at: datetime | None) -> None:
    expires_key = expires_at.isoformat() if expires_at else "unknown"
    with pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE client_channel_accounts
                SET meta = COALESCE(meta, '{}'::jsonb) || %s::jsonb,
                    updated_at = NOW()
                WHERE id = %s::uuid
                """,
                (
                    json_dumps(
                        {
                            "token_expiry_alert_for": expires_key,
                            "token_expiry_alert_sent_at": datetime.now(timezone.utc).isoformat(),
                        }
                    ),
                    account_id,
                ),
            )
            conn.commit()


def _clear_alert_marker(account_id: str) -> None:
    with pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE client_channel_accounts
                SET meta = COALESCE(meta, '{}'::jsonb)
                     - 'token_expiry_alert_for'
                     - 'token_expiry_alert_sent_at',
                    updated_at = NOW()
                WHERE id = %s::uuid
                """,
                (account_id,),
            )
            conn.commit()


def _dispatch_token_alert(
    *,
    row: dict[str, Any],
    status: str,
    expires_at: datetime | None,
) -> bool:
    from ptt_agency.notifications import notify_agency_ops

    client_code = str(row.get("client_code") or "")
    client_name = str(row.get("client_name") or "")
    account_id = str(row.get("external_account_id") or "")
    display = str(row.get("display_name") or account_id)
    recipient = str(row.get("owner_am_id") or "").strip() or "admin"
    client_uuid = str(row.get("client_id") or "")
    channel_account_id = str(row.get("id") or "")

    exp_text = expires_at.strftime("%Y-%m-%d") if expires_at else "không rõ"
    if status == "expired":
        title = f"Meta token hết hạn — {client_code}"
        body = (
            f"Ad account {display} ({account_id}) của {client_name} đã hết hạn token ({exp_text}). "
            "Insights sync sẽ fail — cập nhật token trong Agency Ops."
        )
    else:
        title = f"Meta token sắp hết hạn — {client_code}"
        body = (
            f"Ad account {display} ({account_id}) của {client_name} hết hạn {exp_text} "
            f"(≤ {alert_window_days()} ngày). Kiểm tra refresh hoặc cập nhật token thủ công."
        )

    link = f"/crm/agency/clients/{client_uuid}" if client_uuid else "/crm/agency/clients"
    notify_agency_ops(
        recipient_id=recipient,
        title=title,
        body=body,
        category="meta_token",
        link_url=link,
        meta={
            "client_id": client_uuid,
            "channel_account_id": channel_account_id,
            "external_account_id": account_id,
            "token_status": status,
            "token_expires_at": expires_at.isoformat() if expires_at else None,
        },
        email_env="PTT_AGENCY_TOKEN_ALERT_EMAIL",
        email_fallback_env="PTT_AGENCY_SLA_ALERT_EMAIL",
        slack_prefix=":key: [PTT Meta Token]",
    )
    _mark_alert_sent(channel_account_id, expires_at=expires_at)
    return True


def alert_expiring_tokens(*, dry_run: bool = False) -> dict[str, Any]:
    """Notify AM/admin for tokens expiring within alert window or already expired."""
    now = datetime.now(timezone.utc)
    alert_cutoff = now + timedelta(days=alert_window_days())
    sent = 0
    skipped = 0
    candidates: list[dict[str, Any]] = []

    for row in list_meta_accounts_for_maintenance():
        token = resolve_meta_access_token(row)
        if not token:
            continue

        expires_at = _parse_expires(row.get("token_expires_at"))
        status = compute_token_status(
            has_token=True,
            token_status=str(row.get("token_status") or ""),
            token_expires_at=expires_at,
        )
        if status not in {"expiring", "expired"}:
            continue
        if expires_at and expires_at > alert_cutoff and status != "expired":
            continue
        if _alert_already_sent(row, expires_at=expires_at):
            skipped += 1
            continue

        candidates.append({"row": row, "status": status, "expires_at": expires_at})

    if dry_run:
        return {
            "alerts_sent": 0,
            "alerts_skipped": skipped,
            "alert_candidates": len(candidates),
            "dry_run": True,
        }

    for item in candidates:
        try:
            if _dispatch_token_alert(
                row=item["row"],
                status=item["status"],
                expires_at=item["expires_at"],
            ):
                sent += 1
        except Exception as exc:
            logger.warning(
                "token alert failed account=%s: %s",
                item["row"].get("external_account_id"),
                exc,
            )

    return {"alerts_sent": sent, "alerts_skipped": skipped, "alert_candidates": len(candidates)}


def refresh_account_token(row: dict[str, Any], *, stub: bool = False) -> dict[str, Any]:
    """Refresh one Meta channel account token; persist to vault."""
    from ptt_agency.clients import set_channel_account_token

    account_uuid = str(row.get("id") or "")
    client_id = str(row.get("client_id") or "")
    external_id = str(row.get("external_account_id") or "")

    current = resolve_meta_access_token(row)
    if not current:
        return {"ok": False, "account_id": account_uuid, "external_account_id": external_id, "error": "no_token"}

    if stub or meta_token_refresh_stub_mode():
        new_token = f"{current}-refreshed-stub"
        expires_iso = (datetime.now(timezone.utc) + timedelta(days=60)).isoformat()
    else:
        outcome = exchange_long_lived_token(current)
        err = outcome.get("_graph_error")
        if err:
            return {
                "ok": False,
                "account_id": account_uuid,
                "external_account_id": external_id,
                "error": str(err),
            }
        new_token = str(outcome.get("access_token") or "")
        expires_iso = _expires_iso_from_seconds(outcome.get("expires_in"))

    if not new_token:
        return {
            "ok": False,
            "account_id": account_uuid,
            "external_account_id": external_id,
            "error": "empty_refreshed_token",
        }

    try:
        set_channel_account_token(
            client_id,
            account_uuid,
            access_token=new_token,
            token_expires_at=expires_iso,
        )
        _clear_alert_marker(account_uuid)
    except ValueError as exc:
        return {
            "ok": False,
            "account_id": account_uuid,
            "external_account_id": external_id,
            "error": str(exc),
        }

    return {
        "ok": True,
        "account_id": account_uuid,
        "external_account_id": external_id,
        "token_expires_at": expires_iso,
        "stub": bool(stub or meta_token_refresh_stub_mode()),
    }


def refresh_due_tokens(*, dry_run: bool = False, force: bool = False) -> dict[str, Any]:
    """Refresh tokens expiring within refresh window (still valid)."""
    now = datetime.now(timezone.utc)
    refresh_cutoff = now + timedelta(days=refresh_window_days())
    refreshed = 0
    failed = 0
    skipped = 0
    results: list[dict[str, Any]] = []

    for row in list_meta_accounts_for_maintenance():
        token = resolve_meta_access_token(row)
        if not token:
            skipped += 1
            continue

        expires_at = _parse_expires(row.get("token_expires_at"))
        if not force:
            if expires_at is None:
                skipped += 1
                continue
            if expires_at <= now:
                skipped += 1
                continue
            if expires_at > refresh_cutoff:
                skipped += 1
                continue

        if dry_run:
            results.append(
                {
                    "ok": True,
                    "dry_run": True,
                    "account_id": str(row.get("id") or ""),
                    "external_account_id": str(row.get("external_account_id") or ""),
                }
            )
            refreshed += 1
            continue

        outcome = refresh_account_token(row)
        results.append(outcome)
        if outcome.get("ok"):
            refreshed += 1
        else:
            failed += 1

    return {
        "refreshed": refreshed,
        "refresh_failed": failed,
        "refresh_skipped": skipped,
        "results": results,
    }


def sync_meta_token_refresh(*, dry_run: bool = False, force: bool = False) -> dict[str, Any]:
    """
    Daily maintenance: refresh due long-lived tokens + alert ≤7 days before expiry.
    """
    if not meta_token_refresh_enabled() and not meta_token_refresh_stub_mode():
        return {"ok": True, "skipped": True, "reason": "PTT_META_TOKEN_REFRESH disabled"}

    if not vault_columns_ready():
        return {"ok": False, "error": "vault_columns_not_ready"}

    refresh_out = refresh_due_tokens(dry_run=dry_run, force=force)
    alert_out = alert_expiring_tokens(dry_run=dry_run)

    ok = refresh_out.get("refresh_failed", 0) == 0
    return {
        "ok": ok,
        "dry_run": dry_run,
        "force": force,
        **refresh_out,
        **alert_out,
    }
