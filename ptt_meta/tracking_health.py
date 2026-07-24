"""B9 tracking health aggregates — Python mirror of Nest /meta/tracking/health."""
from __future__ import annotations

import logging
from typing import Any

from ptt_jobs.db import pg_connection
from ptt_meta.capi_dispatch import capi_stats, pg_capi_ready

logger = logging.getLogger(__name__)


def _parse_meta(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    return {}


def list_tracking_accounts(*, client_id: str | None = None) -> list[dict[str, Any]]:
    clauses = ["cca.channel = 'meta'", "COALESCE(cca.status, 'active') = 'active'"]
    params: list[Any] = []
    if client_id:
        clauses.append("cca.client_id = %s::uuid")
        params.append(client_id)

    with pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT
                   cca.id::text AS channel_account_id,
                   cca.client_id::text AS client_id,
                   cca.meta,
                   c.code AS client_code,
                   c.name AS client_name,
                   (
                     SELECT MAX(cel.sent_at)
                     FROM capi_event_log cel
                     WHERE cel.client_id = cca.client_id AND cel.status = 'sent'
                   ) AS last_sent_at
                FROM client_channel_accounts cca
                JOIN clients c ON c.id = cca.client_id
                WHERE {' AND '.join(clauses)}
                ORDER BY c.code NULLS LAST, cca.display_name NULLS LAST
                """,
                params,
            )
            cols = [d[0] for d in cur.description]
            rows = [dict(zip(cols, row)) for row in cur.fetchall()]

    accounts: list[dict[str, Any]] = []
    for row in rows:
        meta = _parse_meta(row.get("meta"))
        pixel_id = str(meta.get("pixel_id") or meta.get("meta_pixel_id") or "").strip() or None
        page_id = str(meta.get("facebook_page_id") or meta.get("page_id") or "").strip() or None
        capi_raw = meta.get("capi_enabled")
        capi_enabled = (
            False
            if capi_raw in (False, "0", 0)
            else bool(pixel_id)
        )
        last_sent = row.get("last_sent_at")
        accounts.append(
            {
                "client_id": str(row.get("client_id")),
                "channel_account_id": str(row.get("channel_account_id")),
                "client_code": row.get("client_code"),
                "client_name": row.get("client_name"),
                "pixel_id": pixel_id,
                "page_id": page_id,
                "capi_enabled": capi_enabled,
                "last_sent_at": last_sent.isoformat() if last_sent else None,
                "pixel_test_ok": None,
            }
        )
    return accounts


def tracking_health(*, client_id: str | None = None, window_days: int = 7) -> dict[str, Any]:
    """Return TrackingHealthResponse-shaped dict for CLI/jobs."""
    days = max(1, min(int(window_days), 90))
    if not pg_capi_ready():
        return {"ok": False, "error": "capi_event_log_not_ready"}

    stats = capi_stats(client_id=client_id, hours=days * 24)
    if not stats.get("ok"):
        return stats

    by_status = stats.get("by_status") or {}
    sent = int(stats.get("sent") or by_status.get("sent") or 0)
    failed = int(stats.get("failed") or by_status.get("failed") or 0)
    skipped = int(stats.get("skipped") or by_status.get("skipped") or 0)
    pending = int(stats.get("pending") or by_status.get("pending") or 0)
    attempted = sent + failed
    fail_rate = float(stats.get("fail_rate_pct") or stats.get("error_rate_pct") or 0)
    match_hint = float(stats.get("match_hint_pct") or stats.get("match_rate_pct") or 0) if attempted else None

    return {
        "ok": True,
        "window_days": days,
        "global": {
            "sent": sent,
            "failed": failed,
            "skipped": skipped,
            "pending": pending,
            "fail_rate_pct": fail_rate,
            "match_hint_pct": match_hint,
            "avg_latency_ms": stats.get("avg_latency_ms"),
        },
        "accounts": list_tracking_accounts(client_id=client_id),
        "attribution_model": "last_touch_crm",
    }
