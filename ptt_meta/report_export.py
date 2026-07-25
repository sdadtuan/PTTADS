"""Meta hub client report PDF export (Prod-S2)."""
from __future__ import annotations

from datetime import datetime
from io import BytesIO
from typing import Any


def build_meta_hub_pdf(
    hub: dict[str, Any],
    *,
    customer_label: str = "",
) -> tuple[BytesIO, str]:
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    except ImportError as exc:
        raise RuntimeError("Cần cài reportlab: pip install reportlab") from exc

    summary = hub.get("summary") or {}
    date_from = hub.get("date_from") or "—"
    date_to = hub.get("date_to") or "—"
    company = customer_label.strip() or "Meta Ads Hub"
    primary = colors.HexColor("#1877F2")

    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=16 * mm, rightMargin=16 * mm)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("MetaTitle", parent=styles["Title"], textColor=primary)
    story: list[Any] = []

    story.append(Paragraph(f"Báo cáo Meta Ads — {company}", title_style))
    story.append(
        Paragraph(
            f"Kỳ {date_from} → {date_to} · Xuất {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            styles["Normal"],
        ),
    )
    story.append(Spacer(1, 10))

    kpi_rows: list[list[str]] = [["Chỉ số", "Giá trị"]]
    kpi_rows.append(["Spend", f"{float(summary.get('total_spend') or 0):,.0f} VND"])
    kpi_rows.append(["Leads CRM", str(summary.get("total_leads") or 0)])
    avg_cpl = summary.get("avg_cpl")
    kpi_rows.append(["CPL TB", f"{float(avg_cpl):,.0f} VND" if avg_cpl is not None else "—"])
    kpi_rows.append(["Chưa map", str(summary.get("unmapped_campaigns") or 0)])
    kpi_rows.append(["Vượt target", str(summary.get("over_target_rows") or 0)])

    tbl = Table(kpi_rows, colWidths=[80 * mm, 80 * mm])
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
    doc.build(story)
    buf.seek(0)
    filename = f"meta-hub-{date_from}_{date_to}.pdf"
    return buf, filename
