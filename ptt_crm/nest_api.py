"""Nest CRM API client helpers (Phase 3)."""
from __future__ import annotations

import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from ptt_crm.config import nest_internal_key, nest_leads_base_url

logger = logging.getLogger(__name__)


def nest_request(
    method: str,
    path: str,
    *,
    body: dict[str, Any] | None = None,
    timeout: float = 10.0,
) -> tuple[int, dict[str, Any]]:
    url = f"{nest_leads_base_url()}{path}"
    data = None
    headers = {"Accept": "application/json"}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    key = nest_internal_key()
    if key:
        headers["X-PTT-Internal-Key"] = key
    req = urllib.request.Request(url, data=data, headers=headers, method=method.upper())
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8") or "{}"
            return resp.status, json.loads(raw)
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8") or "{}"
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            payload = {"error": raw or exc.reason}
        return exc.code, payload
    except Exception as exc:
        logger.warning("nest_request failed %s %s: %s", method, path, exc)
        return 0, {"error": str(exc)}


def submit_creative(body: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    return nest_request("POST", "/api/v1/creatives", body=body)


def start_onboarding_workflow(client_id: str, started_by: str = "") -> tuple[int, dict[str, Any]]:
    return nest_request(
        "POST",
        "/api/v1/workflows/onboarding/start",
        body={"client_id": client_id, "started_by": started_by},
    )


def nudge_onboarding_workflow(client_id: str) -> tuple[int, dict[str, Any]]:
    return nest_request("POST", f"/api/v1/workflows/onboarding/{client_id}/nudge", body={})


def start_launch_qa_workflow(body: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    return nest_request("POST", "/api/v1/workflows/launch-qa/start", body=body)


def nudge_launch_qa_workflow(run_id: str) -> tuple[int, dict[str, Any]]:
    return nest_request("POST", f"/api/v1/workflows/launch-qa/{run_id}/nudge", body={})


def submit_campaign_write(body: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    return nest_request("POST", "/api/v1/campaign-writes", body=body)


def list_pending_campaign_writes(client_id: str | None = None) -> tuple[int, dict[str, Any]]:
    qs = f"?client_id={urllib.parse.quote(client_id)}" if client_id else ""
    return nest_request("GET", f"/api/v1/campaign-writes/pending{qs}")


def approve_campaign_write(request_id: str, body: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    return nest_request("POST", f"/api/v1/campaign-writes/{request_id}/approve", body=body)


def reject_campaign_write(request_id: str, body: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    return nest_request("POST", f"/api/v1/campaign-writes/{request_id}/reject", body=body)


def sync_launch_qa_budget_confirmed(body: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    return nest_request("POST", "/api/internal/launch-qa/sync-budget-confirmed", body=body)
