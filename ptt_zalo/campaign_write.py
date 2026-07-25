"""Zalo Ads campaign write API (Prod-Z4 / GAP-Z4-01)."""
from __future__ import annotations

import json
import logging
import os
import secrets
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from ptt_zalo.token_vault import normalize_account_id, resolve_zalo_access_token

logger = logging.getLogger(__name__)

_ADS_CAMPAIGNS_URL = "https://business.openapi.zalo.me/ads/campaigns"


def _truthy(name: str, default: str = "0") -> bool:
    return os.environ.get(name, default).strip().lower() in {"1", "true", "yes", "on"}


def campaign_write_stub_mode() -> bool:
    return _truthy("PTT_ZALO_CAMPAIGN_WRITE_STUB", "0")


def campaign_write_pilot_mode() -> bool:
    return _truthy("PTT_ZALO_CAMPAIGN_WRITE_PILOT", "0")


def _pilot_set(name: str) -> set[str]:
    raw = (os.environ.get(name) or "").strip()
    if not raw:
        return set()
    return {part.strip() for part in raw.split(",") if part.strip()}


def campaign_write_allowed(*, client_id: str, external_campaign_id: str) -> tuple[bool, str | None]:
    if campaign_write_stub_mode():
        return True, None
    if not campaign_write_pilot_mode():
        return False, "pilot_mode_disabled"
    clients = _pilot_set("PTT_ZALO_CAMPAIGN_WRITE_PILOT_CLIENTS")
    campaigns = _pilot_set("PTT_ZALO_CAMPAIGN_WRITE_PILOT_CAMPAIGNS")
    cid = (client_id or "").strip()
    camp = (external_campaign_id or "").strip()
    if clients and cid not in clients:
        return False, "client_not_in_pilot"
    if campaigns and camp and camp not in campaigns and not camp.startswith("pending:"):
        return False, "campaign_not_in_pilot"
    return True, None


def _zalo_request(
    *,
    method: str,
    path: str,
    access_token: str,
    body: dict[str, Any] | None = None,
) -> tuple[dict[str, Any] | None, str | None]:
    url = path if path.startswith("http") else f"{_ADS_CAMPAIGNS_URL}{path}"
    data = None
    headers = {"access_token": access_token, "Accept": "application/json"}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method.upper())
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            payload = json.loads(resp.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")[:500]
        logger.warning("zalo campaign write HTTP %s: %s", exc.code, raw)
        return None, f"zalo_ads_http_{exc.code}"
    except Exception as exc:
        logger.warning("zalo campaign write error: %s", exc)
        return None, str(exc)

    if isinstance(payload, dict) and payload.get("error") not in (None, 0):
        return payload, str(payload.get("message") or payload.get("error") or "zalo_api_error")
    return payload if isinstance(payload, dict) else {"data": payload}, None


def create_campaign(
    *,
    account: dict[str, Any],
    new_value: dict[str, Any],
    client_id: str = "",
) -> dict[str, Any]:
    account_id = normalize_account_id(
        str(new_value.get("external_account_id") or account.get("external_account_id") or "")
    )
    campaign_name = str(new_value.get("campaign_name") or "PTT Zalo Campaign").strip()
    daily_budget = int(new_value.get("daily_budget_vnd") or 0)
    pending_ref = str(new_value.get("pending_ref") or campaign_name)

    if campaign_write_stub_mode():
        ext_id = f"stub_zalo_{secrets.token_hex(6)}"
        return {
            "ok": True,
            "stub": True,
            "external_campaign_id": ext_id,
            "external_campaign_name": campaign_name,
            "external_account_id": account_id or "stub_zalo_account",
            "daily_budget_vnd": daily_budget,
            "pending_ref": pending_ref,
        }

    allowed, reason = campaign_write_allowed(
        client_id=client_id or str(account.get("client_id") or ""),
        external_campaign_id=pending_ref,
    )
    if not allowed:
        return {"ok": False, "error": reason or "not_allowed"}

    token = resolve_zalo_access_token(account)
    if not token:
        return {"ok": False, "error": "missing_access_token"}
    if not account_id:
        return {"ok": False, "error": "missing_account_id"}

    body = {
        "account_id": account_id,
        "name": campaign_name,
        "daily_budget": daily_budget,
        "objective": str(new_value.get("objective") or "LEAD_GENERATION"),
        "status": "ACTIVE",
    }
    payload, err = _zalo_request(method="POST", path="", access_token=token, body=body)
    if err:
        return {"ok": False, "error": err}

    data = payload.get("data") if isinstance(payload, dict) else {}
    if isinstance(data, dict):
        ext_id = str(data.get("campaign_id") or data.get("id") or "")
    else:
        ext_id = str(payload.get("campaign_id") or payload.get("id") or "") if isinstance(payload, dict) else ""

    if not ext_id:
        return {"ok": False, "error": "missing_campaign_id_in_response", "response": payload}

    return {
        "ok": True,
        "external_campaign_id": ext_id,
        "external_campaign_name": campaign_name,
        "external_account_id": account_id,
        "response": payload,
    }


def apply_campaign_status(
    *,
    account: dict[str, Any],
    external_campaign_id: str,
    status: str,
    client_id: str = "",
) -> dict[str, Any]:
    normalized = (status or "").strip().upper()
    if normalized not in {"ACTIVE", "PAUSED", "STOPPED", "ARCHIVED"}:
        return {"ok": False, "error": "invalid_status"}

    if campaign_write_stub_mode():
        return {
            "ok": True,
            "stub": True,
            "external_campaign_id": external_campaign_id,
            "status": normalized,
        }

    allowed, reason = campaign_write_allowed(
        client_id=client_id or str(account.get("client_id") or ""),
        external_campaign_id=external_campaign_id,
    )
    if not allowed:
        return {"ok": False, "error": reason or "not_allowed"}

    token = resolve_zalo_access_token(account)
    if not token:
        return {"ok": False, "error": "missing_access_token"}

    path = f"/{urllib.parse.quote(external_campaign_id)}"
    payload, err = _zalo_request(
        method="PATCH",
        path=path,
        access_token=token,
        body={"status": normalized},
    )
    if err:
        return {"ok": False, "error": err}
    return {
        "ok": True,
        "external_campaign_id": external_campaign_id,
        "status": normalized,
        "response": payload,
    }


def apply_daily_budget(
    *,
    account: dict[str, Any],
    external_campaign_id: str,
    daily_budget_vnd: int,
    client_id: str = "",
) -> dict[str, Any]:
    if daily_budget_vnd < 0:
        return {"ok": False, "error": "invalid_budget"}

    if campaign_write_stub_mode():
        return {
            "ok": True,
            "stub": True,
            "external_campaign_id": external_campaign_id,
            "daily_budget_vnd": daily_budget_vnd,
        }

    allowed, reason = campaign_write_allowed(
        client_id=client_id or str(account.get("client_id") or ""),
        external_campaign_id=external_campaign_id,
    )
    if not allowed:
        return {"ok": False, "error": reason or "not_allowed"}

    token = resolve_zalo_access_token(account)
    if not token:
        return {"ok": False, "error": "missing_access_token"}

    path = f"/{urllib.parse.quote(external_campaign_id)}"
    payload, err = _zalo_request(
        method="PATCH",
        path=path,
        access_token=token,
        body={"daily_budget": int(daily_budget_vnd)},
    )
    if err:
        return {"ok": False, "error": err}
    return {
        "ok": True,
        "external_campaign_id": external_campaign_id,
        "daily_budget_vnd": daily_budget_vnd,
        "response": payload,
    }
