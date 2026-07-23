"""Meta Ads Flask admin retirement — ops-web canonical hub (Horizon 1 B3.3)."""
from __future__ import annotations

from typing import Any

from ptt_crm.config import (
    meta_ads_admin_retired,
    meta_ads_ops_on_ops_web,
    meta_ads_ops_web_hub_path,
    meta_ads_ops_web_hub_url,
)


def flask_meta_ads_admin_redirect() -> tuple[str, int] | None:
    """When retired, Flask HTML routes should 302 to ops-web Meta hub."""
    if not meta_ads_admin_retired():
        return None
    return meta_ads_ops_web_hub_url(), 302


def migration_status() -> dict[str, Any]:
    retired = meta_ads_admin_retired()
    return {
        "ok": True,
        "flask_meta_ads_admin_retired": retired,
        "ops_web_hub_url": meta_ads_ops_web_hub_url(),
        "ops_web_hub_path": meta_ads_ops_web_hub_path(),
        "canonical_upstream": "ops-web" if meta_ads_ops_on_ops_web() else "flask",
        "gate_m1_g09": retired,
    }
