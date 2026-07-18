"""Agency Ops — UI + REST API (Phase 1)."""
from __future__ import annotations

from typing import Any

from flask import Blueprint, jsonify, redirect, render_template, request, url_for

from crm_http import deps

bp = Blueprint("crm_agency", __name__)


def _can(action: str = "view") -> bool:
    return deps.admin_section_can("crm_agency", action)


def _can_facebook_ads(action: str = "view") -> bool:
    if deps.admin_section_can("crm_facebook_ads", action):
        return True
    return deps.admin_section_can("crm_agency", action)


def _deny_json(action: str = "view") -> Any:
    return deps.admin_section_forbidden_json("crm_agency", action)


def _deny_facebook_json(action: str = "view") -> Any:
    return deps.admin_section_forbidden_json("crm_facebook_ads", action)


def _pg_error_response(exc: Exception) -> tuple[Any, int]:
    return jsonify({"error": str(exc), "hint": "Kiểm tra DATABASE_URL và docker compose up -d"}), 503


def _deny_flask_write() -> tuple[Any, int] | None:
    from ptt_crm.flask_guard import deny_flask_write

    return deny_flask_write("agency_write")


def _recipient_id() -> str:
    return str(request.cookies.get("ptt_session") or deps.crm_audit_user() or "admin")


# ---------------------------------------------------------------------------
# HTML pages
# ---------------------------------------------------------------------------


@bp.get("/crm/agency")
def crm_agency_dashboard_page() -> str:
    redir = deps.ensure_crm_session_html()
    if redir is not None:
        return redir
    if not _can("view"):
        return redirect(url_for("crm_leads_page"))
    stats: dict[str, Any] = {"pg_ready": False, "jobs": {}, "clients": {}, "form_spillover": {"open": 0, "total": 0}}
    try:
        from ptt_agency.clients import client_counts, pg_ready
        from ptt_jobs.store import job_stats

        stats["pg_ready"] = pg_ready()
        if stats["pg_ready"]:
            stats["jobs"] = job_stats()
            stats["clients"] = client_counts()
    except Exception:
        pass
    try:
        from ptt_jobs.form_ingest_failure import spillover_stats

        stats["form_spillover"] = spillover_stats()
    except Exception:
        pass
    return render_template(
        "crm_agency_dashboard.html",
        agency_stats=stats,
        **deps.admin_page_template_kwargs(),
    )


@bp.get("/crm/agency/clients")
@bp.get("/crm/agency/clients/new")
def crm_agency_clients_page() -> str:
    redir = deps.ensure_crm_session_html()
    if redir is not None:
        return redir
    if not _can("view"):
        return redirect(url_for("crm_leads_page"))
    return render_template(
        "crm_agency_clients.html",
        is_new=request.path.endswith("/new"),
        **deps.admin_page_template_kwargs(),
    )


@bp.get("/crm/agency/clients/<client_id>")
def crm_agency_client_detail_page(client_id: str) -> str:
    redir = deps.ensure_crm_session_html()
    if redir is not None:
        return redir
    if not _can("view"):
        return redirect(url_for("crm_agency.crm_agency_clients_page"))
    return render_template(
        "crm_agency_client_detail.html",
        client_id=client_id,
        **deps.admin_page_template_kwargs(),
    )


@bp.get("/crm/agency/ingest")
def crm_agency_ingest_page() -> str:
    redir = deps.ensure_crm_session_html()
    if redir is not None:
        return redir
    if not _can("view"):
        return redirect(url_for("crm_leads_page"))
    return render_template("crm_agency_ingest.html", **deps.admin_page_template_kwargs())


@bp.get("/crm/agency/notifications")
def crm_agency_notifications_page() -> str:
    redir = deps.ensure_crm_session_html()
    if redir is not None:
        return redir
    if not _can("view"):
        return redirect(url_for("crm_leads_page"))
    return render_template("crm_agency_notifications.html", **deps.admin_page_template_kwargs())


