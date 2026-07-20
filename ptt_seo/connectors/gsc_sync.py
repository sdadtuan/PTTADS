"""GSC OAuth sync orchestration — writes seo_gsc_daily_stats via PG (Phase 4)."""
from __future__ import annotations

import logging
import os
from datetime import date
from typing import Any

from ptt_seo.connectors.gsc_api import (
    default_date_range,
    fetch_search_analytics,
    gsc_stub_mode,
    list_sites,
    refresh_access_token,
)
from ptt_seo.connectors.gsc_oauth import resolve_gsc_refresh_token
from ptt_seo.connectors.gsc import _finish_sync_run, _start_sync_run, _ts
from ptt_seo.db import seo_pg_only
from ptt_seo.integrations import get_gsc_integration, patch_integrations

logger = logging.getLogger(__name__)


def gsc_sync_enabled() -> bool:
    return os.environ.get("PTT_GSC_SYNC_ENABLED", "0").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def list_gsc_connected_customer_ids() -> list[int]:
    """Customers with GSC OAuth connected (PostgreSQL integrations_json)."""
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
        gsc = get_gsc_integration(cid)
        if gsc.get("refresh_token_encrypted") or (
            gsc_stub_mode() and gsc.get("site_url")
        ):
            if str(gsc.get("status") or "") not in ("revoked", "disconnected"):
                ids.append(cid)
    if gsc_stub_mode() and not ids:
        dev = (os.environ.get("PTT_GSC_SYNC_CUSTOMER_ID") or "").strip()
        if dev.isdigit():
            ids.append(int(dev))
    return sorted(set(ids))


def sync_gsc_for_customer(
    customer_id: int,
    *,
    days: int = 28,
    site_url: str | None = None,
) -> dict[str, Any]:
    """Pull GSC Search Analytics → seo_aeo.seo_gsc_daily_stats (PostgreSQL only)."""
    gsc = get_gsc_integration(customer_id)
    refresh = resolve_gsc_refresh_token(customer_id)
    if not refresh and not gsc_stub_mode():
        return {"ok": False, "error": "GSC chưa kết nối OAuth"}

    site = (site_url or gsc.get("site_url") or "").strip()
    with seo_pg_only() as conn:
        run_id = _start_sync_run(conn, customer_id, "gsc_oauth")
        try:
            access = refresh_access_token(refresh) if refresh else "stub"
            if not site:
                sites = list_sites(access)
                site = sites[0] if sites else ""
            if not site:
                raise ValueError("Không tìm thấy GSC property — cấu hình site_url")

            start, end = default_date_range(days)
            rows = fetch_search_analytics(access, site, start_date=start, end_date=end)
            count = 0
            for row in rows:
                conn.execute(
                    """
                    INSERT INTO seo_gsc_daily_stats (
                        customer_id, stat_date, query, page, clicks, impressions, ctr, position, created_at
                    ) VALUES (?,?,?,?,?,?,?,?,?)
                    ON CONFLICT(customer_id, stat_date, query, page) DO UPDATE SET
                        clicks=excluded.clicks,
                        impressions=excluded.impressions,
                        ctr=excluded.ctr,
                        position=excluded.position
                    """,
                    (
                        customer_id,
                        row["stat_date"],
                        row.get("query") or "",
                        row.get("page") or "",
                        int(row.get("clicks") or 0),
                        int(row.get("impressions") or 0),
                        float(row.get("ctr") or 0),
                        float(row.get("position") or 0),
                        _ts(),
                    ),
                )
                count += 1
            conn.commit()
            _finish_sync_run(conn, run_id, ok=True, rows=count)
            patch_integrations(
                customer_id,
                {
                    "gsc": {
                        **gsc,
                        "site_url": site,
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
                "site_url": site,
                "start_date": start.isoformat(),
                "end_date": end.isoformat(),
            }
        except Exception as exc:
            _finish_sync_run(conn, run_id, ok=False, error=str(exc))
            patch_integrations(
                customer_id,
                {
                    "gsc": {
                        **gsc,
                        "last_sync_at": _ts(),
                        "last_sync_status": "failed",
                        "last_sync_error": str(exc)[:500],
                    }
                },
            )
            logger.exception("gsc sync failed customer_id=%s", customer_id)
            return {"ok": False, "run_id": run_id, "error": str(exc)}


def enqueue_gsc_sync(customer_id: int, *, days: int = 28) -> dict[str, Any]:
    """Enqueue seo_gsc_sync job; inline fallback when queue unavailable."""
    payload = {"customer_id": customer_id, "days": days}
    idem = f"seo_gsc_sync:{customer_id}:{date.today().isoformat()}"
    try:
        from ptt_jobs.config import jobs_enabled, jobs_sync_fallback
        from ptt_jobs.db import pg_available
        from ptt_jobs.enqueue import enqueue_job

        if jobs_enabled() and pg_available():
            job = enqueue_job("seo_gsc_sync", payload, idem)
            return {"ok": True, "mode": "queue", "job": job}
        if jobs_sync_fallback():
            outcome = sync_gsc_for_customer(customer_id, days=days)
            return {"ok": outcome.get("ok", False), "mode": "sync", "outcome": outcome}
        return {"ok": False, "error": "job_queue_unavailable"}
    except Exception as exc:
        logger.exception("enqueue_gsc_sync failed")
        return {"ok": False, "error": str(exc)}


def process_seo_gsc_sync_payload(payload: dict[str, Any]) -> dict[str, Any]:
    customer_id = int(payload.get("customer_id") or 0)
    if not customer_id:
        return {"ok": False, "error": "missing_customer_id"}
    days = int(payload.get("days") or 28)
    return sync_gsc_for_customer(customer_id, days=days)


def sync_all_gsc_customers(*, days: int = 28) -> dict[str, Any]:
    """Daily batch — sync every GSC-connected SEO client (systemd timer entrypoint)."""
    if not gsc_sync_enabled() and not gsc_stub_mode():
        return {"ok": True, "skipped": True, "reason": "PTT_GSC_SYNC_ENABLED=0"}

    customer_ids = list_gsc_connected_customer_ids()
    if not customer_ids:
        return {"ok": True, "skipped": True, "reason": "no_gsc_connected_customers", "customers": 0}

    results: list[dict[str, Any]] = []
    ok_count = 0
    for cid in customer_ids:
        outcome = sync_gsc_for_customer(cid, days=days)
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
