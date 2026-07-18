"""Retention / churn / renewal cohort — từ crm_contracts + crm_customers."""
from __future__ import annotations

import calendar
import sqlite3
from datetime import date, timedelta
from typing import Any

# HĐ vẫn coi KH còn active nếu overlap tháng
CONTRACT_ACTIVE_STATUSES: frozenset[str] = frozenset({
    "signed",
    "active",
    "expiring",
    "paused",
    "renewed",
})

CONTRACT_CHURN_STATUSES: frozenset[str] = frozenset({"lost", "cancelled"})
CONTRACT_RENEWED_STATUS = "renewed"
CONTRACT_COMPLETED_STATUS = "completed"

# Loại khỏi cohort renewal & active count
CONTRACT_EXCLUDE_STATUSES: frozenset[str] = frozenset({"draft", "negotiation"})


def _parse_ymd(text: str | None) -> date | None:
    raw = str(text or "").strip()[:10]
    if len(raw) != 10:
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return None


def _month_bounds(year: int, month: int) -> tuple[date, date]:
    y, m = int(year), int(month)
    last_day = calendar.monthrange(y, m)[1]
    return date(y, m, 1), date(y, m, last_day)


def _prev_month(year: int, month: int) -> tuple[int, int]:
    y, m = int(year), int(month)
    if m == 1:
        return y - 1, 12
    return y, m - 1


def _contract_overlaps_period(
    row: dict[str, Any],
    period_start: date,
    period_end: date,
) -> bool:
    status = str(row.get("status") or "").strip()
    if status in CONTRACT_EXCLUDE_STATUSES:
        return False
    if status in CONTRACT_CHURN_STATUSES:
        return False
    if status == CONTRACT_COMPLETED_STATUS:
        return False
    if status not in CONTRACT_ACTIVE_STATUSES:
        return False

    start = _parse_ymd(str(row.get("starts_on") or ""))
    end = _parse_ymd(str(row.get("ends_on") or ""))
    if start and start > period_end:
        return False
    if end and end < period_start:
        return False
    return True


def _contract_overlaps_month(
    row: dict[str, Any],
    period_start: date,
    period_end: date,
) -> bool:
    return _contract_overlaps_period(row, period_start, period_end)


def _active_customer_ids_for_period(
    conn: sqlite3.Connection,
    *,
    period_start: date,
    period_end: date,
    exclude_placeholder: bool = True,
) -> set[int]:
    ph = " AND COALESCE(cu.is_placeholder, 0) = 0" if exclude_placeholder else ""
    rows = conn.execute(
        f"""
        SELECT ct.customer_id, ct.status, ct.starts_on, ct.ends_on
        FROM crm_contracts ct
        LEFT JOIN crm_customers cu ON cu.id = ct.customer_id
        WHERE ct.customer_id IS NOT NULL{ph}
        """,
    ).fetchall()
    ids: set[int] = set()
    for row in rows:
        d = dict(row)
        cid = d.get("customer_id")
        if cid is None:
            continue
        if _contract_overlaps_period(d, period_start, period_end):
            ids.add(int(cid))
    return ids


def get_retention_metrics_for_period(
    conn: sqlite3.Connection,
    *,
    period_start: date,
    period_end: date,
    exclude_placeholder: bool = True,
) -> dict[str, Any]:
    """Retention/churn theo khoảng ngày — so sánh với kỳ trước cùng độ dài."""
    if period_end < period_start:
        period_start, period_end = period_end, period_start
    length_days = (period_end - period_start).days + 1
    prior_end = period_start - timedelta(days=1)
    prior_start = prior_end - timedelta(days=length_days - 1)

    active_curr = _active_customer_ids_for_period(
        conn,
        period_start=period_start,
        period_end=period_end,
        exclude_placeholder=exclude_placeholder,
    )
    active_prev = _active_customer_ids_for_period(
        conn,
        period_start=prior_start,
        period_end=prior_end,
        exclude_placeholder=exclude_placeholder,
    )
    retained = active_curr & active_prev
    prev_n = len(active_prev)
    curr_n = len(active_curr)
    retained_n = len(retained)
    customer_retention_pct = round(retained_n / prev_n * 100, 1) if prev_n > 0 else 0.0
    customer_churn_pct = round((prev_n - retained_n) / prev_n * 100, 1) if prev_n > 0 else 0.0

    return {
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
        "prior_start": prior_start.isoformat(),
        "prior_end": prior_end.isoformat(),
        "active_customers": curr_n,
        "active_customers_prev": prev_n,
        "customers_retained": retained_n,
        "customer_retention_pct": customer_retention_pct,
        "customer_churn_pct": customer_churn_pct,
    }


