"""Multi-tenant report white-label config (Gate C P3)."""
from __future__ import annotations

from typing import Any


DEFAULT_PRIMARY = "#2563eb"
DEFAULT_FOOTER = "Báo cáo SEO/AEO — confidential"


def brand_config_from_settings(settings: dict[str, Any] | None) -> dict[str, Any]:
    """Build PDF branding from seo_client_settings.brand_guidelines."""
    settings = settings or {}
    brand = settings.get("brand_guidelines") or {}
    if not isinstance(brand, dict):
        brand = {}
    company = (
        str(brand.get("report_company_name") or brand.get("company_name") or "").strip()
        or str(settings.get("company_name") or "").strip()
    )
    hide = brand.get("hide_agency_branding")
    return {
        "company_name": company,
        "report_title_prefix": str(brand.get("report_title_prefix") or "SEO/AEO Report").strip(),
        "primary_color": _hex_color(brand.get("primary_color"), DEFAULT_PRIMARY),
        "accent_color": _hex_color(brand.get("accent_color"), "#1e40af"),
        "footer_text": str(brand.get("report_footer") or brand.get("footer_text") or DEFAULT_FOOTER).strip(),
        "hide_agency_branding": hide in (True, 1, "1", "true", "yes"),
        "logo_url": str(brand.get("logo_url") or "").strip(),
    }


def _hex_color(raw: Any, default: str) -> str:
    val = str(raw or "").strip()
    if val.startswith("#") and len(val) in (4, 7):
        return val
    if val.startswith("#") and len(val) == 9:
        return val[:7]
    return default
