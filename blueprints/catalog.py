"""Catalog DV/ngành + phạm vi phân công lead."""
from __future__ import annotations

from typing import Any

from flask import Blueprint, jsonify, redirect, render_template, request, url_for

from crm_http import deps

bp = Blueprint("crm_catalog", __name__)


@bp.get("/crm/catalog", endpoint="crm_catalog_page")
def crm_catalog_page() -> str:
    redir = deps.ensure_crm_session_html()
    if redir is not None:
        return redir
    if not deps.admin_section_can("crm_leads", "view"):
        return redirect(url_for("crm_leads_page"))
    with deps.get_connection() as conn:
        from crm_lead_catalog import catalog_public_payload
        from crm_lead_assign_scope import list_staff_assign_scopes

        catalog = catalog_public_payload(conn)
        scopes = list_staff_assign_scopes(conn)
        staff_rows = conn.execute(
            "SELECT id, name FROM crm_staff WHERE COALESCE(active, 1) = 1 ORDER BY name"
        ).fetchall()
        return render_template(
            "crm_catalog.html",
            **{
                **deps.admin_page_template_kwargs(),
                "crm_catalog_services": catalog.get("services") or [],
                "crm_catalog_industries": catalog.get("industries") or [],
                "crm_assign_scopes": scopes,
                "crm_assign_staff": [
                    {"id": int(r["id"]), "name": str(r["name"] or "")} for r in staff_rows
                ],
                "crm_leads_can_configure": deps.admin_section_can("crm_leads", "configure"),
            },
        )


@bp.get("/api/crm/catalog", endpoint="api_crm_catalog_public")
def api_crm_catalog_public() -> Any:
    if not deps.admin_section_can("crm_leads", "view"):
        return deps.admin_section_forbidden_json("crm_leads", "view")
    with deps.get_connection() as conn:
        from crm_lead_catalog import catalog_public_payload

        return jsonify(catalog_public_payload(conn))


@bp.get("/api/crm/catalog/services", endpoint="api_crm_catalog_services_list")
def api_crm_catalog_services_list() -> Any:
    if not deps.admin_section_can("crm_leads", "view"):
        return deps.admin_section_forbidden_json("crm_leads", "view")
    with deps.get_connection() as conn:
        from crm_lead_catalog import list_catalog_services

        return jsonify({"services": list_catalog_services(conn)})


@bp.post("/api/crm/catalog/services", endpoint="api_crm_catalog_services_create")
def api_crm_catalog_services_create() -> Any:
    if not deps.admin_section_can("crm_leads", "configure"):
        return deps.admin_section_forbidden_json("crm_leads", "configure")
    payload = request.get_json(force=True) or {}
    with deps.get_connection() as conn:
        from crm_lead_catalog import create_catalog_service

        try:
            row = create_catalog_service(
                conn,
                slug=str(payload.get("slug") or ""),
                name=str(payload.get("name") or ""),
                description=str(payload.get("description") or ""),
                sort_order=int(payload.get("sort_order") or 0),
                active=bool(payload.get("active", True)),
                updated_by=deps.crm_audit_user(),
            )
            conn.commit()
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
    return jsonify({"service": row}), 201


@bp.patch(
    "/api/crm/catalog/services/<int:service_id>",
    endpoint="api_crm_catalog_services_update",
)
def api_crm_catalog_services_update(service_id: int) -> Any:
    if not deps.admin_section_can("crm_leads", "configure"):
        return deps.admin_section_forbidden_json("crm_leads", "configure")
    payload = request.get_json(force=True) or {}
    with deps.get_connection() as conn:
        from crm_lead_catalog import update_catalog_service

        try:
            row = update_catalog_service(
                conn,
                service_id,
                name=payload.get("name"),
                description=payload.get("description"),
                sort_order=(
                    int(payload["sort_order"])
                    if payload.get("sort_order") is not None
                    else None
                ),
                active=payload.get("active") if "active" in payload else None,
            )
            conn.commit()
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
    return jsonify({"service": row})


@bp.get("/api/crm/catalog/industries", endpoint="api_crm_catalog_industries_list")
def api_crm_catalog_industries_list() -> Any:
    if not deps.admin_section_can("crm_leads", "view"):
        return deps.admin_section_forbidden_json("crm_leads", "view")
    with deps.get_connection() as conn:
        from crm_lead_catalog import list_catalog_industries

        return jsonify({"industries": list_catalog_industries(conn)})