@bp.get("/crm/agency/kpi-definitions")
def crm_agency_kpi_page() -> str:
    redir = deps.ensure_crm_session_html()
    if redir is not None:
        return redir
    if not _can("view"):
        return redirect(url_for("crm_leads_page"))
    return render_template("crm_agency_kpi.html", **deps.admin_page_template_kwargs())


@bp.get("/crm/facebook-ads")
def crm_facebook_ads_hub_page() -> str:
    redir = deps.ensure_crm_session_html()
    if redir is not None:
        return redir
    if not _can_facebook_ads("view"):
        return redirect(url_for("crm_leads_page"))
    return render_template("crm_facebook_ads_hub.html", **deps.admin_page_template_kwargs())


# ---------------------------------------------------------------------------
# REST — clients
# ---------------------------------------------------------------------------


@bp.get("/api/v1/clients")
def api_list_clients() -> Any:
    if not _can("view"):
        return _deny_json("view")
    try:
        from ptt_agency.clients import list_clients

        rows = list_clients(
            status=(request.args.get("status") or "").strip() or None,
            q=(request.args.get("q") or "").strip() or None,
            owner_am_id=(request.args.get("owner_am_id") or "").strip() or None,
            industry_slug=(request.args.get("industry") or "").strip() or None,
            limit=min(int(request.args.get("limit") or 100), 200),
        )
        return jsonify({"clients": rows})
    except Exception as exc:
        return _pg_error_response(exc)


@bp.post("/api/v1/clients")
def api_create_client() -> Any:
    blocked = _deny_flask_write()
    if blocked:
        return blocked
    if not _can("create"):
        return _deny_json("create")
    payload = request.get_json(force=True) or {}
    try:
        from ptt_agency.clients import create_client

        client = create_client(
            code=str(payload.get("code") or ""),
            name=str(payload.get("name") or ""),
            industry_slug=str(payload.get("industry_slug") or ""),
            owner_am_id=str(payload.get("owner_am_id") or ""),
            notes=str(payload.get("notes") or ""),
        )
        return jsonify(client), 201
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        return _pg_error_response(exc)


@bp.get("/api/v1/clients/<client_id>/leads")
def api_client_leads(client_id: str) -> Any:
    if not _can("view"):
        return _deny_json("view")
    try:
        from ptt_agency.clients import fetch_client
        from ptt_agency.leads import list_leads_for_client

        if not fetch_client(client_id):
            return jsonify({"error": "Not found"}), 404
        limit = min(int(request.args.get("limit") or 50), 200)
        return jsonify({"leads": list_leads_for_client(client_id, limit=limit)})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@bp.get("/api/v1/clients/<client_id>")
def api_get_client(client_id: str) -> Any:
    if not _can("view"):
        return _deny_json("view")
    try:
        from ptt_agency.clients import fetch_client, list_channel_accounts, onboarding_progress

        client = fetch_client(client_id)
        if not client:
            return jsonify({"error": "Not found"}), 404
        client["progress"] = onboarding_progress(client_id)
        client["channel_accounts"] = list_channel_accounts(client_id)
        return jsonify(client)
    except Exception as exc:
        return _pg_error_response(exc)


@bp.patch("/api/v1/clients/<client_id>")
def api_patch_client(client_id: str) -> Any:
    blocked = _deny_flask_write()
    if blocked:
        return blocked
    if not _can("edit"):
        return _deny_json("edit")
    payload = request.get_json(force=True) or {}
    try:
        from ptt_agency.clients import update_client

        return jsonify(update_client(client_id, payload))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        return _pg_error_response(exc)


@bp.get("/api/v1/clients/<client_id>/checklist")
def api_get_checklist(client_id: str) -> Any:
    if not _can("view"):
        return _deny_json("view")
    try:
        from ptt_agency.clients import list_onboarding_items, onboarding_progress

        return jsonify(
            {"items": list_onboarding_items(client_id), "progress": onboarding_progress(client_id)}
        )
    except Exception as exc:
        return _pg_error_response(exc)


