"""Meta anomaly detection (B10) — median spike rules + meta_alerts."""
from __future__ import annotations

import logging
import os
from datetime import date, datetime, timedelta, timezone
from statistics import median
from typing import Any

from ptt_jobs.db import pg_connection

logger = logging.getLogger(__name__)

ANOMALY_TYPES = frozenset({"spend_spike", "cpl_spike", "roas_low"})


def _truthy(name: str, default: str = "0") -> bool:
    return os.environ.get(name, default).strip().lower() in {"1", "true", "yes", "on"}


def meta_anomaly_enabled() -> bool:
    return _truthy("PTT_META_ANOMALY_ENABLED", "0")


def _spike_pct() -> float:
    raw = os.environ.get("PTT_META_ANOMALY_SPIKE_PCT", "50").strip()
    try:
        return max(0.0, float(raw))
    except ValueError:
        return 50.0


def _window_days() -> int:
    raw = os.environ.get("PTT_META_ANOMALY_WINDOW_DAYS", "7").strip()
    try:
        return max(2, int(raw))
    except ValueError:
        return 7


def _roas_min_target() -> float:
    raw = os.environ.get("PTT_META_ROAS_MIN_TARGET", "3").strip()
    try:
        return max(0.0, float(raw))
    except ValueError:
        return 3.0


def _roas_min_spend() -> float:
    raw = os.environ.get("PTT_META_ROAS_MIN_SPEND_VND", "500000").strip()
    try:
        return max(0.0, float(raw))
    except ValueError:
        return 500_000.0


def compute_spike_pct(current: float, baseline_median: float) -> float | None:
    if baseline_median <= 0 or current <= baseline_median:
        return None
    return round(((current - baseline_median) / baseline_median) * 1000) / 10


def is_median_spike(current: float, baseline_values: list[float], spike_pct: float) -> tuple[bool, float | None]:
    """Return (is_spike, baseline_median)."""
    cleaned = [v for v in baseline_values if v > 0]
    if not cleaned or current <= 0:
        return False, None
    base = float(median(cleaned))
    if base <= 0:
        return False, None
    threshold = base * (1.0 + spike_pct / 100.0)
    return current > threshold, base


def detect_campaign_anomalies(
    *,
    perf_date: date,
    spend_today: float,
    leads_today: int,
    conversion_value_today: float,
    spend_history: list[float],
    cpl_history: list[float],
    spike_pct: float,
    roas_min_target: float,
    roas_min_spend: float,
) -> list[dict[str, Any]]:
    """Pure anomaly detection for one campaign/day."""
    out: list[dict[str, Any]] = []

    spend_spike, spend_median = is_median_spike(spend_today, spend_history, spike_pct)
    if spend_spike and spend_median is not None:
        pct = compute_spike_pct(spend_today, spend_median)
        out.append(
            {
                "alert_type": "spend_spike",
                "severity": "warning",
                "metric_value": spend_today,
                "threshold_value": spend_median * (1.0 + spike_pct / 100.0),
                "spike_pct": pct,
                "message": f"Spend spike {pct:.1f}% vs median 7d ({spend_today:,.0f} VND)",
            }
        )

    if leads_today >= 2:
        cpl_today = spend_today / leads_today if leads_today > 0 else 0.0
        cpl_spike, cpl_median = is_median_spike(cpl_today, cpl_history, spike_pct)
        if cpl_spike and cpl_median is not None:
            pct = compute_spike_pct(cpl_today, cpl_median)
            out.append(
                {
                    "alert_type": "cpl_spike",
                    "severity": "warning",
                    "metric_value": cpl_today,
                    "threshold_value": cpl_median * (1.0 + spike_pct / 100.0),
                    "spike_pct": pct,
                    "message": f"CPL spike {pct:.1f}% vs median 7d ({cpl_today:,.0f} VND)",
                }
            )

    if spend_today >= roas_min_spend and conversion_value_today > 0:
        roas = conversion_value_today / spend_today
        if roas < roas_min_target:
            out.append(
                {
                    "alert_type": "roas_low",
                    "severity": "warning",
                    "metric_value": round(roas, 4),
                    "threshold_value": roas_min_target,
                    "spike_pct": None,
                    "message": f"ROAS {roas:.2f} dưới ngưỡng {roas_min_target:.2f}",
                }
            )

    return out


