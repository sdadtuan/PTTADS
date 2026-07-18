"""Lead intake form definitions — single source for HTML generator + CRM UI."""
from __future__ import annotations

import importlib.util
from functools import lru_cache
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent

BANT_KEYS: tuple[str, ...] = (
    "budget",
    "authority",
    "need",
    "timeline",
    "fit",
    "history",
)

STAKEHOLDER_ROLES: tuple[tuple[str, str], ...] = (
    ("decision_maker", "Decision Maker"),
    ("influencer", "Influencer"),
    ("gatekeeper", "Gatekeeper"),
    ("user", "User"),
)

GO_THRESHOLDS: dict[str, int] = {"go": 24, "nurture_min": 18}
# Giữ 24/18 đến khi Director ký §6 sign-off. Mục tiêu sau ký: go=22, nurture_min=16 (Q1).

COMMON_FORM_SLUG = "_common"

COMMON_CRM_FIELDS: list[dict[str, str]] = [
    {"key": "suspected_service", "label": "Dịch vụ nghi ngờ / ưu tiên", "type": "text"},
    {"key": "need", "label": "Nhu cầu / pain point", "type": "textarea"},
    {"key": "budget", "label": "Ngân sách (VND)", "type": "number"},
    {"key": "notes", "label": "Ghi chú AM / bước tiếp", "type": "textarea"},
]

_COMMON_SLUG_ALIASES = frozenset({
    COMMON_FORM_SLUG,
    "00-form-chung",
    "common",
    "form-chung",
})


