"""SEO/AEO dashboard PDF export (Phase 2 UI parity + P3 white-label)."""
from __future__ import annotations

from datetime import datetime
from io import BytesIO
from typing import Any


def build_dashboard_pdf(
    data: dict[str, Any],
    *,
    customer_label: str = "",
    brand: dict[str, Any] | None = None,
) -> tuple[BytesIO, str]:
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    except ImportError as exc:
        raise RuntimeError("Cần cài reportlab: pip install reportlab") from exc

    brand = brand or {}
    primary_hex = str(brand.get("primary_color") or "#2563eb")
    primary = colors.HexColor(primary_hex)
    title_prefix = str(brand.get("report_title_prefix") or "SEO/AEO Report")
    footer_text = str(brand.get("footer_text") or "Báo cáo SEO/AEO — confidential")
    hide_agency = bool(brand.get("hide_agency_branding"))
    company = str(brand.get("company_name") or customer_label or "").strip()

    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=16 * mm, rightMargin=16 * mm)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "BrandTitle",
        parent=styles["Title"],
        textColor=primary,
    )
    story: list[Any] = []

    dtype = str(data.get("type") or "executive")
    title = f"{title_prefix} — {dtype.title()}"
    if company:
        title += f" ({company})"
    story.append(Paragraph(title, title_style))
    story.append(Paragraph(f"Xuất lúc: {datetime.now().strftime('%Y-%m-%d %H:%M')}", styles["Normal"]))
    if not hide_agency:
        story.append(Paragraph("Powered by PTT Agency Ops", styles["Normal"]))
    story.append(Spacer(1, 10))

    metrics: list[list[str]] = [["Chỉ số", "Giá trị"]]
    gsc = data.get("gsc") or {}
    if gsc:
        metrics.append(["GSC Clicks", str(gsc.get("clicks", "—"))])
        metrics.append(["GSC Impressions", str(gsc.get("impressions", "—"))])
        ctr = gsc.get("avg_ctr")
        metrics.append(["Avg CTR", f"{float(ctr) * 100:.2f}%" if ctr is not None else "—"])
    if data.get("critical_issues") is not None:
        metrics.append(["Critical issues", str(data["critical_issues"])])
    aeo = data.get("aeo") or {}
    if aeo.get("coverage_pct") is not None:
        metrics.append(["AEO coverage", f"{aeo['coverage_pct']}%"])
    if data.get("open_alerts") is not None:
        metrics.append(["Open alerts", str(data["open_alerts"])])

    if len(metrics) > 1:
        tbl = Table(metrics, colWidths=[80 * mm, 80 * mm])
        tbl.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), primary),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                ]
            )
        )
        story.append(tbl)
        story.append(Spacer(1, 12))

    story.append(Spacer(1, 8))
    story.append(Paragraph(footer_text, styles["Normal"]))

    content_by_status = data.get("content_by_status") or {}
    if content_by_status:
        story.append(Paragraph("Content by status", styles["Heading2"]))
        rows = [["Status", "Count"]] + [[k, str(v)] for k, v in content_by_status.items()]
        ct = Table(rows, colWidths=[80 * mm, 40 * mm])
        ct.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.25, colors.grey), ("FONTSIZE", (0, 0), (-1, -1), 8)]))
        story.append(ct)
        story.append(Spacer(1, 12))

    severity = data.get("severity") or {}
    if severity:
        story.append(Paragraph("Technical severity", styles["Heading2"]))
        rows = [["Severity", "Count"]] + [[k, str(v)] for k, v in severity.items()]
        st = Table(rows, colWidths=[80 * mm, 40 * mm])
        st.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.25, colors.grey), ("FONTSIZE", (0, 0), (-1, -1), 8)]))
        story.append(st)

    doc.build(story)
    buf.seek(0)
    stamp = datetime.now().strftime("%Y-%m-%d")
    slug = dtype.replace(" ", "-")
    return buf, f"seo-aeo-{slug}-{stamp}.pdf"
