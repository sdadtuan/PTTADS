"""Fetch Meta/Zalo hub payload for scheduled report export."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any


def fetch_meta_hub_for_client(*, client_id: str, window_days: int = 7) -> dict[str, Any]:
    from ptt_agency.facebook_ads_hub import facebook_ads_hub_summary

    hub = facebook_ads_hub_summary(window_days=window_days)
    if not hub.get("ok", True) and hub.get("error"):
        return hub
    clients = [c for c in hub.get("clients") or [] if str(c.get("id")) == client_id]
    summary = hub.get("summary") or {}
    if clients:
        c = clients[0]
        summary = {
            **summary,
            "total_spend": c.get("spend"),
            "total_leads": c.get("leads_crm"),
            "avg_cpl": c.get("cpl"),
            "unmapped_campaigns": c.get("unmapped_campaigns"),
            "over_target_rows": c.get("over_target_rows"),
        }
    return {
        "ok": True,
        "date_from": hub.get("date_from"),
        "date_to": hub.get("date_to"),
        "window_days": hub.get("window_days") or window_days,
        "summary": summary,
        "clients": clients,
    }


def fetch_zalo_hub_for_client(*, client_id: str, window_days: int = 7) -> dict[str, Any]:
    from ptt_jobs.db import pg_connection

    end = datetime.now(timezone.utc).date() - timedelta(days=1)
    start = end - timedelta(days=max(1, min(int(window_days), 90)) - 1)

    with pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT code, name FROM clients WHERE id = %s::uuid", (client_id,))
            client_row = cur.fetchone()
            cur.execute(
                """
                SELECT
                  SUM(dp.spend) AS spend,
                  SUM(dp.leads_crm) AS leads_crm,
                  COUNT(DISTINCT dp.external_campaign_id) AS campaigns,
                  COUNT(DISTINCT dp.external_campaign_id)
                    FILTER (WHERE dp.hub_campaign_map_id IS NULL) AS unmapped_campaigns,
                  COUNT(*) FILTER (
                    WHERE hcm.target_cpl_vnd IS NOT NULL
                      AND dp.leads_crm > 0
                      AND (dp.spend / dp.leads_crm) > hcm.target_cpl_vnd
                  ) AS over_target_rows
                FROM daily_performance dp
                LEFT JOIN hub_campaign_map hcm ON hcm.id = dp.hub_campaign_map_id
                WHERE dp.client_id = %s::uuid
                  AND dp.channel = 'zalo'
                  AND dp.performance_date BETWEEN %s AND %s
                """,
                (client_id, start, end),
            )
            perf = cur.fetchone()

    spend = float(perf[0] or 0) if perf else 0.0
    leads = int(perf[1] or 0) if perf else 0
    cpl = round(spend / leads) if leads > 0 else None
    client = {
        "id": client_id,
        "code": client_row[0] if client_row else None,
        "name": client_row[1] if client_row else None,
        "spend": spend,
        "leads_crm": leads,
        "cpl": cpl,
        "campaigns": int(perf[2] or 0) if perf else 0,
        "unmapped_campaigns": int(perf[3] or 0) if perf else 0,
        "over_target_rows": int(perf[4] or 0) if perf else 0,
        "conversions_won": 0,
        "avg_cpa": None,
    }
    return {
        "ok": True,
        "date_from": start.isoformat(),
        "date_to": end.isoformat(),
        "window_days": window_days,
        "summary": {
            "total_spend": spend,
            "total_leads": leads,
            "avg_cpl": cpl,
            "unmapped_campaigns": client["unmapped_campaigns"],
            "over_target_rows": client["over_target_rows"],
            "total_conversions": 0,
            "avg_cpa": None,
        },
        "clients": [client],
    }


def portal_performance_link(client_id: str, channel: str) -> str:
    import os

    base = (
        os.environ.get("PTT_PORTAL_PUBLIC_URL")
        or os.environ.get("NEXT_PUBLIC_PORTAL_URL")
        or "https://portal.pttads.vn"
    ).rstrip("/")
    path = "/meta" if channel == "meta" else "/zalo" if channel == "zalo" else "/dashboard"
    return f"{base}{path}?client_hint={client_id}"
