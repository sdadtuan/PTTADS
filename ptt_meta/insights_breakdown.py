"""Meta insights breakdown sync (B8.1) — publisher_platform and other Graph breakdowns."""
from __future__ import annotations

import json
import logging
import os
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from ptt_jobs.db import json_dumps, pg_connection

logger = logging.getLogger(__name__)

BREAKDOWN_TYPES = frozenset(
    {"publisher_platform", "platform_position", "age", "gender", "device_platform", "country"}
)
DEFAULT_BREAKDOWN_TYPE = "publisher_platform"


def _truthy(name: str, default: str = "0") -> bool:
    return os.environ.get(name, default).strip().lower() in {"1", "true", "yes", "on"}


def meta_insights_breakdown_enabled() -> bool:
    return _truthy("PTT_META_INSIGHTS_BREAKDOWN", "0")


def pg_daily_performance_breakdown_ready() -> bool:
    try:
        from ptt_crm.pg_schema import pg_daily_performance_breakdown_ready as _ready

        return _ready()
    except Exception:
        return False


def normalize_breakdown_row(
    row: dict[str, Any],
    *,
    breakdown_type: str,
) -> dict[str, Any] | None:
    campaign_id = str(row.get("external_campaign_id") or row.get("campaign_id") or "").strip()
    if not campaign_id:
        return None
    breakdown_value = str(row.get("breakdown_value") or row.get(breakdown_type) or "unknown").strip()
    if not breakdown_value:
        breakdown_value = "unknown"
    spend = float(row.get("spend") or 0)
    return {
        "external_campaign_id": campaign_id,
        "external_campaign_name": str(row.get("external_campaign_name") or row.get("campaign_name") or ""),
        "performance_date": str(row.get("performance_date") or row.get("date_start") or "")[:10],
        "breakdown_type": breakdown_type,
        "breakdown_value": breakdown_value[:64],
        "spend": spend,
        "impressions": int(float(row.get("impressions") or 0)),
        "clicks": int(float(row.get("clicks") or 0)),
        "leads_platform": int(row.get("leads_platform") or 0),
        "raw_insights": row.get("raw_insights") or row,
    }


