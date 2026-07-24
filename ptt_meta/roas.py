"""Meta ROAS engine (B10) — CRM conversion_value / spend."""
from __future__ import annotations

import os
from datetime import date, datetime, timedelta, timezone
from typing import Any

from ptt_jobs.db import pg_connection


def _truthy(name: str, default: str = "0") -> bool:
    return os.environ.get(name, default).strip().lower() in {"1", "true", "yes", "on"}


def meta_roas_enabled() -> bool:
    return _truthy("PTT_META_ROAS_ENABLED", "0")


def compute_roas(conversion_value: float, spend: float) -> float | None:
    if spend <= 0 or conversion_value <= 0:
        return None
    return round((conversion_value / spend) * 10000) / 10000


def compute_roas_summary(
    *,
    total_spend: float,
    total_conversion_value: float,
) -> dict[str, Any]:
    roas = compute_roas(total_conversion_value, total_spend)
    return {
        "total_spend": round(total_spend, 2),
        "total_conversion_value": round(total_conversion_value, 2),
        "avg_roas": roas,
        "roas_stub": roas is None and total_spend > 0,
    }


def fetch_roas_series(
    *,
    client_id: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    default_days: int = 7,
) -> dict[str, Any]:
    """Aggregate ROAS by day from daily_performance."""
    if not meta_roas_enabled():
        return {"ok": True, "disabled": True, "series": [], "summary": compute_roas_summary(total_spend=0, total_conversion_value=0)}

    if date_to is None:
        date_to = datetime.now(timezone.utc).date() - timedelta(days=1)
    if date_from is None:
        date_from = date_to - timedelta(days=max(1, default_days) - 1)

    client_filter = ""
    params: list[Any] = [date_from, date_to]
    if client_id:
        client_filter = "AND dp.client_id = %s::uuid"
        params.append(client_id)

    with pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT dp.performance_date::date,
                       SUM(dp.spend) AS spend,
                       SUM(dp.conversion_value) AS conversion_value
                FROM daily_performance dp
                WHERE dp.channel = 'meta'
                  AND dp.performance_date BETWEEN %s::date AND %s::date
                  {client_filter}
                GROUP BY dp.performance_date
                ORDER BY dp.performance_date ASC
                """,
                params,
            )
            rows = cur.fetchall()

            cur.execute(
                f"""
                SELECT COALESCE(SUM(dp.spend) FILTER (WHERE dp.hub_campaign_map_id IS NULL), 0),
                       COALESCE(SUM(dp.spend), 0),
                       MAX(dp.performance_date)::date
                FROM daily_performance dp
                WHERE dp.channel = 'meta'
                  AND dp.performance_date BETWEEN %s::date AND %s::date
                  {client_filter}
                """,
                params,
            )
            unmapped_row = cur.fetchone()

    series: list[dict[str, Any]] = []
    total_spend = 0.0
    total_conv = 0.0
    for row in rows:
        spend = float(row[1] or 0)
        conv = float(row[2] or 0)
        total_spend += spend
        total_conv += conv
        roas = compute_roas(conv, spend)
        series.append(
            {
                "performance_date": str(row[0]),
                "spend": round(spend, 2),
                "conversion_value": round(conv, 2),
                "roas": roas,
                "roas_stub": roas is None and spend > 0,
            }
        )

    unmapped = float(unmapped_row[0] or 0) if unmapped_row else 0.0
    all_spend = float(unmapped_row[1] or 0) if unmapped_row else total_spend
    unmapped_pct = round((unmapped / all_spend) * 1000) / 10 if all_spend > 0 else 0.0

    return {
        "ok": True,
        "date_from": date_from.isoformat(),
        "date_to": date_to.isoformat(),
        "series": series,
        "summary": compute_roas_summary(total_spend=total_spend, total_conversion_value=total_conv),
        "unmapped_spend_pct": unmapped_pct,
        "through_date": str(unmapped_row[2]) if unmapped_row and unmapped_row[2] else date_to.isoformat(),
    }
