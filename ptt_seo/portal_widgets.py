"""Portal client-facing SEO widget payloads (Gate C P3)."""
from __future__ import annotations

import sqlite3
from typing import Any

from ptt_seo.content import list_content
from ptt_seo.portal_bridge import _sanitize_portal_dashboard
from ptt_seo.report import dashboard


def portal_widgets(conn: sqlite3.Connection, customer_id: int) -> dict[str, Any]:
    """Compact KPI widgets for portal dashboard cards."""
    exec_dash = _sanitize_portal_dashboard(dashboard(conn, customer_id=customer_id, dashboard_type="executive"))
    pending_review = len(list_content(conn, customer_id, workflow_status="client_review"))
    gsc = exec_dash.get("gsc") or {}
    aeo = exec_dash.get("aeo") or {}
    trend = exec_dash.get("gsc_trend") or []
    sparkline = [int(p.get("clicks") or 0) for p in trend[-7:] if isinstance(p, dict)]
    return {
        "ok": True,
        "customer_id": customer_id,
        "widgets": {
            "gsc_clicks": {
                "label": "GSC Clicks (T-7)",
                "value": gsc.get("clicks"),
                "sparkline": sparkline,
            },
            "gsc_impressions": {
                "label": "Impressions",
                "value": gsc.get("impressions"),
            },
            "critical_issues": {
                "label": "Critical issues",
                "value": exec_dash.get("critical_issues") or 0,
            },
            "aeo_coverage": {
                "label": "AEO coverage",
                "value": aeo.get("coverage_pct"),
                "unit": "%",
            },
            "open_alerts": {
                "label": "Open alerts",
                "value": exec_dash.get("open_alerts") or 0,
            },
            "content_in_review": {
                "label": "Pending review",
                "value": pending_review,
            },
        },
    }
