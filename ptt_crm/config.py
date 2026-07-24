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
    """Phase 1 — off by default when PG is primary (no SQLite→PG replica needed)."""
    if leads_write_source_pg():
        return _truthy("PTT_LEAD_REPLICA_SYNC", "0")
    return _truthy("PTT_LEAD_REPLICA_SYNC", "1")


def lead_shadow_sync_enabled() -> bool:
    """Phase 2 W2 — PG crm_leads → SQLite shadow (rollback safety)."""
    return _truthy("PTT_LEAD_SHADOW_SYNC", "0")


def ingest_rules_source() -> str:
    """
    Lead ingest rules (facebook config, assign, catalog) — pg | sqlite.
    Default pg when PTT_LEADS_WRITE_SOURCE=pg.
    """
    explicit = (os.environ.get("PTT_LEAD_INGEST_RULES_SOURCE") or "").strip().lower()
    if explicit in {"pg", "sqlite"}:
        return explicit
    return "pg" if leads_write_source_pg() else "sqlite"


def ingest_rules_from_pg() -> bool:
    return ingest_rules_source() == "pg"


def meta_insights_sync_enabled() -> bool:
    """Phase 2 M2 — Meta Marketing API → daily_performance."""
    return _truthy("PTT_META_INSIGHTS_SYNC", "0")


def meta_insights_hourly_enabled() -> bool:
    """B14 ME52 — hourly insights sync for allowlisted high-spend clients."""
    return _truthy("PTT_META_INSIGHTS_HOURLY", "0")


def meta_warehouse_export_enabled() -> bool:
    """B14 ME48 — daily_performance → ClickHouse facts."""
    return _truthy("PTT_META_WAREHOUSE_EXPORT", "0")


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


def leads_write_source() -> str:
    """Ingest write target — pg (Phase 1 default) or sqlite (rollback)."""
    mode = (os.environ.get("PTT_LEADS_WRITE_SOURCE") or "pg").strip().lower()
    return mode if mode in {"sqlite", "pg"} else "pg"


def leads_write_source_pg() -> bool:
    return leads_write_source() == "pg"


def leads_pg_primary() -> bool:
    """True when PostgreSQL is authoritative for lead OLTP (Phase 1+)."""
    return leads_write_source_pg()


def leads_read_source_pg() -> bool:
    """Read leads from PG instead of ptt.db (ops-web, Nest, Flask v1 proxy)."""
    explicit = (os.environ.get("PTT_LEADS_READ_SOURCE") or "").strip().lower()
    if explicit == "pg":
        return True
    if explicit == "sqlite":
        return False
    return leads_write_source_pg()


def facebook_background_in_gunicorn() -> bool:
    """When false (Sprint 0 default), FB autosync runs in ptt-fb-autosync.service only."""
    return _truthy("CRM_FACEBOOK_BACKGROUND_IN_GUNICORN", "0")


def meta_ads_admin_retired() -> bool:
    """Horizon 1 B3.3 — Flask /crm/facebook-ads admin off; ops-web canonical."""
    return _truthy("PTT_FLASK_META_ADS_ADMIN_RETIRED", "0")


def meta_ads_ops_web_hub_path() -> str:
    return "/meta/facebook-ads"


def meta_ads_ops_on_ops_web() -> bool:
    if meta_ads_admin_retired():
        return True
    mode = (os.environ.get("PTT_META_ADS_UPSTREAM") or "ops-web").strip().lower()
    if mode in {"flask", "legacy"}:
        return False
    return mode in {"ops-web", "nest", "ops"}


def ops_web_base_url() -> str:
    return (os.environ.get("PTT_OPS_WEB_URL") or "http://127.0.0.1:3200").rstrip("/")


def meta_ads_ops_web_hub_url() -> str:
    return f"{ops_web_base_url()}{meta_ads_ops_web_hub_path()}"


def agency_ops_on_ops_web() -> bool:
    """Phase 2 — agency UI/API primary on ops-web."""
    mode = (os.environ.get("PTT_AGENCY_OPS_UPSTREAM") or "ops-web").strip().lower()
    return mode in {"ops-web", "nest", "ops"}


def agency_flask_readonly() -> bool:
    if agency_ops_on_ops_web():
        return True
    return _truthy("PTT_AGENCY_FLASK_READONLY", "0")


