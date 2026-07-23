"""Meta Ads Flask admin retirement — ops-web canonical hub (Horizon 1 B3.3)."""
from __future__ import annotations

from typing import Any

from ptt_crm.config import (
    meta_ads_admin_retired,
    meta_ads_ops_on_ops_web,
    meta_ads_ops_web_hub_path,
    meta_ads_ops_web_hub_url,
)
from ptt_crm.meta_ads_nginx_redirect import nginx_redirect_status
from ptt_crm.meta_ads_retirement_preflight import retirement_dry_run_status
from ptt_crm.meta_ads_retirement_apply import retirement_apply_status


def flask_meta_ads_admin_redirect() -> tuple[str, int] | None:
    """When retired, Flask HTML routes should 302 to ops-web Meta hub."""
    if not meta_ads_admin_retired():
        return None
    return meta_ads_ops_web_hub_url(), 302


def migration_status(*, include_nginx_live: bool = False) -> dict[str, Any]:
    retired = meta_ads_admin_retired()
    nginx = nginx_redirect_status(include_live=include_nginx_live)
    dry_run = retirement_dry_run_status()
    applied = retirement_apply_status()
    return {
        "ok": True,
        "flask_meta_ads_admin_retired": retired,
        "ops_web_hub_url": meta_ads_ops_web_hub_url(),
        "ops_web_hub_path": meta_ads_ops_web_hub_path(),
        "legacy_rs_path": nginx["legacy_path"],
        "canonical_upstream": "ops-web" if meta_ads_ops_on_ops_web() else "flask",
        "gate_m1_g09": retired,
        "gate_m1_g06": bool(nginx["gate_m1_g06"]),
        "gate_m1_g06_config": bool(nginx["gate_m1_g06_config"]),
        "gate_m1_g06_live": nginx.get("gate_m1_g06_live"),
        "nginx_redirect_live_skipped": nginx["live_verify_skipped"],
        "nginx_deploy_config_ok": nginx["deploy_nginx"]["ok"],
        "nginx_live_site_configured": nginx["live_nginx_site"].get("configured"),
        "gate_m1_g11": bool(dry_run["gate_m1_g11"]),
        "retirement_dry_run_ok": dry_run.get("dry_run_artifact_ok"),
        "retirement_env_pending_changes": dry_run.get("env_pending_changes"),
        "retirement_env_already_applied": dry_run.get("env_already_applied"),
        "retirement_next_apply_command": dry_run.get("next_apply_command"),
        "gate_m1_g12": bool(applied["gate_m1_g12"]),
        "retirement_applied_ok": applied.get("retirement_applied_ok"),
        "retirement_env_applied_ok": applied.get("retirement_env_applied_ok"),
        "retirement_apply_artifact_present": applied.get("retirement_apply_artifact_present"),
    }
