"""Meta insights → daily_performance sync (Phase 2 M2)."""
from __future__ import annotations

import json
import logging
import os
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from ptt_meta.graph_insights import fetch_campaign_insights, stub_campaign_insights
from ptt_meta.token_vault import normalize_ad_account_id, resolve_meta_access_token
from ptt_jobs.db import json_dumps, pg_connection

logger = logging.getLogger(__name__)


def _truthy(name: str, default: str = "0") -> bool:
    return os.environ.get(name, default).strip().lower() in {"1", "true", "yes", "on"}


def meta_insights_sync_enabled() -> bool:
    return _truthy("PTT_META_INSIGHTS_SYNC", "0")


def meta_insights_stub_mode() -> bool:
    return _truthy("PTT_META_INSIGHTS_STUB", "0")


def meta_insights_hourly_enabled() -> bool:
    return _truthy("PTT_META_INSIGHTS_HOURLY", "0")


def _hourly_allowlist() -> set[str]:
    raw = os.environ.get("PTT_META_INSIGHTS_HOURLY_CLIENTS", "")
    return {item.strip() for item in raw.split(",") if item.strip()}


def _filter_hourly_accounts(accounts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not meta_insights_hourly_enabled():
        return accounts
    allow = _hourly_allowlist()
    if not allow:
        return []
    return [a for a in accounts if str(a.get("client_id")) in allow]


def pg_meta_insights_ready() -> bool:
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
                      AND table_name IN ('daily_performance', 'meta_insights_sync_state')
                    """
                )
                return int(cur.fetchone()[0] or 0) >= 2
    except Exception as exc:
        logger.debug("pg_meta_insights_ready: %s", exc)
        return False


def _target_date(value: date | str | None = None) -> date:
    if value is None:
        return (datetime.now(timezone.utc).date() - timedelta(days=1))
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def _load_meta_accounts(*, client_id: str | None = None) -> list[dict[str, Any]]:
    from ptt_agency.clients import load_channel_account_for_sync

    rows = load_channel_account_for_sync(client_id, channel="meta")
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
                  AND channel = 'meta'
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


def count_crm_leads(*, client_id: str, campaign_id: str, perf_date: date) -> int:
    with pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(*)::int FROM crm_leads
                WHERE agency_client_id = %s::uuid
                  AND campaign_id = %s
                  AND DATE(COALESCE(received_at, created_at) AT TIME ZONE 'UTC') = %s
                  AND is_duplicate IS NOT TRUE
                """,
                (client_id, campaign_id, perf_date),
            )
            return int(cur.fetchone()[0] or 0)