def catalog_ops_on_ops_web() -> bool:
    """Wave 1 — catalog admin on ops-web + Nest API."""
    mode = (os.environ.get("PTT_CRM_CATALOG_UPSTREAM") or "ops-web").strip().lower()
    if mode in {"flask", "legacy"}:
        return False
    return mode in {"ops-web", "nest", "ops"} or _truthy("PTT_FLASK_CRM_CATALOG_RETIRED", "0")


def catalog_flask_readonly() -> bool:
    if catalog_ops_on_ops_web():
        return True
    return _truthy("PTT_FLASK_CRM_CATALOG_RETIRED", "0")


def leads_legacy_ops_on_nest() -> bool:
    """Wave 1b — lead activities/assign/audit on Nest + ops-web."""
    mode = (os.environ.get("PTT_CRM_LEADS_LEGACY_UPSTREAM") or "nest").strip().lower()
    if mode in {"flask", "legacy"}:
        return False
    return mode in {"nest", "ops-web", "ops"} or _truthy("PTT_FLASK_CRM_LEADS_LEGACY_RETIRED", "0")


def leads_legacy_flask_readonly() -> bool:
    if leads_legacy_ops_on_nest():
        return True
    return _truthy("PTT_FLASK_CRM_LEADS_LEGACY_RETIRED", "0")


def leads_ops_on_ops_web() -> bool:
    """Wave 1 full — lead list/detail UI on ops-web; Flask HTML redirect."""
    mode = (os.environ.get("PTT_CRM_LEADS_UPSTREAM") or "ops-web").strip().lower()
    if mode in {"flask", "legacy"}:
        return False
    return mode in {"ops-web", "nest", "ops"} or _truthy("PTT_FLASK_CRM_LEADS_UI_RETIRED", "0")


def leads_flask_ui_retired() -> bool:
    if leads_ops_on_ops_web():
        return True
    return _truthy("PTT_FLASK_CRM_LEADS_UI_RETIRED", "0")


def customers_ops_on_ops_web() -> bool:
    """Wave 2 — customer 360 UI on ops-web + Nest API."""
    mode = (os.environ.get("PTT_CRM_CUSTOMERS_UPSTREAM") or "ops-web").strip().lower()
    if mode in {"flask", "legacy"}:
        return False
    return mode in {"ops-web", "nest", "ops"} or _truthy("PTT_FLASK_CRM_CUSTOMERS_RETIRED", "0")


def customers_flask_readonly() -> bool:
    if customers_ops_on_ops_web():
        return True
    return _truthy("PTT_FLASK_CRM_CUSTOMERS_RETIRED", "0")


def intake_ops_on_ops_web() -> bool:
    """Wave 2 — lead intake UI on ops-web + Nest API."""
    mode = (os.environ.get("PTT_CRM_INTAKE_UPSTREAM") or "ops-web").strip().lower()
    if mode in {"flask", "legacy"}:
        return False
    return mode in {"ops-web", "nest", "ops"} or _truthy("PTT_FLASK_CRM_INTAKE_RETIRED", "0")


def intake_flask_readonly() -> bool:
    if intake_ops_on_ops_web():
        return True
    return _truthy("PTT_FLASK_CRM_INTAKE_RETIRED", "0")


def cases_ops_on_nest() -> bool:
    """Wave 2+ — CRM cases API on Nest."""
    mode = (os.environ.get("PTT_CRM_CASES_UPSTREAM") or "nest").strip().lower()
    if mode in {"flask", "legacy"}:
        return False
    return mode in {"nest", "ops-web", "ops"} or _truthy("PTT_FLASK_CRM_CASES_RETIRED", "0")


def cases_flask_readonly() -> bool:
    if cases_ops_on_nest():
        return True
    return _truthy("PTT_FLASK_CRM_CASES_RETIRED", "0")


def marketing_plans_ops_on_ops_web() -> bool:
    """Wave 3 — marketing plans UI on ops-web + Nest API."""
    mode = (os.environ.get("PTT_CRM_MARKETING_PLANS_UPSTREAM") or "ops-web").strip().lower()
    if mode in {"flask", "legacy"}:
        return False
    return mode in {"ops-web", "nest", "ops"} or _truthy("PTT_FLASK_CRM_MARKETING_PLANS_RETIRED", "0")


