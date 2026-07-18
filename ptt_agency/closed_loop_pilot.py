"""Staging closed-loop pilot checklist — 1 client (Phase 2 P0 #4)."""
from __future__ import annotations

import os
import re
from datetime import date, timedelta
from typing import Any

_PIXEL_RE = re.compile(r"^[0-9]{5,20}$")
_STUB_CAMPAIGN_ID = "stub_campaign_1"


def resolve_client(*, client_id: str | None = None, client_code: str | None = None) -> dict[str, Any]:
    from ptt_agency.clients import fetch_client, fetch_client_by_code

    if client_id:
        row = fetch_client(client_id.strip())
        if row:
            return {"ok": True, "client": row}
        return {"ok": False, "error": "client_not_found", "client_id": client_id}
    code = str(client_code or os.environ.get("CLIENT_CODE") or os.environ.get("PTT_CLIENT_CODE") or "").strip()
    if not code:
        return {"ok": False, "error": "client_id_or_code_required"}
    row = fetch_client_by_code(code)
    if not row:
        return {"ok": False, "error": "client_not_found", "client_code": code.upper()}
    return {"ok": True, "client": row}


def check_meta_token(client_id: str) -> dict[str, Any]:
    from ptt_agency.clients import list_channel_accounts

    accounts = list_channel_accounts(client_id)
    meta_accounts = [a for a in accounts if str(a.get("channel") or "") == "meta"]
    if not meta_accounts:
        return {"ok": False, "error": "no_meta_channel_account", "accounts": 0}
    ready = [
        a
        for a in meta_accounts
        if a.get("has_token") and str(a.get("token_status") or "") in {"valid", "expiring", "unknown"}
    ]
    if not ready:
        return {
            "ok": False,
            "error": "meta_token_missing_or_invalid",
            "meta_accounts": len(meta_accounts),
            "token_statuses": [a.get("token_status") for a in meta_accounts],
        }
    primary = ready[0]
    return {
        "ok": True,
        "account_id": primary.get("id"),
        "external_account_id": primary.get("external_account_id"),
        "token_status": primary.get("token_status"),
        "meta_accounts": len(meta_accounts),
    }


def check_pixel_configured(client_id: str) -> dict[str, Any]:
    from ptt_agency.clients import list_channel_accounts

    meta_accounts = [
        a for a in list_channel_accounts(client_id) if str(a.get("channel") or "") == "meta"
    ]
    with_pixel = [a for a in meta_accounts if a.get("pixel_configured") and a.get("pixel_id")]
    global_pixel = (os.environ.get("PTT_META_PIXEL_ID") or os.environ.get("META_PIXEL_ID") or "").strip()
    if with_pixel:
        return {
            "ok": True,
            "source": "channel_account",
            "pixel_id": str(with_pixel[0].get("pixel_id")),
            "account_id": with_pixel[0].get("id"),
        }
    if global_pixel and _PIXEL_RE.match(global_pixel):
        return {"ok": True, "source": "env_fallback", "pixel_id": global_pixel}
    return {
        "ok": False,
        "error": "pixel_not_configured",
        "hint": "Set pixel on Meta channel account or PTT_META_PIXEL_ID",
    }


