"""Derived KPI metrics engine (Phase 2 M4)."""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from ptt_jobs.db import pg_connection

logger = logging.getLogger(__name__)


def _target_date(value: date | str | None = None) -> date:
    if value is None:
        return datetime.now(timezone.utc).date() - timedelta(days=1)
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def compute_cpl_snapshots(
    *,
    target_date: date | str | None = None,
    client_id: str | None = None,
) -> dict[str, Any]:
    """
    Compute CPL = spend / NULLIF(leads_crm, 0) per campaign/day.
    Upserts metrics_snapshots (kpi_code=CPL) and refreshes leads_crm on daily_performance.
    """
    perf_date = _target_date(target_date)
    refreshed = refresh_leads_crm_counts(target_date=perf_date, client_id=client_id)

    clauses = ["performance_date = %s", "channel = 'meta'"]
    params: list[Any] = [perf_date]
    if client_id:
        clauses.append("client_id = %s::uuid")
        params.append(client_id)

    where = " AND ".join(clauses)
    computed = 0
    with pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT id, client_id, external_campaign_id, hub_campaign_map_id,
                       spend, leads_crm, currency
                FROM daily_performance
                WHERE {where}
                """,
                params,
            )
            rows = cur.fetchall()
            cols = [d[0] for d in cur.description]
            for row in rows:
                rec = dict(zip(cols, row))
                spend = Decimal(str(rec.get("spend") or 0))
                leads = int(rec.get("leads_crm") or 0)
                if spend <= 0:
                    continue
                cpl = float(spend / leads) if leads > 0 else 0.0
                ext = str(rec.get("external_campaign_id") or "")
                cur.execute(
                    """
                    DELETE FROM metrics_snapshots
                    WHERE client_id = %s::uuid
                      AND kpi_code = 'CPL'
                      AND channel = 'meta'
                      AND COALESCE(external_campaign_id, '') = %s
                      AND period_start = %s
                      AND period_end = %s
                      AND granularity = 'day'
                    """,
                    (str(rec["client_id"]), ext, perf_date, perf_date),
                )
                cur.execute(
                    """
                    INSERT INTO metrics_snapshots (
                        client_id, kpi_code, channel, external_campaign_id,
                        hub_campaign_map_id, period_start, period_end, granularity,
                        value_numeric, value_json
                    ) VALUES (
                        %s::uuid, 'CPL', 'meta', %s, %s::uuid,
                        %s, %s, 'day', %s,
                        jsonb_build_object(
                            'spend', %s::numeric,
                            'leads_crm', %s,
                            'currency', %s
                        )
                    )
                    """,
                    (
                        str(rec["client_id"]),
                        rec.get("external_campaign_id"),
                        str(rec["hub_campaign_map_id"]) if rec.get("hub_campaign_map_id") else None,
                        perf_date,
                        perf_date,
                        cpl,
                        spend,
                        leads,
                        rec.get("currency") or "VND",
                    ),
                )
                computed += 1
        conn.commit()

    return {
        "ok": True,
        "performance_date": perf_date.isoformat(),
        "leads_crm_refreshed": refreshed,
        "cpl_snapshots": computed,
    }


def compute_roas(
    conversion_value: float | Decimal,
    spend: float | Decimal,
) -> float | None:
    """
    ROAS = conversion_value / spend.

    Returns None when spend <= 0 or conversion_value <= 0 (stub — no revenue signal yet).
    """
    s = float(spend or 0)
    v = float(conversion_value or 0)
    if s <= 0 or v <= 0:
        return None
    return round(v / s, 4)


def compute_roas_snapshots(
    *,
    target_date: date | str | None = None,
    client_id: str | None = None,
) -> dict[str, Any]:
    """
    Compute ROAS snapshots from daily_performance.conversion_value / spend.

    When conversion_value=0, deletes stale ROAS rows and skips insert (roas_stub tracked in return).
    """
    perf_date = _target_date(target_date)
    clauses = ["performance_date = %s", "channel = 'meta'"]
    params: list[Any] = [perf_date]
    if client_id:
        clauses.append("client_id = %s::uuid")
        params.append(client_id)
    where = " AND ".join(clauses)
    computed = 0
    stub_count = 0
    with pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT id, client_id, external_campaign_id, hub_campaign_map_id,
                       spend, conversion_value, currency
                FROM daily_performance
                WHERE {where}
                """,
                params,
            )
            rows = cur.fetchall()
            cols = [d[0] for d in cur.description]
            for row in rows:
                rec = dict(zip(cols, row))
                spend = Decimal(str(rec.get("spend") or 0))
                conv = Decimal(str(rec.get("conversion_value") or 0))
                if spend <= 0:
                    continue
                roas = compute_roas(conv, spend)
                is_stub = roas is None
                ext = str(rec.get("external_campaign_id") or "")
                cur.execute(
                    """
                    DELETE FROM metrics_snapshots
                    WHERE client_id = %s::uuid
                      AND kpi_code = 'ROAS'
                      AND channel = 'meta'
                      AND COALESCE(external_campaign_id, '') = %s
                      AND period_start = %s
                      AND period_end = %s
                      AND granularity = 'day'
                    """,
                    (str(rec["client_id"]), ext, perf_date, perf_date),
                )
                if is_stub:
                    stub_count += 1
                    continue
                cur.execute(
                    """
                    INSERT INTO metrics_snapshots (
                        client_id, kpi_code, channel, external_campaign_id,
                        hub_campaign_map_id, period_start, period_end, granularity,
                        value_numeric, value_json
                    ) VALUES (
                        %s::uuid, 'ROAS', 'meta', %s, %s::uuid,
                        %s, %s, 'day', %s,
                        jsonb_build_object(
                            'spend', %s::numeric,
                            'conversion_value', %s::numeric,
                            'roas_stub', false,
                            'formula', 'conversion_value / spend',
                            'currency', %s
                        )
                    )
                    """,
                    (
                        str(rec["client_id"]),
                        rec.get("external_campaign_id"),
                        str(rec["hub_campaign_map_id"]) if rec.get("hub_campaign_map_id") else None,
                        perf_date,
                        perf_date,
                        roas,
                        spend,
                        conv,
                        rec.get("currency") or "VND",
                    ),
                )
                computed += 1
        conn.commit()

    return {
        "ok": True,
        "performance_date": perf_date.isoformat(),
        "roas_snapshots": computed,
        "roas_stub_count": stub_count,
    }


