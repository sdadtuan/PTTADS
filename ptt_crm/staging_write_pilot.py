"""Staging write cutover pilot gates (Phase 2 P0 #3)."""
from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

VALID_SYNC_MODES = frozenset({"sqlite_to_pg", "pg_primary", "paused"})
STAGING_FLAGS = (
    "PTT_LEADS_WRITE_ENABLED",
    "PTT_LEADS_WRITE_UPSTREAM",
    "PTT_LEAD_SHADOW_SYNC",
    "PTT_LEADS_READ_UPSTREAM",
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_ts(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        dt = value
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt
    text = str(value).strip()
    if not text:
        return None
    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return None


def nest_leads_base_url() -> str:
    return (
        os.environ.get("PTT_NEST_LEADS_URL")
        or os.environ.get("CRM_API_URL")
        or "http://127.0.0.1:3000"
    ).rstrip("/")


def fetch_nest_health(*, timeout_sec: float = 5.0) -> dict[str, Any]:
    url = f"{nest_leads_base_url()}/health"
    try:
        with urllib.request.urlopen(url, timeout=timeout_sec) as resp:
            body = json.loads(resp.read().decode())
            return {"ok": True, "status": resp.status, "body": body, "url": url}
    except (urllib.error.URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError) as exc:
        return {"ok": False, "error": str(exc), "url": url}


def check_staging_env_flags(*, expect_pg_primary: bool = False) -> dict[str, Any]:
    """Verify pilot env flags (best-effort — reads current process env)."""
    from ptt_crm.config import lead_shadow_sync_enabled, leads_write_upstream

    write_enabled = os.environ.get("PTT_LEADS_WRITE_ENABLED", "0").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    upstream = leads_write_upstream()
    shadow = lead_shadow_sync_enabled()
    read_upstream = (os.environ.get("PTT_LEADS_READ_UPSTREAM") or "flask").strip().lower()

    checks = {
        "write_enabled": write_enabled,
        "write_upstream": upstream,
        "shadow_sync": shadow,
        "read_upstream": read_upstream,
    }
    issues: list[str] = []
    if not write_enabled:
        issues.append("PTT_LEADS_WRITE_ENABLED!=1")
    if upstream != "nest":
        issues.append("PTT_LEADS_WRITE_UPSTREAM!=nest")
    if not shadow:
        issues.append("PTT_LEAD_SHADOW_SYNC!=1")
    if read_upstream != "nest":
        issues.append("PTT_LEADS_READ_UPSTREAM!=nest (recommended for pilot)")

    sync_mode = get_sync_mode()
    if expect_pg_primary and sync_mode.get("sync_mode") != "pg_primary":
        issues.append(f"sync_mode={sync_mode.get('sync_mode')} expected pg_primary")

    return {
        "ok": len(issues) == 0,
        "checks": checks,
        "issues": issues,
        "sync_mode": sync_mode,
    }


def get_sync_mode() -> dict[str, Any]:
    try:
        from ptt_jobs.db import pg_connection

        with pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT sync_mode, last_sync_at, updated_at
                    FROM crm_leads_sync_state
                    WHERE id = 1
                    """
                )
                row = cur.fetchone()
                if not row:
                    return {"ok": False, "error": "sync_state_missing"}
                return {
                    "ok": True,
                    "sync_mode": str(row[0] or ""),
                    "last_sync_at": row[1].isoformat() if row[1] else None,
                    "updated_at": row[2].isoformat() if row[2] else None,
                }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def set_sync_mode(mode: str) -> dict[str, Any]:
    if mode not in VALID_SYNC_MODES:
        return {"ok": False, "error": f"invalid_mode:{mode}"}
    try:
        from ptt_jobs.db import pg_connection

        with pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE crm_leads_sync_state
                    SET sync_mode = %s, updated_at = NOW()
                    WHERE id = 1
                    RETURNING sync_mode, updated_at
                    """,
                    (mode,),
                )
                row = cur.fetchone()
            conn.commit()
        return {
            "ok": True,
            "sync_mode": str(row[0]) if row else mode,
            "updated_at": row[1].isoformat() if row and row[1] else None,
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def check_pg_preflight() -> dict[str, Any]:
    from ptt_crm.pg_schema import pg_leads_replica_ready, pg_shadow_ready, pg_v3_ready

    v3 = pg_v3_ready()
    replica = pg_leads_replica_ready()
    shadow = pg_shadow_ready()
    stats = {}
    try:
        from ptt_crm.pg_schema import pg_leads_stats

        stats = pg_leads_stats()
    except Exception as exc:
        stats = {"error": str(exc)}

    issues: list[str] = []
    if not replica:
        issues.append("pg_leads_replica_not_ready")
    if not shadow:
        issues.append("pg_shadow_not_ready")
    if not v3:
        issues.append("pg_v3_not_ready")

    return {
        "ok": len(issues) == 0,
        "pg_v3_ready": v3,
        "pg_replica_ready": replica,
        "pg_shadow_ready": shadow,
        "pg_leads_stats": stats,
        "issues": issues,
    }


def check_shadow_lag(*, max_lag_sec: int = 300) -> dict[str, Any]:
    try:
        from ptt_jobs.db import pg_connection

        with pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT last_shadow_at, last_pg_version, rows_shadowed
                    FROM crm_leads_shadow_state
                    WHERE id = 1
                    """
                )
                row = cur.fetchone()
        if not row:
            return {"ok": False, "error": "shadow_state_missing"}
        last_at = row[0]
        lag_sec: float | None = None
        if last_at is not None:
            ts = _parse_ts(last_at)
            if ts:
                lag_sec = max(0.0, (_utc_now() - ts).total_seconds())
        ok = lag_sec is not None and lag_sec <= max(1, max_lag_sec)
        return {
            "ok": ok,
            "last_shadow_at": last_at.isoformat() if hasattr(last_at, "isoformat") else str(last_at),
            "lag_sec": lag_sec,
            "max_lag_sec": max_lag_sec,
            "last_pg_version": int(row[1] or 0),
            "rows_shadowed": int(row[2] or 0),
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def check_lead_assigned_event(
    *,
    lead_id: int | None = None,
    within_minutes: int = 30,
) -> dict[str, Any]:
    try:
        from ptt_jobs.db import pg_connection

        clauses = ["event_type = 'LeadAssigned'"]
        params: list[Any] = []
        if lead_id is not None:
            clauses.append("aggregate_id = %s")
            params.append(str(int(lead_id)))
        where = " AND ".join(clauses)
        with pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT id, aggregate_id, published_at, created_at, payload
                    FROM domain_events
                    WHERE {where}
                    ORDER BY created_at DESC
                    LIMIT 5
                    """,
                    params,
                )
                rows = cur.fetchall()
        if not rows:
            return {
                "ok": False,
                "error": "no_lead_assigned_events",
                "lead_id": lead_id,
            }

        now = _utc_now()
        window_sec = max(60, within_minutes * 60)
        recent = []
        for row in rows:
            created = _parse_ts(row[3])
            published = _parse_ts(row[2])
            lag_sec = None
            if created and published:
                lag_sec = max(0.0, (published - created).total_seconds())
            age_sec = (now - created).total_seconds() if created else None
            recent.append(
                {
                    "id": str(row[0]),
                    "lead_id": row[1],
                    "published_at": published.isoformat() if published else None,
                    "created_at": created.isoformat() if created else None,
                    "publish_lag_sec": lag_sec,
                    "age_sec": age_sec,
                }
            )

        best = recent[0]
        ok = True
        if lead_id is not None and str(best.get("lead_id")) != str(lead_id):
            ok = False
        if best.get("age_sec") is not None and float(best["age_sec"]) > window_sec:
            ok = False
        if best.get("publish_lag_sec") is not None and float(best["publish_lag_sec"]) > 30:
            ok = False

        return {
            "ok": ok,
            "lead_id": lead_id,
            "events": recent,
            "within_minutes": within_minutes,
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc), "lead_id": lead_id}


