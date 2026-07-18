"""Campaign performance read API — daily_performance + CPL (Phase 2 M3/M6)."""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from ptt_jobs.db import pg_connection

logger = logging.getLogger(__name__)


def _parse_date(value: str | None, default: date) -> date:
    if not value or not str(value).strip():
        return default
    return date.fromisoformat(str(value).strip()[:10])


def _iso(value: Any) -> str | None:
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _decimal(value: Any) -> float:
    if value is None:
        return 0.0
    return float(Decimal(str(value)))


def compute_cpl(spend: float, leads: int) -> float | None:
    if spend <= 0:
        return None
    if leads <= 0:
        return None
    return round(spend / leads, 2)


def compute_roas(conversion_value: float, spend: float) -> float | None:
    """
    ROAS = conversion_value / spend.

    When conversion_value is 0 (no CAPI Purchase / CRM revenue yet), returns None
    and callers should set roas_stub=True — do not treat as 0× ROAS.
    """
    if spend <= 0:
        return None
    if conversion_value <= 0:
        return None
    return round(conversion_value / spend, 4)


def pg_performance_ready() -> bool:
    try:
        from ptt_crm.pg_schema import pg_v3_ready

        return pg_v3_ready()
    except Exception as exc:
        logger.debug("pg_performance_ready: %s", exc)
        return False


def _date_window(
    *,
    date_from: str | None,
    date_to: str | None,
    default_days: int = 7,
) -> tuple[date, date]:
    today = datetime.now(timezone.utc).date()
    end = _parse_date(date_to, today - timedelta(days=1))
    start_default = end - timedelta(days=max(1, default_days) - 1)
    start = _parse_date(date_from, start_default)
    if start > end:
        start, end = end, start
    return start, end


def _row_to_performance(rec: dict[str, Any]) -> dict[str, Any]:
    spend = _decimal(rec.get("spend"))
    leads_crm = int(rec.get("leads_crm") or 0)
    leads_platform = int(rec.get("leads_platform") or 0)
    cpl = rec.get("cpl_snapshot")
    if cpl is not None:
        cpl_val = round(float(cpl), 2)
    else:
        cpl_val = compute_cpl(spend, leads_crm)

    target = rec.get("target_cpl_vnd")
    target_val = round(float(target), 2) if target is not None else None
    delta_pct = None
    delta_vnd = None
    if cpl_val is not None and target_val is not None and target_val > 0:
        delta_vnd = round(cpl_val - target_val, 2)
        delta_pct = round((cpl_val - target_val) / target_val * 100, 1)

    conv_value = _decimal(rec.get("conversion_value"))
    spend_for_roas = spend
    roas_snap = rec.get("roas_snapshot")
    if roas_snap is not None:
        roas_val = round(float(roas_snap), 4)
        roas_stub = False
    else:
        roas_val = compute_roas(conv_value, spend_for_roas)
        roas_stub = roas_val is None and spend_for_roas > 0

    hub_id = rec.get("hub_campaign_id")
    channel = str(rec.get("channel") or "meta").strip().lower()
    return {
        "performance_date": _iso(rec.get("performance_date")),
        "channel": channel,
        "external_campaign_id": rec.get("external_campaign_id"),
        "external_campaign_name": rec.get("external_campaign_name"),
        "spend": spend,
        "currency": rec.get("currency") or "VND",
        "impressions": int(rec.get("impressions") or 0),
        "clicks": int(rec.get("clicks") or 0),
        "leads_crm": leads_crm,
        "leads_platform": leads_platform,
        "cpl": cpl_val,
        "target_cpl_vnd": target_val,
        "cpl_delta_vnd": delta_vnd,
        "cpl_delta_pct": delta_pct,
        "conversion_value": conv_value,
        "roas": roas_val,
        "roas_stub": roas_stub,
        "hub_campaign_map_id": str(rec["hub_campaign_map_id"]) if rec.get("hub_campaign_map_id") else None,
        "hub_campaign_id": int(hub_id) if hub_id is not None else None,
        "hub_mapped": bool(rec.get("hub_campaign_map_id")),
        "hub_url": f"/crm/hub?campaign_id={int(hub_id)}" if hub_id is not None else "/crm/hub",
        "synced_at": _iso(rec.get("synced_at")),
    }


