"""Flask monolith guard stub — Flask HTTP retired."""
from __future__ import annotations

from typing import Any


def flask_monolith_readonly() -> bool:
    return False


def flask_monolith_retired() -> bool:
    return True


def deny_flask_write(action: str = "write") -> tuple[Any, int] | None:
    return None


def deny_flask_lead_write(action: str = "lead_write") -> tuple[Any, int] | None:
    return None


def deny_flask_agency_write(action: str = "agency_write") -> tuple[Any, int] | None:
    return None


def deny_flask_leads_legacy_write(action: str = "leads_legacy_write") -> tuple[Any, int] | None:
    return None


def deny_flask_customers_write(action: str = "customers_write") -> tuple[Any, int] | None:
    return None


def deny_flask_intake_write(action: str = "intake_write") -> tuple[Any, int] | None:
    return None


def deny_flask_cases_write(action: str = "cases_write") -> tuple[Any, int] | None:
    return None


def deny_flask_marketing_plans_write(action: str = "marketing_plans_write") -> tuple[Any, int] | None:
    return None


def deny_flask_service_lifecycle_write(action: str = "service_lifecycle_write") -> tuple[Any, int] | None:
    return None


def deny_flask_sop_write(action: str = "sop_write") -> tuple[Any, int] | None:
    return None


def deny_flask_sales_write(action: str = "sales_write") -> tuple[Any, int] | None:
    return None


def deny_flask_kpi_write(action: str = "kpi_write") -> tuple[Any, int] | None:
    return None


def deny_flask_staff_write(action: str = "staff_write") -> tuple[Any, int] | None:
    return None


def deny_flask_proposals_write(action: str = "proposals_write") -> tuple[Any, int] | None:
    return None


def deny_flask_re_projects_write(action: str = "re_projects_write") -> tuple[Any, int] | None:
    return None


def deny_flask_payroll_write(action: str = "payroll_write") -> tuple[Any, int] | None:
    return None


def deny_flask_finance_write(action: str = "finance_write") -> tuple[Any, int] | None:
    return None


def deny_flask_svc_finance_write(action: str = "svc_finance_write") -> tuple[Any, int] | None:
    return None


def deny_flask_meta_ads_admin(action: str = "meta_ads_admin") -> tuple[Any, int] | None:
    """Redirect Flask Meta hub to ops-web when PTT_FLASK_META_ADS_ADMIN_RETIRED=1."""
    from ptt_crm.meta_ads_admin_retirement import flask_meta_ads_admin_redirect

    target = flask_meta_ads_admin_redirect()
    if not target:
        return None
    url, code = target
    return ({"redirect": url, "reason": action, "flask_meta_ads_admin_retired": True}, code)