def _active_customer_ids(
    conn: sqlite3.Connection,
    *,
    year: int,
    month: int,
    exclude_placeholder: bool = True,
) -> set[int]:
    period_start, period_end = _month_bounds(year, month)
    ph = " AND COALESCE(cu.is_placeholder, 0) = 0" if exclude_placeholder else ""
    rows = conn.execute(
        f"""
        SELECT ct.customer_id, ct.status, ct.starts_on, ct.ends_on
        FROM crm_contracts ct
        LEFT JOIN crm_customers cu ON cu.id = ct.customer_id
        WHERE ct.customer_id IS NOT NULL{ph}
        """,
    ).fetchall()
    ids: set[int] = set()
    for row in rows:
        d = dict(row)
        cid = d.get("customer_id")
        if cid is None:
            continue
        if _contract_overlaps_month(d, period_start, period_end):
            ids.add(int(cid))
    return ids


def get_retention_metrics(
    conn: sqlite3.Connection,
    *,
    year: int,
    month: int,
    exclude_placeholder: bool = True,
) -> dict[str, Any]:
    """
    KPI retention/churn nhóm 3.

    - Customer retention MoM: KH active tháng trước còn active tháng này.
    - Renewal cohort: HĐ có ends_on trong tháng → renewed / churn / completed.
      renewal_rate = renewed / (renewed + churned + completed) — chỉ HĐ đã quyết định.
    """
    period_start, period_end = _month_bounds(year, month)
    prev_y, prev_m = _prev_month(year, month)

    active_curr = _active_customer_ids(
        conn, year=year, month=month, exclude_placeholder=exclude_placeholder
    )
    active_prev = _active_customer_ids(
        conn, year=prev_y, month=prev_m, exclude_placeholder=exclude_placeholder
    )
    retained = active_curr & active_prev
    prev_n = len(active_prev)
    curr_n = len(active_curr)
    retained_n = len(retained)
    customer_retention_pct = round(retained_n / prev_n * 100, 1) if prev_n > 0 else 0.0
    customer_churn_pct = round((prev_n - retained_n) / prev_n * 100, 1) if prev_n > 0 else 0.0

    ph = " AND COALESCE(cu.is_placeholder, 0) = 0" if exclude_placeholder else ""
    cohort_rows = conn.execute(
        f"""
        SELECT ct.id, ct.customer_id, ct.title, ct.status, ct.ends_on, ct.amount_vnd,
               cu.name AS customer_name
        FROM crm_contracts ct
        LEFT JOIN crm_customers cu ON cu.id = ct.customer_id
        WHERE ct.ends_on >= ? AND ct.ends_on <= ?
          AND ct.status NOT IN ('draft', 'negotiation')
          {ph}
        ORDER BY ct.ends_on, ct.id
        """,
        (period_start.isoformat(), period_end.isoformat()),
    ).fetchall()

    renewed = churned = completed = pending = 0
    cohort_items: list[dict[str, Any]] = []
    for row in cohort_rows:
        d = dict(row)
        status = str(d.get("status") or "")
        if status == CONTRACT_RENEWED_STATUS:
            renewed += 1
            outcome = "renewed"
        elif status in CONTRACT_CHURN_STATUSES:
            churned += 1
            outcome = "churned"
        elif status == CONTRACT_COMPLETED_STATUS:
            completed += 1
            outcome = "completed"
        else:
            pending += 1
            outcome = "pending"
        cohort_items.append(
            {
                "contract_id": int(d["id"]),
                "customer_id": d.get("customer_id"),
                "customer_name": d.get("customer_name") or "—",
                "title": d.get("title") or "",
                "ends_on": str(d.get("ends_on") or "")[:10],
                "status": status,
                "outcome": outcome,
                "amount_vnd": int(d.get("amount_vnd") or 0),
            }
        )

    cohort_size = len(cohort_items)
    decided = renewed + churned + completed
    renewal_rate_pct = round(renewed / decided * 100, 1) if decided > 0 else 0.0
    cohort_churn_rate_pct = round(churned / cohort_size * 100, 1) if cohort_size > 0 else 0.0

    return {
        "year": int(year),
        "month": int(month),
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
        "active_customers": curr_n,
        "active_customers_prev": prev_n,
        "customers_retained": retained_n,
        "customer_retention_pct": customer_retention_pct,
        "customer_churn_pct": customer_churn_pct,
        "renewal_cohort": {
            "contracts_ending": cohort_size,
            "contracts_decided": decided,
            "renewed": renewed,
            "churned": churned,
            "completed": completed,
            "pending": pending,
            "renewal_rate_pct": renewal_rate_pct,
            "cohort_churn_rate_pct": cohort_churn_rate_pct,
            "items": cohort_items,
        },
    }