def check_hub_campaign_map(client_id: str, *, min_maps: int = 1) -> dict[str, Any]:
    try:
        from ptt_jobs.db import pg_connection

        with pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT hub_campaign_id, external_campaign_id, target_cpl_vnd, active
                    FROM hub_campaign_map
                    WHERE client_id = %s::uuid AND channel = 'meta'
                    ORDER BY updated_at DESC
                    LIMIT 20
                    """,
                    (client_id,),
                )
                cols = [d[0] for d in cur.description]
                rows = [dict(zip(cols, r)) for r in cur.fetchall()]
        active = [r for r in rows if r.get("active") is not False]
        ok = len(active) >= min_maps
        return {
            "ok": ok,
            "total": len(rows),
            "active": len(active),
            "min_required": min_maps,
            "maps": [
                {
                    "hub_campaign_id": r.get("hub_campaign_id"),
                    "external_campaign_id": r.get("external_campaign_id"),
                    "target_cpl_vnd": float(r["target_cpl_vnd"]) if r.get("target_cpl_vnd") is not None else None,
                }
                for r in active[:5]
            ],
            "error": None if ok else "hub_map_incomplete",
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def check_insights_sync_enabled() -> dict[str, Any]:
    from ptt_meta.insights_sync import meta_insights_sync_enabled, meta_insights_stub_mode, pg_meta_insights_ready

    enabled = meta_insights_sync_enabled()
    stub = meta_insights_stub_mode()
    ready = pg_meta_insights_ready()
    issues: list[str] = []
    if not enabled and not stub:
        issues.append("PTT_META_INSIGHTS_SYNC!=1")
    if not ready:
        issues.append("pg_meta_insights_not_ready")
    return {
        "ok": len(issues) == 0,
        "PTT_META_INSIGHTS_SYNC": enabled,
        "PTT_META_INSIGHTS_STUB": stub,
        "pg_ready": ready,
        "issues": issues,
    }


def run_insights_sync_for_client(
    client_id: str,
    *,
    target_date: date | str | None = None,
) -> dict[str, Any]:
    from ptt_meta.insights_sync import sync_meta_insights

    out = sync_meta_insights(target_date=target_date, client_id=client_id, compute_metrics=True)
    return out


def check_daily_performance(client_id: str, *, min_rows: int = 1) -> dict[str, Any]:
    try:
        from ptt_jobs.db import pg_connection

        with pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT COUNT(*)::int, MAX(performance_date), MAX(synced_at)
                    FROM daily_performance
                    WHERE client_id = %s::uuid AND channel = 'meta'
                    """,
                    (client_id,),
                )
                count, latest_date, latest_sync = cur.fetchone()
        ok = int(count or 0) >= min_rows
        return {
            "ok": ok,
            "row_count": int(count or 0),
            "latest_performance_date": latest_date.isoformat() if latest_date else None,
            "latest_synced_at": latest_sync.isoformat() if latest_sync else None,
            "error": None if ok else "no_daily_performance_rows",
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def check_cpl_tab_data(
    client_id: str,
    *,
    date_from: str | None = None,
    date_to: str | None = None,
    min_rows: int = 1,
) -> dict[str, Any]:
    from ptt_agency.performance import list_campaign_performance

    if not date_to:
        date_to = (date.today() - timedelta(days=1)).isoformat()
    if not date_from:
        date_from = (date.fromisoformat(date_to) - timedelta(days=6)).isoformat()

    out = list_campaign_performance(
        client_id=client_id,
        date_from=date_from,
        date_to=date_to,
        group_by="day",
    )
    if not out.get("ok"):
        return {"ok": False, "error": out.get("error") or "performance_api_failed", "api": out}
    rows = out.get("rows") or []
    ok = len(rows) >= min_rows
    summary = out.get("summary") or {}
    return {
        "ok": ok,
        "row_count": len(rows),
        "summary": summary,
        "sample_rows": rows[:3],
        "date_from": out.get("date_from"),
        "date_to": out.get("date_to"),
        "error": None if ok else "cpl_tab_empty",
        "ui_path": f"/crm/agency/clients/{client_id}#performance",
    }


def run_closed_loop_pilot(
    *,
    client_id: str | None = None,
    client_code: str | None = None,
    run_sync: bool = False,
    min_hub_maps: int = 1,
    min_perf_rows: int = 1,
) -> dict[str, Any]:
    """Full checklist for one staging client — token + pixel + map + insights → CPL tab."""
    steps: dict[str, Any] = {}

    resolved = resolve_client(client_id=client_id, client_code=client_code)
    steps["client"] = resolved
    if not resolved.get("ok"):
        return _pilot_report(steps, ok=False)

    cid = str(resolved["client"]["id"])
    steps["meta_token"] = check_meta_token(cid)
    steps["pixel"] = check_pixel_configured(cid)
    steps["hub_map"] = check_hub_campaign_map(cid, min_maps=min_hub_maps)
    steps["insights_flag"] = check_insights_sync_enabled()

    if run_sync:
        sync_out = run_insights_sync_for_client(cid)
        steps["insights_sync"] = sync_out
        if not sync_out.get("ok") and not sync_out.get("skipped"):
            return _pilot_report(steps, ok=False)

    steps["daily_performance"] = check_daily_performance(cid, min_rows=min_perf_rows)
    steps["cpl_tab"] = check_cpl_tab_data(cid, min_rows=min_perf_rows)

    failed = [name for name, result in steps.items() if isinstance(result, dict) and not result.get("ok")]
    return _pilot_report(steps, ok=len(failed) == 0, failed_steps=failed)


def _pilot_report(steps: dict[str, Any], *, ok: bool, failed_steps: list[str] | None = None) -> dict[str, Any]:
    failed = failed_steps or [n for n, r in steps.items() if isinstance(r, dict) and not r.get("ok")]
    client = (steps.get("client") or {}).get("client") or {}
    return {
        "ok": ok,
        "phase": "closed_loop_pilot",
        "client_id": client.get("id"),
        "client_code": client.get("code"),
        "failed_steps": failed,
        "stub_campaign_hint": _STUB_CAMPAIGN_ID,
        "steps": steps,
    }
