"""B10 daily insights read API helpers — campaign / adset granularity."""
from __future__ import annotations

import os
from datetime import date, datetime, timedelta, timezone
from typing import Any

from ptt_jobs.db import pg_connection

VALID_LEVELS = frozenset({"campaign", "adset", "ad"})


def insights_level_enabled() -> str:
    raw = (os.environ.get("PTT_META_INSIGHTS_LEVEL") or "campaign").strip().lower()
    return raw if raw in VALID_LEVELS else "campaign"


def pg_insight_level_column_ready() -> bool:
    try:
        with pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT 1 FROM information_schema.columns
                    WHERE table_schema = 'public'
                      AND table_name = 'daily_performance'
                      AND column_name = 'insight_level'
                    LIMIT 1
                    """
                )
                return cur.fetchone() is not None
    except Exception:
        return False


def fetch_daily_insights(
    *,
    level: str = "campaign",
    client_id: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    default_days: int = 7,
    limit: int = 500,
) -> dict[str, Any]:
    level_norm = (level or "campaign").strip().lower()
    if level_norm not in VALID_LEVELS:
        return {"ok": False, "error": "invalid_insight_level", "level": level_norm}

    enabled_level = insights_level_enabled()
    if level_norm != "campaign" and enabled_level != level_norm:
        return {
            "ok": True,
            "disabled": True,
            "level": level_norm,
            "enabled_level": enabled_level,
            "rows": [],
            "count": 0,
        }

    if not pg_insight_level_column_ready():
        if level_norm != "campaign":
            return {
                "ok": True,
                "disabled": True,
                "level": level_norm,
                "reason": "insight_level_column_not_ready",
                "rows": [],
                "count": 0,
                "hint": "./scripts/apply_pg_ddl_v6_meta_insights_level.sh",
            }
        level_norm = "campaign"

    if date_to is None:
        date_to = datetime.now(timezone.utc).date() - timedelta(days=1)
    if date_from is None:
        date_from = date_to - timedelta(days=max(1, default_days) - 1)

    clauses = [
        "dp.channel = 'meta'",
        "dp.performance_date BETWEEN %s::date AND %s::date",
    ]
    params: list[Any] = [date_from, date_to]

    if pg_insight_level_column_ready():
        clauses.append("dp.insight_level = %s")
        params.append(level_norm)
    if client_id:
        clauses.append("dp.client_id = %s::uuid")
        params.append(client_id)

    params.append(min(max(limit, 1), 2000))

    adset_cols = ""
    if pg_insight_level_column_ready():
        adset_cols = ", dp.external_adset_id, dp.external_adset_name, dp.insight_level"

    with pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT dp.client_id::text,
                       c.code AS client_code,
                       c.name AS client_name,
                       dp.external_campaign_id,
                       dp.external_campaign_name,
                       dp.performance_date::date,
                       dp.spend,
                       dp.impressions,
                       dp.clicks,
                       dp.leads_crm,
                       dp.conversion_value
                       {adset_cols}
                FROM daily_performance dp
                JOIN clients c ON c.id = dp.client_id
                WHERE {' AND '.join(clauses)}
                ORDER BY dp.performance_date DESC, dp.spend DESC
                LIMIT %s
                """,
                params,
            )
            raw_rows = cur.fetchall()
            cols = [d[0] for d in cur.description]

    rows: list[dict[str, Any]] = []
    for raw in raw_rows:
        item = dict(zip(cols, raw))
        rows.append(
            {
                "client_id": str(item["client_id"]),
                "client_code": item.get("client_code"),
                "client_name": item.get("client_name"),
                "external_campaign_id": item.get("external_campaign_id"),
                "external_campaign_name": item.get("external_campaign_name"),
                "performance_date": str(item["performance_date"]),
                "spend": float(item.get("spend") or 0),
                "impressions": int(item.get("impressions") or 0),
                "clicks": int(item.get("clicks") or 0),
                "leads_crm": int(item.get("leads_crm") or 0),
                "conversion_value": float(item.get("conversion_value") or 0),
                "external_adset_id": item.get("external_adset_id"),
                "external_adset_name": item.get("external_adset_name"),
                "insight_level": item.get("insight_level") or level_norm,
            }
        )

    return {
        "ok": True,
        "level": level_norm,
        "enabled_level": enabled_level,
        "date_from": date_from.isoformat(),
        "date_to": date_to.isoformat(),
        "rows": rows,
        "count": len(rows),
    }
