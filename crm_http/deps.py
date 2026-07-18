"""Lazy access to app.py helpers — avoids circular import at blueprint load time."""
from __future__ import annotations

from typing import Any


def _app():
    import app as application

    return application


def get_connection():
    return _app().get_connection()


def admin_section_can(section_id: str, action: str, conn=None) -> bool:
    return _app()._admin_section_can(section_id, action, conn)


def admin_section_forbidden_json(section_id: str, action: str) -> Any:
    return _app()._admin_section_forbidden_json(section_id, action)


def ensure_crm_session_html() -> Any | None:
    return _app()._ensure_crm_session_html()


def admin_page_template_kwargs() -> dict[str, Any]:
    return _app()._admin_page_template_kwargs()


def crm_audit_user() -> str:
    return _app()._crm_audit_user()


def crm_ts() -> str:
    return _app()._crm_ts()


def crm_presales_on_lead_enabled() -> bool:
    return _app()._crm_presales_on_lead_enabled()


def crm_lead_can_access(conn, row) -> bool:
    return _app()._crm_lead_can_access(conn, row)
