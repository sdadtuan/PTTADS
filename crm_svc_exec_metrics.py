"""Executive KPI — CAC, delivery on-time, MRR/ARR (mở rộng sau nhóm 1–5)."""
from __future__ import annotations

import calendar
import os
import sqlite3
from datetime import date, datetime, timedelta
from typing import Any

from crm_svc_finance import BILLING_TYPE_RECURRING, COST_PHASE_PRESALES

ENV_MARKETING_SPEND = "PTT_MONTHLY_MARKETING_SPEND_VND"
ENV_DELIVERY_TASK_SLA_DAYS = "PTT_DELIVERY_TASK_SLA_DAYS"
DEFAULT_DELIVERY_TASK_SLA_DAYS = 14

DELIVERY_ONTIME_STAGES: frozenset[str] = frozenset({"deliver", "handover"})
CONTRACT_MRR_STATUSES: frozenset[str] = frozenset({
    "signed",
    "active",
    "expiring",
    "renewed",
})


def _month_prefix(year: int, month: int) -> str:
    return f"{int(year):04d}-{int(month):02d}"


def _month_bounds(year: int, month: int) -> tuple[date, date]:
    y, m = int(year), int(month)
    last_day = calendar.monthrange(y, m)[1]
    return date(y, m, 1), date(y, m, last_day)


def _parse_ymd(text: str | None) -> date | None:
    raw = str(text or "").strip()[:10]
    if len(raw) != 10:
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return None


def _parse_ts_date(text: str | None) -> date | None:
    raw = str(text or "").strip()
    if not raw:
        return None
    for fmt, length in (("%Y-%m-%d %H:%M:%S", 19), ("%Y-%m-%d", 10)):
        try:
            return datetime.strptime(raw[:length], fmt).date()
        except ValueError:
            continue
    return _parse_ymd(raw)


def _env_nonneg_int(name: str, default: int = 0) -> int:
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return max(0, value)


def delivery_task_sla_days() -> int:
    return _env_nonneg_int(ENV_DELIVERY_TASK_SLA_DAYS, DEFAULT_DELIVERY_TASK_SLA_DAYS)


def monthly_marketing_spend_vnd() -> int:
    return _env_nonneg_int(ENV_MARKETING_SPEND, 0)


