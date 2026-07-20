"""Microsoft Teams webhook alerts for SEO/AEO Ops (Gate D)."""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any

from ptt_seo.slack_notify import SLACK_ALERT_TYPES, _SLACK_PREFIX


def seo_teams_enabled() -> bool:
    return bool((os.getenv("PTT_SEO_TEAMS_WEBHOOK") or "").strip())


def seo_teams_webhook_url() -> str:
    return (os.getenv("PTT_SEO_TEAMS_WEBHOOK") or os.getenv("TEAMS_WEBHOOK_URL") or "").strip()


def post_seo_teams(text: str) -> dict[str, Any]:
    url = seo_teams_webhook_url()
    if not url:
        return {"ok": False, "skipped": True, "error": "teams_webhook_not_configured"}
    payload = json.dumps({"text": text}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            if 200 <= resp.status < 300:
                return {"ok": True}
            return {"ok": False, "error": f"HTTP {resp.status}"}
    except urllib.error.HTTPError as exc:
        return {"ok": False, "error": f"HTTP {exc.code}"}
    except urllib.error.URLError as exc:
        return {"ok": False, "error": str(exc.reason or exc)}


def notify_teams_for_alert(*, alert_type: str, message: str, link: str = "") -> dict[str, Any] | None:
    if not seo_teams_enabled():
        return None
    if alert_type not in SLACK_ALERT_TYPES and alert_type not in ("aeo_coverage_low", "content_overdue", "crawl_stale"):
        return None
    prefix = _SLACK_PREFIX.get(alert_type, ":bell:")
    body = f"{prefix} **[SEO/AEO]** {message}"
    if link:
        body += f"\n{link}"
    return post_seo_teams(body)
