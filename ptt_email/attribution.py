"""Email revenue attribution — CRM closed-loop proxy (Wave 2)."""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

SCHEMA = "email_mkt"


def _email_lead_filter_sql(alias: str = "cl") -> str:
    a = alias
    return f"""
        (
            LOWER(COALESCE({a}.meta_json->>'utm_medium', '')) = 'email'
            OR COALESCE({a}.meta_json->>'email_send_id', '') <> ''
            OR COALESCE({a}.meta_json->>'utm_source', '') ILIKE '%email%'
            OR LOWER(COALESCE({a}.channel, '')) LIKE '%email%'
            OR LOWER(COALESCE({a}.source, '')) LIKE '%email%'
        )
    """


def email_revenue_attributed(client_id: str, *, days: int = 28) -> float:
    """Sum deal_value_vnd from won CRM leads attributed to email."""
    from ptt_jobs.db import pg_connection

    safe_days = max(1, min(int(days), 365))
    try:
        with pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT COALESCE(SUM(
                      NULLIF(regexp_replace(COALESCE(cl.meta_json->>'deal_value_vnd', '0'), '[^0-9.-]', '', 'g'), '')::numeric
                    ), 0) AS total
                    FROM crm_leads cl
                    WHERE cl.agency_client_id = %s::uuid
                      AND cl.is_duplicate IS NOT TRUE
                      AND LOWER(COALESCE(cl.status, '')) IN ('won', 'closed_won', 'closed won')
                      AND COALESCE(cl.created_at, cl.received_at) >= NOW() - (%s || ' days')::interval
                      AND {_email_lead_filter_sql('cl')}
                    """,
                    (client_id, safe_days),
                )
                row = cur.fetchone()
                return float(row[0] or 0) if row else 0.0
    except Exception as exc:
        logger.debug("email_revenue_attributed: %s", exc)
        return 0.0


def email_attribution_summary(client_id: str, *, days: int = 28) -> dict[str, Any]:
    from ptt_jobs.db import pg_connection

    safe_days = max(1, min(int(days), 365))
    revenue = email_revenue_attributed(client_id, days=safe_days)
    clicks = 0
    leads_influenced = 0
    try:
        with pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT COUNT(*) FROM {SCHEMA}.engagement_events ee
                    WHERE ee.client_id = %s::uuid
                      AND ee.event_type = 'click'
                      AND ee.occurred_at >= NOW() - (%s || ' days')::interval
                    """,
                    (client_id, safe_days),
                )
                clicks = int(cur.fetchone()[0] or 0)
                cur.execute(
                    f"""
                    SELECT COUNT(*) FROM crm_leads cl
                    WHERE cl.agency_client_id = %s::uuid
                      AND cl.is_duplicate IS NOT TRUE
                      AND COALESCE(cl.created_at, cl.received_at) >= NOW() - (%s || ' days')::interval
                      AND {_email_lead_filter_sql('cl')}
                    """,
                    (client_id, safe_days),
                )
                leads_influenced = int(cur.fetchone()[0] or 0)
    except Exception as exc:
        logger.debug("email_attribution_summary: %s", exc)

    return {
        "client_id": client_id,
        "days": safe_days,
        "revenue_attrib": round(revenue, 2),
        "email_clicks": clicks,
        "leads_influenced": leads_influenced,
    }


def rollup_daily_metrics(*, client_id: str | None = None, metric_date: str | None = None) -> dict[str, Any]:
    """Persist daily_metrics for hub/reports (revenue_attrib, clicks, sent)."""
    from datetime import date
    from ptt_jobs.db import pg_connection

    d = metric_date or date.today().isoformat()
    updated = 0
    with pg_connection() as conn:
        with conn.cursor() as cur:
            if client_id:
                client_ids = [client_id]
            else:
                cur.execute(f"SELECT DISTINCT client_id::text FROM {SCHEMA}.workspaces")
                client_ids = [str(r[0]) for r in cur.fetchall()]

            for cid in client_ids:
                summary = email_attribution_summary(cid, days=28)
                metrics = {
                    "revenue_attrib": summary["revenue_attrib"],
                    "leads_influenced": summary["leads_influenced"],
                    "email_clicks_28d": summary["email_clicks"],
                }
                cur.execute(
                    f"""
                    SELECT COUNT(*) FROM {SCHEMA}.send_queue sq
                    WHERE sq.client_id = %s::uuid
                      AND sq.status IN ('sent', 'delivered')
                      AND COALESCE(sq.sent_at, sq.scheduled_at)::date = %s::date
                    """,
                    (cid, d),
                )
                metrics["sent"] = float(cur.fetchone()[0] or 0)

                for name, value in metrics.items():
                    cur.execute(
                        f"""
                        INSERT INTO {SCHEMA}.daily_metrics (client_id, metric_date, metric_name, metric_value)
                        VALUES (%s::uuid, %s::date, %s, %s)
                        ON CONFLICT (client_id, metric_date, metric_name)
                        DO UPDATE SET metric_value = EXCLUDED.metric_value, computed_at = NOW()
                        """,
                        (cid, d, name, value),
                    )
                    updated += 1
        conn.commit()
    return {"ok": True, "updated": updated, "metric_date": d}
