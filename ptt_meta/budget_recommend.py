"""Meta budget recommendations (B10) — read-only heuristics."""
from __future__ import annotations

import os
from datetime import date, datetime, timedelta, timezone
from typing import Any

from ptt_jobs.db import pg_connection
from ptt_meta.roas import compute_roas


def _truthy(name: str, default: str = "0") -> bool:
    return os.environ.get(name, default).strip().lower() in {"1", "true", "yes", "on"}


def meta_budget_recommend_enabled() -> bool:
    return _truthy("PTT_META_ROAS_ENABLED", "0") or _truthy("PTT_META_ANOMALY_ENABLED", "0")


def _decrease_pct() -> float:
    raw = os.environ.get("PTT_META_BUDGET_RECOMMEND_DECREASE_PCT", "15").strip()
    try:
        return max(1.0, float(raw))
    except ValueError:
        return 15.0


def _increase_pct() -> float:
    raw = os.environ.get("PTT_META_BUDGET_RECOMMEND_INCREASE_PCT", "10").strip()
    try:
        return max(1.0, float(raw))
    except ValueError:
        return 10.0


def _cpl_over_target_ratio() -> float:
    raw = os.environ.get("PTT_META_BUDGET_RECOMMEND_CPL_OVER", "1.15").strip()
    try:
        return max(1.0, float(raw))
    except ValueError:
        return 1.15


def _cpl_under_target_ratio() -> float:
    raw = os.environ.get("PTT_META_BUDGET_RECOMMEND_CPL_UNDER", "0.85").strip()
    try:
        return max(0.1, float(raw))
    except ValueError:
        return 0.85


def recommend_budget_change(
    *,
    avg_daily_spend: float,
    cpl: float | None,
    target_cpl: float | None,
    leads: int,
    roas: float | None,
    decrease_pct: float,
    increase_pct: float,
    cpl_over_ratio: float,
    cpl_under_ratio: float,
) -> dict[str, Any] | None:
    """Pure recommendation logic for one campaign window."""
    if avg_daily_spend <= 0 or cpl is None or target_cpl is None or target_cpl <= 0:
        return None

    if cpl > target_cpl * cpl_over_ratio and leads >= 2:
        suggested = round(avg_daily_spend * (1.0 - decrease_pct / 100.0))
        return {
            "recommendation_type": "decrease_budget",
            "change_pct": -decrease_pct,
            "suggested_daily_budget_vnd": max(0, suggested),
            "rationale": f"CPL {cpl:,.0f} VND vượt target {target_cpl:,.0f} — giảm ngân sách {decrease_pct:.0f}%",
            "write_request": {
                "change_type": "daily_budget",
                "daily_budget_vnd": max(0, suggested),
            },
        }

    if cpl < target_cpl * cpl_under_ratio and leads >= 3 and (roas is None or roas >= 1.0):
        suggested = round(avg_daily_spend * (1.0 + increase_pct / 100.0))
        return {
            "recommendation_type": "increase_budget",
            "change_pct": increase_pct,
            "suggested_daily_budget_vnd": suggested,
            "rationale": f"CPL {cpl:,.0f} VND dưới target {target_cpl:,.0f} — tăng ngân sách {increase_pct:.0f}%",
            "write_request": {
                "change_type": "daily_budget",
                "daily_budget_vnd": suggested,
            },
        }

    return None


def fetch_budget_recommendations(
    *,
    client_id: str | None = None,
    window_days: int = 7,
) -> dict[str, Any]:
    if not meta_budget_recommend_enabled():
        return {"ok": True, "disabled": True, "recommendations": [], "count": 0}

    date_to = datetime.now(timezone.utc).date() - timedelta(days=1)
    date_from = date_to - timedelta(days=max(1, window_days) - 1)

    client_filter = ""
    params: list[Any] = [date_from, date_to]
    if client_id:
        client_filter = "AND dp.client_id = %s::uuid"
        params.append(client_id)

    decrease_pct = _decrease_pct()
    increase_pct = _increase_pct()
    cpl_over = _cpl_over_target_ratio()
    cpl_under = _cpl_under_target_ratio()

    with pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT dp.client_id::text,
                       c.code,
                       c.name,
                       dp.external_campaign_id,
                       MAX(hcm.external_campaign_name) AS campaign_name,
                       SUM(dp.spend) AS spend,
                       SUM(dp.leads_crm) AS leads_crm,
                       SUM(dp.conversion_value) AS conversion_value,
                       MAX(hcm.target_cpl_vnd) AS target_cpl_vnd,
                       COUNT(DISTINCT dp.performance_date) AS day_count
                FROM daily_performance dp
                JOIN clients c ON c.id = dp.client_id
                LEFT JOIN hub_campaign_map hcm ON hcm.id = dp.hub_campaign_map_id
                WHERE dp.channel = 'meta'
                  AND dp.performance_date BETWEEN %s::date AND %s::date
                  {client_filter}
                GROUP BY dp.client_id, c.code, c.name, dp.external_campaign_id
                HAVING SUM(dp.spend) > 0
                """,
                params,
            )
            rows = cur.fetchall()

    recommendations: list[dict[str, Any]] = []
    for row in rows:
        spend = float(row[5] or 0)
        leads = int(row[6] or 0)
        conv = float(row[7] or 0)
        target = row[8]
        day_count = int(row[9] or 1)
        if target is None or leads <= 0:
            continue
        target_f = float(target)
        cpl = spend / leads
        avg_daily = spend / max(day_count, 1)
        roas = compute_roas(conv, spend)
        rec = recommend_budget_change(
            avg_daily_spend=avg_daily,
            cpl=cpl,
            target_cpl=target_f,
            leads=leads,
            roas=roas,
            decrease_pct=decrease_pct,
            increase_pct=increase_pct,
            cpl_over_ratio=cpl_over,
            cpl_under_ratio=cpl_under,
        )
        if not rec:
            continue
        camp_id = str(row[3] or "")
        write_req = dict(rec["write_request"])
        write_req["external_campaign_id"] = camp_id
        recommendations.append(
            {
                "client_id": str(row[0]),
                "client_code": row[1],
                "client_name": row[2],
                "external_campaign_id": camp_id or None,
                "external_campaign_name": row[4],
                "recommendation_type": rec["recommendation_type"],
                "current_daily_spend_vnd": round(avg_daily, 2),
                "suggested_daily_budget_vnd": rec["suggested_daily_budget_vnd"],
                "change_pct": rec["change_pct"],
                "rationale": rec["rationale"],
                "write_request": write_req,
            }
        )

    return {
        "ok": True,
        "date_from": date_from.isoformat(),
        "date_to": date_to.isoformat(),
        "recommendations": recommendations,
        "count": len(recommendations),
        "read_only": True,
    }