def refresh_leads_crm_counts(
    *,
    target_date: date | str | None = None,
    client_id: str | None = None,
) -> int:
    """Re-count CRM leads matched to daily_performance rows for a date."""
    from ptt_meta.insights_sync import count_crm_leads

    perf_date = _target_date(target_date)
    updated = 0
    with pg_connection() as conn:
        with conn.cursor() as cur:
            clauses = ["performance_date = %s", "channel = 'meta'"]
            params: list[Any] = [perf_date]
            if client_id:
                clauses.append("client_id = %s::uuid")
                params.append(client_id)
            cur.execute(
                f"""
                SELECT client_id, external_campaign_id
                FROM daily_performance
                WHERE {' AND '.join(clauses)}
                """,
                params,
            )
            for cid, campaign_id in cur.fetchall():
                leads = count_crm_leads(
                    client_id=str(cid),
                    campaign_id=str(campaign_id),
                    perf_date=perf_date,
                )
                cur.execute(
                    """
                    UPDATE daily_performance
                    SET leads_crm = %s, synced_at = NOW()
                    WHERE client_id = %s::uuid
                      AND channel = 'meta'
                      AND external_campaign_id = %s
                      AND performance_date = %s
                    """,
                    (leads, str(cid), str(campaign_id), perf_date),
                )
                updated += cur.rowcount
        conn.commit()
    return updated
