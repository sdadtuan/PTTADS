"""Lightweight SMTP helpers for SEO/AEO scheduled reports."""
from __future__ import annotations

import os
import smtplib
from email.message import EmailMessage
from typing import Any, BinaryIO


def smtp_configured() -> bool:
    return bool(os.environ.get("SMTP_HOST", "").strip())


def send_email_with_attachment(
    to_addrs: list[str],
    subject: str,
    body: str,
    *,
    cc_addrs: list[str] | None = None,
    bcc_addrs: list[str] | None = None,
    html_body: str | None = None,
    attachment: BinaryIO | None = None,
    attachment_name: str = "report.pdf",
    mime_type: str = "application/pdf",
) -> dict[str, Any]:
    recipients = [a.strip() for a in to_addrs if a and a.strip()]
    cc = [a.strip() for a in (cc_addrs or []) if a and a.strip()]
    bcc = [a.strip() for a in (bcc_addrs or []) if a and a.strip()]
    all_rcpt = recipients + cc + bcc
    if not recipients:
        return {"ok": False, "error": "no_recipients"}
    host = os.environ.get("SMTP_HOST", "").strip()
    if not host:
        return {"ok": False, "error": "smtp_not_configured", "skipped": True}

    port = int(os.environ.get("SMTP_PORT", "587"))
    user = os.environ.get("SMTP_USERNAME", "").strip()
    password = os.environ.get("SMTP_PASSWORD", "").strip()
    from_addr = os.environ.get("SMTP_FROM", user).strip() or user

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = ", ".join(recipients)
    if cc:
        msg["Cc"] = ", ".join(cc)
    msg.set_content(body)
    if html_body:
        msg.add_alternative(html_body, subtype="html")
    if attachment is not None:
        data = attachment.read()
        msg.add_attachment(data, maintype="application", subtype="pdf", filename=attachment_name)

    with smtplib.SMTP(host, port, timeout=20) as smtp:
        if user:
            smtp.starttls()
            smtp.login(user, password)
        smtp.send_message(msg, to_addrs=all_rcpt)

    return {"ok": True, "sent_to": recipients, "cc": cc, "bcc": bcc}
