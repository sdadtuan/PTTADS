"""Pre-send gate for Meta/Zalo scheduled reports (PROD-P0-RPT / P0-R-W3)."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any


def _yesterday_utc() -> date:
    today = datetime.now(timezone.utc).date()
    return today - timedelta(days=1)


def check_channel_report_gate(
    *,
    channel: str,
    client_id: str,
    window_days: int = 7,
) -> dict[str, Any]:
    """
    Gate rules:
    - unmapped campaigns for client in window must be 0
    - latest performance_date for channel must be >= T-1 (yesterday UTC)
    """
    from ptt_jobs.db import pg_connection

    ch = channel.strip().lower()
    if ch not in ("meta", "zalo"):
        return {"ok": False, "error": "invalid_channel"}

    end = _yesterday_utc()
    start = end - timedelta(days=max(1, min(int(window_days), 90)) - 1)

    with pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                  COUNT(DISTINCT dp.external_campaign_id)
                    FILTER (WHERE dp.hub_campaign_map_id IS NULL) AS unmapped,
                  MAX(dp.performance_date) AS through_date
                FROM daily_performance dp
                WHERE dp.client_id = %s::uuid
                  AND dp.channel = %s
                  AND dp.performance_date BETWEEN %s AND %s
                """,
                (client_id, ch, start, end),
            )
            row = cur.fetchone()
            unmapped = int(row[0] or 0) if row else 0
            through = row[1] if row else None

    through_date = through.isoformat()[:10] if hasattr(through, "isoformat") else str(through or "")[:10]
    required = end.isoformat()
    sync_ok = bool(through_date and through_date >= required)

    if unmapped > 0:
        return {
            "ok": False,
            "skipped": True,
            "reason": "unmapped_campaigns",
            "unmapped_campaigns": unmapped,
            "through_date": through_date,
        }
    if not sync_ok:
        return {
            "ok": False,
            "skipped": True,
            "reason": "sync_not_green_t_minus_1",
            "through_date": through_date,
            "required_through": required,
        }
    return {
        "ok": True,
        "unmapped_campaigns": 0,
        "through_date": through_date,
        "date_from": start.isoformat(),
        "date_to": end.isoformat(),
    }