def evaluate_anomaly_alerts(
    *,
    client_id: str | None = None,
    performance_date: date | str | None = None,
) -> dict[str, Any]:
    """Evaluate B10 median anomalies and insert deduped rows into meta_alerts."""
    if not meta_anomaly_enabled():
        return {"ok": True, "skipped": True, "reason": "anomaly_disabled"}

    from ptt_meta.alerts import _dedupe_key, _insert_alert, pg_meta_alerts_ready

    if not pg_meta_alerts_ready():
        return {"ok": False, "error": "meta_alerts_table_not_ready"}

    if performance_date is None:
        perf_date = datetime.now(timezone.utc).date() - timedelta(days=1)
    elif isinstance(performance_date, date):
        perf_date = performance_date
    else:
        perf_date = date.fromisoformat(str(performance_date)[:10])

    spike_pct = _spike_pct()
    window_days = _window_days()
    roas_min = _roas_min_target()
    roas_min_spend = _roas_min_spend()
    history_start = perf_date - timedelta(days=window_days)
    history_end = perf_date - timedelta(days=1)
    created = 0

    client_filter = ""
    params: list[Any] = [history_start, history_end, perf_date]
    if client_id:
        client_filter = "AND dp.client_id = %s::uuid"
        params.append(client_id)

    with pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT dp.client_id::text,
                       dp.external_campaign_id,
                       dp.performance_date::date,
                       SUM(dp.spend) AS spend,
                       SUM(dp.leads_crm) AS leads_crm,
                       SUM(dp.conversion_value) AS conversion_value
                FROM daily_performance dp
                WHERE dp.channel = 'meta'
                  AND dp.performance_date BETWEEN %s::date AND %s::date
                  {client_filter}
                GROUP BY dp.client_id, dp.external_campaign_id, dp.performance_date
                """,
                params,
            )
            rows = cur.fetchall()

    by_campaign: dict[tuple[str, str], list[tuple[date, float, int, float]]] = {}
    for row in rows:
        key = (str(row[0]), str(row[1] or ""))
        by_campaign.setdefault(key, []).append(
            (row[2], float(row[3] or 0), int(row[4] or 0), float(row[5] or 0))
        )

    for (cid, camp_id), day_rows in by_campaign.items():
        today_row = next((r for r in day_rows if r[0] == perf_date), None)
        if not today_row:
            continue
        spend_today, leads_today, conv_today = today_row[1], today_row[2], today_row[3]
        history = [r for r in day_rows if r[0] < perf_date]
        spend_history = [r[1] for r in history]
        cpl_history = [r[1] / r[2] for r in history if r[2] > 0]

        anomalies = detect_campaign_anomalies(
            perf_date=perf_date,
            spend_today=spend_today,
            leads_today=leads_today,
            conversion_value_today=conv_today,
            spend_history=spend_history,
            cpl_history=cpl_history,
            spike_pct=spike_pct,
            roas_min_target=roas_min,
            roas_min_spend=roas_min_spend,
        )
        for item in anomalies:
            alert_type = str(item["alert_type"])
            key = _dedupe_key(alert_type, cid, camp_id, perf_date)
            if _insert_alert(
                client_id=cid,
                alert_type=alert_type,
                severity=str(item.get("severity") or "warning"),
                message=str(item.get("message") or alert_type),
                dedupe_key=key,
                external_campaign_id=camp_id or None,
                metric_value=item.get("metric_value"),
                threshold_value=item.get("threshold_value"),
                performance_date=perf_date,
            ):
                created += 1

    return {"ok": True, "alerts_created": created, "performance_date": perf_date.isoformat()}


def list_anomalies_from_db(
    *,
    client_id: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """Read B10 anomaly rows from meta_alerts for API parity."""
    if not meta_anomaly_enabled():
        return []

    from ptt_meta.alerts import pg_meta_alerts_ready

    if not pg_meta_alerts_ready():
        return []

    clauses = ["ma.channel = 'meta'", "ma.alert_type = ANY(%s)"]
    params: list[Any] = [list(ANOMALY_TYPES)]
    if client_id:
        clauses.append("ma.client_id = %s::uuid")
        params.append(client_id)
    params.append(min(max(limit, 1), 500))

    with pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT ma.*, c.code AS client_code, c.name AS client_name
                FROM meta_alerts ma
                JOIN clients c ON c.id = ma.client_id
                WHERE {' AND '.join(clauses)}
                ORDER BY ma.created_at DESC
                LIMIT %s
                """,
                params,
            )
            rows = cur.fetchall()

    out: list[dict[str, Any]] = []
    cols = [
        "id",
        "client_id",
        "channel",
        "external_campaign_id",
        "alert_type",
        "severity",
        "metric_value",
        "threshold_value",
        "message",
        "performance_date",
        "dedupe_key",
        "acknowledged_at",
        "created_at",
        "client_code",
        "client_name",
    ]
    for row in rows:
        data = dict(zip(cols, row))
        out.append(
            {
                "id": str(data["id"]),
                "client_id": str(data["client_id"]),
                "external_campaign_id": data["external_campaign_id"],
                "alert_type": data["alert_type"],
                "severity": data["severity"],
                "metric_value": float(data["metric_value"]) if data["metric_value"] is not None else None,
                "threshold_value": float(data["threshold_value"]) if data["threshold_value"] is not None else None,
                "message": data["message"],
                "performance_date": str(data["performance_date"])[:10] if data["performance_date"] else None,
                "created_at": data["created_at"].isoformat() if data["created_at"] else None,
                "client_code": data["client_code"],
                "client_name": data["client_name"],
            }
        )
    return out
