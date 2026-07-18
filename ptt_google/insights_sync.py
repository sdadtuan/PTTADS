"""Google Ads insights → daily_performance sync (Phase 3 G2)."""
from __future__ import annotations

import json
import logging
import os
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from ptt_google.ads_api import fetch_campaign_insights, google_ads_stub_mode, stub_campaign_insights
from ptt_google.token_vault import normalize_customer_id, resolve_google_refresh_token
from ptt_jobs.db import json_dumps, pg_connection
from ptt_meta.insights_sync import count_crm_leads, upsert_daily_performance

logger = logging.getLogger(__name__)


def _truthy(name: str, default: str = "0") -> bool:
    return os.environ.get(name, default).strip().lower() in {"1", "true", "yes", "on"}


def google_insights_sync_enabled() -> bool:
    return _truthy("PTT_GOOGLE_INSIGHTS_SYNC", "0")


def pg_google_insights_ready() -> bool:
    try:
        from ptt_jobs.db import pg_available

        if not pg_available():
            return False
        with pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT COUNT(*) FROM information_schema.tables
                    WHERE table_schema = 'public'
                      AND table_name IN ('daily_performance', 'google_insights_sync_state')
                    """
                )
                return int(cur.fetchone()[0] or 0) >= 2
    except Exception as exc:
        logger.debug("pg_google_insights_ready: %s", exc)
        return False


def _target_date(value: date | str | None = None) -> date:
    if value is None:
        return datetime.now(timezone.utc).date() - timedelta(days=1)
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def _load_google_accounts(*, client_id: str | None = None) -> list[dict[str, Any]]:
    from ptt_agency.clients import load_channel_account_for_sync

    rows = load_channel_account_for_sync(client_id, channel="google")
    return [
        {
            "id": str(r["id"]),
            "client_id": str(r["client_id"]),
            "channel": r["channel"],
            "external_account_id": r["external_account_id"],
            "display_name": r.get("display_name"),
            "credential_ref": r.get("credential_ref"),
            "access_token_encrypted": r.get("access_token_encrypted"),
            "meta": r.get("meta") or {},
            "token_status": r.get("token_status"),
            "status": r.get("status"),
        }
        for r in rows
        if str(r.get("token_status") or "") != "revoked"
    ]


def _hub_map_lookup(client_id: str, external_campaign_id: str) -> dict[str, Any] | None:
    with pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, external_campaign_name, external_account_id, target_cpl_vnd
                FROM hub_campaign_map
                WHERE client_id = %s::uuid
                  AND channel = 'google'
                  AND external_campaign_id = %s
                  AND active IS TRUE
                LIMIT 1
                """,
                (client_id, external_campaign_id),
            )
            row = cur.fetchone()
            if not row:
                return None
            cols = [d[0] for d in cur.description]
            return dict(zip(cols, row))


