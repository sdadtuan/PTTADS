"""Meta campaign write API (Phase 4 U-P3-01)."""
from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from ptt_meta.token_vault import normalize_ad_account_id, resolve_meta_access_token

logger = logging.getLogger(__name__)
_GRAPH_VER = "v19.0"


def _truthy(name: str, default: str = "0") -> bool:
    return os.environ.get(name, default).strip().lower() in {"1", "true", "yes", "on"}


def campaign_write_stub_mode() -> bool:
    return _truthy("PTT_META_CAMPAIGN_WRITE_STUB", "0")


def campaign_write_pilot_mode() -> bool:
    """When set, real Meta writes only allowed for pilot client/campaign lists."""
    return _truthy("PTT_META_CAMPAIGN_WRITE_PILOT", "0")


def _pilot_set(name: str) -> set[str]:
    raw = (os.environ.get(name) or "").strip()
    if not raw:
        return set()
    return {part.strip() for part in raw.split(",") if part.strip()}


def campaign_write_allowed(*, client_id: str, external_campaign_id: str) -> tuple[bool, str | None]:
    """Gate real Meta API calls — stub always allowed; pilot lists when enabled."""
    if campaign_write_stub_mode():
        return True, None
    if not campaign_write_pilot_mode():
        return False, "pilot_mode_disabled"
    clients = _pilot_set("PTT_META_CAMPAIGN_WRITE_PILOT_CLIENTS")
    campaigns = _pilot_set("PTT_META_CAMPAIGN_WRITE_PILOT_CAMPAIGNS")
    cid = (client_id or "").strip()
    camp = (external_campaign_id or "").strip()
    if clients and cid not in clients:
        return False, "client_not_in_pilot"
    if campaigns and camp not in campaigns:
        return False, "campaign_not_in_pilot"
    return True, None


def apply_daily_budget(
    *,
    account: dict[str, Any],
    external_campaign_id: str,
    daily_budget_vnd: int,
    client_id: str = "",
) -> dict[str, Any]:
    """Apply daily budget change on Meta campaign (VND → account currency units)."""
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

    token = resolve_meta_access_token(account)
    if not token:
        return {"ok": False, "error": "missing_access_token"}

    ad_account_id = normalize_ad_account_id(str(account.get("external_account_id") or ""))
    if not ad_account_id:
        return {"ok": False, "error": "missing_ad_account_id"}

    # Meta uses minor units (e.g. cents); VND has no subunit — pass as integer string
    budget_str = str(int(daily_budget_vnd))
    params = {
        "daily_budget": budget_str,
        "access_token": token,
    }
    path = f"{external_campaign_id}"
    url = f"https://graph.facebook.com/{_GRAPH_VER}/{path}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
        if isinstance(data, dict) and data.get("success") is True:
            return {"ok": True, "external_campaign_id": external_campaign_id, "response": data}
        if isinstance(data, dict) and data.get("id"):
            return {"ok": True, "external_campaign_id": external_campaign_id, "response": data}
        return {"ok": False, "error": str(data)}
    except urllib.error.HTTPError as exc:
        try:
            body = json.loads(exc.read().decode())
            err = body.get("error", {}) if isinstance(body, dict) else {}
            return {"ok": False, "error": str(err.get("message") or exc.reason)}
        except (json.JSONDecodeError, OSError, AttributeError):
            return {"ok": False, "error": f"Graph HTTP {exc.code}"}
    except (urllib.error.URLError, json.JSONDecodeError, TimeoutError, OSError) as exc:
        return {"ok": False, "error": str(exc) or "network_error"}
