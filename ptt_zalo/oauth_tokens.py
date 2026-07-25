"""Zalo OAuth token exchange helpers (Prod-S3)."""
from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

logger = logging.getLogger(__name__)

_OAUTH_TOKEN_URL = "https://oauth.zaloapp.com/v4/access_token"


def zalo_app_credentials() -> tuple[str, str]:
    app_id = (os.environ.get("PTT_ZALO_APP_ID") or "").strip()
    app_secret = (os.environ.get("PTT_ZALO_APP_SECRET") or "").strip()
    return app_id, app_secret


def exchange_zalo_refresh_token(refresh_token: str) -> dict[str, Any]:
    """Refresh Zalo OA access token using stored refresh_token."""
    app_id, app_secret = zalo_app_credentials()
    if not app_id or not app_secret:
        return {"_zalo_error": "missing_zalo_oauth_env"}

    token = str(refresh_token or "").strip()
    if not token:
        return {"_zalo_error": "missing_refresh_token"}

    body = urllib.parse.urlencode(
        {
            "refresh_token": token,
            "app_id": app_id,
            "grant_type": "refresh_token",
        }
    )
    req = urllib.request.Request(
        _OAUTH_TOKEN_URL,
        data=body.encode("utf-8"),
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "secret_key": app_secret,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            payload = json.loads(resp.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as exc:
        body_text = exc.read().decode("utf-8", errors="replace")[:500]
        logger.warning("zalo refresh HTTP %s: %s", exc.code, body_text)
        return {"_zalo_error": f"zalo_refresh_http_{exc.code}", "detail": body_text}
    except Exception as exc:
        logger.warning("zalo refresh error: %s", exc)
        return {"_zalo_error": str(exc)}

    if payload.get("error") not in (None, 0):
        return {
            "_zalo_error": str(payload.get("message") or payload.get("error") or "zalo_refresh_failed"),
            "detail": payload,
        }

    access = str(payload.get("access_token") or "").strip()
    if not access:
        return {"_zalo_error": "missing_access_token", "detail": payload}

    out: dict[str, Any] = {"access_token": access}
    if payload.get("refresh_token"):
        out["refresh_token"] = str(payload["refresh_token"]).strip()
    if payload.get("expires_in") is not None:
        try:
            out["expires_in"] = int(payload["expires_in"])
        except (TypeError, ValueError):
            pass
    return out