def _update_sync_state(
    *,
    ok: bool,
    accounts_total: int,
    accounts_failed: int,
    rows_upserted: int,
    last_error: str | None = None,
) -> None:
    with pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE google_insights_sync_state
                SET last_sync_at = NOW(),
                    last_success_at = CASE WHEN %s THEN NOW() ELSE last_success_at END,
                    last_error = %s,
                    accounts_total = %s,
                    accounts_failed = %s,
                    rows_upserted = rows_upserted + %s,
                    updated_at = NOW()
                WHERE id = 1
                """,
                (ok and accounts_failed == 0, last_error, accounts_total, accounts_failed, rows_upserted),
            )
        conn.commit()


def sync_account_insights(
    account: dict[str, Any],
    *,
    target_date: date,
    stub: bool = False,
) -> dict[str, Any]:
    client_id = str(account["client_id"])
    customer_id = normalize_customer_id(str(account.get("external_account_id") or ""))
    if not customer_id:
        return {"ok": False, "error": "missing_customer_id", "upserted": 0}

    day = target_date.isoformat()
    if stub or google_ads_stub_mode():
        rows = stub_campaign_insights(since=day, until=day, customer_id=customer_id)
        fetch_error = None
    else:
        refresh_token = resolve_google_refresh_token(account)
        if not refresh_token:
            return {"ok": False, "error": "missing_refresh_token", "upserted": 0}
        rows, fetch_error = fetch_campaign_insights(
            customer_id=customer_id,
            refresh_token=refresh_token,
            since=day,
            until=day,
        )
        if fetch_error:
            return {"ok": False, "error": fetch_error, "upserted": 0}

    upserted = 0
    for row in rows:
        campaign_id = row.get("external_campaign_id") or ""
        if not campaign_id:
            continue
        hub = _hub_map_lookup(client_id, campaign_id)
        leads_crm = count_crm_leads(client_id=client_id, campaign_id=campaign_id, perf_date=target_date)
        record = {
            "client_id": client_id,
            "channel": "google",
            "external_account_id": customer_id,
            "external_campaign_id": campaign_id,
            "external_campaign_name": row.get("external_campaign_name")
            or (hub or {}).get("external_campaign_name")
            or "",
            "hub_campaign_map_id": str(hub["id"]) if hub else None,
            "performance_date": target_date,
            "currency": "VND",
            "spend": Decimal(str(row.get("spend") or 0)),
            "impressions": int(row.get("impressions") or 0),
            "clicks": int(row.get("clicks") or 0),
            "reach": row.get("reach"),
            "frequency": row.get("frequency"),
            "cpc": row.get("cpc"),
            "cpm": row.get("cpm"),
            "ctr": row.get("ctr"),
            "leads_platform": int(row.get("leads_platform") or 0),
            "leads_crm": leads_crm,
            "conversions": Decimal("0"),
            "conversion_value": Decimal("0"),
            "raw_insights": json_dumps(row.get("raw_insights") or {}),
        }
        upsert_daily_performance(record)
        upserted += 1

    return {"ok": True, "upserted": upserted, "account_id": customer_id}


def sync_google_insights(
    *,
    target_date: date | str | None = None,
    client_id: str | None = None,
    compute_metrics: bool = True,
) -> dict[str, Any]:
    if not google_insights_sync_enabled() and not google_ads_stub_mode():
        return {"ok": True, "skipped": True, "reason": "disabled"}
    if not pg_google_insights_ready():
        return {"ok": False, "error": "pg_google_insights_not_ready"}

    perf_date = _target_date(target_date)
    accounts = _load_google_accounts(client_id=client_id)
    if not accounts:
        _update_sync_state(ok=True, accounts_total=0, accounts_failed=0, rows_upserted=0, last_error=None)
        return {"ok": True, "skipped": True, "reason": "no_google_accounts", "performance_date": perf_date.isoformat()}

    stub = google_ads_stub_mode()
    total_upserted = 0
    failed: list[dict[str, Any]] = []
    for account in accounts:
        outcome = sync_account_insights(account, target_date=perf_date, stub=stub)
        if outcome.get("ok"):
            total_upserted += int(outcome.get("upserted") or 0)
        else:
            failed.append(
                {
                    "client_id": str(account.get("client_id")),
                    "account_id": account.get("external_account_id"),
                    "error": outcome.get("error"),
                }
            )
            logger.warning("google insights sync account failed: %s", failed[-1])

    last_error = None
    if failed:
        last_error = json.dumps(failed[:5], ensure_ascii=False)[:2000]

    _update_sync_state(
        ok=len(failed) == 0,
        accounts_total=len(accounts),
        accounts_failed=len(failed),
        rows_upserted=total_upserted,
        last_error=last_error,
    )

    metrics_out: dict[str, Any] | None = None
    if compute_metrics and total_upserted > 0:
        try:
            from ptt_metrics.compute import compute_cpl_snapshots

            metrics_out = compute_cpl_snapshots(target_date=perf_date, client_id=client_id)
        except Exception as exc:
            logger.exception("Metrics compute after google sync: %s", exc)
            metrics_out = {"ok": False, "error": str(exc)}

    return {
        "ok": len(failed) == 0,
        "performance_date": perf_date.isoformat(),
        "accounts_total": len(accounts),
        "accounts_failed": len(failed),
        "rows_upserted": total_upserted,
        "failures": failed[:10],
        "metrics": metrics_out,
    }
