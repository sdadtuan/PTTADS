"""Meta Graph OAuth — long-lived token exchange (Phase 2 M1-03)."""
from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from ptt_meta.graph_insights import _GRAPH_VER, graph_error

logger = logging.getLogger(__name__)


def meta_app_credentials() -> tuple[str, str]:
    app_id = (
        os.environ.get("META_APP_ID")
        or os.environ.get("CRM_FACEBOOK_APP_ID")
        or os.environ.get("FACEBOOK_APP_ID")
        or ""
    ).strip()
    app_secret = (
        os.environ.get("META_APP_SECRET")
        or os.environ.get("CRM_FACEBOOK_APP_SECRET")
        or os.environ.get("FACEBOOK_APP_SECRET")
        or ""
    ).strip()
    return app_id, app_secret


def exchange_long_lived_token(current_token: str) -> dict[str, Any]:
    """
    Exchange a long-lived user access token for a new long-lived token (~60 days).

    Returns dict with keys: access_token, expires_in (seconds), or _graph_error.
    """
    app_id, app_secret = meta_app_credentials()
    if not app_id or not app_secret:
        return {"_graph_error": "META_APP_ID / META_APP_SECRET not configured"}

    token = str(current_token or "").strip()
    if not token:
        return {"_graph_error": "empty access token"}

    q = urllib.parse.urlencode(
        {
            "grant_type": "fb_exchange_token",
            "client_id": app_id,
            "client_secret": app_secret,
            "fb_exchange_token": token,
        }
    )
    url = f"https://graph.facebook.com/{_GRAPH_VER}/oauth/access_token?{q}"
    try:
        with urllib.request.urlopen(url, timeout=30) as resp:
            data = json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        try:
            body = json.loads(exc.read().decode())
            err = body.get("error") if isinstance(body, dict) else {}
            return {
                "_graph_error": str(err.get("message") or exc.reason or "OAuth HTTP error"),
                "_graph_error_code": err.get("code"),
            }
        except (json.JSONDecodeError, OSError, AttributeError):
            return {"_graph_error": f"OAuth HTTP {exc.code}: {exc.reason}"}
    except (urllib.error.URLError, json.JSONDecodeError, TimeoutError, OSError) as exc:
        return {"_graph_error": str(exc) or "OAuth network error"}

    if not isinstance(data, dict):
        return {"_graph_error": "invalid OAuth response"}

    err = graph_error(data)
    if err:
        return {"_graph_error": err, "_graph_error_code": data.get("_graph_error_code")}

    access_token = str(data.get("access_token") or "").strip()
    if not access_token:
        return {"_graph_error": "OAuth response missing access_token"}

    expires_in = data.get("expires_in")
    try:
        expires_in = int(expires_in) if expires_in is not None else None
    except (TypeError, ValueError):
        expires_in = None

    return {"access_token": access_token, "expires_in": expires_in, "token_type": data.get("token_type")}
