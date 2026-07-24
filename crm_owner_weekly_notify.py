"""Gửi digest dashboard tuần — Slack + email (cron thứ 2)."""
from __future__ import annotations

import os
import sqlite3
from typing import Any

from crm_owner_weekly_dashboard import get_owner_weekly_dashboard, resolve_week_bounds
from crm_owner_weekly_inbox import sync_owner_weekly_inbox
from crm_svc_finance_kpi_notify import post_slack_webhook, send_alert_email

ENV_SLACK_WEBHOOK = "PTT_OWNER_WEEKLY_SLACK_WEBHOOK"
ENV_ALERT_EMAIL = "PTT_OWNER_WEEKLY_ALERT_EMAIL"
ENV_ALERT_ONLY_RED = "PTT_OWNER_WEEKLY_ALERT_ONLY_RED"
ENV_FINANCE_SLACK = "PTT_FINANCE_KPI_SLACK_WEBHOOK"
ENV_FINANCE_EMAIL = "PTT_FINANCE_KPI_ALERT_EMAIL"


def _env_bool(name: str, default: bool = True) -> bool:
    raw = (os.getenv(name) or "").strip().lower()
    if not raw:
        return default
    return raw not in ("0", "false", "no", "off")


def _slack_webhook_url() -> str:
    return (os.getenv(ENV_SLACK_WEBHOOK) or os.getenv(ENV_FINANCE_SLACK) or "").strip()


def _alert_email_to() -> str:
    return (os.getenv(ENV_ALERT_EMAIL) or os.getenv(ENV_FINANCE_EMAIL) or "").strip()


def build_weekly_digest(
    dashboard: dict[str, Any],
    *,
    dashboard_url: str = "",
) -> tuple[str, str]:
    """Trả (subject, body plain text)."""
    week = dashboard.get("week") or {}
    brief = dashboard.get("pre_execution") or {}
    rag = dashboard.get("rag_counts") or {}
    iso_year = week.get("iso_year")
    iso_week = week.get("iso_week")
    subject = (
        f"[PTT Tuần] {brief.get('red_count', 0)} đỏ · "
        f"{brief.get('yellow_count', 0)} vàng — W{iso_week}/{iso_year}"
    )
    lines = [
        str(week.get("label") or f"Tuần {iso_week}/{iso_year}"),
        f"Xanh: {rag.get('green', 0)} · Vàng: {rag.get('yellow', 0)} · Đỏ: {rag.get('red', 0)}",
        f"Hành động cần xử lý: {brief.get('action_count', 0)}",
        "",
        str(brief.get("subtitle") or ""),
        "",
    ]
    for action in (brief.get("actions") or [])[:12]:
        tag = "DO" if action.get("status") == "red" else "THEO DOI"
        lines.append(f"[{tag}] {action.get('block_label')} — {action.get('metric_label')}")
        if action.get("hint"):
            lines.append(f"  {action.get('hint')}")
        for step in (action.get("steps") or [])[:3]:
            lines.append(f"  - {step}")
        lines.append("")
    try:
        from ptt_meta.intelligence_snapshot import fetch_latest_snapshot_digest

        snap = fetch_latest_snapshot_digest()
        if snap:
            lines.extend(
                [
                    "Meta Intelligence snapshot:",
                    f"  Kỳ {snap.get('period_start')} → {snap.get('period_end')}",
                    f"  Artifact {snap.get('byte_size', 0)} bytes (gzip)",
                    "",
                ]
            )
    except Exception:
        pass
    if dashboard_url:
        lines.append(f"Dashboard: {dashboard_url}")
    lines.append("Export: /api/crm/owner-weekly/export")
    return subject, "\n".join(lines).strip()


def dispatch_owner_weekly_alerts(
    conn: sqlite3.Connection,
    *,
    iso_year: int | None = None,
    iso_week: int | None = None,
    only_red: bool | None = None,
    dashboard_url: str = "",
) -> dict[str, Any]:
    """
    Cron tuần — sync Hub + gửi Slack/email nếu có chỉ số đỏ/vàng.

    Mặc đnh tuần trước (ISO). only_red=True → chỉ gửi khi có đỏ.
    """
    if only_red is None:
        only_red = _env_bool(ENV_ALERT_ONLY_RED, False)

    if iso_year is not None and iso_week is not None:
        dashboard = get_owner_weekly_dashboard(conn, year=int(iso_year), iso_week=int(iso_week))
        y, w = int(iso_year), int(iso_week)
    else:
        _start, _end, y, w = resolve_week_bounds()
        dashboard = get_owner_weekly_dashboard(conn, year=y, iso_week=w)

    week = dashboard.get("week") or {}
    y = int(week.get("iso_year") or y)
    w = int(week.get("iso_week") or w)
    dash_url = dashboard_url or f"/crm/owner-weekly?year={y}&week={w}"

    inbox_result = sync_owner_weekly_inbox(
        conn,
        iso_year=y,
        iso_week=w,
        dashboard=dashboard,
        dashboard_url=dash_url,
    )
    brief = dashboard.get("pre_execution") or {}
    action_count = int(brief.get("action_count") or 0)
    red_count = int(brief.get("red_count") or 0)

    base_out = {
        "inbox": inbox_result,
        "dashboard": {
            "iso_year": y,
            "iso_week": w,
            "week_label": week.get("label"),
            "rag_counts": dashboard.get("rag_counts"),
            "pre_execution": {
                "red_count": red_count,
                "yellow_count": brief.get("yellow_count"),
                "action_count": action_count,
            },
        },
    }

    if action_count == 0:
        return {"ok": True, "sent": False, "reason": "no_actions", **base_out}
    if only_red and red_count == 0:
        return {"ok": True, "sent": False, "reason": "no_red", **base_out}

    subject, body = build_weekly_digest(dashboard, dashboard_url=dash_url)
    channels: dict[str, Any] = {}

    slack_url = _slack_webhook_url()
    if slack_url:
        ok, detail = post_slack_webhook(slack_url, body)
        channels["slack"] = {"ok": ok, "detail": detail}

    email_to = _alert_email_to()
    if email_to:
        ok, detail = send_alert_email(email_to, subject, body)
        channels["email"] = {"ok": ok, "detail": detail}

    if not channels:
        return {
            "ok": True,
            "sent": False,
            "reason": "inbox_only",
            **base_out,
        }

    sent = any(ch.get("ok") for ch in channels.values())
    return {
        "ok": sent or inbox_result.get("synced", 0) > 0,
        "sent": sent,
        "reason": "dispatched" if sent else "dispatch_failed",
        "channels": channels,
        **base_out,
    }
