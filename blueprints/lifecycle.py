"""TMMT chính thức @ Deliver (service lifecycle)."""
from __future__ import annotations

from typing import Any

from flask import Blueprint, jsonify, request

from crm_http import deps

bp = Blueprint("crm_lifecycle", __name__)


@bp.get(
    "/api/crm/service-lifecycle/<int:lifecycle_id>/marketing-plan",
    endpoint="api_svc_lifecycle_marketing_plan_get",
)
def api_svc_lifecycle_marketing_plan_get(lifecycle_id: int) -> Any:
    if not deps.admin_section_can("crm_leads", "view"):
        return deps.admin_section_forbidden_json("crm_leads", "view")
    with deps.get_connection() as conn:
        row = conn.execute(
            "SELECT id FROM crm_service_lifecycle WHERE id = ?", (lifecycle_id,)
        ).fetchone()
        if row is None:
            return jsonify({"error": "Không tìm thấy lifecycle"}), 404
        from crm_lead_presales_marketing_plan import official_plan_payload

        payload = official_plan_payload(conn, lifecycle_id)
    return jsonify(payload)


@bp.patch(
    "/api/crm/service-lifecycle/<int:lifecycle_id>/marketing-plan",
    endpoint="api_svc_lifecycle_marketing_plan_patch",
)
def api_svc_lifecycle_marketing_plan_patch(lifecycle_id: int) -> Any:
    if not deps.admin_section_can("crm_leads", "edit"):
        return deps.admin_section_forbidden_json("crm_leads", "edit")
    body = request.get_json(silent=True) or {}
    with deps.get_connection() as conn:
        row = conn.execute(
            "SELECT id FROM crm_service_lifecycle WHERE id = ?", (lifecycle_id,)
        ).fetchone()
        if row is None:
            return jsonify({"error": "Không tìm thấy lifecycle"}), 404
        from crm_lead_presales_marketing_plan import (
            official_plan_payload,
            update_official_plan,
        )

        try:
            update_official_plan(conn, lifecycle_id, body)
            conn.commit()
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        payload = official_plan_payload(conn, lifecycle_id)
    return jsonify(payload)
