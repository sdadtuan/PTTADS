"""Unified SEO alert channels — Slack + Teams (Gate D)."""
from __future__ import annotations

from typing import Any


def notify_seo_alert(*, alert_type: str, message: str, link: str = "") -> dict[str, Any]:
    results: dict[str, Any] = {}
    try:
        from ptt_seo.slack_notify import notify_slack_for_alert

        results["slack"] = notify_slack_for_alert(alert_type=alert_type, message=message, link=link)
    except Exception as exc:
        results["slack"] = {"ok": False, "error": str(exc)}
    try:
        from ptt_seo.teams_notify import notify_teams_for_alert

        results["teams"] = notify_teams_for_alert(alert_type=alert_type, message=message, link=link)
    except Exception as exc:
        results["teams"] = {"ok": False, "error": str(exc)}
    return results