def marketing_plans_flask_readonly() -> bool:
    if marketing_plans_ops_on_ops_web():
        return True
    return _truthy("PTT_FLASK_CRM_MARKETING_PLANS_RETIRED", "0")


def service_lifecycle_ops_on_ops_web() -> bool:
    """Wave 3 — service delivery UI on ops-web + Nest API."""
    mode = (os.environ.get("PTT_CRM_SERVICE_LIFECYCLE_UPSTREAM") or "ops-web").strip().lower()
    if mode in {"flask", "legacy"}:
        return False
    return mode in {"ops-web", "nest", "ops"} or _truthy("PTT_FLASK_CRM_SERVICE_LIFECYCLE_RETIRED", "0")


def service_lifecycle_flask_readonly() -> bool:
    if service_lifecycle_ops_on_ops_web():
        return True
    return _truthy("PTT_FLASK_CRM_SERVICE_LIFECYCLE_RETIRED", "0")


def sop_ops_on_ops_web() -> bool:
    """Wave 3 — SOP UI on ops-web + Nest API."""
    mode = (os.environ.get("PTT_CRM_SOP_UPSTREAM") or "ops-web").strip().lower()
    if mode in {"flask", "legacy"}:
        return False
    return mode in {"ops-web", "nest", "ops"} or _truthy("PTT_FLASK_CRM_SOP_RETIRED", "0")


def sop_flask_readonly() -> bool:
    if sop_ops_on_ops_web():
        return True
    return _truthy("PTT_FLASK_CRM_SOP_RETIRED", "0")


def sales_ops_on_ops_web() -> bool:
    """Wave 4 — sales hub UI on ops-web + Nest API."""
    mode = (os.environ.get("PTT_CRM_SALES_UPSTREAM") or "ops-web").strip().lower()
    if mode in {"flask", "legacy"}:
        return False
    return mode in {"ops-web", "nest", "ops"} or _truthy("PTT_FLASK_CRM_SALES_RETIRED", "0")


def sales_flask_readonly() -> bool:
    if sales_ops_on_ops_web():
        return True
    return _truthy("PTT_FLASK_CRM_SALES_RETIRED", "0")


def kpi_ops_on_ops_web() -> bool:
    """Wave 4 — KPI UI on ops-web + Nest API."""
    mode = (os.environ.get("PTT_CRM_KPI_UPSTREAM") or "ops-web").strip().lower()
    if mode in {"flask", "legacy"}:
        return False
    return mode in {"ops-web", "nest", "ops"} or _truthy("PTT_FLASK_CRM_KPI_RETIRED", "0")


def kpi_flask_readonly() -> bool:
    if kpi_ops_on_ops_web():
        return True
    return _truthy("PTT_FLASK_CRM_KPI_RETIRED", "0")


def staff_roster_ops_on_ops_web() -> bool:
    """Wave 4 — staff roster UI on ops-web + Nest API."""
    mode = (os.environ.get("PTT_CRM_STAFF_UPSTREAM") or "ops-web").strip().lower()
    if mode in {"flask", "legacy"}:
        return False
    return mode in {"ops-web", "nest", "ops"} or _truthy("PTT_FLASK_CRM_STAFF_RETIRED", "0")


def staff_roster_flask_readonly() -> bool:
    if staff_roster_ops_on_ops_web():
        return True
    return _truthy("PTT_FLASK_CRM_STAFF_RETIRED", "0")


def proposals_ops_on_ops_web() -> bool:
    """Wave 4+ — proposals UI on ops-web + Nest API."""
    mode = (os.environ.get("PTT_CRM_PROPOSALS_UPSTREAM") or "ops-web").strip().lower()
    if mode in {"flask", "legacy"}:
        return False
    return mode in {"ops-web", "nest", "ops"} or _truthy("PTT_FLASK_CRM_PROPOSALS_RETIRED", "0")


def proposals_flask_readonly() -> bool:
    if proposals_ops_on_ops_web():
        return True
    return _truthy("PTT_FLASK_CRM_PROPOSALS_RETIRED", "0")


def re_projects_ops_on_ops_web() -> bool:
    """Wave 5 — RE projects UI on ops-web + Nest API."""
    mode = (os.environ.get("PTT_CRM_RE_PROJECTS_UPSTREAM") or "ops-web").strip().lower()
    if mode in {"flask", "legacy"}:
        return False
    return mode in {"ops-web", "nest", "ops"} or _truthy("PTT_FLASK_CRM_RE_PROJECTS_RETIRED", "0")


