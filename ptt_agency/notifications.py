"""Notification inbox + SLA sync hooks."""
from __future__ import annotations

import logging
import os
import smtplib
from email.message import EmailMessage
from typing import Any

from ptt_jobs.db import pg_connection

logger = logging.getLogger(__name__)


def create_notification(
    *,
    recipient_id: str,
    title: str,
    body: str = "",
    category: str = "system",
    link_url: str = "",
    meta: dict[str, Any] | None = None,
) -> str | None:
    import json

    with pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO notification_inbox (
                    recipient_id, category, title, body, link_url, meta
                )
                VALUES (%s, %s, %s, %s, %s, %s::jsonb)
                RETURNING id
                """,
                (
                    recipient_id,
                    category,
                    title,
                    body,
                    link_url or None,
                    json.dumps(meta or {}, ensure_ascii=False),
                ),
            )
            row = cur.fetchone()
            conn.commit()
            return str(row[0]) if row else None


def list_notifications(
    recipient_id: str,
    *,
    unread_only: bool = False,
    category: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    clauses = ["recipient_id = %s"]
    params: list[Any] = [recipient_id]
    if unread_only:
        clauses.append("read_at IS NULL")
    if category:
        clauses.append("category = %s")
        params.append(category)
    params.append(limit)
    with pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT id, category, title, body, link_url, read_at, created_at
                FROM notification_inbox
                WHERE {' AND '.join(clauses)}
                ORDER BY created_at DESC
                LIMIT %s
                """,
                params,
            )
            cols = [d[0] for d in cur.description]
            out = []
            for row in cur.fetchall():
                item = {cols[i]: row[i] for i in range(len(cols))}
                if hasattr(item.get("created_at"), "isoformat"):
                    item["created_at"] = item["created_at"].isoformat()
                if item.get("read_at") and hasattr(item["read_at"], "isoformat"):
                    item["read_at"] = item["read_at"].isoformat()
                item["id"] = str(item["id"])
                out.append(item)
            return out


def mark_notification_read(notification_id: str, recipient_id: str) -> bool:
    with pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE notification_inbox
                SET read_at = NOW()
                WHERE id = %s::uuid AND recipient_id = %s AND read_at IS NULL
                """,
                (notification_id, recipient_id),
            )
            ok = cur.rowcount > 0
            conn.commit()
            return ok


def mark_all_read(recipient_id: str) -> int:
    with pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE notification_inbox SET read_at = NOW()
                WHERE recipient_id = %s AND read_at IS NULL
                """,
                (recipient_id,),
            )
            n = cur.rowcount
            conn.commit()
            return n


def _send_email(to_addr: str, subject: str, body: str) -> None:
    host = os.environ.get("SMTP_HOST", "").strip()
    if not host or not to_addr:
        return
    port = int(os.environ.get("SMTP_PORT", "587"))
    user = os.environ.get("SMTP_USERNAME", "").strip()
    password = os.environ.get("SMTP_PASSWORD", "").strip()
    from_addr = os.environ.get("SMTP_FROM", user).strip()
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = to_addr
    msg.set_content(body)
    with smtplib.SMTP(host, port, timeout=20) as smtp:
        if user:
            smtp.starttls()
            smtp.login(user, password)
        smtp.send_message(msg)


