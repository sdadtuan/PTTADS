"""Pre-sales marketing plan (KH MKT sơ bộ) trên lead."""
from __future__ import annotations

from typing import Any

from flask import Blueprint, jsonify, request

from crm_http import deps
from crm_lead_store import fetch_lead_by_id

bp = Blueprint("crm_presales", __name__)


@bp.get(
    "/api/crm/leads/<int:lead_id>/presales/marketing-plan",
    endpoint="api_crm_lead_presales_marketing_plan_get",
)
def api_crm_lead_presales_marketing_plan_get(lead_id: int) -> Any:
    if not deps.admin_section_can("crm_leads", "view"):
        return deps.admin_section_forbidden_json("crm_leads", "view")
    if not deps.crm_presales_on_lead_enabled():
        return jsonify({"error": "PTT_PRESALES_ON_LEAD chưa bật"}), 400
    with deps.get_connection() as conn:
        prev = fetch_lead_by_id(conn, lead_id)
        if not deps.crm_lead_can_access(conn, prev):
            return jsonify({"error": "Không có quyền."}), 403
        if prev is None:
            return jsonify({"error": "Không tìm thấy lead."}), 404
        ps = conn.execute(
            "SELECT id FROM crm_lead_presales WHERE lead_id = ?", (lead_id,)
        ).fetchone()
        if ps is None:
            return jsonify({"error": "Chưa có pre-sales"}), 404
        from crm_lead_presales_marketing_plan import preliminary_plan_payload

        payload = preliminary_plan_payload(conn, int(ps["id"]))
    return jsonify(payload)


@bp.patch(
    "/api/crm/leads/<int:lead_id>/presales/marketing-plan",
    endpoint="api_crm_lead_presales_marketing_plan_patch",
)
def api_crm_lead_presales_marketing_plan_patch(lead_id: int) -> Any:
    if not deps.admin_section_can("crm_leads", "edit"):
        return deps.admin_section_forbidden_json("crm_leads", "edit")
    if not deps.crm_presales_on_lead_enabled():
        return jsonify({"error": "PTT_PRESALES_ON_LEAD chưa bật"}), 400
    body = request.get_json(silent=True) or {}
    with deps.get_connection() as conn:
        prev = fetch_lead_by_id(conn, lead_id)
        if not deps.crm_lead_can_access(conn, prev):
            return jsonify({"error": "Không có quyền."}), 403
        if prev is None:
            return jsonify({"error": "Không tìm thấy lead."}), 404
        from crm_lead_presales import require_presales_care_gate

        try:
            require_presales_care_gate(conn, lead_id)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        ps = conn.execute(
            "SELECT id FROM crm_lead_presales WHERE lead_id = ?", (lead_id,)
        ).fetchone()
        if ps is None:
            return jsonify({"error": "Chưa có pre-sales"}), 404
        from crm_lead_presales_marketing_plan import (
            preliminary_plan_payload,
            update_preliminary_plan,
        )

        update_preliminary_plan(conn, int(ps["id"]), body)
        payload = preliminary_plan_payload(conn, int(ps["id"]))
    return jsonify(payload)
