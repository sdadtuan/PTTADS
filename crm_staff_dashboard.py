"""Tổng hợp dữ liệu trang chủ portal nhân viên."""
from __future__ import annotations

from datetime import datetime
from typing import Any


def build_staff_dashboard(
    conn: Any,
    staff_id: int,
    *,
    ts: str,
    kpi_status_labels: dict[str, str] | None = None,
) -> dict[str, Any]:
    """KPI + Lead phân công + báo cáo ngày cho một nhân viên."""
    from crm_daily_work_report_store import fetch_daily_work_report_by_staff_date
    from crm_lead_store import fetch_leads, fetch_lead_stats, lead_row_to_dict

    from app import (
        CRM_KPI_STATUS_LABELS_VI,
        _crm_ensure_staff_kpi_rows,
        _crm_position_metric_ids,
        _crm_staff_position_id,
        _crm_staff_profile,
    )

    labels = kpi_status_labels or CRM_KPI_STATUS_LABELS_VI
    profile = _crm_staff_profile(conn, staff_id) or {}
    now = datetime.now()
    year, month = now.year, now.month
    today = now.strftime("%Y-%m-%d")

    position_id = _crm_staff_position_id(conn, staff_id)
    _crm_ensure_staff_kpi_rows(conn, staff_id, position_id, year, month)
    metric_ids = _crm_position_metric_ids(conn, position_id)
    kpi_clauses = ["k.staff_id = ?", "k.year = ?", "k.month = ?"]
    kpi_params: list[Any] = [staff_id, year, month]
    if metric_ids:
        kpi_clauses.append(f"k.metric_id IN ({','.join('?' * len(metric_ids))})")
        kpi_params.extend(metric_ids)
    kpi_rows = conn.execute(
        f"""
        SELECT k.id, k.metric_id, k.target_value, k.actual_value, k.status, k.note,
               m.name AS metric_name, m.unit AS metric_unit
        FROM crm_staff_kpi k
        JOIN crm_kpi_metrics m ON m.id = k.metric_id
        WHERE {' AND '.join(kpi_clauses)}
        ORDER BY m.sort_order ASC, m.name COLLATE NOCASE ASC
        LIMIT 12
        """,
        kpi_params,
    ).fetchall()
    kpi_items: list[dict[str, Any]] = []
    kpi_counts = {"draft": 0, "achieved": 0, "at_risk": 0, "missed": 0}
    for r in kpi_rows:
        st = str(r["status"] or "draft")
        kpi_counts[st] = kpi_counts.get(st, 0) + 1
        kpi_items.append(
            {
                "id": int(r["id"]),
                "metric_name": str(r["metric_name"] or ""),
                "unit": str(r["metric_unit"] or ""),
                "target_value": r["target_value"],
                "actual_value": r["actual_value"],
                "status": st,
                "status_label": labels.get(st, st),
            }
        )

    lead_stats = fetch_lead_stats(conn, owner_id=staff_id)
    recent_lead_rows = fetch_leads(conn, owner_id=staff_id, limit=8)
    recent_leads = [lead_row_to_dict(r, conn) for r in recent_lead_rows]

    report_row = fetch_daily_work_report_by_staff_date(conn, staff_id=staff_id, report_date=today)
    today_report = None
    if report_row:
        from crm_daily_work_report_store import daily_work_report_row_to_dict

        today_report = daily_work_report_row_to_dict(report_row)

    open_cases = conn.execute(
        """
        SELECT COUNT(*) AS c FROM crm_cases
        WHERE assigned_staff_id = ? AND status NOT IN ('closed', 'cancelled')
        """,
        (staff_id,),
    ).fetchone()
    customers = conn.execute(
        """
        SELECT COUNT(DISTINCT c.id) AS c
        FROM crm_customers c
        INNER JOIN crm_cases cs ON cs.customer_id = c.id
        WHERE cs.assigned_staff_id = ? AND cs.status NOT IN ('closed', 'cancelled')
        """,
        (staff_id,),
    ).fetchone()

    return {
        "staff": {
            "id": staff_id,
            "name": str(profile.get("name") or ""),
            "position_name": str(profile.get("position_name") or ""),
            "department": str(profile.get("department") or ""),
        },
        "period": {"year": year, "month": month, "today": today},
        "kpi": {
            "total": len(kpi_items),
            "counts": kpi_counts,
            "items": kpi_items,
        },
        "leads": {
            "stats": lead_stats,
            "recent": recent_leads,
        },
        "daily_report": {
            "today": today,
            "submitted": today_report is not None,
            "report": today_report,
        },
        "workload": {
            "open_cases": int(open_cases["c"]) if open_cases else 0,
            "active_customers": int(customers["c"]) if customers else 0,
        },
    }
