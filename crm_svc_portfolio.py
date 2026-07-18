"""Concentration risk + team capacity — nhóm 5 KPI portfolio."""
from __future__ import annotations

import os
import sqlite3
from datetime import date
from typing import Any

ENV_AM_LIFECYCLE_CAPACITY = "PTT_AM_LIFECYCLE_CAPACITY"
ENV_SP_LIFECYCLE_CAPACITY = "PTT_SP_LIFECYCLE_CAPACITY"
DEFAULT_AM_LIFECYCLE_CAPACITY = 8
DEFAULT_SP_LIFECYCLE_CAPACITY = 12

CONCENTRATION_WARN_TOP1_PCT = 40.0
CONCENTRATION_WARN_TOP2_PCT = 50.0
CAPACITY_WARN_UTIL_PCT = 85.0


def _month_prefix(year: int, month: int) -> str:
    return f"{int(year):04d}-{int(month):02d}"


def _env_pos_int(name: str, default: int) -> int:
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value > 0 else default


def am_lifecycle_capacity() -> int:
    return _env_pos_int(ENV_AM_LIFECYCLE_CAPACITY, DEFAULT_AM_LIFECYCLE_CAPACITY)


def sp_lifecycle_capacity() -> int:
    return _env_pos_int(ENV_SP_LIFECYCLE_CAPACITY, DEFAULT_SP_LIFECYCLE_CAPACITY)


def get_concentration_metrics(
    conn: sqlite3.Connection,
    *,
    year: int,
    month: int,
    exclude_placeholder: bool = True,
    top_n: int = 5,
) -> dict[str, Any]:
    """
    Rủi ro tập trung doanh thu — thu tháng theo KH.

    top2_concentration_pct = (top1 + top2) / tổng thu tháng × 100
    Chỉ tính KH thật (có customer_id, không placeholder).
    """
    month_str = _month_prefix(year, month)
    ph = " AND COALESCE(cu.is_placeholder, 0) = 0" if exclude_placeholder else ""
    rows = conn.execute(
        f"""
        SELECT cu.id AS customer_id,
               COALESCE(cu.name, '—') AS customer_name,
               COALESCE(SUM(p.amount_vnd), 0) AS received_vnd
        FROM crm_svc_payments p
        INNER JOIN crm_service_lifecycle lc ON lc.id = p.lifecycle_id
        INNER JOIN crm_customers cu ON cu.id = lc.customer_id
        WHERE p.status = 'received'
          AND p.received_on LIKE ?
          AND lc.customer_id IS NOT NULL
          {ph}
        GROUP BY cu.id, cu.name
        ORDER BY received_vnd DESC, cu.id ASC
        """,
        (f"{month_str}%",),
    ).fetchall()

    total_row = conn.execute(
        """
        SELECT COALESCE(SUM(p.amount_vnd), 0)
        FROM crm_svc_payments p
        WHERE p.status = 'received' AND p.received_on LIKE ?
        """,
        (f"{month_str}%",),
    ).fetchone()
    total_received_vnd = int(total_row[0] if total_row else 0)

    customers: list[dict[str, Any]] = []
    for row in rows:
        amt = int(row["received_vnd"] or 0)
        if amt <= 0:
            continue
        customers.append(
            {
                "customer_id": int(row["customer_id"]),
                "customer_name": str(row["customer_name"] or "—"),
                "received_vnd": amt,
                "share_pct": round(amt / total_received_vnd * 100, 1)
                if total_received_vnd > 0
                else 0.0,
            }
        )

    top1_vnd = customers[0]["received_vnd"] if len(customers) >= 1 else 0
    top2_vnd = sum(c["received_vnd"] for c in customers[:2])
    top1_pct = round(top1_vnd / total_received_vnd * 100, 1) if total_received_vnd else 0.0
    top2_pct = round(top2_vnd / total_received_vnd * 100, 1) if total_received_vnd else 0.0

    return {
        "year": int(year),
        "month": int(month),
        "total_received_vnd": total_received_vnd,
        "paying_customers": len(customers),
        "top1_received_vnd": top1_vnd,
        "top2_received_vnd": top2_vnd,
        "top1_share_pct": top1_pct,
        "top2_concentration_pct": top2_pct,
        "concentration_risk": top2_pct >= CONCENTRATION_WARN_TOP2_PCT
        or top1_pct >= CONCENTRATION_WARN_TOP1_PCT,
        "top_customers": customers[: int(top_n)],
    }


