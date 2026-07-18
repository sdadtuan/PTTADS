"""Facebook Ads hub — cross-client Meta summary for AM / Media Buyer."""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any

from ptt_agency.performance import compute_cpl, pg_performance_ready
from ptt_jobs.db import pg_connection

logger = logging.getLogger(__name__)

_META_JOB_TYPES = (
    "meta_insights_sync",
    "meta_token_refresh",
    "ingest_lead",
    "capi_dispatch",
)


def _parse_date(value: str | None, default: date) -> date:
    if not value or not str(value).strip():
        return default
    return date.fromisoformat(str(value).strip()[:10])


def _date_window(*, window_days: int = 7, date_to: str | None = None) -> tuple[date, date]:
    days = max(1, min(int(window_days), 90))
    today = datetime.now(timezone.utc).date()
    end = _parse_date(date_to, today - timedelta(days=1))
    start = end - timedelta(days=days - 1)
    return start, end


def _iso(value: Any) -> str | None:
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def pg_facebook_hub_ready() -> bool:
    try:
        from ptt_agency.clients import pg_ready

        return pg_ready() and pg_performance_ready()
    except Exception as exc:
        logger.debug("pg_facebook_hub_ready: %s", exc)
        return False


def _meta_job_counts() -> dict[str, int]:
    out = {"dead": 0, "failed": 0, "pending": 0}
    try:
        with pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT status, COUNT(*)::int
                    FROM job_queue
                    WHERE job_type = ANY(%s)
                    GROUP BY status
                    """,
                    (list(_META_JOB_TYPES),),
                )
                for status, count in cur.fetchall():
                    key = str(status or "").strip().lower()
                    if key in out:
                        out[key] = int(count)
    except Exception as exc:
        logger.debug("_meta_job_counts: %s", exc)
    return out


def _build_alerts(
    *,
    token_expiring: int,
    token_expired: int,
    no_token_clients: int,
    unmapped_campaigns: int,
    over_target_rows: int,
    meta_jobs_dead: int,
) -> list[dict[str, str]]:
    alerts: list[dict[str, str]] = []
    if meta_jobs_dead > 0:
        alerts.append(
            {
                "severity": "danger",
                "message": f"Có {meta_jobs_dead} job Meta trong DLQ — cần xử lý pipeline.",
                "link": "/crm/agency/ingest?status=dead",
                "link_label": "Xem pipeline",
            }
        )
    if token_expired > 0:
        alerts.append(
            {
                "severity": "danger",
                "message": f"{token_expired} tài khoản Meta token đã hết hạn.",
                "link": "/crm/facebook-ads#clients-table",
                "link_label": "Xem client",
            }
        )
    if token_expiring > 0:
        alerts.append(
            {
                "severity": "warn",
                "message": f"{token_expiring} token Meta sắp hết hạn (≤ 7 ngày).",
                "link": "/crm/facebook-ads#clients-table",
                "link_label": "Kiểm tra token",
            }
        )
    if no_token_clients > 0:
        alerts.append(
            {
                "severity": "warn",
                "message": f"{no_token_clients} client chưa cấu hình token Meta.",
                "link": "/crm/agency/clients",
                "link_label": "Mở danh sách client",
            }
        )
    if unmapped_campaigns > 0:
        alerts.append(
            {
                "severity": "warn",
                "message": f"{unmapped_campaigns} campaign Meta chưa map Hub.",
                "link": "/crm/hub",
                "link_label": "Mở Hub",
            }
        )
    if over_target_rows > 0:
        alerts.append(
            {
                "severity": "warn",
                "message": f"{over_target_rows} hàng CPL vượt target trong kỳ đã chọn.",
                "link": "/crm/facebook-ads#clients-table",
                "link_label": "Xem chi tiết",
            }
        )
    return alerts


def facebook_ads_hub_summary(
    *,
    window_days: int = 7,
    date_to: str | None = None,
    status: str | None = None,
) -> dict[str, Any]:
    """
    Aggregate Meta/Facebook Ads ops view across agency clients.

    Returns summary stats, alerts, and per-client rows for the hub UI.
    """
    if not pg_facebook_hub_ready():
        return {"ok": False, "error": "facebook_hub_not_ready", "pg_ready": False}

    start, end = _date_window(window_days=window_days, date_to=date_to)
    status_filter = (status or "").strip().lower() or None

    from ptt_agency.channel_vault import vault_columns_ready

    vault_ready = vault_columns_ready()

    client_clauses = ["1=1"]
    params: list[Any] = [start, end]
    if status_filter:
        client_clauses.append("c.status = %s")
        params.append(status_filter)

    token_select = ""
    if vault_ready:
        token_select = """
            BOOL_OR(
                cca.channel = 'meta'
                AND (
                    COALESCE(cca.access_token_encrypted, '') <> ''
                    OR COALESCE(cca.credential_ref, '') <> ''
                )
            ) AS meta_has_token,
            MIN(
                CASE
                    WHEN cca.channel = 'meta' AND cca.token_expires_at IS NOT NULL
                    THEN cca.token_expires_at
                END
            ) AS meta_token_expires_at,
            MAX(
                CASE
                    WHEN cca.channel = 'meta' THEN COALESCE(cca.token_status, '')
                END
            ) AS meta_token_status,
        """
    else:
        token_select = """
            BOOL_OR(cca.channel = 'meta') AS meta_has_token,
            NULL::timestamptz AS meta_token_expires_at,
            '' AS meta_token_status,
        """

    sql = f"""
        WITH perf AS (
            SELECT
                dp.client_id,
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
            WHERE dp.channel = 'meta'
              AND dp.performance_date BETWEEN %s AND %s
            GROUP BY dp.client_id
        ),
        meta_acct AS (
            SELECT
                cca.client_id,
                COUNT(*) FILTER (WHERE cca.channel = 'meta') AS meta_account_count,
                MAX(CASE WHEN cca.channel = 'meta' THEN cca.external_account_id END) AS ad_account_id,
                MAX(CASE WHEN cca.channel = 'meta' THEN cca.display_name END) AS ad_account_name,
                {token_select}
                MAX(CASE WHEN cca.channel = 'meta' THEN cca.status END) AS meta_account_status
            FROM client_channel_accounts cca
            GROUP BY cca.client_id
        )
        SELECT
            c.id,
            c.code,
            c.name,
            c.status,
            c.owner_am_id,
            COALESCE(ma.meta_account_count, 0) AS meta_account_count,
            ma.ad_account_id,
            ma.ad_account_name,
            COALESCE(ma.meta_has_token, FALSE) AS meta_has_token,
            ma.meta_token_expires_at,
            ma.meta_token_status,
            ma.meta_account_status,
            COALESCE(p.spend, 0) AS spend,
            COALESCE(p.leads_crm, 0) AS leads_crm,
            COALESCE(p.campaigns, 0) AS campaigns,
            COALESCE(p.unmapped_campaigns, 0) AS unmapped_campaigns,
            COALESCE(p.over_target_rows, 0) AS over_target_rows
        FROM clients c
        LEFT JOIN meta_acct ma ON ma.client_id = c.id
        LEFT JOIN perf p ON p.client_id = c.id
        WHERE {' AND '.join(client_clauses)}
          AND (
            COALESCE(ma.meta_account_count, 0) > 0
            OR COALESCE(p.spend, 0) > 0
            OR COALESCE(p.leads_crm, 0) > 0
            OR c.status IN ('active', 'onboarding')
          )
        ORDER BY COALESCE(p.spend, 0) DESC, c.code ASC
        LIMIT 200
    """

    clients: list[dict[str, Any]] = []
    totals = {
        "meta_clients": 0,
        "meta_accounts": 0,
        "clients_with_spend": 0,
        "total_spend": 0.0,
        "total_leads": 0,
        "avg_cpl": None,
        "over_target_rows": 0,
        "unmapped_campaigns": 0,
        "token_expiring": 0,
        "token_expired": 0,
        "no_token_clients": 0,
    }

    now = datetime.now(timezone.utc)
    expiring_cutoff = now + timedelta(days=7)

    try:
        with pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                cols = [d[0] for d in cur.description]
                for row in cur.fetchall():
                    rec = dict(zip(cols, row))
                    spend = float(rec.get("spend") or 0)
                    leads = int(rec.get("leads_crm") or 0)
                    meta_count = int(rec.get("meta_account_count") or 0)
                    has_token = bool(rec.get("meta_has_token"))
                    expires_raw = rec.get("meta_token_expires_at")
                    expires_dt = None
                    if expires_raw is not None:
                        if hasattr(expires_raw, "tzinfo") and expires_raw.tzinfo is None:
                            expires_dt = expires_raw.replace(tzinfo=timezone.utc)
                        else:
                            expires_dt = expires_raw

                    token_status = "unknown"
                    if meta_count == 0:
                        token_status = "none"
                    elif not has_token:
                        token_status = "missing"
                    elif expires_dt and expires_dt < now:
                        token_status = "expired"
                        totals["token_expired"] += 1
                    elif expires_dt and expires_dt <= expiring_cutoff:
                        token_status = "expiring"
                        totals["token_expiring"] += 1
                    elif str(rec.get("meta_token_status") or "").lower() == "revoked":
                        token_status = "revoked"
                    else:
                        token_status = "valid"

                    if meta_count > 0 and not has_token:
                        totals["no_token_clients"] += 1

                    if meta_count > 0:
                        totals["meta_clients"] += 1
                        totals["meta_accounts"] += meta_count

                    if spend > 0 or leads > 0:
                        totals["clients_with_spend"] += 1

                    totals["total_spend"] += spend
                    totals["total_leads"] += leads
                    totals["over_target_rows"] += int(rec.get("over_target_rows") or 0)
                    totals["unmapped_campaigns"] += int(rec.get("unmapped_campaigns") or 0)

                    clients.append(
                        {
                            "id": str(rec["id"]),
                            "code": rec.get("code"),
                            "name": rec.get("name"),
                            "status": rec.get("status"),
                            "owner_am_id": rec.get("owner_am_id"),
                            "meta_account_count": meta_count,
                            "ad_account_id": rec.get("ad_account_id"),
                            "ad_account_name": rec.get("ad_account_name"),
                            "meta_has_token": has_token,
                            "token_status": token_status,
                            "token_expires_at": _iso(expires_dt),
                            "spend": round(spend, 2),
                            "leads_crm": leads,
                            "cpl": compute_cpl(spend, leads),
                            "campaigns": int(rec.get("campaigns") or 0),
                            "unmapped_campaigns": int(rec.get("unmapped_campaigns") or 0),
                            "over_target_rows": int(rec.get("over_target_rows") or 0),
                            "detail_url": f"/crm/agency/clients/{rec['id']}",
                            "channels_url": f"/crm/agency/clients/{rec['id']}#channels",
                            "performance_url": f"/crm/agency/clients/{rec['id']}#performance",
                        }
                    )
    except Exception as exc:
        logger.exception("facebook_ads_hub_summary failed")
        return {"ok": False, "error": str(exc), "pg_ready": False}

    totals["total_spend"] = round(totals["total_spend"], 2)
    totals["avg_cpl"] = compute_cpl(totals["total_spend"], totals["total_leads"])

    meta_jobs = _meta_job_counts()
    alerts = _build_alerts(
        token_expiring=totals["token_expiring"],
        token_expired=totals["token_expired"],
        no_token_clients=totals["no_token_clients"],
        unmapped_campaigns=totals["unmapped_campaigns"],
        over_target_rows=totals["over_target_rows"],
        meta_jobs_dead=meta_jobs.get("dead", 0),
    )

    return {
        "ok": True,
        "pg_ready": True,
        "date_from": start.isoformat(),
        "date_to": end.isoformat(),
        "window_days": max(1, min(int(window_days), 90)),
        "summary": totals,
        "meta_jobs": meta_jobs,
        "alerts": alerts,
        "clients": clients,
    }