@lru_cache(maxsize=1)
def _generator_module() -> Any:
    path = ROOT / "scripts" / "generate_lead_intake_forms.py"
    spec = importlib.util.spec_from_file_location("_ptt_intake_forms_gen", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load intake definitions from {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def service_slugs() -> tuple[str, ...]:
    return tuple(_generator_module().SERVICE_SLUGS)


def service_forms() -> dict[str, dict[str, Any]]:
    return _generator_module().SERVICE_FORMS


def bant_rows() -> list[tuple[str, str]]:
    return list(_generator_module().BANT_ROWS)


def is_common_slug(slug: str) -> bool:
    return str(slug or "").strip().lower() in _COMMON_SLUG_ALIASES


def normalize_intake_slug(slug: str) -> str:
    if is_common_slug(slug):
        return COMMON_FORM_SLUG
    return str(slug or "").strip()


def resolve_definition_slug(service_slug: str) -> str:
    """Slug dùng load UI — unknown slug → form chung."""
    if is_common_slug(service_slug):
        return COMMON_FORM_SLUG
    s = str(service_slug or "").strip()
    if s in service_slugs():
        return s
    return COMMON_FORM_SLUG


def get_common_form_definition() -> dict[str, Any]:
    return _generator_module().build_common_form_dict()


def get_service_definition(slug: str) -> dict[str, Any] | None:
    if is_common_slug(slug):
        return get_common_form_definition()
    return service_forms().get(str(slug or "").strip())


def _ui_payload_from_service(slug: str, svc: dict[str, Any]) -> dict[str, Any]:
    return {
        "slug": slug,
        "title": svc.get("title") or slug,
        "group": svc.get("group") or "",
        "overview": svc.get("overview") or "",
        "icp": svc.get("icp") or "",
        "sla": svc.get("sla") or "",
        "call_script": svc.get("call_script") or "",
        "phone_questions": list(svc.get("phone_qs") or []),
        "inperson_questions": list(svc.get("inperson_qs") or []),
        "red_flags": list(svc.get("red_flags") or []),
        "urgency_triggers": list(svc.get("urgency") or []),
        "objections": [{"title": t, "hint": h} for t, h in svc.get("objections") or []],
        "demo_checklist": list(svc.get("demo_checklist") or []),
        "docs": [{"name": d[0], "lead": d[1], "onboard": d[2]} for d in svc.get("docs") or []],
        "kpi_questions": list(svc.get("kpi_questions") or []),
        "scope_questions": list(svc.get("scope_questions") or []),
        "closing_script": svc.get("closing_script") or "",
        "upsell_paths": list(svc.get("upsell") or []),
        "bant_rows": build_bant_rows_ui(),
        "is_common_form": slug == COMMON_FORM_SLUG,
    }


def get_ui_definition(slug: str) -> dict[str, Any]:
    """Payload gọn cho CRM intake UI."""
    def_slug = resolve_definition_slug(slug)
    svc = get_service_definition(def_slug)
    if not svc:
        svc = get_common_form_definition()
        def_slug = COMMON_FORM_SLUG
    return _ui_payload_from_service(def_slug, svc)


def get_crm_fields_for_slug(slug: str) -> list[dict[str, str]]:
    """Trường CRM tab Chốt — form chung dùng field generic."""
    if resolve_definition_slug(slug) == COMMON_FORM_SLUG:
        return list(COMMON_CRM_FIELDS)
    from crm_svc_workflow_steps import SERVICE_WORKFLOW_STEPS

    steps = SERVICE_WORKFLOW_STEPS.get(str(slug or "").strip(), {}).get("lead") or []
    if not steps:
        return list(COMMON_CRM_FIELDS)
    fields = steps[0].get("form_fields") or []
    return list(fields) if fields else list(COMMON_CRM_FIELDS)


# Lead / Intake crm_fields → Consult task form_data (C2 prefill)
_DEFAULT_CRM_TO_CONSULT: dict[str, str] = {
    "niche": "target_audience",
    "domain": "current_status",
    "goal": "current_status",
    "campaign_goal": "product_usp",
}

_SLUG_CRM_TO_CONSULT: dict[str, dict[str, str]] = {
    "dich-vu-seo-tong-the": {
        "domain": "current_status",
        "need": "current_status",
    },
    "dich-vu-aeo": {
        "domain": "current_status",
        "need": "current_status",
    },
    "dich-vu-seo-local": {
        "city": "local_keywords",
        "gbp_status": "current_status",
        "need": "current_status",
    },
    "dich-vu-seo-audit": {
        "domain": "current_status",
        "need": "audit_scope",
    },
    "dich-vu-quan-tri-website": {
        "domain": "current_status",
        "platform": "current_status",
        "need": "pain_points",
    },
    "thiet-ke-website": {
        "website_type": "current_status",
        "need": "current_status",
    },
    "thiet-ke-website-tron-goi": {
        "website_type": "current_status",
        "features": "current_status",
        "need": "integrations",
    },
    "thiet-ke-landing-page": {
        "lp_purpose": "usp",
        "campaign": "target_audience",
        "niche": "target_audience",
    },
    "quang-cao-facebook": {
        "niche": "target_audience",
        "campaign_goal": "product_usp",
        "has_ads_account": "current_status",
        "daily_budget": "current_status",
    },
    "quang-cao-google": {
        "niche": "target_keywords",
        "campaign_type": "current_status",
        "has_google_ads": "current_status",
        "monthly_budget": "current_status",
    },
    "thue-tai-khoan-quang-cao": {
        "platform": "current_status",
        "urgency": "risk_assessment",
        "niche": "current_status",
        "monthly_spend": "current_status",
    },
    "tiep-thi-noi-dung": {
        "channels": "current_status",
        "articles_per_month": "current_status",
        "need": "current_status",
    },
}


def get_crm_field_map(slug: str) -> dict[str, str]:
    """Map key crm_fields (Lead/Intake) → key form Consult — theo slug."""
    key = str(slug or "").strip()
    merged = dict(_DEFAULT_CRM_TO_CONSULT)
    merged.update(_SLUG_CRM_TO_CONSULT.get(key, {}))
    return merged


def build_bant_rows_ui() -> list[dict[str, str]]:
    key_map = {
        "Budget": "budget",
        "Authority": "authority",
        "Need": "need",
        "Timeline": "timeline",
        "Fit": "fit",
        "History": "history",
    }
    return [
        {"key": key_map.get(label, label.lower()), "label": label, "hint": hint}
        for label, hint in bant_rows()
    ]