@bp.post("/api/crm/catalog/industries", endpoint="api_crm_catalog_industries_create")
def api_crm_catalog_industries_create() -> Any:
    if not deps.admin_section_can("crm_leads", "configure"):
        return deps.admin_section_forbidden_json("crm_leads", "configure")
    payload = request.get_json(force=True) or {}
    with deps.get_connection() as conn:
        from crm_lead_catalog import create_catalog_industry

        try:
            row = create_catalog_industry(
                conn,
                slug=str(payload.get("slug") or ""),
                name=str(payload.get("name") or ""),
                description=str(payload.get("description") or ""),
                sort_order=int(payload.get("sort_order") or 0),
                active=bool(payload.get("active", True)),
            )
            conn.commit()
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
    return jsonify({"industry": row}), 201


@bp.patch(
    "/api/crm/catalog/industries/<int:industry_id>",
    endpoint="api_crm_catalog_industries_update",
)
def api_crm_catalog_industries_update(industry_id: int) -> Any:
    if not deps.admin_section_can("crm_leads", "configure"):
        return deps.admin_section_forbidden_json("crm_leads", "configure")
    payload = request.get_json(force=True) or {}
    with deps.get_connection() as conn:
        from crm_lead_catalog import update_catalog_industry

        try:
            row = update_catalog_industry(
                conn,
                industry_id,
                name=payload.get("name"),
                description=payload.get("description"),
                sort_order=(
                    int(payload["sort_order"])
                    if payload.get("sort_order") is not None
                    else None
                ),
                active=payload.get("active") if "active" in payload else None,
                traits=payload.get("traits") if "traits" in payload else None,
            )
            conn.commit()
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
    return jsonify({"industry": row})


@bp.get("/api/crm/assign-scopes", endpoint="api_crm_assign_scopes_list")
def api_crm_assign_scopes_list() -> Any:
    if not deps.admin_section_can("crm_leads", "view"):
        return deps.admin_section_forbidden_json("crm_leads", "view")
    with deps.get_connection() as conn:
        from crm_lead_assign_scope import list_staff_assign_scopes

        scopes = list_staff_assign_scopes(conn)
        staff_rows = conn.execute(
            """
            SELECT id, name, internal_code
            FROM crm_staff
            WHERE COALESCE(active, 1) = 1
            ORDER BY name ASC, id ASC
            """
        ).fetchall()
        staff = [
            {
                "id": int(r["id"]),
                "name": str(r["name"] or ""),
                "internal_code": str(r["internal_code"] or ""),
            }
            for r in staff_rows
        ]
    return jsonify({"scopes": scopes, "staff": staff})


@bp.post("/api/crm/assign-scopes", endpoint="api_crm_assign_scopes_create")
def api_crm_assign_scopes_create() -> Any:
    if not deps.admin_section_can("crm_leads", "configure"):
        return deps.admin_section_forbidden_json("crm_leads", "configure")
    payload = request.get_json(force=True) or {}
    with deps.get_connection() as conn:
        from crm_lead_assign_scope import create_staff_assign_scope

        try:
            row = create_staff_assign_scope(
                conn,
                staff_id=int(payload.get("staff_id") or 0),
                industry_slug=str(payload.get("industry_slug") or "*"),
                service_slug=str(payload.get("service_slug") or "*"),
                active=bool(payload.get("active", True)),
            )
            conn.commit()
        except (TypeError, ValueError) as exc:
            return jsonify({"error": str(exc)}), 400
    return jsonify({"scope": row}), 201


@bp.patch(
    "/api/crm/assign-scopes/<int:scope_id>",
    endpoint="api_crm_assign_scopes_update",
)
def api_crm_assign_scopes_update(scope_id: int) -> Any:
    if not deps.admin_section_can("crm_leads", "configure"):
        return deps.admin_section_forbidden_json("crm_leads", "configure")
    payload = request.get_json(force=True) or {}
    with deps.get_connection() as conn:
        from crm_lead_assign_scope import update_staff_assign_scope

        try:
            row = update_staff_assign_scope(
                conn,
                scope_id,
                active=payload.get("active") if "active" in payload else None,
            )
            conn.commit()
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
    return jsonify({"scope": row})


@bp.delete(
    "/api/crm/assign-scopes/<int:scope_id>",
    endpoint="api_crm_assign_scopes_delete",
)
def api_crm_assign_scopes_delete(scope_id: int) -> Any:
    if not deps.admin_section_can("crm_leads", "configure"):
        return deps.admin_section_forbidden_json("crm_leads", "configure")
    with deps.get_connection() as conn:
        from crm_lead_assign_scope import delete_staff_assign_scope

        try:
            delete_staff_assign_scope(conn, scope_id)
            conn.commit()
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
    return jsonify({"ok": True})
