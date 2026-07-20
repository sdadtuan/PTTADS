"""Google Search Console OAuth (Phase 4 — PG-only token storage)."""
from __future__ import annotations

import base64
import json
import os
import secrets
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from typing import Any

from ptt_seo.integrations import get_gsc_integration, patch_integrations

_OAUTH_AUTH = "https://accounts.google.com/o/oauth2/v2/auth"
_OAUTH_TOKEN = "https://oauth2.googleapis.com/token"
_GSC_SCOPE = "https://www.googleapis.com/auth/webmasters.readonly"


def _ts() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")


def _client_config() -> tuple[str, str, str]:
    client_id = (
        os.environ.get("PTT_GSC_OAUTH_CLIENT_ID")
        or os.environ.get("PTT_GOOGLE_ADS_CLIENT_ID")
        or ""
    ).strip()
    client_secret = (
        os.environ.get("PTT_GSC_OAUTH_CLIENT_SECRET")
        or os.environ.get("PTT_GOOGLE_ADS_CLIENT_SECRET")
        or ""
    ).strip()
    redirect_uri = (
        os.environ.get("PTT_GSC_OAUTH_REDIRECT_URI")
        or os.environ.get("PTT_GOOGLE_OAUTH_REDIRECT_URI")
        or ""
    ).strip()
    if not client_id or not client_secret or not redirect_uri:
        raise ValueError("missing_gsc_oauth_env")
    return client_id, client_secret, redirect_uri


def build_oauth_state(*, customer_id: int, site_url: str = "") -> str:
    payload = {
        "customer_id": customer_id,
        "site_url": site_url,
        "nonce": secrets.token_urlsafe(12),
    }
    return urllib.parse.quote(json.dumps(payload, separators=(",", ":")), safe="")


def parse_oauth_state(state: str) -> dict[str, Any]:
    raw = urllib.parse.unquote(state or "")
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("invalid_state")
    return {
        "customer_id": int(data.get("customer_id") or 0),
        "site_url": str(data.get("site_url") or ""),
    }


def authorization_url(*, customer_id: int, site_url: str = "") -> str:
    cid, _, redirect_uri = _client_config()
    state = build_oauth_state(customer_id=customer_id, site_url=site_url)
    params = {
        "client_id": cid,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": _GSC_SCOPE,
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


def _encrypt_refresh_token(refresh_token: str) -> str:
    try:
        from ptt_meta.token_crypto import encrypt_token, vault_configured

        if vault_configured():
            return base64.b64encode(encrypt_token(refresh_token)).decode("ascii")
    except Exception:
        pass
    return f"plain:{refresh_token}"


def resolve_gsc_refresh_token(customer_id: int) -> str | None:
    gsc = get_gsc_integration(customer_id)
    enc = gsc.get("refresh_token_encrypted")
    if enc:
        if isinstance(enc, str) and enc.startswith("plain:"):
            return enc[6:]
        try:
            from ptt_meta.token_crypto import decrypt_token

            blob = base64.b64decode(str(enc).encode("ascii"))
            tok = decrypt_token(blob)
            if tok:
                return tok
        except Exception:
            return None
    dev = (os.environ.get("PTT_GSC_REFRESH_TOKEN") or "").strip()
    return dev or None


def save_gsc_oauth_tokens(
    customer_id: int,
    tokens: dict[str, Any],
    *,
    site_url: str = "",
) -> dict[str, Any]:
    refresh = str(tokens.get("refresh_token") or "")
    if not refresh:
        raise ValueError("missing_refresh_token")
    gsc = {
        "status": "connected",
        "site_url": site_url,
        "refresh_token_encrypted": _encrypt_refresh_token(refresh),
        "connected_at": _ts(),
        "token_type": tokens.get("token_type") or "Bearer",
    }
    patch_integrations(customer_id, {"gsc": gsc})
    return get_gsc_integration(customer_id)
