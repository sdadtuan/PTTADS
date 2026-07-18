"""Lead product-model routes: tra soát B2 + add-on ngành."""
from __future__ import annotations

from typing import Any

from flask import Blueprint, jsonify, request

from crm_http import deps
from crm_lead_store import fetch_lead_by_id, lead_row_to_dict

bp = Blueprint("crm_leads_product", __name__)


@bp.post("/api/crm/leads/review-queue/sync", endpoint="api_crm_leads_review_queue_sync")
def api_crm_leads_review_queue_sync() -> Any:
    if not deps.admin_section_can("crm_leads", "configure"):
        return deps.admin_section_forbidden_json("crm_leads", "configure")
    from crm_lead_review_queue import sync_b2_review_queue

    dry_run = str(request.args.get("dry_run") or "").strip().lower() in ("1", "true", "yes")
    ts = deps.crm_ts()
    with deps.get_connection() as conn:
        summary = sync_b2_review_queue(
            conn,
            ts=ts,
            actor=deps.crm_audit_user(),
            dry_run=dry_run,
        )
        if not dry_run:
            conn.commit()
    return jsonify({"summary": summary})


@bp.post(
    "/api/crm/leads/<int:lead_id>/review-queue/release",
    endpoint="api_crm_lead_review_queue_release",
)
def api_crm_lead_review_queue_release(lead_id: int) -> Any:
    if not deps.admin_section_can("crm_leads", "configure"):
        return deps.admin_section_forbidden_json("crm_leads", "configure")
    from crm_lead_review_queue import release_lead_from_review_queue

    payload = request.get_json(force=True) or {}
    mode = str(payload.get("mode") or "").strip().lower()
    note = str(payload.get("note") or "").strip()
    raw_owner = payload.get("owner_id")
    new_owner_id: int | None = None
    if raw_owner not in (None, "", 0):
        try:
            new_owner_id = int(raw_owner)
        except (TypeError, ValueError):
            return jsonify({"error": "owner_id không hợp lệ."}), 400
    ts = deps.crm_ts()
    actor = deps.crm_audit_user()
    with deps.get_connection() as conn:
        prev = fetch_lead_by_id(conn, lead_id)
        if not deps.crm_lead_can_access(conn, prev):
            return jsonify({"error": "Không có quyền."}), 403
        if prev is None:
            return jsonify({"error": "Không tìm thấy lead."}), 404
        try:
            row = release_lead_from_review_queue(
                conn,
                lead_id,
                mode=mode,
                new_owner_id=new_owner_id,
                actor=actor,
                ts=ts,
                note=note,
            )
            conn.commit()
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        out = lead_row_to_dict(row, conn)
    return jsonify({"lead": out})


@bp.get(
    "/api/crm/leads/<int:lead_id>/industry-addon",
    endpoint="api_crm_lead_industry_addon_get",
)
def api_crm_lead_industry_addon_get(lead_id: int) -> Any:
    if not deps.admin_section_can("crm_leads", "view"):
        return deps.admin_section_forbidden_json("crm_leads", "view")
    with deps.get_connection() as conn:
        prev = fetch_lead_by_id(conn, lead_id)
        if not deps.crm_lead_can_access(conn, prev):
            return jsonify({"error": "Không có quyền."}), 403
        if prev is None:
            return jsonify({"error": "Không tìm thấy lead."}), 404
        from crm_lead_industry_addon import lead_industry_addon_payload

        payload = lead_industry_addon_payload(
            conn, lead_id, industry_slug=str(dict(prev).get("industry_slug") or "")
        )
    return jsonify(payload)


@bp.patch(
    "/api/crm/leads/<int:lead_id>/industry-addon",
    endpoint="api_crm_lead_industry_addon_patch",
)
def api_crm_lead_industry_addon_patch(lead_id: int) -> Any:
    if not deps.admin_section_can("crm_leads", "edit"):
        return deps.admin_section_forbidden_json("crm_leads", "edit")
    body = request.get_json(silent=True) or {}
    with deps.get_connection() as conn:
        prev = fetch_lead_by_id(conn, lead_id)
        if not deps.crm_lead_can_access(conn, prev):
            return jsonify({"error": "Không có quyền."}), 403
        if prev is None:
            return jsonify({"error": "Không tìm thấy lead."}), 404
        from crm_lead_industry_addon import update_lead_industry_addon

        try:
            payload = update_lead_industry_addon(conn, lead_id, body)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
    return jsonify(payload)