def get_concentration_metrics_for_period(
    conn: sqlite3.Connection,
    *,
    period_start: date,
    period_end: date,
    exclude_placeholder: bool = True,
    top_n: int = 5,
) -> dict[str, Any]:
    """Rủi ro tập trung doanh thu — thu trong khoảng ngày."""
    ph = " AND COALESCE(cu.is_placeholder, 0) = 0" if exclude_placeholder else ""
    rows = conn.execute(
        f"""
        SELECT cu.id AS customer_id,
               COALESCE(cu.name, '—') AS customer_name,
               COALESCE(SUM(p.amount_vnd), 0) AS received_vnd
        FROM crm_svc_payments p
        INNER JOIN crm_service_lifecycle lc ON lc.id = p.lifecycle_id
        INNER JOIN crm_customers cu ON cu.id = lc.customer_id
        WHERE p.status = 'received'
          AND substr(p.received_on, 1, 10) >= ?
          AND substr(p.received_on, 1, 10) <= ?
          AND lc.customer_id IS NOT NULL
          {ph}
        GROUP BY cu.id, cu.name
        ORDER BY received_vnd DESC, cu.id ASC
        """,
        (period_start.isoformat(), period_end.isoformat()),
    ).fetchall()

    total_row = conn.execute(
        """
        SELECT COALESCE(SUM(amount_vnd), 0)
        FROM crm_svc_payments
        WHERE status = 'received'
          AND substr(received_on, 1, 10) >= ?
          AND substr(received_on, 1, 10) <= ?
        """,
        (period_start.isoformat(), period_end.isoformat()),
    ).fetchone()
    total_received_vnd = int(total_row[0] if total_row else 0)

    customers: list[dict[str, Any]] = []
    for row in rows:
        amt = int(row["received_vnd"] or 0)
        if amt <= 0:
            continue
        customers.append(
            {
                "customer_id": int(row["customer_id"]),
                "customer_name": str(row["customer_name"] or "—"),
                "received_vnd": amt,
                "share_pct": round(amt / total_received_vnd * 100, 1)
                if total_received_vnd > 0
                else 0.0,
            }
        )

    top1_vnd = customers[0]["received_vnd"] if len(customers) >= 1 else 0
    top2_vnd = sum(c["received_vnd"] for c in customers[:2])
    top1_pct = round(top1_vnd / total_received_vnd * 100, 1) if total_received_vnd else 0.0
    top2_pct = round(top2_vnd / total_received_vnd * 100, 1) if total_received_vnd else 0.0

    return {
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
        "total_received_vnd": total_received_vnd,
        "paying_customers": len(customers),
        "top1_received_vnd": top1_vnd,
        "top2_received_vnd": top2_vnd,
        "top1_share_pct": top1_pct,
        "top2_concentration_pct": top2_pct,
        "concentration_risk": top2_pct >= CONCENTRATION_WARN_TOP2_PCT
        or top1_pct >= CONCENTRATION_WARN_TOP1_PCT,
        "top_customers": customers[: int(top_n)],
    }


