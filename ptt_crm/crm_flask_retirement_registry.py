"""CRM Flask retirement — module registry and gap tracking."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class CrmModuleStatus(str, Enum):
    FLASK_ONLY = "flask_only"
    PARTIAL = "partial"
    OPS_WEB = "ops_web"
    RETIRED = "retired"


@dataclass(frozen=True)
class CrmModule:
    id: str
    label: str
    status: CrmModuleStatus
    flask_routes: str
    nest_module: str | None
    ops_web_route: str | None
    wave: int
    notes: str = ""


_RETIRED_NOTE = "Nest + ops-web canonical; Flask HTTP removed"

CRM_MODULES: tuple[CrmModule, ...] = (
    CrmModule(
        "leads",
        "CRM Leads",
        CrmModuleStatus.RETIRED,
        "app.py + crm_leads_v1 + crm-leads-legacy",
        "leads/ + crm-leads-legacy/",
        "/crm/leads",
        1,
        _RETIRED_NOTE,
    ),
    CrmModule("hub", "Hub campaigns", CrmModuleStatus.RETIRED, "app.py", "agency/", "/crm/hub", 1, _RETIRED_NOTE),
    CrmModule("agency", "Agency ops", CrmModuleStatus.RETIRED, "blueprints/agency.py", "agency/", "/agency", 0, _RETIRED_NOTE),
    CrmModule("meta", "Meta / Facebook Ads", CrmModuleStatus.RETIRED, "blueprints/agency.py", "agency/", "/meta/facebook-ads", 0, _RETIRED_NOTE),
    CrmModule("seo", "SEO / AEO admin", CrmModuleStatus.RETIRED, "blueprints/seo_aeo.py", "seo-admin/", "/seo/hub", 0, _RETIRED_NOTE),
    CrmModule("email", "Email marketing", CrmModuleStatus.RETIRED, "—", "email-marketing/", "/email/hub", 0, "Greenfield — never Flask"),
    CrmModule("webhooks", "Channel webhooks", CrmModuleStatus.RETIRED, "channel_webhooks.py", "webhooks/", "—", 0, _RETIRED_NOTE),
    CrmModule("catalog", "Lead catalog DV/ngành", CrmModuleStatus.RETIRED, "blueprints/catalog.py", "catalog/", "/crm/catalog", 1, _RETIRED_NOTE),
    CrmModule(
        "customers",
        "Customers / CSKH",
        CrmModuleStatus.RETIRED,
        "app.py",
        "customers/",
        "/crm/customers",
        2,
        _RETIRED_NOTE,
    ),
    CrmModule(
        "intake",
        "Lead intake forms",
        CrmModuleStatus.RETIRED,
        "app.py",
        "intake/",
        "/crm/intake",
        2,
        _RETIRED_NOTE,
    ),
    CrmModule(
        "staff",
        "Staff / HR",
        CrmModuleStatus.RETIRED,
        "app.py",
        "crm-staff/",
        "/crm/staff",
        4,
        _RETIRED_NOTE,
    ),
    CrmModule(
        "payroll",
        "Payroll / attendance",
        CrmModuleStatus.RETIRED,
        "app.py",
        "payroll/",
        "/crm/payroll",
        5,
        _RETIRED_NOTE,
    ),
    CrmModule(
        "marketing_plans",
        "Marketing plans",
        CrmModuleStatus.RETIRED,
        "app.py + presales",
        "marketing-plans/",
        "/crm/marketing-plan",
        3,
        _RETIRED_NOTE,
    ),
    CrmModule(
        "service_lifecycle",
        "Service delivery",
        CrmModuleStatus.RETIRED,
        "app.py + lifecycle",
        "service-lifecycle/ + svc-finance/",
        "/crm/service-delivery",
        3,
        _RETIRED_NOTE,
    ),
    CrmModule(
        "sop",
        "SOP runs",
        CrmModuleStatus.RETIRED,
        "app.py",
        "sop/",
        "/crm/sop",
        3,
        _RETIRED_NOTE,
    ),
    CrmModule(
        "sales",
        "Sales pipeline",
        CrmModuleStatus.RETIRED,
        "app.py",
        "sales/",
        "/crm/sales",
        4,
        _RETIRED_NOTE,
    ),
    CrmModule(
        "kpi",
        "KPI / staff KPI",
        CrmModuleStatus.RETIRED,
        "app.py",
        "kpi/",
        "/crm/kpi",
        4,
        _RETIRED_NOTE,
    ),
    CrmModule(
        "re_projects",
        "RE projects",
        CrmModuleStatus.RETIRED,
        "app.py",
        "re-projects/",
        "/crm/re-projects",
        5,
        _RETIRED_NOTE,
    ),
    CrmModule(
        "finance",
        "Finance / owner-weekly",
        CrmModuleStatus.RETIRED,
        "app.py",
        "finance/ + owner-weekly/",
        "/crm/business-dashboard",
        6,
        _RETIRED_NOTE,
    ),
    CrmModule(
        "cases",
        "Care cases",
        CrmModuleStatus.RETIRED,
        "app.py",
        "cases/",
        None,
        2,
        _RETIRED_NOTE,
    ),
    CrmModule(
        "proposals",
        "Proposals",
        CrmModuleStatus.RETIRED,
        "app.py",
        "proposals/",
        "/crm/proposals",
        4,
        _RETIRED_NOTE,
    ),
    CrmModule(
        "crm_shell",
        "CRM home / board",
        CrmModuleStatus.RETIRED,
        "app.py /crm",
        "crm-board/",
        "/crm",
        7,
        _RETIRED_NOTE,
    ),
)


def module_by_id(module_id: str) -> CrmModule | None:
    for m in CRM_MODULES:
        if m.id == module_id:
            return m
    return None


def gap_report() -> dict[str, Any]:
    total = len(CRM_MODULES)
    retired = sum(1 for m in CRM_MODULES if m.status == CrmModuleStatus.RETIRED)
    partial = sum(1 for m in CRM_MODULES if m.status == CrmModuleStatus.PARTIAL)
    ops = sum(1 for m in CRM_MODULES if m.status == CrmModuleStatus.OPS_WEB)
    flask_only = sum(1 for m in CRM_MODULES if m.status == CrmModuleStatus.FLASK_ONLY)
    migrated_pct = round(((retired + partial + ops) / total) * 100, 1) if total else 0.0
    waves: dict[int, list[dict[str, Any]]] = {}
    for m in CRM_MODULES:
        waves.setdefault(m.wave, []).append(
            {
                "id": m.id,
                "label": m.label,
                "status": m.status.value,
                "nest": m.nest_module,
                "ops_web": m.ops_web_route,
                "flask": m.flask_routes,
                "notes": m.notes,
            }
        )
    blockers = [m.id for m in CRM_MODULES if m.status == CrmModuleStatus.FLASK_ONLY and m.wave <= 3]
    return {
        "ok": flask_only == 0,
        "total_modules": total,
        "retired": retired,
        "partial": partial,
        "ops_web": ops,
        "flask_only": flask_only,
        "migrated_pct": migrated_pct,
        "can_stop_ptt_service": flask_only == 0 and partial == 0 and ops == 0,
        "phase5_blockers": blockers,
        "waves": waves,
        "next_modules": [m.id for m in CRM_MODULES if m.status == CrmModuleStatus.FLASK_ONLY and m.wave == min(x.wave for x in CRM_MODULES if x.status == CrmModuleStatus.FLASK_ONLY)],
    }


def main() -> None:
    import json
    import sys

    print(json.dumps(gap_report(), indent=2, ensure_ascii=False))
    sys.exit(0 if gap_report().get("can_stop_ptt_service") else 1)


if __name__ == "__main__":
    main()
