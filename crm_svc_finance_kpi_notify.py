"""Gửi cảnh báo KPI finance — Slack webhook + email (cron)."""
from __future__ import annotations

import json
import os
import smtplib
import sqlite3
import urllib.error
import urllib.request
from email.message import EmailMessage
from typing import Any

from crm_svc_finance_kpi import collect_finance_kpi_alerts
from crm_svc_finance_kpi_inbox import sync_finance_kpi_inbox

ENV_SLACK_WEBHOOK = "PTT_FINANCE_KPI_SLACK_WEBHOOK"
ENV_ALERT_EMAIL = "PTT_FINANCE_KPI_ALERT_EMAIL"
ENV_ALERT_ONLY_CRITICAL = "PTT_FINANCE_KPI_ALERT_ONLY_CRITICAL"


def _env_bool(name: str, default: bool = True) -> bool:
    raw = (os.getenv(name) or "").strip().lower()
    if not raw:
        return default
    return raw not in ("0", "false", "no", "off")


def build_alert_digest(
    alerts_result: dict[str, Any],
    *,
    dashboard_url: str = "",
) -> tuple[str, str]:
    """Trả (subject, body plain text)."""
    year = alerts_result.get("year")
    month = alerts_result.get("month")
    subject = f"[PTT KPI] {alerts_result.get('critical_count', 0)} nghiêm trọng · {alerts_result.get('alert_count', 0)} cảnh báo — {month:02d}/{year}"
    lines = [
        f"KPI Finance — {month:02d}/{year}",
        f"Tổng cảnh báo: {alerts_result.get('alert_count', 0)} "
        f"(nghiêm trọng: {alerts_result.get('critical_count', 0)})",
        "",
    ]
    for alert in alerts_result.get("alerts") or []:
        level = "NGHIEM TRONG" if alert.get("level") == "critical" else "CANH BAO"
        lines.append(f"[{level}] {alert.get('title')}")
        lines.append(f"  {alert.get('message')}")
        lines.append("")
    if dashboard_url:
        lines.append(f"Xem dashboard: {dashboard_url}")
    lines.append("Chi tiết: /crm/financials")
    return subject, "\n".join(lines).strip()


def post_slack_webhook(webhook_url: str, text: str) -> tuple[bool, str]:
    url = str(webhook_url or "").strip()
    if not url:
        return False, "missing webhook"
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
                return True, "ok"
            return False, f"HTTP {resp.status}"
    except urllib.error.HTTPError as exc:
        return False, f"HTTP {exc.code}"
    except urllib.error.URLError as exc:
        return False, str(exc.reason or exc)


def send_alert_email(to_addrs: str, subject: str, body: str) -> tuple[bool, str]:
    recipients = [a.strip() for a in str(to_addrs or "").split(",") if a.strip()]
    if not recipients:
        return False, "missing recipients"

    smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_username = (os.getenv("SMTP_USERNAME") or "").strip()
    smtp_password = (os.getenv("SMTP_PASSWORD") or "").strip()
    sender_email = (os.getenv("SMTP_FROM") or smtp_username).strip()
    if not smtp_username or not smtp_password or not sender_email:
        return False, "SMTP not configured"

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = sender_email
    message["To"] = ", ".join(recipients)
    message.set_content(body)

    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=20) as server:
            server.starttls()
            server.login(smtp_username, smtp_password)
            server.send_message(message)
    except OSError as exc:
        return False, str(exc)
    return True, "ok"


def dispatch_finance_kpi_alerts(
    conn: sqlite3.Connection,
    *,
    year: int,
    month: int,
    only_critical: bool | None = None,
    dashboard_url: str = "",
) -> dict[str, Any]:
    """
    Gửi digest cảnh báo qua Slack/email nếu có alert phù hợp ngưỡng.

    only_critical: mặc định đọc env PTT_FINANCE_KPI_ALERT_ONLY_CRITICAL (true).
    """
    if only_critical is None:
        only_critical = _env_bool(ENV_ALERT_ONLY_CRITICAL, True)

    alerts_result = collect_finance_kpi_alerts(conn, year=year, month=month)
    inbox_result = sync_finance_kpi_inbox(
        conn,
        year=year,
        month=month,
        alerts_result=alerts_result,
        dashboard_url=dashboard_url,
    )
    alert_count = int(alerts_result.get("alert_count") or 0)
    has_critical = bool(alerts_result.get("has_critical"))

    base_out = {
        "inbox": inbox_result,
        "alerts": alerts_result,
    }

    if alert_count == 0:
        return {
            "ok": True,
            "sent": False,
            "reason": "no_alerts",
            **base_out,
        }
    if only_critical and not has_critical:
        return {
            "ok": True,
            "sent": False,
            "reason": "no_critical",
            **base_out,
        }

    subject, body = build_alert_digest(alerts_result, dashboard_url=dashboard_url)
    channels: dict[str, Any] = {}

    slack_url = (os.getenv(ENV_SLACK_WEBHOOK) or "").strip()
    if slack_url:
        ok, detail = post_slack_webhook(slack_url, body)
        channels["slack"] = {"ok": ok, "detail": detail}

    email_to = (os.getenv(ENV_ALERT_EMAIL) or "").strip()
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
