"""Google Ads OAuth helpers (Phase 3 G1)."""
from __future__ import annotations

import json
import os
import secrets
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

_OAUTH_AUTH = "https://accounts.google.com/o/oauth2/v2/auth"
_OAUTH_TOKEN = "https://oauth2.googleapis.com/token"
_SCOPES = "https://www.googleapis.com/auth/adwords"


def _client_config() -> tuple[str, str, str]:
    client_id = (os.environ.get("PTT_GOOGLE_ADS_CLIENT_ID") or "").strip()
    client_secret = (os.environ.get("PTT_GOOGLE_ADS_CLIENT_SECRET") or "").strip()
    redirect_uri = (os.environ.get("PTT_GOOGLE_OAUTH_REDIRECT_URI") or "").strip()
    if not client_id or not client_secret or not redirect_uri:
        raise ValueError("missing_google_oauth_env")
    return client_id, client_secret, redirect_uri


def build_oauth_state(*, client_id: str, account_id: str | None = None) -> str:
    nonce = secrets.token_urlsafe(16)
    payload = {"client_id": client_id, "account_id": account_id or "", "nonce": nonce}
    return urllib.parse.quote(json.dumps(payload, separators=(",", ":")), safe="")


def parse_oauth_state(state: str) -> dict[str, str]:
    raw = urllib.parse.unquote(state or "")
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("invalid_state")
    return {
        "client_id": str(data.get("client_id") or ""),
        "account_id": str(data.get("account_id") or ""),
    }


def authorization_url(*, agency_client_id: str, account_id: str | None = None) -> str:
    cid, _, redirect_uri = _client_config()
    state = build_oauth_state(client_id=agency_client_id, account_id=account_id)
    params = {
        "client_id": cid,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": _SCOPES,
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
    }
    return f"{_OAUTH_AUTH}?{urllib.parse.urlencode(params)}"


def exchange_authorization_code(code: str) -> dict[str, Any]:
    cid, secret, redirect_uri = _client_config()
    body = urllib.parse.urlencode(
        {
            "code": code,
            "client_id": cid,
            "client_secret": secret,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        }
    ).encode()
    req = urllib.request.Request(
        _OAUTH_TOKEN,
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
        if not isinstance(data, dict) or not data.get("refresh_token"):
            raise ValueError("missing_refresh_token")
        return data
    except urllib.error.HTTPError as exc:
        try:
            err = json.loads(exc.read().decode())
            raise ValueError(str(err.get("error_description") or err.get("error") or exc.reason)) from exc
        except (json.JSONDecodeError, OSError, AttributeError) as inner:
            raise ValueError(f"OAuth HTTP {exc.code}") from inner
