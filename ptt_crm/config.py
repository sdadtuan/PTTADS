"""CRM platform configuration (Phase 1b)."""
from __future__ import annotations

import os


def _truthy(name: str, default: str = "0") -> bool:
    return os.environ.get(name, default).strip().lower() in {"1", "true", "yes", "on"}


def dual_run_enabled() -> bool:
    return _truthy("PTT_LEADS_API_DUAL_RUN", "0")


def nest_leads_base_url() -> str:
    return (
        os.environ.get("PTT_NEST_LEADS_URL")
        or os.environ.get("CRM_API_URL")
        or "http://127.0.0.1:3000"
    ).rstrip("/")


def nest_internal_key() -> str | None:
    key = (os.environ.get("PTT_CRM_INTERNAL_KEY") or "").strip()
    return key or None


def dual_run_timeout_sec() -> float:
    try:
        return max(0.5, float(os.environ.get("PTT_DUAL_RUN_TIMEOUT_SEC", "2.0")))
    except ValueError:
        return 2.0


def dual_run_async() -> bool:
    """When true, compare in background thread (default — no added latency)."""
    return _truthy("PTT_DUAL_RUN_ASYNC", "1")


def lead_replica_sync_enabled() -> bool:
    return _truthy("PTT_LEAD_REPLICA_SYNC", "1")


def lead_shadow_sync_enabled() -> bool:
    """Phase 2 W2 — PG crm_leads → SQLite shadow (rollback safety)."""
    return _truthy("PTT_LEAD_SHADOW_SYNC", "0")


def meta_insights_sync_enabled() -> bool:
    """Phase 2 M2 — Meta Marketing API → daily_performance."""
    return _truthy("PTT_META_INSIGHTS_SYNC", "0")


def meta_token_refresh_enabled() -> bool:
    """Phase 2 M1-03 — Meta long-lived token refresh + expiry alerts."""
    return _truthy("PTT_META_TOKEN_REFRESH", "0")


def capi_dispatch_enabled() -> bool:
    """Phase 2 M5 — Meta CAPI Lead events (async pilot)."""
    return _truthy("PTT_CAPI_ENABLED", "0")


def hub_read_source_pg() -> bool:
    """Phase 3 D1 — Hub campaign metadata reads from PostgreSQL."""
    return _truthy("PTT_HUB_READ_SOURCE", "0") or hub_pg_primary()


def hub_pg_primary() -> bool:
    """Dual flag: Hub read+write PG primary (SQLite dual-write during cutover)."""
    return _truthy("PTT_HUB_PG_PRIMARY", "0")


def sop_read_source_pg() -> bool:
    """Phase 3 D3 — SOP templates/runs read from PostgreSQL."""
    return _truthy("PTT_SOP_READ_SOURCE", "0")


def google_insights_sync_enabled() -> bool:
    """Phase 3 G2 — Google Ads → daily_performance."""
    return _truthy("PTT_GOOGLE_INSIGHTS_SYNC", "0")


def flask_monolith_mode() -> str:
    """Phase 4 F3 — active | readonly | retired."""
    mode = (os.environ.get("PTT_FLASK_MONOLITH_MODE") or "active").strip().lower()
    return mode if mode in {"active", "readonly", "retired"} else "active"


def leads_write_upstream() -> str:
    """Write upstream for assign/legacy CRM — flask (default) or nest (Phase 2 W8 cutover)."""
    mode = (os.environ.get("PTT_LEADS_WRITE_UPSTREAM") or "flask").strip().lower()
    return mode if mode in {"flask", "nest"} else "flask"


def leads_read_upstream() -> str:
    """Read upstream for GET /api/v1/leads — flask (default) or nest (Bước 8 cutover)."""
    mode = (os.environ.get("PTT_LEADS_READ_UPSTREAM") or "flask").strip().lower()
    return mode if mode in {"flask", "nest"} else "flask"
