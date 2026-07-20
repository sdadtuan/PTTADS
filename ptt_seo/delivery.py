"""Service Workflow delivery panel data."""
from __future__ import annotations

from typing import Any

from ptt_seo.client_settings import get_settings
from ptt_seo.constants import is_seo_aeo_service_slug, project_type_for_slug
from ptt_seo.initiatives import list_initiatives
from ptt_seo.projects import ensure_project_for_lifecycle, get_project_by_lifecycle


def build_delivery_panel(
    conn: Any,
    *,
    customer_id: int,
    lifecycle_id: int,
    service_slug: str,
    customer_name: str = "",
    seo_conn: Any | None = None,
) -> dict[str, Any] | None:
    if not is_seo_aeo_service_slug(service_slug):
        return None

    seo = seo_conn if seo_conn is not None else conn

    project_id = ensure_project_for_lifecycle(
        seo,
        customer_id=customer_id,
        lifecycle_id=lifecycle_id,
        service_slug=service_slug,
        name=f"{customer_name} — {service_slug}".strip(" —"),
    )
    project = get_project_by_lifecycle(seo, lifecycle_id) or {}
    settings = get_settings(seo, customer_id)
    initiatives = list_initiatives(seo, customer_id, lifecycle_id=lifecycle_id)[:5]

    content_counts: dict[str, int] = {}
    content_total = 0
    try:
        from ptt_seo.content import count_by_status

        content_counts = count_by_status(seo, customer_id)
        content_total = sum(content_counts.values())
    except Exception:
        pass

    aeo_stats: dict[str, int] | None = None
    try:
        from ptt_seo.aeo_store import list_aeo_questions
        from ptt_seo.db import SeoDB

        db = seo if isinstance(seo, SeoDB) else SeoDB(seo, "sqlite")
        qs = list_aeo_questions(db, customer_id)
        aeo_stats = {
            "total": len(qs),
            "visible": sum(1 for q in qs if int(q.get("brand_visible") or 0) == 1),
        }
    except Exception:
        aeo_stats = {"total": 0, "visible": 0}

    technical_open = 0
    gsc_clicks = 0
    try:
        from ptt_seo.connectors.gsc import gsc_summary
        from ptt_seo.technical import list_issues

        technical_open = len(list_issues(seo, customer_id))
        gsc = gsc_summary(seo, customer_id, days=28)
        gsc_clicks = int(gsc.get("clicks") or 0)
    except Exception:
        pass

    domains = settings.get("domains") or []
    return {
        "project_id": project_id,
        "project_type": project_type_for_slug(service_slug),
        "service_slug": service_slug,
        "settings_configured": bool(domains or settings.get("industry")),
        "domains": domains,
        "contract_tier": settings.get("contract_tier") or "standard",
        "initiatives": initiatives,
        "initiatives_count": len(initiatives),
        "content_counts": content_counts,
        "content_total": content_total,
        "aeo_stats": aeo_stats,
        "technical_open": technical_open,
        "gsc_clicks_28d": gsc_clicks,
        "project": project,
    }