def list_campaign_performance(
    *,
    client_id: str,
    date_from: str | None = None,
    date_to: str | None = None,
    group_by: str = "day",
) -> dict[str, Any]:
    """
    Read daily_performance joined with hub map + CPL snapshots.

    group_by: day (default) | campaign — aggregate by campaign over the window.
    """
    if not pg_performance_ready():
        return {"ok": False, "error": "performance_tables_not_ready"}

    start, end = _date_window(date_from=date_from, date_to=date_to)
    group = (group_by or "day").strip().lower()
    if group not in {"day", "campaign"}:
        group = "day"

    with pg_connection() as conn:
        with conn.cursor() as cur:
            if group == "campaign":
                cur.execute(
                    """
                    SELECT
                        dp.external_campaign_id,
                        MAX(dp.channel) AS channel,
                        MAX(dp.external_campaign_name) AS external_campaign_name,
                        SUM(dp.spend) AS spend,
                        MAX(dp.currency) AS currency,
                        SUM(dp.impressions) AS impressions,
                        SUM(dp.clicks) AS clicks,
                        SUM(dp.leads_crm) AS leads_crm,
                        SUM(dp.leads_platform) AS leads_platform,
                        SUM(dp.conversion_value) AS conversion_value,
                        MAX(dp.hub_campaign_map_id) AS hub_campaign_map_id,
                        MAX(hcm.hub_campaign_id) AS hub_campaign_id,
                        MAX(hcm.target_cpl_vnd) AS target_cpl_vnd,
                        MAX(dp.synced_at) AS synced_at,
                        CASE
                            WHEN SUM(dp.leads_crm) > 0 THEN SUM(dp.spend) / SUM(dp.leads_crm)
                            ELSE NULL
                        END AS cpl_snapshot,
                        CASE
                            WHEN SUM(dp.spend) > 0 AND SUM(dp.conversion_value) > 0
                            THEN SUM(dp.conversion_value) / SUM(dp.spend)
                            ELSE NULL
                        END AS roas_snapshot
                    FROM daily_performance dp
                    LEFT JOIN hub_campaign_map hcm ON hcm.id = dp.hub_campaign_map_id
                    WHERE dp.client_id = %s::uuid
                      AND dp.channel IN ('meta', 'google')
                      AND dp.performance_date BETWEEN %s AND %s
                    GROUP BY dp.external_campaign_id
                    ORDER BY SUM(dp.spend) DESC, dp.external_campaign_id
                    """,
                    (client_id, start, end),
                )
            else:
                cur.execute(
                    """
                    SELECT
                        dp.performance_date,
                        dp.channel,
                        dp.external_campaign_id,
                        dp.external_campaign_name,
                        dp.spend,
                        dp.currency,
                        dp.impressions,
                        dp.clicks,
                        dp.leads_crm,
                        dp.leads_platform,
                        dp.conversion_value,
                        dp.hub_campaign_map_id,
                        hcm.hub_campaign_id,
                        hcm.target_cpl_vnd,
                        dp.synced_at,
                        ms.value_numeric AS cpl_snapshot,
                        ms_roas.value_numeric AS roas_snapshot
                    FROM daily_performance dp
                    LEFT JOIN hub_campaign_map hcm ON hcm.id = dp.hub_campaign_map_id
                    LEFT JOIN metrics_snapshots ms
                        ON ms.client_id = dp.client_id
                       AND ms.kpi_code = 'CPL'
                       AND ms.channel = dp.channel
                       AND COALESCE(ms.external_campaign_id, '') = dp.external_campaign_id
                       AND ms.period_start = dp.performance_date
                       AND ms.period_end = dp.performance_date
                       AND ms.granularity = 'day'
                    LEFT JOIN metrics_snapshots ms_roas
                        ON ms_roas.client_id = dp.client_id
                       AND ms_roas.kpi_code = 'ROAS'
                       AND ms_roas.channel = dp.channel
                       AND COALESCE(ms_roas.external_campaign_id, '') = dp.external_campaign_id
                       AND ms_roas.period_start = dp.performance_date
                       AND ms_roas.period_end = dp.performance_date
                       AND ms_roas.granularity = 'day'
                    WHERE dp.client_id = %s::uuid
                      AND dp.channel IN ('meta', 'google')
                      AND dp.performance_date BETWEEN %s AND %s
                    ORDER BY dp.performance_date DESC, dp.external_campaign_name NULLS LAST
                    """,
                    (client_id, start, end),
                )

            cols = [d[0] for d in cur.description]
            rows = [_row_to_performance(dict(zip(cols, row))) for row in cur.fetchall()]

            cur.execute(
                """
                SELECT MAX(performance_date), MAX(synced_at), COUNT(DISTINCT external_campaign_id)
                FROM daily_performance
                WHERE client_id = %s::uuid AND channel IN ('meta', 'google')
                """,
                (client_id,),
            )
            latest_date, latest_sync, campaign_count = cur.fetchone()

    total_spend = sum(r["spend"] for r in rows)
    total_leads = sum(r["leads_crm"] for r in rows)
    total_conv = sum(r.get("conversion_value") or 0 for r in rows)
    mapped_rows = [r for r in rows if r.get("hub_mapped")]
    over_target = [
        r for r in mapped_rows
        if r.get("cpl") is not None and r.get("target_cpl_vnd") is not None
        and r["cpl"] > r["target_cpl_vnd"]
    ]

    return {
        "ok": True,
        "client_id": client_id,
        "date_from": start.isoformat(),
        "date_to": end.isoformat(),
        "group_by": group,
        "rows": rows,
        "summary": {
            "row_count": len(rows),
            "total_spend": round(total_spend, 2),
            "total_leads_crm": total_leads,
            "avg_cpl": compute_cpl(total_spend, total_leads),
            "total_conversion_value": round(total_conv, 2),
            "avg_roas": compute_roas(total_conv, total_spend),
            "roas_stub": compute_roas(total_conv, total_spend) is None and total_spend > 0,
            "latest_performance_date": _iso(latest_date),
            "latest_synced_at": _iso(latest_sync),
            "campaigns_tracked": int(campaign_count or 0),
            "mapped_rows": len(mapped_rows),
            "over_target_rows": len(over_target),
        },
    }
