"""Meta CPL/spend forecast (B11) — linear regression + 7d projection."""
from __future__ import annotations

import logging
import os
from datetime import date, datetime, timedelta, timezone
from typing import Any

from ptt_jobs.db import pg_connection

logger = logging.getLogger(__name__)


def _truthy(name: str, default: str = "0") -> bool:
    return os.environ.get(name, default).strip().lower() in {"1", "true", "yes", "on"}


def meta_forecast_enabled() -> bool:
    return _truthy("PTT_META_FORECAST_ENABLED", "0")


def _history_days() -> int:
    raw = os.environ.get("PTT_META_FORECAST_HISTORY_DAYS", "14").strip()
    try:
        return max(3, int(raw))
    except ValueError:
        return 14


def _projection_days() -> int:
    raw = os.environ.get("PTT_META_FORECAST_PROJECTION_DAYS", "7").strip()
    try:
        return max(1, int(raw))
    except ValueError:
        return 7


def linear_regression(points: list[tuple[float, float]]) -> tuple[float, float]:
    """Return (slope, intercept) for y = slope * x + intercept."""
    n = len(points)
    if n == 0:
        return 0.0, 0.0
    if n == 1:
        return 0.0, points[0][1]
    sum_x = sum(p[0] for p in points)
    sum_y = sum(p[1] for p in points)
    sum_xy = sum(p[0] * p[1] for p in points)
    sum_xx = sum(p[0] * p[0] for p in points)
    denom = n * sum_xx - sum_x * sum_x
    if denom == 0:
        return 0.0, sum_y / n
    slope = (n * sum_xy - sum_x * sum_y) / denom
    intercept = (sum_y - slope * sum_x) / n
    return slope, intercept


def build_forecast(
    *,
    historical: list[dict[str, Any]],
    projection_days: int | None = None,
) -> dict[str, Any]:
    """Pure forecast from daily rows with performance_date + value."""
    proj_days = projection_days if projection_days is not None else _projection_days()
    sorted_rows = sorted(historical, key=lambda r: str(r["performance_date"]))
    points: list[tuple[float, float]] = []
    for idx, row in enumerate(sorted_rows):
        val = float(row.get("value") or 0)
        if val > 0:
            points.append((float(idx), val))

    slope, intercept = linear_regression(points)
    last_date = date.fromisoformat(str(sorted_rows[-1]["performance_date"])[:10]) if sorted_rows else datetime.now(
        timezone.utc
    ).date()
    last_idx = len(points) - 1 if points else 0

    projection: list[dict[str, Any]] = []
    for offset in range(1, proj_days + 1):
        x = last_idx + offset
        projected = max(0.0, slope * x + intercept)
        day = last_date + timedelta(days=offset)
        projection.append(
            {
                "performance_date": day.isoformat(),
                "projected_value": round(projected * 100) / 100,
            }
        )

    return {
        "slope": round(slope * 10000) / 10000,
        "intercept": round(intercept * 100) / 100,
        "historical": [
            {
                "performance_date": str(r["performance_date"])[:10],
                "value": round(float(r.get("value") or 0) * 100) / 100,
            }
            for r in sorted_rows
        ],
        "projection": projection,
    }


def fetch_daily_metric_series(
    *,
    metric: str,
    client_id: str | None = None,
    days: int | None = None,
) -> dict[str, Any]:
    if not meta_forecast_enabled():
        return {"ok": True, "disabled": True, "metric": metric, "historical": [], "projection": []}

    history_days = days if days is not None else _history_days()
    end = datetime.now(timezone.utc).date() - timedelta(days=1)
    start = end - timedelta(days=history_days - 1)

    clauses = ["dp.channel = 'meta'", "dp.performance_date BETWEEN %s AND %s"]
    values: list[Any] = [start, end]
    if client_id:
        clauses.append("dp.client_id = %s::uuid")
        values.append(client_id)

    with pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT dp.performance_date::date,
                       SUM(dp.spend) AS spend,
                       SUM(dp.leads_crm) AS leads_crm
                FROM daily_performance dp
                WHERE {' AND '.join(clauses)}
                GROUP BY dp.performance_date
                ORDER BY dp.performance_date ASC
                """,
                values,
            )
            rows = cur.fetchall()

    historical: list[dict[str, Any]] = []
    for perf_date, spend, leads in rows:
        spend_f = float(spend or 0)
        leads_i = int(leads or 0)
        if metric == "spend":
            value = spend_f
        elif metric == "cpl":
            value = spend_f / leads_i if leads_i > 0 else 0.0
        else:
            return {"ok": False, "error": "invalid_metric", "metric": metric}
        historical.append({"performance_date": perf_date.isoformat(), "value": value})

    forecast = build_forecast(historical=historical)
    return {
        "ok": True,
        "metric": metric,
        "date_from": start.isoformat(),
        "date_to": end.isoformat(),
        **forecast,
    }
