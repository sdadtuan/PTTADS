"""CMS webhook pilot — defaults, seed helpers."""
from __future__ import annotations

import os


def pilot_webhook_secret() -> str:
    return (os.environ.get("PTT_SEO_CMS_WEBHOOK_SECRET") or "pilot-dev-secret").strip()


def default_pilot_webhook_url() -> str:
    explicit = (os.environ.get("PTT_SEO_CMS_PILOT_WEBHOOK_URL") or "").strip()
    if explicit:
        return explicit.rstrip("/")
    base = (os.environ.get("PTT_NEST_API_URL") or os.environ.get("PTT_FLASK_MONOLITH_URL") or "http://127.0.0.1:3000").strip().rstrip("/")
    return f"{base}/api/v1/seo/internal/cms-webhook/receive"


def pilot_target_payload(*, base_url: str | None = None, bearer_token: str | None = None) -> dict:
    return {
        "cms_type": "webhook",
        "base_url": (base_url or default_pilot_webhook_url()).rstrip("/"),
        "active": True,
        "auth": {
            "bearer_token": bearer_token if bearer_token is not None else pilot_webhook_secret(),
        },
    }
