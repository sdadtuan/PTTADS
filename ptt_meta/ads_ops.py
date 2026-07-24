"""B15 — Meta Ads Ops launch templates, preflight, and payload builders."""
from __future__ import annotations

import os
from typing import Any

LAUNCH_TEMPLATES: list[dict[str, Any]] = [
    {
        "id": "re_lead_default",
        "label": "RE Lead — mặc định",
        "objective": "OUTCOME_LEADS",
        "optimization_goal": "LEAD_GENERATION",
        "billing_event": "IMPRESSIONS",
        "default_daily_budget_vnd": 500_000,
        "description": "Template Lead Gen cho BĐS — objective OUTCOME_LEADS",
    },
    {
        "id": "re_traffic_warm",
        "label": "RE Traffic warm-up",
        "objective": "OUTCOME_TRAFFIC",
        "optimization_goal": "LINK_CLICKS",
        "billing_event": "IMPRESSIONS",
        "default_daily_budget_vnd": 300_000,
        "description": "Traffic warm trước khi chuyển Lead",
    },
]


def ads_ops_enabled() -> bool:
    return os.environ.get("PTT_META_ADS_OPS_ENABLED", "0").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def ads_ops_pilot_clients() -> set[str]:
    raw = os.environ.get("PTT_META_ADS_OPS_PILOT_CLIENTS", "")
    return {item.strip() for item in raw.split(",") if item.strip()}


def check_ads_ops_pilot(client_id: str) -> dict[str, Any]:
    if not ads_ops_enabled():
        return {"allowed": False, "reason": "PTT_META_ADS_OPS_ENABLED=0"}
    allowlist = ads_ops_pilot_clients()
    if allowlist and client_id.strip() not in allowlist:
        return {"allowed": False, "reason": "client_not_in_pilot", "pilot_clients": sorted(allowlist)}
    return {"allowed": True}


def list_launch_templates() -> list[dict[str, Any]]:
    return list(LAUNCH_TEMPLATES)


def get_launch_template(template_id: str) -> dict[str, Any] | None:
    tid = str(template_id or "").strip()
    for item in LAUNCH_TEMPLATES:
        if item["id"] == tid:
            return dict(item)
    return None


def build_create_campaign_payload(
    *,
    client_id: str,
    external_account_id: str,
    template_id: str,
    campaign_name: str,
    adset_name: str,
    ad_name: str,
    daily_budget_vnd: int,
    creative_submission_id: str,
    objective: str | None = None,
    submitted_by: str | None = None,
) -> dict[str, Any]:
    template = get_launch_template(template_id) or LAUNCH_TEMPLATES[0]
    return {
        "action": "create_campaign",
        "client_id": client_id,
        "external_account_id": external_account_id,
        "template_id": template["id"],
        "campaign_name": campaign_name,
        "adset_name": adset_name,
        "ad_name": ad_name,
        "objective": objective or template["objective"],
        "optimization_goal": template["optimization_goal"],
        "daily_budget_vnd": int(daily_budget_vnd),
        "creative_submission_id": creative_submission_id,
        "submitted_by": submitted_by or "am@pttads.vn",
    }


def validate_launch_payload(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for key in (
        "client_id",
        "external_account_id",
        "campaign_name",
        "adset_name",
        "ad_name",
        "creative_submission_id",
    ):
        if not str(payload.get(key) or "").strip():
            errors.append(f"{key}_required")
    budget = payload.get("daily_budget_vnd")
    if budget is None or int(budget) <= 0:
        errors.append("daily_budget_vnd_invalid")
    return errors
