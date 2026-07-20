"""Slack webhook alerts for SEO/AEO Ops (P3e)."""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any

SLACK_ALERT_TYPES = frozenset({
    "critical_issues",
    "report_schedule_failed",
    "sync_failed",
    "freshness_urgent",
    "aeo_coverage_low",
    "content_overdue",
    "crawl_stale",
})

_SLACK_PREFIX: dict[str, str] = {
    "critical_issues": ":rotating_light:",
    "report_schedule_failed": ":warning:",
    "sync_failed": ":warning:",
    "freshness_urgent": ":fire:",
    "aeo_coverage_low": ":chart_with_downwards_trend:",
    "content_overdue": ":hourglass:",
    "crawl_stale": ":spider_web:",
}


def seo_slack_enabled() -> bool:
    return bool((os.getenv("PTT_SEO_SLACK_WEBHOOK") or "").strip())


def seo_slack_webhook_url() -> str:
    return (os.getenv("PTT_SEO_SLACK_WEBHOOK") or os.getenv("SLACK_WEBHOOK_URL") or "").strip()


def post_seo_slack(text: str) -> dict[str, Any]:
    url = seo_slack_webhook_url()
    if not url:
        return {"ok": False, "skipped": True, "error": "webhook_not_configured"}
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


def notify_slack_for_alert(*, alert_type: str, message: str, link: str = "") -> dict[str, Any] | None:
    if not seo_slack_enabled():
        return None
    if alert_type not in SLACK_ALERT_TYPES:
        return None
    prefix = _SLACK_PREFIX.get(alert_type, ":bell:")
    body = f"{prefix} *[SEO/AEO]* {message}"
    if link:
        body += f"\n<{link}|Mở console>"
    return post_seo_slack(body)


def notify_slack_report_failed(
    *,
    schedule_id: int,
    customer_label: str,
    dashboard_type: str,
    error: str,
) -> dict[str, Any] | None:
    if not seo_slack_enabled():
        return None
    msg = (
        f"Báo cáo lịch #{schedule_id} thất bại — {customer_label} ({dashboard_type}). "
        f"Lỗi: {(error or 'unknown')[:200]}"
    )
    return notify_slack_for_alert(
        alert_type="report_schedule_failed",
        message=msg,
        link="/crm/seo/reports",
    )