def upsert_daily_performance_breakdown(record: dict[str, Any]) -> None:
    with pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO daily_performance_breakdown (
                    client_id, channel, external_campaign_id, performance_date,
                    breakdown_type, breakdown_value, spend, impressions, clicks,
                    leads_platform, raw_insights, synced_at
                ) VALUES (
                    %s::uuid, %s, %s, %s::date,
                    %s, %s, %s, %s, %s,
                    %s, %s::jsonb, NOW()
                )
                ON CONFLICT ON CONSTRAINT daily_performance_breakdown_unique
                DO UPDATE SET
                    spend = EXCLUDED.spend,
                    impressions = EXCLUDED.impressions,
                    clicks = EXCLUDED.clicks,
                    leads_platform = EXCLUDED.leads_platform,
                    raw_insights = EXCLUDED.raw_insights,
                    synced_at = NOW()
                """,
                (
                    record["client_id"],
                    record.get("channel") or "meta",
                    record["external_campaign_id"],
                    record["performance_date"],
                    record["breakdown_type"],
                    record["breakdown_value"],
                    Decimal(str(record.get("spend") or 0)),
                    int(record.get("impressions") or 0),
                    int(record.get("clicks") or 0),
                    int(record.get("leads_platform") or 0),
                    json_dumps(record.get("raw_insights") or {}),
                ),
            )
        conn.commit()


def sync_account_breakdown_insights(
    account: dict[str, Any],
    *,
    target_date: date,
    breakdown_type: str = DEFAULT_BREAKDOWN_TYPE,
    stub: bool = False,
) -> dict[str, Any]:
    if not meta_insights_breakdown_enabled():
        return {"ok": True, "skipped": True, "reason": "PTT_META_INSIGHTS_BREAKDOWN=0"}
    if not pg_daily_performance_breakdown_ready():
        return {"ok": False, "error": "daily_performance_breakdown_not_ready"}

    from ptt_meta.graph_insights import fetch_campaign_insights_breakdown, stub_campaign_breakdown_insights
    from ptt_meta.insights_sync import meta_insights_stub_mode
    from ptt_meta.token_vault import normalize_ad_account_id, resolve_meta_access_token

    client_id = str(account["client_id"])
    ad_account_id = normalize_ad_account_id(str(account.get("external_account_id") or ""))
    if not ad_account_id:
        return {"ok": False, "error": "missing_ad_account_id", "upserted": 0}

    day = target_date.isoformat()
    use_stub = stub or meta_insights_stub_mode()
    if use_stub:
        rows = stub_campaign_breakdown_insights(
            since=day,
            until=day,
            ad_account_id=ad_account_id,
            breakdown_type=breakdown_type,
        )
        fetch_error = None
    else:
        token = resolve_meta_access_token(account)
        if not token:
            return {"ok": False, "error": "missing_access_token", "upserted": 0}
        rows, fetch_error = fetch_campaign_insights_breakdown(
            ad_account_id=ad_account_id,
            access_token=token,
            since=day,
            until=day,
            breakdown_type=breakdown_type,
        )
        if fetch_error:
            return {"ok": False, "error": fetch_error, "upserted": 0}

    upserted = 0
    for raw in rows:
        normalized = normalize_breakdown_row(raw, breakdown_type=breakdown_type)
        if not normalized:
            continue
        upsert_daily_performance_breakdown(
            {
                "client_id": client_id,
                "channel": "meta",
                **normalized,
            }
        )
        upserted += 1

    return {"ok": True, "upserted": upserted, "breakdown_type": breakdown_type}


def list_breakdown_rows(
    *,
    client_id: str | None = None,
    external_campaign_id: str | None = None,
    breakdown_type: str = DEFAULT_BREAKDOWN_TYPE,
    date_from: date,
    date_to: date,
    limit: int = 500,
) -> list[dict[str, Any]]:
    if not pg_daily_performance_breakdown_ready():
        return []

    clauses = [
        "dpb.channel = 'meta'",
        "dpb.breakdown_type = %s",
        "dpb.performance_date BETWEEN %s AND %s",
    ]
    values: list[Any] = [breakdown_type, date_from, date_to]
    if client_id:
        clauses.append("dpb.client_id = %s::uuid")
        values.append(client_id)
    if external_campaign_id:
        clauses.append("dpb.external_campaign_id = %s")
        values.append(external_campaign_id)
    values.append(min(max(limit, 1), 2000))

    with pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT dpb.client_id::text, dpb.external_campaign_id, dpb.performance_date::date,
                       dpb.breakdown_type, dpb.breakdown_value,
                       dpb.spend, dpb.impressions, dpb.clicks, dpb.leads_platform
                FROM daily_performance_breakdown dpb
                WHERE {' AND '.join(clauses)}
                ORDER BY dpb.performance_date DESC, dpb.spend DESC
                LIMIT %s
                """,
                values,
            )
            rows = cur.fetchall()

    return [
        {
            "client_id": r[0],
            "external_campaign_id": r[1],
            "performance_date": r[2].isoformat() if hasattr(r[2], "isoformat") else str(r[2]),
            "breakdown_type": r[3],
            "breakdown_value": r[4],
            "spend": float(r[5] or 0),
            "impressions": int(r[6] or 0),
            "clicks": int(r[7] or 0),
            "leads_platform": int(r[8] or 0),
        }
        for r in rows
    ]


def campaign_spend_total(
    *,
    client_id: str | None,
    external_campaign_id: str,
    date_from: date,
    date_to: date,
) -> float:
    clauses = [
        "dp.channel = 'meta'",
        "dp.external_campaign_id = %s",
        "dp.performance_date BETWEEN %s AND %s",
    ]
    values: list[Any] = [external_campaign_id, date_from, date_to]
    if client_id:
        clauses.append("dp.client_id = %s::uuid")
        values.append(client_id)

    with pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT COALESCE(SUM(dp.spend), 0)
                FROM daily_performance dp
                WHERE {' AND '.join(clauses)}
                """,
                values,
            )
            return float(cur.fetchone()[0] or 0)


def query_breakdown_summary(
    *,
    client_id: str | None = None,
    external_campaign_id: str | None = None,
    breakdown_type: str = DEFAULT_BREAKDOWN_TYPE,
    date_from: date,
    date_to: date,
) -> dict[str, Any]:
    rows = list_breakdown_rows(
        client_id=client_id,
        external_campaign_id=external_campaign_id,
        breakdown_type=breakdown_type,
        date_from=date_from,
        date_to=date_to,
    )
    breakdown_spend = sum(r["spend"] for r in rows)
    total_spend = 0.0
    if external_campaign_id:
        total_spend = campaign_spend_total(
            client_id=client_id,
            external_campaign_id=external_campaign_id,
            date_from=date_from,
            date_to=date_to,
        )
    delta_pct: float | None = None
    if total_spend > 0:
        delta_pct = round(((breakdown_spend - total_spend) / total_spend) * 1000) / 10

    return {
        "ok": True,
        "breakdown_type": breakdown_type,
        "date_from": date_from.isoformat(),
        "date_to": date_to.isoformat(),
        "rows": rows,
        "count": len(rows),
        "total_spend": round(total_spend * 100) / 100,
        "breakdown_spend": round(breakdown_spend * 100) / 100,
        "spend_delta_pct": delta_pct,
    }
