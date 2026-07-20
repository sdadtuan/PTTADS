"""Build PDF reports for scheduled email client delivery (Wave 2)."""
from __future__ import annotations

import io
from typing import Any


def build_email_report_pdf(
    summary: dict[str, Any],
    *,
    client_label: str,
    report_type: str = "executive",
) -> tuple[io.BytesIO, str]:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    width, height = A4
    y = height - 50
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, y, f"Email Marketing Report — {client_label}")
    y -= 24
    c.setFont("Helvetica", 11)
    c.drawString(50, y, f"Type: {report_type}")
    y -= 18
    rows = [
        ("Sent", summary.get("sent", 0)),
        ("Opens", summary.get("opens", 0)),
        ("Clicks", summary.get("clicks", 0)),
        ("Open rate %", summary.get("open_rate_pct", 0)),
        ("Click rate %", summary.get("click_rate_pct", 0)),
        ("Revenue attributed", summary.get("revenue_attrib", 0)),
        ("Bounce rate %", summary.get("bounce_rate_pct", 0)),
        ("Complaint rate %", summary.get("complaint_rate_pct", 0)),
    ]
    for label, val in rows:
        y -= 16
        c.drawString(50, y, f"{label}: {val}")
    c.showPage()
    c.save()
    buf.seek(0)
    safe_label = client_label.replace(" ", "-")[:40]
    return buf, f"email-report-{safe_label}.pdf"