def upsert_daily_performance(record: dict[str, Any]) -> None:
    from ptt_crm.pg_schema import pg_daily_performance_insight_level_ready

    rec = dict(record)
    if pg_daily_performance_insight_level_ready():
        rec.setdefault("insight_level", "campaign")
        rec.setdefault("external_adset_id", "")
        rec.setdefault("external_adset_name", None)
        conflict = "(client_id, channel, external_campaign_id, external_adset_id, insight_level, performance_date)"
        extra_cols = ", insight_level, external_adset_id, external_adset_name"
        extra_vals = ", %(insight_level)s, %(external_adset_id)s, %(external_adset_name)s"
    else:
        conflict = "(client_id, channel, external_campaign_id, performance_date)"
        extra_cols = ""
        extra_vals = ""

    with pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                INSERT INTO daily_performance (
                    client_id, channel, external_account_id, external_campaign_id,
                    external_campaign_name, hub_campaign_map_id, performance_date,
                    currency, spend, impressions, clicks, reach, frequency,
                    cpc, cpm, ctr, leads_platform, leads_crm, conversions,
                    conversion_value, raw_insights, synced_at, sync_version
                    {extra_cols}
                ) VALUES (
                    %(client_id)s::uuid, %(channel)s, %(external_account_id)s,
                    %(external_campaign_id)s, %(external_campaign_name)s,
                    %(hub_campaign_map_id)s::uuid, %(performance_date)s,
                    %(currency)s, %(spend)s, %(impressions)s, %(clicks)s,
                    %(reach)s, %(frequency)s, %(cpc)s, %(cpm)s, %(ctr)s,
                    %(leads_platform)s, %(leads_crm)s, %(conversions)s,
                    %(conversion_value)s, %(raw_insights)s::jsonb, NOW(), 1
                    {extra_vals}
                )
                ON CONFLICT {conflict}
                DO UPDATE SET
                    external_account_id = EXCLUDED.external_account_id,
                    external_campaign_name = EXCLUDED.external_campaign_name,
                    hub_campaign_map_id = EXCLUDED.hub_campaign_map_id,
                    spend = EXCLUDED.spend,
                    impressions = EXCLUDED.impressions,
                    clicks = EXCLUDED.clicks,
                    reach = EXCLUDED.reach,
                    frequency = EXCLUDED.frequency,
                    cpc = EXCLUDED.cpc,
                    cpm = EXCLUDED.cpm,
                    ctr = EXCLUDED.ctr,
                    leads_platform = EXCLUDED.leads_platform,
                    leads_crm = EXCLUDED.leads_crm,
                    raw_insights = EXCLUDED.raw_insights,
                    synced_at = NOW(),
                    sync_version = daily_performance.sync_version + 1
                """,
                rec,
            )
        conn.commit()


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
                UPDATE meta_insights_sync_state
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


def _dispatch_insights_sync_alert(
    *,
    failed: list[dict[str, Any]],
    performance_date: str,
    accounts_total: int,
) -> bool:
    """Notify agency ops + Sentry when Meta insights sync has account failures (P2 #13)."""
    if not failed:
        return False
    from ptt_agency.notifications import notify_agency_ops

    sample = failed[:3]
    lines = [
        f"{f.get('client_id', '?')} / {f.get('account_id', '?')}: {f.get('error', 'error')}"
        for f in sample
    ]
    title = f"Meta insights sync fail — {len(failed)}/{accounts_total} account(s)"
    body = (
        f"Ngày {performance_date}: {len(failed)} ad account sync thất bại. "
        + "; ".join(lines)
        + (f" (+{len(failed) - len(sample)} nữa)" if len(failed) > len(sample) else "")
        + ". Xem meta_insights_sync_state.last_error và chạy replay."
    )
    notify_agency_ops(
        recipient_id="admin",
        title=title,
        body=body,
        category="meta_insights",
        link_url="/crm/agency/ingest",
        meta={
            "performance_date": performance_date,
            "accounts_failed": len(failed),
            "accounts_total": accounts_total,
            "failures": sample,
        },
        slack_prefix=":warning: [Meta Insights]",
    )
    try:
        import sentry_sdk

        sentry_sdk.capture_message(
            title,
            level="warning",
            extras={"failures": failed[:10], "performance_date": performance_date},
        )
    except Exception as exc:
        logger.debug("Sentry insights alert skipped: %s", exc)
    return True


def sync_account_insights(
    account: dict[str, Any],
    *,
    target_date: date,
    stub: bool = False,
) -> dict[str, Any]:
    client_id = str(account["client_id"])
    ad_account_id = normalize_ad_account_id(str(account.get("external_account_id") or ""))
    if not ad_account_id:
        return {"ok": False, "error": "missing_ad_account_id", "upserted": 0}

    day = target_date.isoformat()
    if stub or meta_insights_stub_mode():
        rows = stub_campaign_insights(since=day, until=day, ad_account_id=ad_account_id)
        fetch_error = None
    else:
        token = resolve_meta_access_token(account)
        if not token:
            return {"ok": False, "error": "missing_access_token", "upserted": 0}
        rows, fetch_error = fetch_campaign_insights(
            ad_account_id=ad_account_id,
            access_token=token,
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
            "channel": "meta",
            "external_account_id": ad_account_id,
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

    breakdown_out: dict[str, Any] = {"ok": True, "skipped": True}
    try:
        from ptt_meta.insights_breakdown import sync_account_breakdown_insights

        breakdown_out = sync_account_breakdown_insights(account, target_date=target_date, stub=stub)
    except Exception as exc:
        logger.warning("meta breakdown sync skipped/failed: %s", exc)
        breakdown_out = {"ok": False, "error": str(exc)}

    return {"ok": True, "upserted": upserted, "account_id": ad_account_id, "breakdown": breakdown_out}


def sync_meta_insights(
    *,
    target_date: date | str | None = None,
    client_id: str | None = None,
    compute_metrics: bool = True,
) -> dict[str, Any]:
    if not meta_insights_sync_enabled() and not meta_insights_stub_mode():
        return {"ok": True, "skipped": True, "reason": "disabled"}
    if not pg_meta_insights_ready():
        return {"ok": False, "error": "pg_meta_insights_not_ready"}

    perf_date = _target_date(target_date)
    accounts = _load_meta_accounts(client_id=client_id)
    if meta_insights_hourly_enabled():
        accounts = _filter_hourly_accounts(accounts)
    if not accounts:
        _update_sync_state(ok=True, accounts_total=0, accounts_failed=0, rows_upserted=0, last_error=None)
        return {"ok": True, "skipped": True, "reason": "no_meta_accounts", "performance_date": perf_date.isoformat()}

    stub = meta_insights_stub_mode()
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
            logger.warning("meta insights sync account failed: %s", failed[-1])

    last_error = None
    if failed:
        last_error = json.dumps(failed[:5], ensure_ascii=False)[:2000]
        try:
            _dispatch_insights_sync_alert(
                failed=failed,
                performance_date=perf_date.isoformat(),
                accounts_total=len(accounts),
            )
        except Exception as exc:
            logger.warning("insights sync alert failed: %s", exc)

    _update_sync_state(
        ok=len(failed) == 0,
        accounts_total=len(accounts),
        accounts_failed=len(failed),
        rows_upserted=total_upserted,
        last_error=last_error,
    )

    metrics_out: dict[str, Any] | None = None
    roas_out: dict[str, Any] | None = None
    if compute_metrics and total_upserted > 0:
        try:
            from ptt_metrics.compute import compute_cpl_snapshots, compute_roas_snapshots

            metrics_out = compute_cpl_snapshots(target_date=perf_date, client_id=client_id)
            roas_out = compute_roas_snapshots(target_date=perf_date, client_id=client_id)
        except Exception as exc:
            logger.exception("Metrics compute after insights sync: %s", exc)
            metrics_out = {"ok": False, "error": str(exc)}

    return {
        "ok": len(failed) == 0,
        "performance_date": perf_date.isoformat(),
        "accounts_total": len(accounts),
        "accounts_failed": len(failed),
        "rows_upserted": total_upserted,
        "failures": failed[:10],
        "metrics": metrics_out,
        "roas_metrics": roas_out,
    }