@bp.patch("/api/v1/clients/<client_id>/checklist/<item_key>")
def api_patch_checklist_item(client_id: str, item_key: str) -> Any:
    blocked = _deny_flask_write()
    if blocked:
        return blocked
    if not _can("edit"):
        return _deny_json("edit")
    payload = request.get_json(force=True) or {}
    try:
        from ptt_agency.clients import set_onboarding_item

        return jsonify(
            set_onboarding_item(
                client_id,
                item_key,
                completed=bool(payload.get("completed")),
                completed_by=deps.crm_audit_user(),
                note=str(payload.get("note") or ""),
            )
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        return _pg_error_response(exc)


@bp.post("/api/v1/clients/<client_id>/activate")
def api_activate_client(client_id: str) -> Any:
    blocked = _deny_flask_write()
    if blocked:
        return blocked
    if not _can("edit"):
        return _deny_json("edit")
    payload = request.get_json(force=True) or {}
    try:
        from ptt_agency.clients import activate_client

        return jsonify(activate_client(client_id, force=bool(payload.get("force"))))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        return _pg_error_response(exc)


@bp.post("/api/v1/clients/<client_id>/channel-accounts")
def api_add_channel_account(client_id: str) -> Any:
    blocked = _deny_flask_write()
    if blocked:
        return blocked
    if not _can("edit"):
        return _deny_json("edit")
    payload = request.get_json(force=True) or {}
    try:
        from ptt_agency.clients import add_channel_account

        row = add_channel_account(
            client_id,
            channel=str(payload.get("channel") or ""),
            external_account_id=str(payload.get("external_account_id") or ""),
            display_name=str(payload.get("display_name") or ""),
            access_token=str(payload.get("access_token") or ""),
            token_expires_at=str(payload.get("token_expires_at") or "") or None,
            credential_ref=str(payload.get("credential_ref") or ""),
            pixel_id=str(payload.get("pixel_id") or ""),
        )
        return jsonify(row), 201
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        return _pg_error_response(exc)


@bp.patch("/api/v1/clients/<client_id>/channel-accounts/<account_id>/token")
def api_set_channel_account_token(client_id: str, account_id: str) -> Any:
    blocked = _deny_flask_write()
    if blocked:
        return blocked
    if not _can("edit"):
        return _deny_json("edit")
    payload = request.get_json(force=True) or {}
    try:
        from ptt_agency.clients import set_channel_account_token

        row = set_channel_account_token(
            client_id,
            account_id,
            access_token=str(payload.get("access_token") or ""),
            token_expires_at=str(payload.get("token_expires_at") or "") or None,
            credential_ref=str(payload.get("credential_ref") or ""),
            revoke=bool(payload.get("revoke")),
        )
        return jsonify(row)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        return _pg_error_response(exc)


@bp.patch("/api/v1/clients/<client_id>/channel-accounts/<account_id>/meta")
def api_update_channel_account_meta(client_id: str, account_id: str) -> Any:
    blocked = _deny_flask_write()
    if blocked:
        return blocked
    if not _can("edit"):
        return _deny_json("edit")
    payload = request.get_json(force=True) or {}
    try:
        from ptt_agency.clients import update_channel_account_meta

        row = update_channel_account_meta(
            client_id,
            account_id,
            pixel_id=str(payload["pixel_id"]).strip() if "pixel_id" in payload else None,
            meta_patch=payload.get("meta") if isinstance(payload.get("meta"), dict) else None,
        )
        return jsonify(row)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        return _pg_error_response(exc)


@bp.get("/api/v1/clients/<client_id>/google/oauth/url")
def api_google_oauth_url(client_id: str) -> Any:
    if not _can("edit"):
        return _deny_json("edit")
    try:
        from ptt_agency.clients import fetch_client
        from ptt_google.oauth import authorization_url

        if not fetch_client(client_id):
            return jsonify({"error": "Not found"}), 404
        account_id = (request.args.get("account_id") or "").strip() or None
        url = authorization_url(agency_client_id=client_id, account_id=account_id)
        return jsonify({"ok": True, "authorization_url": url})
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        return _pg_error_response(exc)


@bp.get("/api/v1/google/oauth/callback")
def api_google_oauth_callback() -> Any:
    code = (request.args.get("code") or "").strip()
    state = (request.args.get("state") or "").strip()
    if not code or not state:
        return jsonify({"error": "missing_code_or_state"}), 400
    try:
        from ptt_google.oauth import exchange_authorization_code, parse_oauth_state
        from ptt_agency.clients import add_channel_account, set_channel_account_token

        parsed = parse_oauth_state(state)
        agency_client_id = parsed.get("client_id") or ""
        if not agency_client_id:
            return jsonify({"error": "invalid_state"}), 400
        tokens = exchange_authorization_code(code)
        refresh = str(tokens.get("refresh_token") or "")
        if not refresh:
            return jsonify({"error": "missing_refresh_token"}), 400

        account_id = parsed.get("account_id") or ""
        customer_id = (request.args.get("customer_id") or "").strip()
        if not account_id:
            row = add_channel_account(
                agency_client_id,
                channel="google",
                external_account_id=customer_id or "pending-customer-id",
                display_name="Google Ads (OAuth)",
                access_token=refresh,
            )
            account_id = str(row.get("id") or "")
        else:
            set_channel_account_token(
                agency_client_id,
                account_id,
                access_token=refresh,
            )
        return jsonify(
            {
                "ok": True,
                "client_id": agency_client_id,
                "account_id": account_id,
                "message": "Google refresh token saved to vault",
            }
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        return _pg_error_response(exc)


# ---------------------------------------------------------------------------
# REST — jobs / ingest
# ---------------------------------------------------------------------------


@bp.get("/api/v1/jobs")
def api_list_jobs() -> Any:
    if not _can("view"):
        return _deny_json("view")
    try:
        from ptt_jobs.store import job_stats, list_jobs

        status = (request.args.get("status") or "").strip() or None
        return jsonify(
            {
                "stats": job_stats(),
                "jobs": list_jobs(status=status, limit=min(int(request.args.get("limit") or 50), 200)),
            }
        )
    except Exception as exc:
        return _pg_error_response(exc)


@bp.get("/api/v1/jobs/<job_id>")
def api_get_job(job_id: str) -> Any:
    if not _can("view"):
        return _deny_json("view")
    try:
        from ptt_jobs.store import get_job_by_id

        job = get_job_by_id(job_id)
        if not job:
            return jsonify({"error": "Not found"}), 404
        return jsonify(job)
    except Exception as exc:
        return _pg_error_response(exc)


@bp.post("/api/v1/jobs/<job_id>/replay")
def api_replay_job(job_id: str) -> Any:
    if not _can("configure"):
        return _deny_json("configure")
    try:
        from ptt_jobs.store import replay_job

        out = replay_job(job_id)
        if not out:
            return jsonify({"error": "Job không ở trạng thái dead hoặc không tồn tại"}), 400
        return jsonify(out)
    except Exception as exc:
        return _pg_error_response(exc)


@bp.get("/api/v1/form-ingest/spillover")
def api_list_form_ingest_spillover() -> Any:
    if not _can("view"):
        return _deny_json("view")
    try:
        from ptt_jobs.form_ingest_failure import list_form_ingest_spillover, spillover_stats

        open_only = request.args.get("open_only", "1") != "0"
        limit = min(int(request.args.get("limit") or 50), 200)
        return jsonify(
            {
                "stats": spillover_stats(),
                "items": list_form_ingest_spillover(limit=limit, open_only=open_only),
            }
        )
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@bp.post("/api/v1/form-ingest/spillover/<int:spillover_id>/replay")
def api_replay_form_ingest_spillover(spillover_id: int) -> Any:
    if not _can("configure"):
        return _deny_json("configure")
    try:
        from ptt_jobs.form_ingest_failure import replay_form_ingest_spillover

        out = replay_form_ingest_spillover(spillover_id)
        if not out.get("ok"):
            code = 404 if out.get("error") == "not_found" else 400
            return jsonify(out), code
        return jsonify(out)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@bp.get("/health/worker")
def health_worker() -> Any:
    try:
        from ptt_agency.clients import pg_ready
        from ptt_jobs.store import job_stats

        if not pg_ready():
            return jsonify({"ok": False, "pg": False}), 503
        stats = job_stats()
        payload: dict[str, Any] = {"ok": True, "pg": True, "jobs": stats}
        try:
            from ptt_crm.pg_schema import pg_leads_stats

            payload["crm_leads_replica"] = pg_leads_stats()
        except Exception:
            pass
        return jsonify(payload)
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 503


# ---------------------------------------------------------------------------
# REST — notifications + SLA cron
# ---------------------------------------------------------------------------


@bp.get("/api/v1/notifications")
def api_list_notifications() -> Any:
    if not _can("view"):
        return _deny_json("view")
    try:
        from ptt_agency.notifications import list_notifications

        rid = str(request.args.get("recipient_id") or _recipient_id())
        rows = list_notifications(
            rid,
            unread_only=request.args.get("unread") == "1",
            category=(request.args.get("category") or "").strip() or None,
        )
        return jsonify({"notifications": rows})
    except Exception as exc:
        return _pg_error_response(exc)


@bp.patch("/api/v1/notifications/<notification_id>")
def api_mark_notification(notification_id: str) -> Any:
    if not _can("edit"):
        return _deny_json("edit")
    try:
        from ptt_agency.notifications import mark_notification_read

        ok = mark_notification_read(notification_id, _recipient_id())
        return jsonify({"ok": ok})
    except Exception as exc:
        return _pg_error_response(exc)


@bp.post("/api/v1/notifications/mark-all-read")
def api_mark_all_notifications() -> Any:
    if not _can("edit"):
        return _deny_json("edit")
    try:
        from ptt_agency.notifications import mark_all_read

        n = mark_all_read(_recipient_id())
        return jsonify({"marked": n})
    except Exception as exc:
        return _pg_error_response(exc)


@bp.get("/api/v1/kpi-definitions")
def api_kpi_definitions() -> Any:
    if not _can("view"):
        return _deny_json("view")
    try:
        from ptt_agency.clients import list_kpi_definitions

        return jsonify({"definitions": list_kpi_definitions()})
    except Exception as exc:
        return _pg_error_response(exc)


@bp.get("/api/v1/facebook-ads/hub")
def api_facebook_ads_hub() -> Any:
    if not _can_facebook_ads("view"):
        return _deny_facebook_json("view")
    try:
        from ptt_agency.facebook_ads_hub import facebook_ads_hub_summary

        window_days = min(max(int(request.args.get("days") or 7), 1), 90)
        status = (request.args.get("status") or "").strip() or None
        date_to = (request.args.get("to") or request.args.get("date_to") or "").strip() or None
        out = facebook_ads_hub_summary(window_days=window_days, date_to=date_to or None, status=status)
        if not out.get("ok"):
            return jsonify(out), 503
        return jsonify(out)
    except Exception as exc:
        return _pg_error_response(exc)


@bp.get("/api/v1/performance")
@bp.get("/api/v1/clients/<client_id>/performance")
def api_campaign_performance(client_id: str | None = None) -> Any:
    if not _can("view"):
        return _deny_json("view")
    cid = (client_id or request.args.get("client_id") or "").strip()
    if not cid:
        return jsonify({"error": "client_id required"}), 400
    try:
        from ptt_agency.clients import fetch_client
        from ptt_agency.performance import list_campaign_performance

        if not fetch_client(cid):
            return jsonify({"error": "Not found"}), 404

        out = list_campaign_performance(
            client_id=cid,
            date_from=(request.args.get("from") or request.args.get("date_from") or "").strip() or None,
            date_to=(request.args.get("to") or request.args.get("date_to") or "").strip() or None,
            group_by=(request.args.get("group_by") or "day").strip(),
        )
        if not out.get("ok"):
            return jsonify(out), 503
        return jsonify(out)
    except Exception as exc:
        return _pg_error_response(exc)


@bp.get("/api/v1/clients/<client_id>/hub-campaign-maps")
def api_hub_campaign_maps(client_id: str) -> Any:
    if not _can("view"):
        return _deny_json("view")
    try:
        from ptt_agency.clients import fetch_client
        from ptt_agency.hub_campaign_map_read import list_hub_campaign_maps

        if not fetch_client(client_id):
            return jsonify({"error": "Not found"}), 404
        active_only = request.args.get("include_inactive", "0").strip().lower() not in {
            "1",
            "true",
            "yes",
        }
        channel = (request.args.get("channel") or "").strip().lower() or None
        out = list_hub_campaign_maps(client_id, channel=channel, active_only=active_only)
        if not out.get("ok"):
            return jsonify(out), 503
        return jsonify(out)
    except Exception as exc:
        return _pg_error_response(exc)


@bp.get("/api/v1/capi/stats")
def api_capi_stats() -> Any:
    if not _can("view"):
        return _deny_json("view")
    try:
        from ptt_meta.capi_dispatch import capi_stats

        client_id = (request.args.get("client_id") or "").strip() or None
        hours = min(int(request.args.get("hours") or 24), 168)
        return jsonify(capi_stats(client_id=client_id, hours=hours))
    except Exception as exc:
        return _pg_error_response(exc)


@bp.post("/api/v1/clients/<client_id>/workflows/onboarding/start")
def api_start_onboarding_workflow(client_id: str) -> Any:
    if not _can("edit"):
        return _deny_json("edit")
    try:
        from ptt_agency.clients import fetch_client
        from ptt_crm.nest_api import start_onboarding_workflow

        if not fetch_client(client_id):
            return jsonify({"error": "Not found"}), 404
        status, body = start_onboarding_workflow(client_id, deps.crm_audit_user())
        return jsonify(body), status if status else 502
    except Exception as exc:
        return _pg_error_response(exc)


@bp.post("/api/v1/clients/<client_id>/creatives/submit")
def api_submit_creative(client_id: str) -> Any:
    if not _can("edit"):
        return _deny_json("edit")
    payload = request.get_json(force=True) or {}
    try:
        from ptt_agency.clients import fetch_client
        from ptt_crm.nest_api import submit_creative

        if not fetch_client(client_id):
            return jsonify({"error": "Not found"}), 404
        body = {
            "client_id": client_id,
            "title": str(payload.get("title") or "").strip(),
            "description": str(payload.get("description") or "").strip(),
            "external_campaign_id": str(payload.get("external_campaign_id") or "").strip(),
            "external_campaign_name": str(payload.get("external_campaign_name") or "").strip(),
            "version": int(payload.get("version") or 1),
            "asset_url": str(payload.get("asset_url") or "").strip(),
            "submitted_by": deps.crm_audit_user(),
        }
        if not body["title"]:
            return jsonify({"error": "title required"}), 400
        status, out = submit_creative(body)
        return jsonify(out), status if status else 502
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        return _pg_error_response(exc)


@bp.get("/api/v1/clients/<client_id>/launch-qa")
def api_list_launch_qa(client_id: str) -> Any:
    if not _can("view"):
        return _deny_json("view")
    try:
        from ptt_agency.clients import fetch_client
        from ptt_agency.launch_qa import launch_qa_progress, list_launch_qa_runs

        if not fetch_client(client_id):
            return jsonify({"error": "Not found"}), 404
        runs = list_launch_qa_runs(client_id)
        for run in runs:
            run["progress"] = launch_qa_progress(run)
        return jsonify({"runs": runs})
    except Exception as exc:
        return _pg_error_response(exc)


@bp.post("/api/v1/clients/<client_id>/launch-qa/start")
def api_start_launch_qa(client_id: str) -> Any:
    if not _can("edit"):
        return _deny_json("edit")
    payload = request.get_json(force=True) or {}
    try:
        from ptt_agency.clients import fetch_client
        from ptt_crm.nest_api import start_launch_qa_workflow

        if not fetch_client(client_id):
            return jsonify({"error": "Not found"}), 404
        ext = str(payload.get("external_campaign_id") or "").strip()
        if not ext:
            return jsonify({"error": "external_campaign_id required"}), 400
        status, body = start_launch_qa_workflow(
            {
                "client_id": client_id,
                "external_campaign_id": ext,
                "campaign_name": str(payload.get("campaign_name") or "").strip(),
                "started_by": deps.crm_audit_user(),
            }
        )
        return jsonify(body), status if status else 502
    except Exception as exc:
        return _pg_error_response(exc)


@bp.patch("/api/v1/clients/<client_id>/launch-qa/<run_id>/checklist/<item_key>")
def api_patch_launch_qa_item(client_id: str, run_id: str, item_key: str) -> Any:
    blocked = _deny_flask_write()
    if blocked:
        return blocked
    if not _can("edit"):
        return _deny_json("edit")
    payload = request.get_json(force=True) or {}
    try:
        from ptt_agency.launch_qa import update_launch_qa_item
        from ptt_crm.nest_api import nudge_launch_qa_workflow

        run = update_launch_qa_item(
            run_id,
            item_key,
            completed=bool(payload.get("completed")),
            completed_by=deps.crm_audit_user(),
            note=str(payload.get("note") or ""),
        )
        if str(run.get("client_id")) != client_id:
            return jsonify({"error": "client mismatch"}), 403
        nudge_launch_qa_workflow(run_id)
        from ptt_agency.launch_qa import launch_qa_progress

        return jsonify({"run": run, "progress": launch_qa_progress(run)})
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        return _pg_error_response(exc)


@bp.get("/api/v1/clients/<client_id>/campaign-writes")
def api_list_campaign_writes(client_id: str) -> Any:
    if not _can("view"):
        return _deny_json("view")
    try:
        from ptt_agency.clients import fetch_client
        from ptt_crm.nest_api import list_pending_campaign_writes

        if not fetch_client(client_id):
            return jsonify({"error": "Not found"}), 404
        status, body = list_pending_campaign_writes(client_id)
        return jsonify(body), status if status else 502
    except Exception as exc:
        return _pg_error_response(exc)


@bp.post("/api/v1/clients/<client_id>/campaign-writes")
def api_submit_campaign_write(client_id: str) -> Any:
    if not _can("edit"):
        return _deny_json("edit")
    payload = request.get_json(force=True) or {}
    try:
        from ptt_agency.clients import fetch_client
        from ptt_crm.nest_api import submit_campaign_write

        if not fetch_client(client_id):
            return jsonify({"error": "Not found"}), 404
        ext = str(payload.get("external_campaign_id") or "").strip()
        if not ext:
            return jsonify({"error": "external_campaign_id required"}), 400
        new_value = payload.get("new_value")
        if not isinstance(new_value, dict):
            budget = payload.get("daily_budget_vnd")
            if budget is None:
                return jsonify({"error": "new_value or daily_budget_vnd required"}), 400
            new_value = {"daily_budget_vnd": int(budget)}
        body = {
            "client_id": client_id,
            "channel": str(payload.get("channel") or "meta").strip().lower(),
            "external_account_id": str(payload.get("external_account_id") or "").strip(),
            "external_campaign_id": ext,
            "external_campaign_name": str(payload.get("external_campaign_name") or "").strip(),
            "change_type": str(payload.get("change_type") or "daily_budget").strip(),
            "old_value": payload.get("old_value") if isinstance(payload.get("old_value"), dict) else {},
            "new_value": new_value,
            "submitted_by": deps.crm_audit_user(),
        }
        status, out = submit_campaign_write(body)
        return jsonify(out), status if status else 502
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        return _pg_error_response(exc)


@bp.post("/api/v1/clients/<client_id>/campaign-writes/<request_id>/approve")
def api_approve_campaign_write(client_id: str, request_id: str) -> Any:
    if not _can("edit"):
        return _deny_json("edit")
    payload = request.get_json(force=True) or {}
    try:
        from ptt_agency.clients import fetch_client
        from ptt_crm.nest_api import approve_campaign_write

        if not fetch_client(client_id):
            return jsonify({"error": "Not found"}), 404
        status, out = approve_campaign_write(
            request_id,
            {
                "approved_by": deps.crm_audit_user(),
                "note": str(payload.get("note") or ""),
            },
        )
        req = out.get("request") if isinstance(out, dict) else None
        if req and str(req.get("client_id")) != client_id:
            return jsonify({"error": "client mismatch"}), 403
        return jsonify(out), status if status else 502
    except Exception as exc:
        return _pg_error_response(exc)


@bp.post("/api/v1/clients/<client_id>/campaign-writes/<request_id>/reject")
def api_reject_campaign_write(client_id: str, request_id: str) -> Any:
    if not _can("edit"):
        return _deny_json("edit")
    payload = request.get_json(force=True) or {}
    try:
        from ptt_agency.clients import fetch_client
        from ptt_crm.nest_api import reject_campaign_write

        if not fetch_client(client_id):
            return jsonify({"error": "Not found"}), 404
        status, out = reject_campaign_write(
            request_id,
            {
                "approved_by": deps.crm_audit_user(),
                "note": str(payload.get("note") or ""),
            },
        )
        req = out.get("request") if isinstance(out, dict) else None
        if req and str(req.get("client_id")) != client_id:
            return jsonify({"error": "client mismatch"}), 403
        return jsonify(out), status if status else 502
    except Exception as exc:
        return _pg_error_response(exc)


@bp.post("/api/crm/agency/sla-sync-cron")
def api_agency_sla_sync_cron() -> Any:
    secret = (request.headers.get("X-Cron-Secret") or request.args.get("secret") or "").strip()
    import os

    expected = os.environ.get("CRM_AGENCY_SLA_CRON_SECRET", "").strip()
    if expected and secret != expected:
        return jsonify({"error": "Unauthorized"}), 401
    try:
        from ptt_agency.notifications import sync_sla_notifications
        from ptt_jobs.config import sqlite_db_path

        out = sync_sla_notifications(sqlite_path=sqlite_db_path(), ts=deps.crm_ts())
        return jsonify(out)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@bp.post("/api/crm/agency/lead-sync-cron")
def api_agency_lead_sync_cron() -> Any:
    secret = (request.headers.get("X-Cron-Secret") or request.args.get("secret") or "").strip()
    import os

    expected = os.environ.get("CRM_AGENCY_LEAD_SYNC_CRON_SECRET", "").strip()
    if expected and secret != expected:
        return jsonify({"error": "Unauthorized"}), 401
    try:
        from ptt_crm.lead_sync import reconcile_leads, sync_incremental

        mode = (request.args.get("mode") or "incremental").strip().lower()
        if mode == "reconcile":
            sample = min(int(request.args.get("sample") or 50), 500)
            return jsonify(reconcile_leads(sample_size=sample))
        if mode == "full":
            from ptt_crm.lead_sync import sync_full_backfill

            return jsonify(sync_full_backfill())
        return jsonify(sync_incremental())
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500