def _send_slack(text: str) -> None:
    import json
    import urllib.request

    url = os.environ.get("SLACK_WEBHOOK_URL", "").strip()
    if not url:
        return
    body = json.dumps({"text": text}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        resp.read()


def notify_agency_ops(
    *,
    recipient_id: str,
    title: str,
    body: str,
    category: str = "system",
    link_url: str = "",
    meta: dict[str, Any] | None = None,
    email_env: str = "PTT_AGENCY_SLA_ALERT_EMAIL",
    email_fallback_env: str = "",
    slack_prefix: str = ":bell: [PTT]",
) -> str | None:
    """PG inbox + optional email/Slack for agency ops alerts."""
    alert_email = os.environ.get(email_env, "").strip()
    if not alert_email and email_fallback_env:
        alert_email = os.environ.get(email_fallback_env, "").strip()

    if alert_email:
        try:
            _send_email(alert_email, f"[PTT] {title}", body)
        except Exception as exc:
            logger.warning("agency alert email failed: %s", exc)

    try:
        _send_slack(f"{slack_prefix} {title} — {body}")
    except Exception as exc:
        logger.warning("agency alert Slack failed: %s", exc)

    try:
        return create_notification(
            recipient_id=recipient_id,
            title=title,
            body=body,
            category=category,
            link_url=link_url,
            meta=meta,
        )
    except Exception as exc:
        logger.debug("PG notification skipped: %s", exc)
        return None


def sync_sla_notifications(*, sqlite_path: str, ts: str, audit_user: str = "sla_cron") -> dict[str, Any]:
    """Sync SLA reminders in SQLite + mirror breaches to PG inbox per owner (P0-07)."""
    import sqlite3

    from crm_lead_sla import sync_lead_sla_reminders

    conn = sqlite3.connect(sqlite_path)
    conn.row_factory = sqlite3.Row
    try:
        overdue = sync_lead_sla_reminders(conn, ts=ts)
        owner_rows = conn.execute(
            """
            SELECT staff_id, COUNT(*) AS cnt
            FROM crm_reminders
            WHERE scope = 'lead' AND reminder_kind = 'sla_overdue'
              AND status = 'pending' AND staff_id IS NOT NULL
            GROUP BY staff_id
            """
        ).fetchall()
        conn.commit()
    finally:
        conn.close()

    created_inbox = 0
    owner_notified: list[dict[str, Any]] = []
    alert_email = os.environ.get("PTT_AGENCY_SLA_ALERT_EMAIL", "").strip()
    zalo_hook = os.environ.get("PTT_SLA_ZALO_WEBHOOK_URL", "").strip()

    for row in owner_rows:
        owner_id = int(row["staff_id"])
        cnt = int(row["cnt"] or 0)
        if cnt <= 0:
            continue
        recipient = f"staff:{owner_id}"
        title = f"SLA — {cnt} lead quá hạn"
        body = f"Bạn có {cnt} lead quá SLA. Xem /crm/leads"
        try:
            create_notification(
                recipient_id=recipient,
                category="sla",
                title=title,
                body=body,
                link_url="/crm/leads",
                meta={"overdue_count": cnt, "owner_id": owner_id},
            )
            created_inbox += 1
            owner_notified.append({"owner_id": owner_id, "count": cnt})
        except Exception as exc:
            logger.debug("PG owner SLA notification skipped owner=%s: %s", owner_id, exc)

        if zalo_hook:
            try:
                import json
                import urllib.request

                payload = json.dumps(
                    {"text": f"[PTT SLA] {title} — {body}"},
                    ensure_ascii=False,
                ).encode("utf-8")
                req = urllib.request.Request(
                    zalo_hook,
                    data=payload,
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=10) as resp:
                    resp.read()
            except Exception as exc:
                logger.warning("SLA Zalo webhook failed owner=%s: %s", owner_id, exc)

    if overdue:
        msg = f"Có {overdue} lead quá hạn SLA. Xem /crm/agency/notifications"
        if alert_email:
            try:
                _send_email(
                    alert_email,
                    f"[PTT] SLA breach — {overdue} lead(s)",
                    msg,
                )
            except Exception as exc:
                logger.warning("SLA email failed: %s", exc)
        try:
            _send_slack(f":warning: [PTT SLA] {overdue} lead quá hạn — {msg}")
        except Exception as exc:
            logger.warning("SLA Slack failed: %s", exc)

    try:
        rid = audit_user or "admin"
        if overdue:
            create_notification(
                recipient_id=rid,
                category="sla",
                title=f"SLA — {overdue} lead quá hạn",
                body="Kiểm tra lead và xử lý ngay.",
                link_url="/crm/leads",
                meta={"overdue_count": overdue, "owners": owner_notified},
            )
            created_inbox += 1
    except Exception as exc:
        logger.debug("PG notification skipped: %s", exc)

    return {
        "overdue_count": overdue,
        "inbox_created": created_inbox,
        "owners_notified": owner_notified,
    }
