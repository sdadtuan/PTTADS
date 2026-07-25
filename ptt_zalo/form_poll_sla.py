"""Zalo form lead poll SLA monitor — alert when last_polled_at > threshold (Prod-S3)."""
from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any

from ptt_jobs.db import pg_connection
from ptt_zalo.form_lead_poll import pg_zalo_leads_ready

logger = logging.getLogger(__name__)


def _truthy(name: str, default: str = "0") -> bool:
    return os.environ.get(name, default).strip().lower() in {"1", "true", "yes", "on"}


def zalo_form_poll_sla_enabled() -> bool:
    return _truthy("PTT_ZALO_FORM_POLL_SLA", "1")


def poll_sla_minutes() -> int:
    try:
        return max(5, int(os.environ.get("PTT_ZALO_FORM_POLL_SLA_MINUTES", "15")))
    except ValueError:
        return 15


def _parse_ts(value: Any) -> datetime | None:
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


def list_stale_form_cursors(*, client_id: str | None = None) -> list[dict[str, Any]]:
    if not pg_zalo_leads_ready():
        return []

    clauses = ["1=1"]
    params: list[Any] = []
    if client_id:
        clauses.append("c.client_id = %s::uuid")
        params.append(client_id)

    with pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT c.id::text AS cursor_id,
                       c.client_id::text,
                       cl.code AS client_code,
                       cl.name AS client_name,
                       cl.owner_am_id,
                       c.oa_id,
                       c.form_id,
                       c.last_polled_at,
                       c.last_status,
                       c.last_error
                FROM zalo_lead_form_sync_cursor c
                JOIN clients cl ON cl.id = c.client_id
                WHERE {' AND '.join(clauses)}
                ORDER BY c.last_polled_at NULLS FIRST, cl.code
                """,
                params,
            )
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]


def evaluate_form_poll_sla(*, client_id: str | None = None, dry_run: bool = False) -> dict[str, Any]:
    if not zalo_form_poll_sla_enabled():
        return {"ok": True, "skipped": True, "reason": "PTT_ZALO_FORM_POLL_SLA disabled"}
    if not pg_zalo_leads_ready():
        return {"ok": False, "error": "pg_zalo_leads_not_ready"}

    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(minutes=poll_sla_minutes())
    stale: list[dict[str, Any]] = []

    for row in list_stale_form_cursors(client_id=client_id):
        last = _parse_ts(row.get("last_polled_at"))
        if last is not None and last >= cutoff:
            continue
        stale.append(row)

    if dry_run:
        return {
            "ok": True,
            "dry_run": True,
            "stale_count": len(stale),
            "sla_minutes": poll_sla_minutes(),
            "stale": stale[:20],
        }

    sent = 0
    for row in stale:
        try:
            from ptt_agency.notifications import notify_agency_ops

            client_code = str(row.get("client_code") or "")
            form_id = str(row.get("form_id") or "")
            oa_id = str(row.get("oa_id") or "")
            recipient = str(row.get("owner_am_id") or "").strip() or "admin"
            client_uuid = str(row.get("client_id") or "")
            last = _parse_ts(row.get("last_polled_at"))
            last_text = last.strftime("%Y-%m-%d %H:%M UTC") if last else "chưa poll"

            notify_agency_ops(
                recipient_id=recipient,
                title=f"Zalo form poll SLA breach — {client_code}",
                body=(
                    f"Form {form_id} (OA {oa_id}) chưa poll thành công trong {poll_sla_minutes()} phút "
                    f"(last: {last_text}). Kiểm tra worker `zalo_form_lead_poll` và token Zalo."
                ),
                category="zalo_form_poll_sla",
                link_url="/zalo/leads",
                meta={
                    "client_id": client_uuid,
                    "form_id": form_id,
                    "oa_id": oa_id,
                    "last_polled_at": last.isoformat() if last else None,
                },
                email_env="PTT_AGENCY_SLA_ALERT_EMAIL",
                slack_prefix=":warning: [PTT Zalo Poll SLA]",
            )
            sent += 1
        except Exception as exc:
            logger.warning("zalo form poll sla alert failed form=%s: %s", row.get("form_id"), exc)

    return {
        "ok": True,
        "stale_count": len(stale),
        "alerts_sent": sent,
        "sla_minutes": poll_sla_minutes(),
    }