def ensure_period_inputs_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS crm_finance_period_inputs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            year INTEGER NOT NULL,
            month INTEGER NOT NULL,
            marketing_spend_vnd INTEGER NOT NULL DEFAULT 0,
            updated_at TEXT NOT NULL DEFAULT '',
            UNIQUE(year, month)
        )
        """
    )
    conn.commit()


def get_marketing_spend_vnd(
    conn: sqlite3.Connection, *, year: int, month: int
) -> tuple[int, str]:
    """Trả (amount, source) — DB ưu tiên, fallback env."""
    ensure_period_inputs_schema(conn)
    row = conn.execute(
        """
        SELECT marketing_spend_vnd FROM crm_finance_period_inputs
        WHERE year = ? AND month = ?
        """,
        (int(year), int(month)),
    ).fetchone()
    if row is not None:
        return max(0, int(row[0] or 0)), "db"
    return monthly_marketing_spend_vnd(), "env"


def set_marketing_spend_vnd(
    conn: sqlite3.Connection, *, year: int, month: int, amount_vnd: int
) -> int:
    ensure_period_inputs_schema(conn)
    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    amount = max(0, int(amount_vnd))
    conn.execute(
        """
        INSERT INTO crm_finance_period_inputs
            (year, month, marketing_spend_vnd, updated_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(year, month) DO UPDATE SET
            marketing_spend_vnd = excluded.marketing_spend_vnd,
            updated_at = excluded.updated_at
        """,
        (int(year), int(month), amount, ts),
    )
    conn.commit()
    return amount


def _sum_presales_cost_month(conn: sqlite3.Connection, month_str: str) -> int:
    row = conn.execute(
        """
        SELECT COALESCE(SUM(amount_vnd), 0)
        FROM crm_svc_expenses
        WHERE cost_phase = ? AND expense_on LIKE ?
        """,
        (COST_PHASE_PRESALES, f"{month_str}%"),
    ).fetchone()
    return int(row[0] if row else 0)


def _count_new_customers_month(
    conn: sqlite3.Connection, month_str: str, *, exclude_placeholder: bool = True
) -> int:
    ph = " AND COALESCE(cu.is_placeholder, 0) = 0" if exclude_placeholder else ""
    row = conn.execute(
        f"""
        SELECT COUNT(*) FROM (
            SELECT lc.customer_id, MIN(p.received_on) AS first_pay
            FROM crm_svc_payments p
            INNER JOIN crm_service_lifecycle lc ON lc.id = p.lifecycle_id
            INNER JOIN crm_customers cu ON cu.id = lc.customer_id
            WHERE p.status = 'received'
              AND lc.customer_id IS NOT NULL
              {ph}
            GROUP BY lc.customer_id
            HAVING substr(first_pay, 1, 7) = ?
        )
        """,
        (month_str,),
    ).fetchone()
    return int(row[0] if row else 0)


def _sum_presales_cost_period(
    conn: sqlite3.Connection, period_start: date, period_end: date
) -> int:
    row = conn.execute(
        """
        SELECT COALESCE(SUM(amount_vnd), 0)
        FROM crm_svc_expenses
        WHERE cost_phase = ?
          AND substr(expense_on, 1, 10) >= ?
          AND substr(expense_on, 1, 10) <= ?
        """,
        (COST_PHASE_PRESALES, period_start.isoformat(), period_end.isoformat()),
    ).fetchone()
    return int(row[0] if row else 0)


def _marketing_spend_for_period(
    conn: sqlite3.Connection, period_start: date, period_end: date
) -> tuple[int, str]:
    """Marketing spend prorate theo ngày trong khoảng (DB tháng hoặc env)."""
    total = 0
    sources: set[str] = set()
    day = period_start
    while day <= period_end:
        spend, source = get_marketing_spend_vnd(conn, year=day.year, month=day.month)
        days_in_month = calendar.monthrange(day.year, day.month)[1]
        total += int(spend / days_in_month) if days_in_month else 0
        sources.add(source)
        day += timedelta(days=1)
    src = "db" if "db" in sources else "env"
    return total, src


def _count_new_customers_period(
    conn: sqlite3.Connection,
    period_start: date,
    period_end: date,
    *,
    exclude_placeholder: bool = True,
) -> int:
    ph = " AND COALESCE(cu.is_placeholder, 0) = 0" if exclude_placeholder else ""
    row = conn.execute(
        f"""
        SELECT COUNT(*) FROM (
            SELECT lc.customer_id, MIN(p.received_on) AS first_pay
            FROM crm_svc_payments p
            INNER JOIN crm_service_lifecycle lc ON lc.id = p.lifecycle_id
            INNER JOIN crm_customers cu ON cu.id = lc.customer_id
            WHERE p.status = 'received'
              AND lc.customer_id IS NOT NULL
              {ph}
            GROUP BY lc.customer_id
            HAVING substr(first_pay, 1, 10) >= ?
               AND substr(first_pay, 1, 10) <= ?
        )
        """,
        (period_start.isoformat(), period_end.isoformat()),
    ).fetchone()
    return int(row[0] if row else 0)


def get_cac_metrics_for_period(
    conn: sqlite3.Connection,
    *,
    period_start: date,
    period_end: date,
) -> dict[str, Any]:
    """CAC khoảng ngày = (pre-sales + marketing prorate) / KH mới trong khoảng."""
    presales_cost_vnd = _sum_presales_cost_period(conn, period_start, period_end)
    marketing_cost_vnd, marketing_spend_source = _marketing_spend_for_period(
        conn, period_start, period_end
    )
    acquisition_cost_vnd = presales_cost_vnd + marketing_cost_vnd
    new_customers = _count_new_customers_period(conn, period_start, period_end)
    cac_vnd = int(acquisition_cost_vnd / new_customers) if new_customers > 0 else 0
    cac_presales_only_vnd = (
        int(presales_cost_vnd / new_customers) if new_customers > 0 else 0
    )
    return {
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
        "presales_cost_vnd": presales_cost_vnd,
        "marketing_cost_vnd": marketing_cost_vnd,
        "marketing_spend_source": marketing_spend_source,
        "acquisition_cost_vnd": acquisition_cost_vnd,
        "new_customers": new_customers,
        "cac_vnd": cac_vnd,
        "cac_presales_only_vnd": cac_presales_only_vnd,
        "definitions": {
            "numerator": "Chi pre-sales + marketing prorate theo ngày trong khoảng",
            "denominator": "KH có payment received đầu tiên trong khoảng",
        },
    }


def get_cac_metrics(
    conn: sqlite3.Connection,
    *,
    year: int,
    month: int,
) -> dict[str, Any]:
    """
    CAC tháng = (chi pre-sales + marketing env) / KH mới.

    KH mới = lần đầu có payment received trong tháng.
    """
    month_str = _month_prefix(year, month)
    presales_cost_vnd = _sum_presales_cost_month(conn, month_str)
    marketing_cost_vnd, marketing_spend_source = get_marketing_spend_vnd(
        conn, year=year, month=month
    )
    acquisition_cost_vnd = presales_cost_vnd + marketing_cost_vnd
    new_customers = _count_new_customers_month(conn, month_str)

    cac_vnd = (
        int(acquisition_cost_vnd / new_customers) if new_customers > 0 else 0
    )
    cac_presales_only_vnd = (
        int(presales_cost_vnd / new_customers) if new_customers > 0 else 0
    )

    return {
        "year": int(year),
        "month": int(month),
        "presales_cost_vnd": presales_cost_vnd,
        "marketing_cost_vnd": marketing_cost_vnd,
        "marketing_spend_source": marketing_spend_source,
        "acquisition_cost_vnd": acquisition_cost_vnd,
        "new_customers": new_customers,
        "cac_vnd": cac_vnd,
        "cac_presales_only_vnd": cac_presales_only_vnd,
        "definitions": {
            "numerator": "Chi pre-sales tháng + marketing (DB tháng hoặc env)",
            "denominator": "KH có payment received đầu tiên trong tháng",
        },
    }


def _stage_first_entered_on(
    conn: sqlite3.Connection, lifecycle_id: int, stage: str
) -> date | None:
    row = conn.execute(
        """
        SELECT created_at FROM crm_service_lifecycle_events
        WHERE lifecycle_id = ? AND to_stage = ?
        ORDER BY created_at ASC, id ASC
        LIMIT 1
        """,
        (int(lifecycle_id), stage),
    ).fetchone()
    if row and row[0]:
        return _parse_ts_date(str(row[0]))
    lc = conn.execute(
        "SELECT stage, stage_entered_at FROM crm_service_lifecycle WHERE id = ?",
        (int(lifecycle_id),),
    ).fetchone()
    if lc and str(lc["stage"] or "") == stage:
        return _parse_ts_date(str(lc["stage_entered_at"] or ""))
    return None


def _task_due_on(
    conn: sqlite3.Connection,
    *,
    lifecycle_id: int,
    stage: str,
    task_due_on: str | None,
) -> date | None:
    explicit = _parse_ymd(task_due_on)
    if explicit:
        return explicit
    entered = _stage_first_entered_on(conn, lifecycle_id, stage)
    if entered is None:
        return None
    return entered + timedelta(days=delivery_task_sla_days())


def get_delivery_ontime_metrics_for_period(
    conn: sqlite3.Connection,
    *,
    period_start: date,
    period_end: date,
) -> dict[str, Any]:
    """
    On-time delivery trong khoảng — chỉ task deliver/handover hoàn thành trong khoảng.
    """
    sla_days = delivery_task_sla_days()
    rows = conn.execute(
        """
        SELECT t.id, t.lifecycle_id, t.stage, t.is_done, t.done_at, t.title,
               COALESCE(t.due_on, '') AS due_on,
               lc.status AS lifecycle_status
        FROM crm_svc_tasks t
        INNER JOIN crm_service_lifecycle lc ON lc.id = t.lifecycle_id
        WHERE t.stage IN ('deliver', 'handover')
          AND lc.status IN ('active', 'closed')
          AND COALESCE(t.is_done, 0) = 1
        """
    ).fetchall()

    on_time = late = 0
    items: list[dict[str, Any]] = []

    for row in rows:
        d = dict(row)
        done_at = _parse_ts_date(str(d.get("done_at") or ""))
        if done_at is None or not (period_start <= done_at <= period_end):
            continue
        lid = int(d["lifecycle_id"])
        stage = str(d["stage"] or "")
        due = _task_due_on(conn, lifecycle_id=lid, stage=stage, task_due_on=d.get("due_on"))
        if due is None:
            continue
        if done_at <= due:
            on_time += 1
            outcome = "on_time"
        else:
            late += 1
            outcome = "late"
        items.append(
            {
                "task_id": int(d["id"]),
                "lifecycle_id": lid,
                "stage": stage,
                "title": str(d.get("title") or ""),
                "due_on": due.isoformat(),
                "done_at": done_at.isoformat(),
                "outcome": outcome,
            }
        )

    decided = on_time + late
    on_time_rate_pct = round(on_time / decided * 100, 1) if decided else 0.0

    return {
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
        "sla_days_default": sla_days,
        "tasks_decided": decided,
        "tasks_on_time": on_time,
        "tasks_late": late,
        "on_time_rate_pct": on_time_rate_pct,
        "items": items[:20],
    }


def get_delivery_ontime_metrics(
    conn: sqlite3.Connection,
    *,
    year: int,
    month: int,
) -> dict[str, Any]:
    """
    On-time delivery — task stage deliver/handover đã hoàn thành.

    on_time_rate = on_time / (on_time + late) — chỉ task đã done.
    due = task.due_on hoặc stage_entered + SLA (PTT_DELIVERY_TASK_SLA_DAYS).
    """
    period_start, period_end = _month_bounds(year, month)
    sla_days = delivery_task_sla_days()

    rows = conn.execute(
        """
        SELECT t.id, t.lifecycle_id, t.stage, t.is_done, t.done_at, t.title,
               COALESCE(t.due_on, '') AS due_on,
               lc.status AS lifecycle_status
        FROM crm_svc_tasks t
        INNER JOIN crm_service_lifecycle lc ON lc.id = t.lifecycle_id
        WHERE t.stage IN ('deliver', 'handover')
          AND lc.status IN ('active', 'closed')
        """
    ).fetchall()

    on_time = late = pending_overdue = pending_not_due = 0
    items: list[dict[str, Any]] = []

    for row in rows:
        d = dict(row)
        lid = int(d["lifecycle_id"])
        stage = str(d["stage"] or "")
        due = _task_due_on(conn, lifecycle_id=lid, stage=stage, task_due_on=d.get("due_on"))
        if due is None:
            continue
        done = int(d.get("is_done") or 0) == 1
        done_at = _parse_ts_date(str(d.get("done_at") or ""))

        if done and done_at:
            if done_at <= due:
                on_time += 1
                outcome = "on_time"
            else:
                late += 1
                outcome = "late"
        elif period_end >= due:
            pending_overdue += 1
            outcome = "overdue"
        else:
            pending_not_due += 1
            outcome = "pending"

        if outcome in ("on_time", "late", "overdue"):
            items.append(
                {
                    "task_id": int(d["id"]),
                    "lifecycle_id": lid,
                    "stage": stage,
                    "title": str(d.get("title") or ""),
                    "due_on": due.isoformat(),
                    "done_at": str(d.get("done_at") or "")[:10] or None,
                    "outcome": outcome,
                }
            )

    decided = on_time + late
    on_time_rate_pct = round(on_time / decided * 100, 1) if decided else 0.0

    return {
        "year": int(year),
        "month": int(month),
        "sla_days_default": sla_days,
        "tasks_decided": decided,
        "tasks_on_time": on_time,
        "tasks_late": late,
        "tasks_pending_overdue": pending_overdue,
        "tasks_pending_not_due": pending_not_due,
        "on_time_rate_pct": on_time_rate_pct,
        "items": items[:20],
    }


def get_mrr_arr_metrics(
    conn: sqlite3.Connection,
    *,
    year: int,
    month: int,
    am_id: int | None = None,
) -> dict[str, Any]:
    """
    MRR/ARR bookings từ HĐ recurring active + cash recurring tháng.

    MRR bookings = SUM amount_vnd HĐ recurring quy về tháng (billing_cycle).
    ARR = MRR × 12.
    """
    from crm_svc_finance import contract_amount_to_mrr_vnd

    month_str = _month_prefix(year, month)
    am_clause = ""
    am_params: list[Any] = []
    if am_id is not None:
        am_clause = " AND lc.assigned_am = ?"
        am_params = [int(am_id)]

    contract_rows = conn.execute(
        f"""
        SELECT DISTINCT ct.id, ct.amount_vnd, ct.billing_cycle
        FROM crm_contracts ct
        INNER JOIN crm_service_lifecycle lc ON lc.contract_id = ct.id
        LEFT JOIN crm_customers cu ON cu.id = lc.customer_id
        WHERE ct.billing_type = ?
          AND ct.status IN ('signed', 'active', 'expiring', 'renewed')
          AND lc.status = 'active'
          AND COALESCE(cu.is_placeholder, 0) = 0
          {am_clause}
        """,
        (BILLING_TYPE_RECURRING, *am_params),
    ).fetchall()
    mrr_bookings_vnd = sum(
        contract_amount_to_mrr_vnd(int(r["amount_vnd"] or 0), r["billing_cycle"])
        for r in contract_rows
    )
    active_recurring_contracts = len(contract_rows)
    arr_bookings_vnd = mrr_bookings_vnd * 12

    recv_row = conn.execute(
        f"""
        SELECT COALESCE(SUM(p.amount_vnd), 0)
        FROM crm_svc_payments p
        INNER JOIN crm_service_lifecycle lc ON lc.id = p.lifecycle_id
        INNER JOIN crm_contracts ct ON ct.id = lc.contract_id
        WHERE ct.billing_type = ?
          AND p.status = 'received'
          AND p.received_on LIKE ?
          {am_clause}
        """,
        (BILLING_TYPE_RECURRING, f"{month_str}%", *am_params),
    ).fetchone()
    mrr_cash_vnd = int(recv_row[0] if recv_row else 0)

    total_row = conn.execute(
        f"""
        SELECT COALESCE(SUM(p.amount_vnd), 0)
        FROM crm_svc_payments p
        INNER JOIN crm_service_lifecycle lc ON lc.id = p.lifecycle_id
        WHERE p.status = 'received' AND p.received_on LIKE ?
        {am_clause}
        """,
        (f"{month_str}%", *am_params),
    ).fetchone()
    total_received_vnd = int(total_row[0] if total_row else 0)

    recurring_revenue_share_pct = (
        round(mrr_cash_vnd / total_received_vnd * 100, 1)
        if total_received_vnd > 0
        else 0.0
    )

    return {
        "year": int(year),
        "month": int(month),
        "am_id": am_id,
        "mrr_bookings_vnd": mrr_bookings_vnd,
        "arr_bookings_vnd": arr_bookings_vnd,
        "mrr_cash_vnd": mrr_cash_vnd,
        "active_recurring_contracts": active_recurring_contracts,
        "total_received_vnd": total_received_vnd,
        "recurring_revenue_share_pct": recurring_revenue_share_pct,
        "definitions": {
            "mrr_bookings": "Tổng amount_vnd HĐ recurring active quy về MRR/tháng (billing_cycle)",
            "mrr_cash": "Thực thu recurring trong tháng",
            "arr": "MRR bookings × 12",
        },
    }


def get_exec_metrics(
    conn: sqlite3.Connection,
    *,
    year: int,
    month: int,
    am_id: int | None = None,
) -> dict[str, Any]:
    """Bundle CAC + on-time + MRR/ARR."""
    return {
        "year": int(year),
        "month": int(month),
        "cac": get_cac_metrics(conn, year=year, month=month),
        "delivery_ontime": get_delivery_ontime_metrics(conn, year=year, month=month),
        "mrr_arr": get_mrr_arr_metrics(conn, year=year, month=month, am_id=am_id),
    }
