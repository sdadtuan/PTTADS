"""SEO/AEO RBAC helpers — spec §9 section keys."""
from __future__ import annotations

from typing import Any

SEO_VIEW_SECTIONS: tuple[str, ...] = (
    "crm_seo_aeo",
    "crm_seo_aeo_write",
    "crm_seo_aeo_approve",
    "crm_seo_aeo_technical",
    "crm_seo_aeo_settings",
    "crm_seo_aeo_reports",
)


def _any(deps: Any, sections: tuple[str, ...], action: str) -> bool:
    act = str(action or "view").strip().lower()
    return any(deps.admin_section_can(s, act) for s in sections)


def can_view(deps: Any) -> bool:
    return _any(deps, SEO_VIEW_SECTIONS, "view")


def can_write(deps: Any, action: str = "edit") -> bool:
    act = action if action in ("edit", "create", "delete") else "edit"
    return _any(deps, ("crm_seo_aeo_write",), act) or deps.admin_section_can("crm_seo_aeo", act)


def can_approve(deps: Any) -> bool:
    return deps.admin_section_can("crm_seo_aeo_approve", "approve") or deps.admin_section_can(
        "crm_seo_aeo", "approve"
    )


def can_technical(deps: Any, action: str = "edit") -> bool:
    act = action if action in ("edit", "create", "view") else "edit"
    if act == "view":
        return can_view(deps)
    return _any(deps, ("crm_seo_aeo_technical",), act) or deps.admin_section_can("crm_seo_aeo", act)


def can_settings(deps: Any, action: str = "configure") -> bool:
    act = action if action in ("view", "edit", "configure") else "configure"
    if act == "view":
        return can_view(deps)
    return _any(deps, ("crm_seo_aeo_settings",), act) or deps.admin_section_can("crm_seo_aeo", act)


def can_reports(deps: Any, action: str = "view") -> bool:
    act = action if action in ("view", "export") else "view"
    return _any(deps, ("crm_seo_aeo_reports",), act) or deps.admin_section_can("crm_seo_aeo", act)


def ui_caps(deps: Any) -> dict[str, bool]:
    return {
        "can_seo_approve": can_approve(deps),
        "can_seo_configure": can_settings(deps, "configure"),
        "can_seo_export": can_reports(deps, "export"),
        "can_seo_write": can_write(deps, "edit") or can_write(deps, "create"),
        "can_seo_technical": can_technical(deps, "edit") or can_technical(deps, "create"),
    }
