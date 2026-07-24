"""Meta statistical anomaly detection (B11) — z-score over rolling window."""
from __future__ import annotations

import logging
import os
from datetime import date, datetime, timedelta, timezone
from typing import Any

from ptt_jobs.db import pg_connection

logger = logging.getLogger(__name__)

STAT_ANOMALY_TYPES = frozenset({"spend_zscore", "cpl_zscore"})


def _truthy(name: str, default: str = "0") -> bool:
    return os.environ.get(name, default).strip().lower() in {"1", "true", "yes", "on"}


def meta_anomaly_stat_enabled() -> bool:
    return _truthy("PTT_META_ANOMALY_STAT_ENABLED", "0")


def _window_days() -> int:
    raw = os.environ.get("PTT_META_ANOMALY_STAT_WINDOW_DAYS", "14").strip()
    try:
        return max(3, int(raw))
    except ValueError:
        return 14


def _zscore_threshold() -> float:
    raw = os.environ.get("PTT_META_ANOMALY_ZSCORE_THRESHOLD", "2.0").strip()
    try:
        return max(0.5, float(raw))
    except ValueError:
        return 2.0


def compute_zscore(value: float, baseline_values: list[float]) -> float | None:
    cleaned = [v for v in baseline_values if v > 0]
    if len(cleaned) < 3 or value <= 0:
        return None
    mean = sum(cleaned) / len(cleaned)
    variance = sum((v - mean) ** 2 for v in cleaned) / len(cleaned)
    std = variance**0.5
    if std <= 0:
        return None
    return round(((value - mean) / std) * 1000) / 1000


def detect_campaign_stat_anomalies(
    *,
    spend_today: float,
    leads_today: int,
    spend_history: list[float],
    cpl_history: list[float],
    zscore_threshold: float,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []

    spend_z = compute_zscore(spend_today, spend_history)
    if spend_z is not None and spend_z >= zscore_threshold:
        out.append(
            {
                "alert_type": "spend_zscore",
                "severity": "warning",
                "metric_value": spend_today,
                "threshold_value": zscore_threshold,
                "z_score": spend_z,
                "message": f"Spend z-score {spend_z:.2f} (threshold {zscore_threshold:.1f})",
            }
        )

    if leads_today >= 2:
        cpl_today = spend_today / leads_today
        cpl_z = compute_zscore(cpl_today, cpl_history)
        if cpl_z is not None and cpl_z >= zscore_threshold:
            out.append(
                {
                    "alert_type": "cpl_zscore",
                    "severity": "warning",
                    "metric_value": cpl_today,
                    "threshold_value": zscore_threshold,
                    "z_score": cpl_z,
                    "message": f"CPL z-score {cpl_z:.2f} (threshold {zscore_threshold:.1f})",
                }
            )

    return out


def evaluate_stat_anomaly_alerts(
    *,
    client_id: str | None = None,
    performance_date: date | None = None,
) -> dict[str, Any]:
    if not meta_anomaly_stat_enabled():
        return {"ok": True, "skipped": True, "reason": "PTT_META_ANOMALY_STAT_ENABLED=0"}

    try:
        from ptt_crm.pg_schema import pg_meta_alerts_ready

        if not pg_meta_alerts_ready():
            return {"ok": False, "error": "meta_alerts_not_ready"}
    except Exception as exc:
        logger.debug("evaluate_stat_anomaly_alerts readiness: %s", exc)
        return {"ok": False, "error": "meta_alerts_not_ready"}

    perf_date = performance_date or (datetime.now(timezone.utc).date() - timedelta(days=1))
    window = _window_days()
    threshold = _zscore_threshold()
    date_from = perf_date - timedelta(days=window + 1)
    inserted = 0

    clauses = ["dp.channel = 'meta'", "dp.performance_date BETWEEN %s AND %s"]
    values: list[Any] = [date_from, perf_date]
    if client_id:
        clauses.append("dp.client_id = %s::uuid")
        values.append(client_id)

    with pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT dp.client_id::text, dp.external_campaign_id,
                       dp.performance_date::date,
                       SUM(dp.spend) AS spend,
                       SUM(dp.leads_crm) AS leads_crm
                FROM daily_performance dp
                WHERE {' AND '.join(clauses)}
                GROUP BY dp.client_id, dp.external_campaign_id, dp.performance_date
                ORDER BY dp.client_id, dp.external_campaign_id, dp.performance_date DESC
                """,
                values,
            )
            rows = cur.fetchall()

    by_campaign: dict[str, list[tuple[date, float, int]]] = {}
    for client, campaign, day, spend, leads in rows:
        key = f"{client}:{campaign}"
        by_campaign.setdefault(key, []).append((day, float(spend or 0), int(leads or 0)))

    from ptt_meta.alerts import _dedupe_key, _insert_alert

    for key, day_rows in by_campaign.items():
        day_rows.sort(key=lambda r: r[0], reverse=True)
        latest_day, spend_today, leads_today = day_rows[0]
        if latest_day != perf_date:
            continue
        history = day_rows[1 : window + 1]
        spend_history = [r[1] for r in history]
        cpl_history = [r[1] / r[2] for r in history if r[2] > 0]
        client, campaign = key.split(":", 1)
        for item in detect_campaign_stat_anomalies(
            spend_today=spend_today,
            leads_today=leads_today,
            spend_history=spend_history,
            cpl_history=cpl_history,
            zscore_threshold=threshold,
        ):
            dedupe = _dedupe_key(item["alert_type"], client, campaign, perf_date)
            if _insert_alert(
                client_id=client,
                alert_type=item["alert_type"],
                severity=item["severity"],
                message=item["message"],
                dedupe_key=dedupe,
                external_campaign_id=campaign,
                metric_value=item["metric_value"],
                threshold_value=item["threshold_value"],
                performance_date=perf_date,
            ):
                inserted += 1

    return {"ok": True, "inserted": inserted, "performance_date": perf_date.isoformat()}