def run_preflight_gates(*, expect_pg_primary: bool = False) -> dict[str, Any]:
    health = fetch_nest_health()
    nest_body = health.get("body") or {}
    nest_write = bool(nest_body.get("leads_write_enabled"))
    env_flags = check_staging_env_flags(expect_pg_primary=expect_pg_primary)
    pg = check_pg_preflight()

    issues: list[str] = []
    if not health.get("ok"):
        issues.append("nest_unreachable")
    elif not nest_write:
        issues.append("nest_leads_write_disabled")
    issues.extend(env_flags.get("issues") or [])
    issues.extend(pg.get("issues") or [])

    return {
        "ok": len(issues) == 0,
        "issues": issues,
        "nest_health": health,
        "nest_leads_write_enabled": nest_write,
        "env_flags": env_flags,
        "pg_preflight": pg,
    }


def run_post_write_gates(
    *,
    lead_id: int | None = None,
    sample_size: int = 20,
    include_nest: bool = True,
    shadow_max_lag_sec: int = 300,
) -> dict[str, Any]:
    from ptt_crm.dual_run_write import run_write_dual_run_check
    from ptt_crm.lead_shadow_sync import reconcile_leads_pg_primary

    shadow = check_shadow_lag(max_lag_sec=shadow_max_lag_sec)
    dual = run_write_dual_run_check(sample_size=max(1, sample_size), include_nest=include_nest)
    reconcile = reconcile_leads_pg_primary(sample_size=max(1, sample_size))
    lead_assigned = check_lead_assigned_event(lead_id=lead_id) if lead_id else check_lead_assigned_event()

    ok = (
        shadow.get("ok")
        and dual.get("ok")
        and (lead_assigned.get("ok") if lead_id else True)
    )
    return {
        "ok": bool(ok),
        "shadow_lag": shadow,
        "write_dual_run": dual,
        "reconcile": reconcile,
        "lead_assigned": lead_assigned,
    }


def build_pilot_report(*, phase: str, steps: dict[str, Any]) -> dict[str, Any]:
    failed = [name for name, result in steps.items() if not (result or {}).get("ok", False)]
    return {
        "phase": phase,
        "generated_at": _utc_now().replace(microsecond=0).isoformat(),
        "ok": len(failed) == 0,
        "failed_steps": failed,
        "steps": steps,
        "environment": {
            "nest_url": nest_leads_base_url(),
            "database_url_set": bool(os.environ.get("DATABASE_URL")),
            "flags": {k: os.environ.get(k) for k in STAGING_FLAGS},
        },
    }
