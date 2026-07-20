"""GA4 OAuth sync orchestration — writes seo_ga4_daily_stats via PG (Phase 4)."""
from __future__ import annotations

import logging
import os
from datetime import date
from typing import Any

from ptt_seo.connectors.ga4_api import (
    default_date_range,
    fetch_daily_metrics,
    ga4_stub_mode,
    list_properties,
    refresh_access_token,
)
from ptt_seo.connectors.ga4_oauth import resolve_ga4_refresh_token
from ptt_seo.connectors.gsc import _finish_sync_run, _start_sync_run, _ts
from ptt_seo.db import seo_pg_only
from ptt_seo.integrations import get_ga4_integration, patch_integrations

logger = logging.getLogger(__name__)


def ga4_sync_enabled() -> bool:
    return os.environ.get("PTT_GA4_SYNC_ENABLED", "0").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def list_ga4_connected_customer_ids() -> list[int]:
    """Customers with GA4 OAuth connected (PostgreSQL integrations_json)."""
    with seo_pg_only() as conn:
        rows = conn.execute(
            """
            SELECT customer_id, integrations_json FROM seo_client_settings
            WHERE integrations_json IS NOT NULL
            """
        ).fetchall()
    ids: list[int] = []
    for row in rows:
        cid = int(row["customer_id"])
        ga4 = get_ga4_integration(cid)
        if ga4.get("refresh_token_encrypted") or (
            ga4_stub_mode() and ga4.get("property_id")
        ):
            if str(ga4.get("status") or "") not in ("revoked", "disconnected"):
                ids.append(cid)
    if ga4_stub_mode() and not ids:
        dev = (os.environ.get("PTT_GA4_SYNC_CUSTOMER_ID") or "").strip()
        if dev.isdigit():
            ids.append(int(dev))
    return sorted(set(ids))


def sync_ga4_for_customer(
    customer_id: int,
    *,
    days: int = 28,
    property_id: str | None = None,
) -> dict[str, Any]:
    """Pull GA4 Data API → seo_aeo.seo_ga4_daily_stats (PostgreSQL only)."""
    ga4 = get_ga4_integration(customer_id)
    refresh = resolve_ga4_refresh_token(customer_id)
    if not refresh and not ga4_stub_mode():
        return {"ok": False, "error": "GA4 chưa kết nối OAuth"}

    prop = (property_id or ga4.get("property_id") or "").strip()
    with seo_pg_only() as conn:
        run_id = _start_sync_run(conn, customer_id, "ga4_oauth")
        try:
            access = refresh_access_token(refresh) if refresh else "stub"
            if not prop:
                props = list_properties(access)
                prop = props[0] if props else ""
            if not prop:
                raise ValueError("Không tìm thấy GA4 property — cấu hình property_id")

            start, end = default_date_range(days)
            rows = fetch_daily_metrics(access, prop, start_date=start, end_date=end)
            count = 0
            for row in rows:
                conn.execute(
                    """
                    INSERT INTO seo_ga4_daily_stats (
                        customer_id, stat_date, landing_page, source_medium,
                        sessions, users, pageviews, bounce_rate, avg_session_duration,
                        conversions, revenue, created_at
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                    ON CONFLICT(customer_id, stat_date, landing_page, source_medium) DO UPDATE SET
                        sessions=excluded.sessions,
                        users=excluded.users,
                        pageviews=excluded.pageviews,
                        bounce_rate=excluded.bounce_rate,
                        avg_session_duration=excluded.avg_session_duration,
                        conversions=excluded.conversions,
                        revenue=excluded.revenue
                    """,
                    (
                        customer_id,
                        row["stat_date"],
                        row.get("landing_page") or "",
                        row.get("source_medium") or "",
                        int(row.get("sessions") or 0),
                        int(row.get("users") or 0),
                        int(row.get("pageviews") or 0),
                        float(row.get("bounce_rate") or 0),
                        float(row.get("avg_session_duration") or 0),
                        float(row.get("conversions") or 0),
                        float(row.get("revenue") or 0),
                        _ts(),
                    ),
                )
                count += 1
            conn.commit()
            _finish_sync_run(conn, run_id, ok=True, rows=count)
            patch_integrations(
                customer_id,
                {
                    "ga4": {
                        **ga4,
                        "property_id": prop,
                        "status": "connected",
                        "last_sync_at": _ts(),
                        "last_sync_status": "done",
                    }
                },
            )
            return {
                "ok": True,
                "run_id": run_id,
                "rows_imported": count,
                "property_id": prop,
                "start_date": start.isoformat(),
                "end_date": end.isoformat(),
            }
        except Exception as exc:
            _finish_sync_run(conn, run_id, ok=False, error=str(exc))
            patch_integrations(
                customer_id,
                {
                    "ga4": {
                        **ga4,
                        "last_sync_at": _ts(),
                        "last_sync_status": "failed",
                        "last_sync_error": str(exc)[:500],
                    }
                },
            )
            logger.exception("ga4 sync failed customer_id=%s", customer_id)
            return {"ok": False, "run_id": run_id, "error": str(exc)}


def enqueue_ga4_sync(customer_id: int, *, days: int = 28) -> dict[str, Any]:
    """Enqueue seo_ga4_sync job; inline fallback when queue unavailable."""
    payload = {"customer_id": customer_id, "days": days}
    idem = f"seo_ga4_sync:{customer_id}:{date.today().isoformat()}"
    try:
        from ptt_jobs.config import jobs_enabled, jobs_sync_fallback
        from ptt_jobs.db import pg_available
        from ptt_jobs.enqueue import enqueue_job

        if jobs_enabled() and pg_available():
            job = enqueue_job("seo_ga4_sync", payload, idem)
            return {"ok": True, "mode": "queue", "job": job}
        if jobs_sync_fallback():
            outcome = sync_ga4_for_customer(customer_id, days=days)
            return {"ok": outcome.get("ok", False), "mode": "sync", "outcome": outcome}
        return {"ok": False, "error": "job_queue_unavailable"}
    except Exception as exc:
        logger.exception("enqueue_ga4_sync failed")
        return {"ok": False, "error": str(exc)}


def process_seo_ga4_sync_payload(payload: dict[str, Any]) -> dict[str, Any]:
    customer_id = int(payload.get("customer_id") or 0)
    if not customer_id:
        return {"ok": False, "error": "missing_customer_id"}
    days = int(payload.get("days") or 28)
    return sync_ga4_for_customer(customer_id, days=days)


def sync_all_ga4_customers(*, days: int = 28) -> dict[str, Any]:
    """Daily batch — sync every GA4-connected SEO client (systemd timer entrypoint)."""
    if not ga4_sync_enabled() and not ga4_stub_mode():
        return {"ok": True, "skipped": True, "reason": "PTT_GA4_SYNC_ENABLED=0"}

    customer_ids = list_ga4_connected_customer_ids()
    if not customer_ids:
        return {"ok": True, "skipped": True, "reason": "no_ga4_connected_customers", "customers": 0}

    results: list[dict[str, Any]] = []
    ok_count = 0
    for cid in customer_ids:
        outcome = sync_ga4_for_customer(cid, days=days)
        results.append({"customer_id": cid, **outcome})
        if outcome.get("ok"):
            ok_count += 1

    failed = len(customer_ids) - ok_count
    return {
        "ok": failed == 0,
        "customers": len(customer_ids),
        "ok_count": ok_count,
        "failed": failed,
        "results": results,
    }
