"""CRM v1 read API — leads + domain events (Phase 1 strangler / NestJS dual-run prep)."""
from __future__ import annotations

from typing import Any

from flask import Blueprint, jsonify, request

from crm_http import deps

bp = Blueprint("crm_leads_v1", __name__)


def _can(action: str = "view") -> bool:
    return deps.admin_section_can("crm_agency", action)


def _deny_json(action: str = "view") -> Any:
    return deps.admin_section_forbidden_json("crm_agency", action)


def _pg_error_response(exc: Exception) -> tuple[Any, int]:
    return jsonify({"error": str(exc), "hint": "Kiểm tra DATABASE_URL và docker compose up -d"}), 503


@bp.get("/api/v1/leads")
def api_list_leads() -> Any:
    if not _can("view"):
        return _deny_json("view")
    try:
        from ptt_crm.leads_upstream import nest_upstream_enabled, proxy_list_leads

        if nest_upstream_enabled():
            body, status = proxy_list_leads(request.query_string.decode())
            return jsonify(body), status
        from ptt_crm.leads_read import list_leads_v1

        limit = min(int(request.args.get("limit") or 50), 200)
        offset = max(0, int(request.args.get("offset") or 0))
        leads, total = list_leads_v1(
            client_id=(request.args.get("client_id") or "").strip() or None,
            status=(request.args.get("status") or "").strip() or None,
            source=(request.args.get("source") or "").strip() or None,
            channel=(request.args.get("channel") or "").strip() or None,
            q=(request.args.get("q") or "").strip() or None,
            limit=limit,
            offset=offset,
        )
        payload = {"leads": leads, "total": total, "limit": limit, "offset": offset}
        from ptt_crm.dual_run import maybe_dual_run_list

        maybe_dual_run_list(payload, query=request.query_string.decode())
        return jsonify(payload)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@bp.get("/api/v1/leads/<int:lead_id>")
def api_get_lead(lead_id: int) -> Any:
    if not _can("view"):
        return _deny_json("view")
    try:
        from ptt_crm.leads_upstream import nest_upstream_enabled, proxy_get_lead

        if nest_upstream_enabled():
            body, status = proxy_get_lead(lead_id)
            return jsonify(body), status
        from ptt_crm.leads_read import get_lead_v1

        lead = get_lead_v1(lead_id)
        from ptt_crm.dual_run import maybe_dual_run_get

        if not lead:
            maybe_dual_run_get(lead_id, None)
            return jsonify({"error": "Not found"}), 404
        maybe_dual_run_get(lead_id, lead)
        return jsonify(lead)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@bp.get("/api/v1/events")
def api_list_events() -> Any:
    if not _can("view"):
        return _deny_json("view")
    try:
        from ptt_jobs.events_store import event_stats, list_domain_events

        event_type = (request.args.get("event_type") or "").strip() or None
        limit = min(int(request.args.get("limit") or 50), 200)
        rows = list_domain_events(event_type=event_type, limit=limit)
        return jsonify({"events": rows, "stats": event_stats()})
    except Exception as exc:
        return _pg_error_response(exc)