def get_capacity_metrics(
    conn: sqlite3.Connection,
    *,
    year: int,
    month: int,
) -> dict[str, Any]:
    """
    Công suất team vs doanh thu — proxy lifecycle/FTE.

    - AM/SP utilization = active lifecycles / (staff đang gán × cap/env)
    - revenue_per_am_vnd = thu tháng / số AM đang gán
    - revenue_per_active_lifecycle_vnd = thu tháng / lifecycle active
    """
    month_str = _month_prefix(year, month)
    am_cap = am_lifecycle_capacity()
    sp_cap = sp_lifecycle_capacity()

    recv_row = conn.execute(
        """
        SELECT COALESCE(SUM(amount_vnd), 0)
        FROM crm_svc_payments
        WHERE status = 'received' AND received_on LIKE ?
        """,
        (f"{month_str}%",),
    ).fetchone()
    received_month_vnd = int(recv_row[0] if recv_row else 0)

    am_load_row = conn.execute(
        """
        SELECT COUNT(*) AS c, COUNT(DISTINCT assigned_am) AS staff
        FROM crm_service_lifecycle
        WHERE status = 'active' AND assigned_am IS NOT NULL
        """
    ).fetchone()
    sp_load_row = conn.execute(
        """
        SELECT COUNT(*) AS c, COUNT(DISTINCT assigned_sp) AS staff
        FROM crm_service_lifecycle
        WHERE status = 'active' AND assigned_sp IS NOT NULL
        """
    ).fetchone()
    active_lc_row = conn.execute(
        "SELECT COUNT(*) FROM crm_service_lifecycle WHERE status = 'active'"
    ).fetchone()

    am_load = int(am_load_row["c"] if am_load_row else 0)
    am_staff = int(am_load_row["staff"] if am_load_row else 0)
    sp_load = int(sp_load_row["c"] if sp_load_row else 0)
    sp_staff = int(sp_load_row["staff"] if sp_load_row else 0)
    active_lifecycle_count = int(active_lc_row[0] if active_lc_row else 0)

    am_capacity_slots = am_staff * am_cap if am_staff > 0 else 0
    sp_capacity_slots = sp_staff * sp_cap if sp_staff > 0 else 0

    am_util = round(am_load / am_capacity_slots * 100, 1) if am_capacity_slots else 0.0
    sp_util = round(sp_load / sp_capacity_slots * 100, 1) if sp_capacity_slots else 0.0
    combined_load = am_load + sp_load
    combined_capacity = am_capacity_slots + sp_capacity_slots
    combined_util = (
        round(combined_load / combined_capacity * 100, 1) if combined_capacity else 0.0
    )

    delivery_staff = am_staff + sp_staff
    revenue_per_am_vnd = (
        int(received_month_vnd / am_staff) if am_staff > 0 else 0
    )
    revenue_per_sp_vnd = (
        int(received_month_vnd / sp_staff) if sp_staff > 0 else 0
    )
    revenue_per_active_lifecycle_vnd = (
        int(received_month_vnd / active_lifecycle_count)
        if active_lifecycle_count > 0
        else 0
    )
    revenue_per_delivery_staff_vnd = (
        int(received_month_vnd / delivery_staff) if delivery_staff > 0 else 0
    )

    staff_rows = conn.execute(
        """
        SELECT s.id, s.name,
               SUM(CASE WHEN lc.assigned_am = s.id AND lc.status = 'active' THEN 1 ELSE 0 END) AS am_load,
               SUM(CASE WHEN lc.assigned_sp = s.id AND lc.status = 'active' THEN 1 ELSE 0 END) AS sp_load
        FROM crm_staff s
        LEFT JOIN crm_service_lifecycle lc ON lc.assigned_am = s.id OR lc.assigned_sp = s.id
        WHERE COALESCE(s.active, 1) = 1
        GROUP BY s.id, s.name
        HAVING am_load > 0 OR sp_load > 0
        ORDER BY (am_load + sp_load) DESC, s.name
        LIMIT 12
        """
    ).fetchall()
    staff_utilization: list[dict[str, Any]] = []
    for row in staff_rows:
        d = dict(row)
        sid = int(d["id"])
        a_load = int(d["am_load"] or 0)
        s_load = int(d["sp_load"] or 0)
        a_util = round(a_load / am_cap * 100, 1) if a_load and am_cap else 0.0
        s_util = round(s_load / sp_cap * 100, 1) if s_load and sp_cap else 0.0
        staff_utilization.append(
            {
                "staff_id": sid,
                "staff_name": str(d["name"] or "—"),
                "am_load": a_load,
                "sp_load": s_load,
                "am_utilization_pct": a_util,
                "sp_utilization_pct": s_util,
            }
        )

    return {
        "year": int(year),
        "month": int(month),
        "received_month_vnd": received_month_vnd,
        "active_lifecycle_count": active_lifecycle_count,
        "am_lifecycle_capacity": am_cap,
        "sp_lifecycle_capacity": sp_cap,
        "am_active_staff": am_staff,
        "sp_active_staff": sp_staff,
        "am_active_lifecycles": am_load,
        "sp_active_lifecycles": sp_load,
        "am_capacity_slots": am_capacity_slots,
        "sp_capacity_slots": sp_capacity_slots,
        "am_utilization_pct": am_util,
        "sp_utilization_pct": sp_util,
        "combined_utilization_pct": combined_util,
        "capacity_warning": combined_util >= CAPACITY_WARN_UTIL_PCT
        or am_util >= CAPACITY_WARN_UTIL_PCT
        or sp_util >= CAPACITY_WARN_UTIL_PCT,
        "revenue_per_am_vnd": revenue_per_am_vnd,
        "revenue_per_sp_vnd": revenue_per_sp_vnd,
        "revenue_per_active_lifecycle_vnd": revenue_per_active_lifecycle_vnd,
        "revenue_per_delivery_staff_vnd": revenue_per_delivery_staff_vnd,
        "staff_utilization": staff_utilization,
    }


def get_portfolio_metrics(
    conn: sqlite3.Connection,
    *,
    year: int,
    month: int,
) -> dict[str, Any]:
    """Tổng hợp nhóm 5 — concentration + capacity."""
    concentration = get_concentration_metrics(conn, year=year, month=month)
    capacity = get_capacity_metrics(conn, year=year, month=month)
    return {
        "year": int(year),
        "month": int(month),
        "concentration": concentration,
        "capacity": capacity,
    }
