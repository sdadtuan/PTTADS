"""Slack/Teams notify for Zalo hub alerts (Z3-5)."""
from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request

logger = logging.getLogger(__name__)

HUB_LINK = "/zalo/zalo-ads"


def _webhook() -> str:
    return (
        os.environ.get("PTT_ZALO_SLACK_WEBHOOK", "").strip()
        or os.environ.get("SLACK_WEBHOOK_URL", "").strip()
        or os.environ.get("PTT_SEO_SLACK_WEBHOOK", "").strip()
    )


def _ops_base() -> str:
    return os.environ.get("OPS_WEB_BASE", os.environ.get("OPS_BASE", "http://127.0.0.1:3200")).rstrip("/")


def notify_zalo_alert(*, alert_type: str, message: str, client_id: str | None = None) -> dict:
    url = _webhook()
    if not url:
        return {"ok": False, "skipped": True, "reason": "webhook_not_configured"}
    link = f"{_ops_base()}{HUB_LINK}"
    if client_id:
        link = f"{link}?client_id={client_id}"
    text = f":warning: *[Zalo Ads]* `{alert_type}` — {message}\n<{link}|Mở Zalo hub →>"
    payload = json.dumps({"text": text}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            ok = 200 <= resp.status < 300
            return {"ok": ok, "status": resp.status}
    except urllib.error.HTTPError as exc:
        logger.warning("zalo slack HTTP %s", exc.code)
        return {"ok": False, "error": f"HTTP {exc.code}"}
    except Exception as exc:
        logger.warning("zalo slack failed: %s", exc)
        return {"ok": False, "error": str(exc)}