def re_projects_flask_readonly() -> bool:
    if re_projects_ops_on_ops_web():
        return True
    return _truthy("PTT_FLASK_CRM_RE_PROJECTS_RETIRED", "0")


def payroll_ops_on_ops_web() -> bool:
    """Wave 5 — payroll full UI on ops-web + Nest API."""
    mode = (os.environ.get("PTT_CRM_PAYROLL_UPSTREAM") or "ops-web").strip().lower()
    if mode in {"flask", "legacy"}:
        return False
    return mode in {"ops-web", "nest", "ops"} or _truthy("PTT_FLASK_CRM_PAYROLL_RETIRED", "0")


def payroll_ops_on_nest() -> bool:
    """Wave 4+ alias — payroll dashboard API on Nest (HTML Flask until Wave 5)."""
    return payroll_ops_on_ops_web()


def payroll_flask_readonly() -> bool:
    if payroll_ops_on_ops_web():
        return True
    return _truthy("PTT_FLASK_CRM_PAYROLL_RETIRED", "0")


def re_projects_accounting_on_nest() -> bool:
    """Wave 5+ — RE project accounting dashboard/cash-flow on Nest."""
    mode = (os.environ.get("PTT_CRM_RE_PROJECTS_ACCOUNTING_UPSTREAM") or "nest").strip().lower()
    if mode in {"flask", "legacy"}:
        return False
    return mode in {"nest", "ops-web", "ops"} or _truthy("PTT_FLASK_CRM_RE_PROJECTS_ACCOUNTING_RETIRED", "0")


def re_projects_kpi_risks_on_nest() -> bool:
    """Wave 5++ — RE project KPI/risks/budget on Nest."""
    mode = (os.environ.get("PTT_CRM_RE_PROJECTS_KPI_RISKS_UPSTREAM") or "nest").strip().lower()
    if mode in {"flask", "legacy"}:
        return False
    return mode in {"nest", "ops-web", "ops"} or _truthy("PTT_FLASK_CRM_RE_PROJECTS_KPI_RISKS_RETIRED", "0")


def re_projects_ops_on_nest() -> bool:
    """Wave 5+++ — RE project staff/lead-config/workflow/export on Nest."""
    mode = (os.environ.get("PTT_CRM_RE_PROJECTS_OPS_UPSTREAM") or "nest").strip().lower()
    if mode in {"flask", "legacy"}:
        return False
    return mode in {"nest", "ops-web", "ops"} or _truthy("PTT_FLASK_CRM_RE_PROJECTS_OPS_RETIRED", "0")


def finance_ops_on_ops_web() -> bool:
    """Wave 6 — finance / owner-weekly UI on ops-web + Nest API."""
    mode = (os.environ.get("PTT_CRM_FINANCE_UPSTREAM") or "ops-web").strip().lower()
    if mode in {"flask", "legacy"}:
        return False
    return mode in {"ops-web", "nest", "ops"} or _truthy("PTT_FLASK_CRM_FINANCE_RETIRED", "0")


def finance_ops_on_nest() -> bool:
    """Wave 6 alias — finance dashboard API on Nest (HTML Flask until Wave 6)."""
    return finance_ops_on_ops_web()


def finance_flask_readonly() -> bool:
    if finance_ops_on_ops_web():
        return True
    return _truthy("PTT_FLASK_CRM_FINANCE_RETIRED", "0")


def crm_shell_ops_on_ops_web() -> bool:
    """Wave 7 — CRM board hub UI on ops-web + Nest API."""
    mode = (os.environ.get("PTT_CRM_SHELL_UPSTREAM") or "ops-web").strip().lower()
    if mode in {"flask", "legacy"}:
        return False
    return mode in {"ops-web", "nest", "ops"} or _truthy("PTT_FLASK_CRM_SHELL_RETIRED", "0")


def crm_shell_flask_readonly() -> bool:
    if crm_shell_ops_on_ops_web():
        return True
    return _truthy("PTT_FLASK_CRM_SHELL_RETIRED", "0")


def phase5_migration_ready() -> bool:
    """True when Wave 7 flags allow Phase 5 Flask stop."""
    return (
        crm_shell_ops_on_ops_web()
        and finance_ops_on_nest()
        and re_projects_ops_on_nest()
    )
