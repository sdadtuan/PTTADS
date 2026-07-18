"""Dashboard tuần cho chủ doanh nghiệp — 4 khối + RAG + điều tra."""
from __future__ import annotations

import os
import sqlite3
from datetime import date, datetime, timedelta
from typing import Any

from crm_lead_kpi_metrics import LEAD_EXCLUDE_STATUSES, get_unified_lead_kpi_summary
from crm_sales_pipeline import STAGE_FOLLOWUP_HOURS, TERMINAL_STAGES, normalize_pipeline_stage
from crm_svc_exec_metrics import (
    get_cac_metrics_for_period,
    get_delivery_ontime_metrics_for_period,
)
from crm_svc_finance import (
    COST_PHASE_DELIVERY,
    COST_PHASE_PRESALES,
    get_ar_aging,
)
from crm_svc_finance_kpi import get_alert_thresholds
from crm_svc_portfolio import (
    get_concentration_metrics_for_period,
    get_portfolio_metrics,
)
from crm_owner_cash_ledger import (
    POSITION_SOURCE_LEDGER,
    build_cash_forecast_30d,
    cash_forecast_note,
    cash_position_note,
    get_cash_position,
    list_cash_snapshots,
)
from crm_svc_retention import get_retention_metrics, get_retention_metrics_for_period

RAG_GREEN = "green"
RAG_YELLOW = "yellow"
RAG_RED = "red"

RAG_LABELS: dict[str, str] = {
    RAG_GREEN: "Đạt / vượt target",
    RAG_YELLOW: "Lệch nhẹ — theo dõi sát",
    RAG_RED: "Cần xử lý trong 7 ngày",
}

BLOCK_KEYS = ("cash", "sales", "efficiency", "risk")
BLOCK_LABELS: dict[str, str] = {
    "cash": "Tiền",
    "sales": "Kinh doanh",
    "efficiency": "Hiệu quả",
    "risk": "Rủi ro",
}

OWNER_WEEKLY_TREND_WEEKS_DEFAULT = 8
OWNER_WEEKLY_TREND_WEEKS_MIN = 4
OWNER_WEEKLY_TREND_WEEKS_MAX = 12

METRIC_TREND_KEYS: dict[str, str] = {
    "cash_close": "cash_close_vnd",
    "cash_in": "cash_in_vnd",
    "ar_overdue": "ar_overdue_vnd",
    "revenue_actual": "revenue_vnd",
    "win_rate": "close_rate_pct",
}

OWNER_WEEKLY_TARGET_DEFAULTS: dict[str, float | int] = {
    "cash_safe_min_vnd": 50_000_000,
    "cash_forecast_min_vnd": 0,
    "ar_overdue_max_vnd": 30_000_000,
    "lead_new_target": 5,
    "lead_qualified_target": 3,
    "proposals_target": 2,
    "deals_closed_target": 1,
    "revenue_target_vnd": 20_000_000,
    "pipeline_next_min_vnd": 50_000_000,
    "gross_margin_target_pct": 30.0,
    "net_margin_target_pct": 15.0,
    "cac_max_vnd": 15_000_000,
    "roas_min": 3.0,
    "cycle_time_max_days": 45,
    "ontime_target_pct": 85.0,
    "close_rate_target_pct": 30.0,
    "bad_debt_min_vnd": 10_000_000,
    "bad_debt_min_days": 30,
    "late_projects_max": 0,
    "stuck_work_max": 3,
    "capacity_max_util_pct": 85.0,
    "top_deal_share_max_pct": 40.0,
    "top1_share_max_pct": 40.0,
    "churn_max_pct": 10.0,
    "win_rate_drop_warn_pct": 15.0,
    "win_rate_drop_critical_pct": 20.0,
}

OWNER_WEEKLY_ENV_KEYS: dict[str, str] = {
    k: f"PTT_OWNER_WEEKLY_{k.upper()}" for k in OWNER_WEEKLY_TARGET_DEFAULTS
}

OWNER_WEEKLY_TARGET_LABELS: dict[str, str] = {
    "cash_safe_min_vnd": "Tiền an toàn tối thiểu (VNĐ)",
    "cash_forecast_min_vnd": "Cash forecast 30 ngày tối thiểu (VNĐ)",
    "ar_overdue_max_vnd": "AR quá hạn tối đa (VNĐ)",
    "lead_new_target": "Lead mới / tuần",
    "lead_qualified_target": "Lead đủ chuẩn / tuần",
    "proposals_target": "Báo giá gửi / tuần",
    "deals_closed_target": "Deal chốt / tuần",
    "revenue_target_vnd": "Doanh thu tuần (VNĐ)",
    "pipeline_next_min_vnd": "Pipeline tối thiểu (VNĐ)",
    "gross_margin_target_pct": "Gross margin target (%)",
    "net_margin_target_pct": "Net margin target (%)",
    "cac_max_vnd": "CAC tối đa (VNĐ)",
    "roas_min": "ROAS tối thiểu",
    "cycle_time_max_days": "Cycle time tối đa (ngày)",
    "ontime_target_pct": "On-time delivery target (%)",
    "close_rate_target_pct": "Win rate target (%)",
    "bad_debt_min_vnd": "Nợ xấu tối thiểu / KH (VNĐ)",
    "bad_debt_min_days": "Nợ xấu — ngày quá hạn tối thiểu",
    "late_projects_max": "Dự án trễ tối đa",
    "stuck_work_max": "Đầu việc kẹt tối đa",
    "capacity_max_util_pct": "Utilization tối đa (%)",
    "top_deal_share_max_pct": "Deal phụ thuộc tối đa (%)",
    "top1_share_max_pct": "Top-1 DT tối đa (%)",
    "churn_max_pct": "Churn tối đa (%)",
    "win_rate_drop_warn_pct": "Win rate giảm — cảnh báo (%)",
    "win_rate_drop_critical_pct": "Win rate giảm — nghiêm trọng (%)",
}

OWNER_WEEKLY_TARGET_GROUPS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("cash", "Tiền", ("cash_safe_min_vnd", "cash_forecast_min_vnd", "ar_overdue_max_vnd", "revenue_target_vnd")),
    (
        "sales",
        "Kinh doanh",
        ("lead_new_target", "lead_qualified_target", "proposals_target", "deals_closed_target", "pipeline_next_min_vnd", "close_rate_target_pct"),
    ),
    (
        "efficiency",
        "Hiệu quả",
        ("gross_margin_target_pct", "net_margin_target_pct", "cac_max_vnd", "roas_min", "cycle_time_max_days", "ontime_target_pct"),
    ),
    (
        "risk",
        "Rủi ro",
        (
            "bad_debt_min_vnd",
            "bad_debt_min_days",
            "late_projects_max",
            "stuck_work_max",
            "capacity_max_util_pct",
            "top_deal_share_max_pct",
            "top1_share_max_pct",
            "churn_max_pct",
            "win_rate_drop_warn_pct",
            "win_rate_drop_critical_pct",
        ),
    ),
)


def _parse_ymd(text: str | None) -> date | None:
    raw = str(text or "").strip()[:10]
    if len(raw) != 10:
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return None


def _parse_ts_datetime(text: str | None) -> datetime | None:
    raw = str(text or "").strip()
    if not raw:
        return None
    for fmt, length in (("%Y-%m-%d %H:%M:%S", 19), ("%Y-%m-%d", 10)):
        try:
            return datetime.strptime(raw[:length], fmt)
        except ValueError:
            continue
    d = _parse_ymd(raw)
    return datetime.combine(d, datetime.min.time()) if d else None


def _parse_ts_date(text: str | None) -> date | None:
    dt = _parse_ts_datetime(text)
    return dt.date() if dt else None


def _env_number(name: str, default: float | int) -> float | int:
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return default
    try:
        if isinstance(default, int):
            return max(0, int(raw))
        return float(raw)
    except ValueError:
        return default


def get_owner_weekly_targets(conn: sqlite3.Connection) -> dict[str, float | int]:
    """Ngưỡng target/RAG — DB ưu tiên, fallback env, rồi default."""
    from crm_svc_finance_kpi import ensure_kpi_config_schema

    ensure_kpi_config_schema(conn)
    db_rows = {
        str(r["config_key"]).replace("owner_", "", 1): str(r["config_value"])
        for r in conn.execute(
            """
            SELECT config_key, config_value FROM crm_finance_kpi_config
            WHERE config_key LIKE 'owner_%'
            """
        ).fetchall()
    }
    out: dict[str, float | int] = {}
    for key, default in OWNER_WEEKLY_TARGET_DEFAULTS.items():
        if key in db_rows:
            raw = db_rows[key].strip()
            try:
                out[key] = int(raw) if isinstance(default, int) else float(raw)
                continue
            except ValueError:
                pass
        env_key = OWNER_WEEKLY_ENV_KEYS.get(key, "")
        out[key] = _env_number(env_key, default) if env_key else default
    return out


def set_owner_weekly_targets(
    conn: sqlite3.Connection, updates: dict[str, Any]
) -> dict[str, float | int]:
    """Lưu target tuần vào crm_finance_kpi_config (prefix owner_)."""
    from crm_svc_finance_kpi import ensure_kpi_config_schema

    ensure_kpi_config_schema(conn)
    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    for key, value in updates.items():
        if key not in OWNER_WEEKLY_TARGET_DEFAULTS:
            continue
        default = OWNER_WEEKLY_TARGET_DEFAULTS[key]
        if isinstance(default, int):
            val = max(0, int(value))
        else:
            val = float(value)
        conn.execute(
            """
            INSERT INTO crm_finance_kpi_config (config_key, config_value, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(config_key) DO UPDATE SET
                config_value = excluded.config_value,
                updated_at = excluded.updated_at
            """,
            (f"owner_{key}", str(val), ts),
        )
    conn.commit()
    return get_owner_weekly_targets(conn)


def resolve_week_bounds(
    *,
    week_end: date | None = None,
    year: int | None = None,
    iso_week: int | None = None,
) -> tuple[date, date, int, int]:
    """
    Tuần ISO Thứ 2 → Chủ nhật.
    Mặc định: tuần trước (đã kết thúc Chủ nhật gần nhất).
    """
    if year is not None and iso_week is not None:
        start = date.fromisocalendar(int(year), int(iso_week), 1)
        end = date.fromisocalendar(int(year), int(iso_week), 7)
        return start, end, int(year), int(iso_week)

    if week_end is not None:
        end = week_end
    else:
        today = date.today()
        days_since_monday = today.weekday()
        this_monday = today - timedelta(days=days_since_monday)
        end = this_monday - timedelta(days=1)
    start = end - timedelta(days=6)
    iso = start.isocalendar()
    return start, end, int(iso[0]), int(iso[1])


def _date_in_range(d: date | None, start: date, end: date) -> bool:
    return d is not None and start <= d <= end


def _sum_received(conn: sqlite3.Connection, start: date, end: date) -> int:
    row = conn.execute(
        """
        SELECT COALESCE(SUM(amount_vnd), 0)
        FROM crm_svc_payments
        WHERE status = 'received'
          AND substr(received_on, 1, 10) >= ?
          AND substr(received_on, 1, 10) <= ?
        """,
        (start.isoformat(), end.isoformat()),
    ).fetchone()
    return int(row[0] if row else 0)


def _sum_expenses(conn: sqlite3.Connection, start: date, end: date, *, phase: str | None = None) -> int:
    where = [
        "substr(expense_on, 1, 10) >= ?",
        "substr(expense_on, 1, 10) <= ?",
    ]
    params: list[Any] = [start.isoformat(), end.isoformat()]
    if phase:
        where.append("COALESCE(cost_phase, 'delivery') = ?")
        params.append(phase)
    row = conn.execute(
        f"SELECT COALESCE(SUM(amount_vnd), 0) FROM crm_svc_expenses WHERE {' AND '.join(where)}",
        params,
    ).fetchone()
    return int(row[0] if row else 0)


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name = ?",
        (name,),
    ).fetchone()
    return row is not None


def _count_leads_created(conn: sqlite3.Connection, start: date, end: date) -> int:
    if not _table_exists(conn, "crm_leads"):
        return 0
    excl = sorted(LEAD_EXCLUDE_STATUSES)
    row = conn.execute(
        f"""
        SELECT COUNT(*) FROM crm_leads
        WHERE COALESCE(is_duplicate, 0) = 0
          AND status NOT IN ({','.join('?' * len(excl))})
          AND substr(replace(trim(created_at), 'T', ' '), 1, 10) >= ?
          AND substr(replace(trim(created_at), 'T', ' '), 1, 10) <= ?
        """,
        [*excl, start.isoformat(), end.isoformat()],
    ).fetchone()
    return int(row[0] if row else 0)


def _count_qualified_in_week(conn: sqlite3.Connection, start: date, end: date) -> int:
    try:
        summary = get_unified_lead_kpi_summary(
            conn,
            period_start=start,
            period_end=end,
            period_cohort=True,
        )
        return int(summary.get("qualified_in_cohort") or 0)
    except sqlite3.OperationalError:
        return 0


def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    if not _table_exists(conn, table):
        return set()
    return {str(r[1]) for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def _count_proposals_sent(conn: sqlite3.Connection, start: date, end: date) -> int:
    """Đếm báo giá gửi trong tuần — dedupe theo customer (proposal + case bao_gia)."""
    seen: set[str] = set()

    if _table_exists(conn, "crm_proposals"):
        rows = conn.execute(
            """
            SELECT id, customer_id
            FROM crm_proposals
            WHERE substr(replace(trim(created_at), 'T', ' '), 1, 10) >= ?
              AND substr(replace(trim(created_at), 'T', ' '), 1, 10) <= ?
            """,
            (start.isoformat(), end.isoformat()),
        ).fetchall()
        for row in rows:
            cid = row["customer_id"]
            key = f"c:{int(cid)}" if cid is not None else f"p:{int(row['id'])}"
            seen.add(key)

    if _table_exists(conn, "crm_cases"):
        case_cols = _table_columns(conn, "crm_cases")
        select_cols = "id, customer_id" if "customer_id" in case_cols else "id"
        rows = conn.execute(
            f"""
            SELECT {select_cols}
            FROM crm_cases
            WHERE COALESCE(pipeline_stage, 'moi') = 'bao_gia'
              AND substr(replace(trim(stage_entered_at), 'T', ' '), 1, 10) >= ?
              AND substr(replace(trim(stage_entered_at), 'T', ' '), 1, 10) <= ?
            """,
            (start.isoformat(), end.isoformat()),
        ).fetchall()
        for row in rows:
            if "customer_id" in case_cols and row["customer_id"] is not None:
                key = f"c:{int(row['customer_id'])}"
            else:
                key = f"case:{int(row['id'])}"
            seen.add(key)

    return len(seen)


def _count_deals_closed(conn: sqlite3.Connection, start: date, end: date) -> int:
    total = 0
    if _table_exists(conn, "crm_cases"):
        row = conn.execute(
            """
            SELECT COUNT(*) FROM crm_cases
            WHERE COALESCE(pipeline_stage, 'moi') = 'chot'
              AND substr(replace(trim(stage_entered_at), 'T', ' '), 1, 10) >= ?
              AND substr(replace(trim(stage_entered_at), 'T', ' '), 1, 10) <= ?
            """,
            (start.isoformat(), end.isoformat()),
        ).fetchone()
        total += int(row[0] if row else 0)
    return total


def _pipeline_next_week_vnd(conn: sqlite3.Connection, week_end: date) -> tuple[int, int]:
    """Pipeline SQL/báo giá có follow-up due trong tuần ISO kế tiếp."""
    if not _table_exists(conn, "crm_cases"):
        return 0, 0
    next_start = week_end + timedelta(days=1)
    next_end = next_start + timedelta(days=6)
    open_stages = ("sql", "bao_gia")
    placeholders = ",".join("?" * len(open_stages))
    rows = conn.execute(
        f"""
        SELECT id, pipeline_stage, stage_entered_at, created_at, deal_value_vnd
        FROM crm_cases
        WHERE COALESCE(pipeline_stage, 'moi') IN ({placeholders})
        """,
        open_stages,
    ).fetchall()
    total = 0
    count = 0
    for row in rows:
        stage = normalize_pipeline_stage(str(row["pipeline_stage"] or ""))
        entered = _parse_ts_datetime(str(row["stage_entered_at"] or row["created_at"] or ""))
        if entered is None:
            continue
        follow_hours = int(STAGE_FOLLOWUP_HOURS.get(stage, 72))
        follow_due = entered + timedelta(hours=follow_hours)
        if not (next_start <= follow_due.date() <= next_end):
            continue
        total += int(row["deal_value_vnd"] or 0)
        count += 1
    return total, count


def _avg_cycle_time_days(conn: sqlite3.Connection, start: date, end: date) -> float | None:
    if not _table_exists(conn, "crm_cases"):
        return None
    rows = conn.execute(
        """
        SELECT created_at, stage_entered_at FROM crm_cases
        WHERE COALESCE(pipeline_stage, 'moi') = 'chot'
        """
    ).fetchall()
    durations: list[int] = []
    for row in rows:
        closed = _parse_ts_date(str(row["stage_entered_at"] or ""))
        created = _parse_ts_date(str(row["created_at"] or ""))
        if not _date_in_range(closed, start, end) or created is None or closed is None:
            continue
        durations.append(max(0, (closed - created).days))
    if not durations:
        return None
    return round(sum(durations) / len(durations), 1)


def _count_bad_debt_customers(
    conn: sqlite3.Connection, as_of: date, *, min_vnd: int, min_days: int
) -> int:
    ar = get_ar_aging(conn, as_of=as_of.isoformat())
    by_customer: dict[str, int] = {}
    for item in ar.get("items") or []:
        if int(item.get("days_overdue") or 0) < min_days:
            continue
        name = str(item.get("customer_name") or "—")
        by_customer[name] = by_customer.get(name, 0) + int(item.get("amount_vnd") or 0)
    return sum(1 for amt in by_customer.values() if amt >= min_vnd)


def _count_late_projects(conn: sqlite3.Connection) -> int:
    if not _table_exists(conn, "crm_svc_tasks"):
        return 0
    today = date.today().isoformat()
    row = conn.execute(
        """
        SELECT COUNT(DISTINCT t.lifecycle_id)
        FROM crm_svc_tasks t
        INNER JOIN crm_service_lifecycle lc ON lc.id = t.lifecycle_id
        WHERE t.stage IN ('deliver', 'handover')
          AND COALESCE(t.is_done, 0) = 0
          AND lc.status = 'active'
          AND COALESCE(t.due_on, '') != ''
          AND substr(t.due_on, 1, 10) < ?
        """,
        (today,),
    ).fetchone()
    return int(row[0] if row else 0)


def _count_stuck_work(conn: sqlite3.Connection) -> int:
    from crm_sales_pipeline import is_sla_overdue

    stuck = 0
    if _table_exists(conn, "crm_cases"):
        rows = conn.execute(
            """
            SELECT pipeline_stage, stage_entered_at FROM crm_cases
            WHERE COALESCE(pipeline_stage, 'moi') NOT IN ('chot', 'mat')
            """
        ).fetchall()
        for row in rows:
            stage = normalize_pipeline_stage(row["pipeline_stage"])
            if stage in TERMINAL_STAGES:
                continue
            if is_sla_overdue(stage, str(row["stage_entered_at"] or "")):
                stuck += 1
    if _table_exists(conn, "crm_leads"):
        from crm_lead_store import is_sla_overdue as lead_sla_overdue

        rows = conn.execute(
            """
            SELECT status, status_entered_at FROM crm_leads
            WHERE COALESCE(is_duplicate, 0) = 0
              AND status NOT IN ('won', 'lost', 'junk', 'spam')
            """
        ).fetchall()
        for row in rows:
            if lead_sla_overdue(str(row["status"] or ""), str(row["status_entered_at"] or "")):
                stuck += 1
    return stuck


def _top_deal_dependency_pct(conn: sqlite3.Connection) -> float:
    if not _table_exists(conn, "crm_cases"):
        return 0.0
    rows = conn.execute(
        """
        SELECT COALESCE(deal_value_vnd, 0) AS dv FROM crm_cases
        WHERE COALESCE(pipeline_stage, 'moi') NOT IN ('chot', 'mat')
          AND COALESCE(deal_value_vnd, 0) > 0
        ORDER BY dv DESC
        """
    ).fetchall()
    values = [int(r[0] or 0) for r in rows]
    total = sum(values)
    if total <= 0 or not values:
        return 0.0
    return round(values[0] / total * 100, 1)


def _metric(
    *,
    key: str,
    label: str,
    value: Any,
    fmt: str = "vnd",
    status: str = RAG_GREEN,
    target: Any = None,
    prior_value: Any = None,
    hint: str = "",
    investigate: dict[str, Any] | None = None,
    note: str = "",
    drill_url: str = "",
    trend_values: list[float | int] | None = None,
) -> dict[str, Any]:
    delta_pct: float | None = None
    if prior_value is not None and isinstance(value, (int, float)) and isinstance(prior_value, (int, float)):
        if prior_value != 0:
            delta_pct = round((float(value) - float(prior_value)) / abs(float(prior_value)) * 100, 1)
        elif value:
            delta_pct = 100.0
    return {
        "key": key,
        "label": label,
        "value": value,
        "format": fmt,
        "status": status,
        "status_label": RAG_LABELS.get(status, status),
        "target": target,
        "prior_value": prior_value,
        "delta_pct": delta_pct,
        "hint": hint,
        "investigate": investigate or None,
        "note": note,
        "drill_url": drill_url or None,
        "trend_values": trend_values or None,
    }


def _investigate(title: str, steps: list[str], links: list[dict[str, str]] | None = None) -> dict[str, Any]:
    return {
        "title": title,
        "steps": steps,
        "links": links or [],
    }


def _rag_higher_better(
    value: float | int,
    target: float | int,
    *,
    yellow_ratio: float = 0.85,
) -> str:
    if value >= target:
        return RAG_GREEN
    if value >= target * yellow_ratio:
        return RAG_YELLOW
    return RAG_RED


def _rag_lower_better(
    value: float | int,
    max_ok: float | int,
    *,
    yellow_ratio: float = 1.15,
) -> str:
    if value <= max_ok:
        return RAG_GREEN
    if value <= max_ok * yellow_ratio:
        return RAG_YELLOW
    return RAG_RED


def _rag_trend_worse(
    current: float | int,
    prior: float | int | None,
    *,
    increase_red_weeks: int = 2,
    prior_prior: float | int | None = None,
) -> str:
    if prior is None:
        return RAG_GREEN
    if current <= prior:
        return RAG_GREEN
    if prior_prior is not None and current > prior > prior_prior:
        return RAG_RED
    if current > prior * 1.1:
        return RAG_YELLOW
    return RAG_GREEN


def _metric_drill_url(
    key: str,
    *,
    iso_year: int,
    iso_week: int,
    month_year: int,
    month_num: int,
) -> str:
    fin = f"/crm/financials?year={month_year}&month={month_num}"
    biz = f"/crm/business-dashboard?year={month_year}&month={month_num}"
    weekly = f"/crm/owner-weekly?year={iso_year}&week={iso_week}"
    urls: dict[str, str] = {
        "cash_open": fin,
        "cash_close": fin,
        "cash_in": fin,
        "cash_out": fin,
        "ar_overdue": fin,
        "cash_forecast_30d": weekly,
        "leads_new": "/crm/leads",
        "leads_qualified": "/crm/leads",
        "proposals_sent": "/crm/proposals",
        "deals_closed": "/crm/sales",
        "revenue_actual": fin,
        "pipeline_next": "/crm/sales",
        "gross_margin": biz,
        "net_margin": biz,
        "cac": biz,
        "roas": biz,
        "cycle_time": "/crm/sales",
        "ontime_delivery": "/crm/service-delivery",
        "bad_debt_customers": fin,
        "late_projects": "/crm/service-delivery",
        "stuck_work": "/crm/hub",
        "staff_shortage": "/crm/service-delivery",
        "deal_dependency": "/crm/sales",
        "top_customer_share": biz,
        "win_rate": "/crm/leads",
        "churn": biz,
    }
    return urls.get(key, "")


def get_owner_weekly_trends(
    conn: sqlite3.Connection,
    *,
    week_end: date,
    weeks: int = OWNER_WEEKLY_TREND_WEEKS_DEFAULT,
) -> dict[str, Any]:
    """Trend 4–12 tuần gần nhất (sparkline trên dashboard)."""
    n = max(OWNER_WEEKLY_TREND_WEEKS_MIN, min(OWNER_WEEKLY_TREND_WEEKS_MAX, int(weeks)))
    labels: list[str] = []
    cash_close_vnd: list[int] = []
    cash_in_vnd: list[int] = []
    ar_overdue_vnd: list[int] = []
    revenue_vnd: list[int] = []
    close_rate_pct: list[float] = []

    for offset in range(n - 1, -1, -1):
        end = week_end - timedelta(days=7 * offset)
        start = end - timedelta(days=6)
        iso = end.isocalendar()
        labels.append(f"W{iso[1]}")
        cash_close_vnd.append(int(get_cash_position(conn, end)["position_vnd"]))
        week_in = _sum_received(conn, start, end)
        cash_in_vnd.append(week_in)
        revenue_vnd.append(week_in)
        try:
            ar = get_ar_aging(conn, as_of=end.isoformat())
            ar_overdue_vnd.append(int(ar.get("total_overdue_vnd") or 0))
        except sqlite3.OperationalError:
            ar_overdue_vnd.append(0)
        try:
            lk = get_unified_lead_kpi_summary(
                conn, period_start=start, period_end=end, period_cohort=True
            )
            close_rate_pct.append(float(lk.get("cohort_close_rate_pct") or 0))
        except sqlite3.OperationalError:
            close_rate_pct.append(0.0)

    return {
        "weeks": n,
        "labels": labels,
        "cash_close_vnd": cash_close_vnd,
        "cash_in_vnd": cash_in_vnd,
        "ar_overdue_vnd": ar_overdue_vnd,
        "revenue_vnd": revenue_vnd,
        "close_rate_pct": close_rate_pct,
    }


def _trend_for_metric(trends: dict[str, Any], metric_key: str) -> list[float | int] | None:
    trend_key = METRIC_TREND_KEYS.get(metric_key)
    if not trend_key:
        return None
    values = trends.get(trend_key)
    return list(values) if values else None


def build_pre_execution_brief(dashboard: dict[str, Any]) -> dict[str, Any]:
    """Phân tích trước khi thực thi — tổng hợp chỉ số vàng/đỏ."""
    actions: list[dict[str, Any]] = []
    for block_key in BLOCK_KEYS:
        block = dashboard["blocks"].get(block_key) or {}
        for m in block.get("metrics") or []:
            st = str(m.get("status") or RAG_GREEN)
            if st not in (RAG_YELLOW, RAG_RED):
                continue
            inv = m.get("investigate") or {}
            actions.append(
                {
                    "block": block_key,
                    "block_label": BLOCK_LABELS.get(block_key, block_key),
                    "metric_key": m.get("key"),
                    "metric_label": m.get("label"),
                    "status": st,
                    "status_label": m.get("status_label"),
                    "hint": m.get("hint") or "",
                    "investigate_title": inv.get("title") or "Mở rộng điều tra",
                    "steps": inv.get("steps") or [],
                    "links": inv.get("links") or [],
                }
            )
    actions.sort(key=lambda a: (0 if a["status"] == RAG_RED else 1, a["block"]))
    red = sum(1 for a in actions if a["status"] == RAG_RED)
    yellow = sum(1 for a in actions if a["status"] == RAG_YELLOW)
    return {
        "title": "Phân tích trước khi thực thi",
        "subtitle": "Xử lý các chỉ số đỏ/vàng trước khi cam kết kế hoạch tuần tới.",
        "red_count": red,
        "yellow_count": yellow,
        "action_count": len(actions),
        "actions": actions,
    }


def get_owner_weekly_dashboard(
    conn: sqlite3.Connection,
    *,
    week_end: date | None = None,
    year: int | None = None,
    iso_week: int | None = None,
    trend_weeks: int = OWNER_WEEKLY_TREND_WEEKS_DEFAULT,
) -> dict[str, Any]:
    """Dashboard tuần 4 khối + RAG + brief điều tra."""
    start, end, iso_year, iso_week_num = resolve_week_bounds(
        week_end=week_end, year=year, iso_week=iso_week
    )
    prior_end = start - timedelta(days=1)
    prior_start = prior_end - timedelta(days=6)

    targets = get_owner_weekly_targets(conn)
    kpi_thresholds = get_alert_thresholds(conn)

    cash_open_meta = get_cash_position(conn, start - timedelta(days=1))
    cash_close_meta = get_cash_position(conn, end)
    cash_open = int(cash_open_meta["position_vnd"])
    cash_close = int(cash_close_meta["position_vnd"])
    cash_position_source = str(cash_close_meta.get("source") or "")
    cash_in = _sum_received(conn, start, end)
    cash_out = _sum_expenses(conn, start, end)
    prior_cash_in = _sum_received(conn, prior_start, prior_end)
    prior_cash_out = _sum_expenses(conn, prior_start, prior_end)

    ar = get_ar_aging(conn, as_of=end.isoformat())
    ar_prior = get_ar_aging(conn, as_of=prior_end.isoformat())
    ar_prior2_end = prior_start - timedelta(days=1)
    ar_prior2 = get_ar_aging(conn, as_of=ar_prior2_end.isoformat())

    forecast_meta = build_cash_forecast_30d(conn, end, current_position=cash_close)
    forecast_30 = int(forecast_meta["forecast_vnd"])
    cash_snapshots = list_cash_snapshots(conn, limit=8)

    lead_new = _count_leads_created(conn, start, end)
    lead_qualified = _count_qualified_in_week(conn, start, end)
    proposals = _count_proposals_sent(conn, start, end)
    deals_closed = _count_deals_closed(conn, start, end)
    revenue = cash_in
    pipeline_vnd, pipeline_count = _pipeline_next_week_vnd(conn, end)
    next_iso = (end + timedelta(days=1)).isocalendar()
    pipeline_note = (
        f"{pipeline_count} deal · follow-up due tuần {next_iso[1]}/{next_iso[0]}."
    )

    recv_week = cash_in
    del_week = _sum_expenses(conn, start, end, phase=COST_PHASE_DELIVERY)
    presales_week = _sum_expenses(conn, start, end, phase=COST_PHASE_PRESALES)
    gross_margin = round((recv_week - del_week) / recv_week * 100, 1) if recv_week > 0 else 0.0
    net_margin = (
        round((recv_week - del_week - presales_week) / recv_week * 100, 1)
        if recv_week > 0
        else 0.0
    )

    cac = get_cac_metrics_for_period(conn, period_start=start, period_end=end)
    marketing_week = int(cac.get("marketing_cost_vnd") or 0)
    roas = round(revenue / marketing_week, 2) if marketing_week > 0 else None

    cycle_time = _avg_cycle_time_days(conn, start, end)
    ontime = get_delivery_ontime_metrics_for_period(
        conn, period_start=start, period_end=end
    )
    ontime_pct = float(ontime.get("on_time_rate_pct") or 0)

    lead_kpi = get_unified_lead_kpi_summary(
        conn, period_start=start, period_end=end, period_cohort=True
    )
    close_rate = float(lead_kpi.get("cohort_close_rate_pct") or 0)
    prior_lead_kpi = get_unified_lead_kpi_summary(
        conn, period_start=prior_start, period_end=prior_end, period_cohort=True
    )
    prior_close_rate = float(prior_lead_kpi.get("cohort_close_rate_pct") or 0)

    month_year, month_num = end.year, end.month
    weekly_retention = get_retention_metrics_for_period(
        conn, period_start=start, period_end=end
    )
    churn_pct = float(weekly_retention.get("customer_churn_pct") or 0)
    retention = get_retention_metrics(conn, year=month_year, month=month_num)
    churn_month_pct = float(retention.get("customer_churn_pct") or 0)

    trends = get_owner_weekly_trends(conn, week_end=end, weeks=trend_weeks)

    conc = get_concentration_metrics_for_period(
        conn, period_start=start, period_end=end
    )
    portfolio = get_portfolio_metrics(conn, year=month_year, month=month_num)
    capacity_util = float((portfolio.get("capacity") or {}).get("combined_utilization_pct") or 0)

    bad_debt = _count_bad_debt_customers(
        conn,
        end,
        min_vnd=int(targets["bad_debt_min_vnd"]),
        min_days=int(targets["bad_debt_min_days"]),
    )
    late_projects = _count_late_projects(conn)
    stuck = _count_stuck_work(conn)
    top_deal_pct = _top_deal_dependency_pct(conn)
    top1_share = float(conc.get("top1_share_pct") or 0)

    safe_min = int(targets["cash_safe_min_vnd"])
    cash_close_status = RAG_RED if cash_close < safe_min else RAG_GREEN
    if cash_close < safe_min * 1.2 and cash_close >= safe_min:
        cash_close_status = RAG_YELLOW

    ar_status = _rag_trend_worse(
        int(ar.get("total_overdue_vnd") or 0),
        int(ar_prior.get("total_overdue_vnd") or 0),
        prior_prior=int(ar_prior2.get("total_overdue_vnd") or 0),
    )
    if int(ar.get("total_overdue_vnd") or 0) >= int(kpi_thresholds.get("ar_overdue_critical_vnd", 50_000_000)):
        ar_status = RAG_RED

    forecast_status = _rag_higher_better(forecast_30, int(targets["cash_forecast_min_vnd"]))

    win_drop = prior_close_rate - close_rate if prior_close_rate > 0 else 0
    win_status = RAG_GREEN
    if win_drop >= float(targets["win_rate_drop_critical_pct"]):
        win_status = RAG_RED
    elif win_drop >= float(targets["win_rate_drop_warn_pct"]):
        win_status = RAG_YELLOW
    elif close_rate < float(targets["close_rate_target_pct"]):
        win_status = _rag_higher_better(close_rate, float(targets["close_rate_target_pct"]))

    churn_status = RAG_RED if churn_pct > float(targets["churn_max_pct"]) else (
        RAG_YELLOW if churn_pct > float(targets["churn_max_pct"]) * 0.8 else RAG_GREEN
    )

    fin_links = [
        {"label": "Chi tiết tài chính", "url": f"/crm/financials?year={month_year}&month={month_num}"},
        {"label": "Business Dashboard", "url": f"/crm/business-dashboard?year={month_year}&month={month_num}"},
    ]
    sales_links = [
        {"label": "Kinh doanh / Pipeline", "url": "/crm/sales"},
        {"label": "Quản lý Lead", "url": "/crm/leads"},
    ]
    risk_links = fin_links + [{"label": "Hub nhắc việc", "url": "/crm/hub"}]

    cash_metrics = [
        _metric(
            key="cash_open",
            label="Tiền đầu tuần",
            value=cash_open,
            fmt="vnd",
            status=RAG_RED if cash_open < safe_min else RAG_GREEN,
            target=safe_min,
            hint="Số dư cuối ngày trước tuần — từ sổ quỹ hoặc proxy thu−chi lũy kế.",
            note=cash_position_note(cash_open_meta),
            investigate=_investigate(
                "Kiểm tra nguồn tiền đầu tuần",
                [
                    "Đối chiếu số dư ngân hàng thực tế với proxy CRM.",
                    "Liệt kê khoản thu pending sắp vào trong 7 ngày.",
                ],
                fin_links,
            )
            if cash_open < safe_min
            else None,
        ),
        _metric(
            key="cash_close",
            label="Tiền cuối tuần",
            value=cash_close,
            fmt="vnd",
            status=cash_close_status,
            target=safe_min,
            prior_value=int(get_cash_position(conn, prior_end)["position_vnd"]),
            note=cash_position_note(cash_close_meta),
            investigate=_investigate(
                "Cash dưới ngưỡng an toàn",
                [
                    "Dừng chi không thiết yếu; ưu tiên thu AR quá hạn.",
                    "Lập kế hoạch thu trong 7 ngày theo từng KH.",
                ],
                fin_links,
            )
            if cash_close_status != RAG_GREEN
            else None,
        ),
        _metric(
            key="cash_in",
            label="Tiền vào",
            value=cash_in,
            fmt="vnd",
            status=_rag_higher_better(cash_in, int(targets["revenue_target_vnd"]), yellow_ratio=0.7),
            target=int(targets["revenue_target_vnd"]),
            prior_value=prior_cash_in,
        ),
        _metric(
            key="cash_out",
            label="Tiền ra",
            value=cash_out,
            fmt="vnd",
            status=_rag_lower_better(cash_out, prior_cash_out or cash_out, yellow_ratio=1.2)
            if prior_cash_out
            else RAG_GREEN,
            prior_value=prior_cash_out,
        ),
        _metric(
            key="ar_overdue",
            label="Công nợ quá hạn",
            value=int(ar.get("total_overdue_vnd") or 0),
            fmt="vnd",
            status=ar_status,
            target=int(targets["ar_overdue_max_vnd"]),
            prior_value=int(ar_prior.get("total_overdue_vnd") or 0),
            investigate=_investigate(
                "AR quá hạn tăng liên tiếp",
                [
                    "Gọi top 3 KH nợ lớn nhất trong 48h.",
                    "Chốt lịch thu / cơ cấu nợ cho từng khoản > ngưỡng.",
                ],
                fin_links,
            )
            if ar_status != RAG_GREEN
            else None,
        ),
        _metric(
            key="cash_forecast_30d",
            label="Cash forecast 30 ngày",
            value=forecast_30,
            fmt="vnd",
            status=forecast_status,
            target=int(targets["cash_forecast_min_vnd"]),
            note=cash_forecast_note(forecast_meta),
            investigate=_investigate(
                "Dự báo cash âm / thấp",
                [
                    "Scenario thu chậm 2 tuần vs kế hoạch.",
                    "Cắt/giãn chi presales & delivery không gắn deal chốt.",
                ],
                fin_links,
            )
            if forecast_status != RAG_GREEN
            else None,
        ),
    ]

    sales_metrics = [
        _metric(
            key="leads_new",
            label="Lead mới",
            value=lead_new,
            fmt="count",
            status=_rag_higher_better(lead_new, int(targets["lead_new_target"])),
            target=int(targets["lead_new_target"]),
        ),
        _metric(
            key="leads_qualified",
            label="Lead đủ chuẩn",
            value=lead_qualified,
            fmt="count",
            status=_rag_higher_better(lead_qualified, int(targets["lead_qualified_target"])),
            target=int(targets["lead_qualified_target"]),
        ),
        _metric(
            key="proposals_sent",
            label="Báo giá gửi đi",
            value=proposals,
            fmt="count",
            status=_rag_higher_better(proposals, int(targets["proposals_target"])),
            target=int(targets["proposals_target"]),
            note="Dedupe theo KH (proposal + case báo giá).",
        ),
        _metric(
            key="deals_closed",
            label="Deal chốt",
            value=deals_closed,
            fmt="count",
            status=_rag_higher_better(deals_closed, int(targets["deals_closed_target"])),
            target=int(targets["deals_closed_target"]),
        ),
        _metric(
            key="revenue_actual",
            label="Doanh thu thực",
            value=revenue,
            fmt="vnd",
            status=_rag_higher_better(revenue, int(targets["revenue_target_vnd"]), yellow_ratio=0.7),
            target=int(targets["revenue_target_vnd"]),
        ),
        _metric(
            key="pipeline_next",
            label="Pipeline tuần tới",
            value=pipeline_vnd,
            fmt="vnd",
            status=_rag_higher_better(pipeline_vnd, int(targets["pipeline_next_min_vnd"]), yellow_ratio=0.6),
            target=int(targets["pipeline_next_min_vnd"]),
            note=pipeline_note,
            investigate=_investigate(
                "Pipeline mỏng",
                [
                    "Review deal SQL/báo giá — next step trong 72h.",
                    "Bổ sung lead MQL từ kênh đang hiệu quả.",
                ],
                sales_links,
            )
            if pipeline_vnd < int(targets["pipeline_next_min_vnd"])
            else None,
        ),
    ]

    efficiency_metrics = [
        _metric(
            key="gross_margin",
            label="Gross margin",
            value=gross_margin,
            fmt="pct",
            status=_rag_higher_better(gross_margin, float(targets["gross_margin_target_pct"])),
            target=float(targets["gross_margin_target_pct"]),
        ),
        _metric(
            key="net_margin",
            label="Net margin",
            value=net_margin,
            fmt="pct",
            status=_rag_higher_better(net_margin, float(targets["net_margin_target_pct"])),
            target=float(targets["net_margin_target_pct"]),
            note="Tuần: sau chi delivery + presales.",
        ),
        _metric(
            key="cac",
            label="CAC",
            value=int(cac.get("cac_vnd") or 0),
            fmt="vnd",
            status=_rag_lower_better(int(cac.get("cac_vnd") or 0), int(targets["cac_max_vnd"])),
            target=int(targets["cac_max_vnd"]),
        ),
        _metric(
            key="roas",
            label="ROAS",
            value=roas if roas is not None else 0,
            fmt="ratio",
            status=_rag_higher_better(roas or 0, float(targets["roas_min"])) if roas is not None else RAG_YELLOW,
            target=float(targets["roas_min"]),
            note="Tuần: DT thực / marketing prorate theo ngày." if roas is not None else "Cần nhập marketing spend tháng.",
        ),
        _metric(
            key="cycle_time",
            label="Cycle time",
            value=cycle_time if cycle_time is not None else 0,
            fmt="days",
            status=_rag_lower_better(cycle_time or 0, float(targets["cycle_time_max_days"]))
            if cycle_time is not None
            else RAG_YELLOW,
            target=float(targets["cycle_time_max_days"]),
            note="TB ngày tạo → chốt deal trong tuần." if cycle_time is not None else "Chưa có deal chốt tuần này.",
        ),
        _metric(
            key="on_time_delivery",
            label="On-time delivery",
            value=ontime_pct,
            fmt="pct",
            status=_rag_higher_better(ontime_pct, float(targets["ontime_target_pct"])),
            target=float(targets["ontime_target_pct"]),
            note="Task deliver/handover hoàn thành trong tuần.",
            investigate=_investigate(
                "Giao hàng trễ",
                [
                    "Escalate task deliver/handover quá hạn.",
                    "Phân bổ lại SP/AM trên lifecycle trễ.",
                ],
                [{"label": "SOP tasks", "url": "/crm/sop"}],
            )
            if ontime_pct < float(targets["ontime_target_pct"])
            else None,
        ),
    ]

    risk_metrics = [
        _metric(
            key="bad_debt_customers",
            label="Khách nợ xấu",
            value=bad_debt,
            fmt="count",
            status=RAG_RED if bad_debt > 0 else RAG_GREEN,
            investigate=_investigate(
                "Khách nợ xấu",
                ["Chốt phương án thu hồi / cắt dịch vụ.", "Cập nhật provisioning trên Hub."],
                risk_links,
            )
            if bad_debt > 0
            else None,
        ),
        _metric(
            key="late_projects",
            label="Dự án trễ",
            value=late_projects,
            fmt="count",
            status=_rag_lower_better(late_projects, int(targets["late_projects_max"]), yellow_ratio=1.0),
            target=int(targets["late_projects_max"]),
        ),
        _metric(
            key="stuck_work",
            label="Đầu việc kẹt",
            value=stuck,
            fmt="count",
            status=_rag_lower_better(stuck, int(targets["stuck_work_max"])),
            target=int(targets["stuck_work_max"]),
            investigate=_investigate(
                "SLA lead/pipeline quá hạn",
                ["Clear inbox lead/pipeline trong 24h.", "Gán owner backup nếu quá tải."],
                sales_links + [{"label": "Hub", "url": "/crm/hub"}],
            )
            if stuck > int(targets["stuck_work_max"])
            else None,
        ),
        _metric(
            key="staff_shortage",
            label="Nhân sự thiếu",
            value=capacity_util,
            fmt="pct",
            status=_rag_lower_better(capacity_util, float(targets["capacity_max_util_pct"])),
            target=float(targets["capacity_max_util_pct"]),
            note="Utilization AM+SP lifecycle.",
        ),
        _metric(
            key="deal_dependency",
            label="Deal phụ thuộc quá lớn",
            value=top_deal_pct,
            fmt="pct",
            status=_rag_lower_better(top_deal_pct, float(targets["top_deal_share_max_pct"])),
            target=float(targets["top_deal_share_max_pct"]),
        ),
        _metric(
            key="top_customer_share",
            label="Tỷ trọng DT khách lớn nhất",
            value=top1_share,
            fmt="pct",
            status=_rag_lower_better(top1_share, float(targets["top1_share_max_pct"])),
            target=float(targets["top1_share_max_pct"]),
        ),
        _metric(
            key="win_rate",
            label="Win rate (tuần)",
            value=close_rate,
            fmt="pct",
            status=win_status,
            target=float(targets["close_rate_target_pct"]),
            prior_value=prior_close_rate,
            note="Cohort: lead đủ chuẩn trong tuần → won/lost.",
            investigate=_investigate(
                "Win rate giảm mạnh",
                [
                    "Review 5 deal lost gần nhất — lý do & pattern.",
                    "Kiểm tra chất lượng lead MQL/SQL.",
                ],
                sales_links,
            )
            if win_status != RAG_GREEN
            else None,
        ),
        _metric(
            key="churn",
            label="Churn KH",
            value=churn_pct,
            fmt="pct",
            status=churn_status,
            target=float(targets["churn_max_pct"]),
            note=f"Cohort tuần WoW (tháng {churn_month_pct}%).",
            investigate=_investigate(
                "Churn tăng",
                ["Gọi KH churn trong tuần — root cause.", "Kích hoạt CSKH retain trên Hub."],
                risk_links,
            )
            if churn_status != RAG_GREEN
            else None,
        ),
    ]

    blocks = {
        "cash": {"key": "cash", "label": BLOCK_LABELS["cash"], "metrics": cash_metrics},
        "sales": {"key": "sales", "label": BLOCK_LABELS["sales"], "metrics": sales_metrics},
        "efficiency": {
            "key": "efficiency",
            "label": BLOCK_LABELS["efficiency"],
            "metrics": efficiency_metrics,
        },
        "risk": {"key": "risk", "label": BLOCK_LABELS["risk"], "metrics": risk_metrics},
    }

    for block in blocks.values():
        for m in block["metrics"]:
            key = str(m.get("key") or "")
            if not m.get("drill_url"):
                url = _metric_drill_url(
                    key,
                    iso_year=iso_year,
                    iso_week=iso_week_num,
                    month_year=month_year,
                    month_num=month_num,
                )
                if url:
                    m["drill_url"] = url
            if not m.get("trend_values"):
                tv = _trend_for_metric(trends, key)
                if tv:
                    m["trend_values"] = tv

    all_metrics = [m for b in blocks.values() for m in b["metrics"]]
    rag_counts = {
        RAG_GREEN: sum(1 for m in all_metrics if m["status"] == RAG_GREEN),
        RAG_YELLOW: sum(1 for m in all_metrics if m["status"] == RAG_YELLOW),
        RAG_RED: sum(1 for m in all_metrics if m["status"] == RAG_RED),
    }

    dashboard = {
        "week": {
            "iso_year": iso_year,
            "iso_week": iso_week_num,
            "start": start.isoformat(),
            "end": end.isoformat(),
            "label": f"Tuần {iso_week_num}/{iso_year} ({start.strftime('%d/%m')} – {end.strftime('%d/%m')})",
        },
        "blocks": blocks,
        "targets": targets,
        "rag_counts": rag_counts,
        "rag_legend": RAG_LABELS,
        "cash_ledger": {
            "position_source": cash_position_source,
            "has_snapshot": cash_position_source == POSITION_SOURCE_LEDGER,
            "latest_snapshot": cash_close_meta.get("snapshot"),
            "snapshots": cash_snapshots,
            "forecast": forecast_meta,
        },
        "trends": trends,
        "retention_weekly": weekly_retention,
    }
    dashboard["pre_execution"] = build_pre_execution_brief(dashboard)
    return dashboard


def _format_metric_export(m: dict[str, Any]) -> str:
    fmt = str(m.get("format") or "")
    value = m.get("value")
    if fmt == "vnd":
        return f"{int(value or 0):,}".replace(",", ".")
    if fmt == "pct":
        return f"{value}%"
    if fmt == "ratio":
        return f"{value}×"
    if fmt == "days":
        return f"{value} ngày"
    return str(value if value is not None else "")


def _kv_rows(pairs: list[tuple[str, Any]]) -> list[list[Any]]:
    return [[k, v] for k, v in pairs]


def build_owner_weekly_export_sheets(
    dashboard: dict[str, Any],
) -> list[tuple[str, list[str], list[list[Any]]]]:
    """Export CSV/XLSX — tóm tắt + chi tiết + hành động."""
    week = dashboard.get("week") or {}
    brief = dashboard.get("pre_execution") or {}
    rag = dashboard.get("rag_counts") or {}

    summary_rows = _kv_rows([
        ("Tuần", week.get("label") or ""),
        ("Bắt đầu", week.get("start") or ""),
        ("Kết thúc", week.get("end") or ""),
        ("Chỉ số xanh", rag.get(RAG_GREEN, 0)),
        ("Chỉ số vàng", rag.get(RAG_YELLOW, 0)),
        ("Chỉ số đỏ", rag.get(RAG_RED, 0)),
        ("Hành động cần xử lý", brief.get("action_count", 0)),
    ])

    detail_headers = [
        "Khối",
        "Chỉ số",
        "Giá trị",
        "Target",
        "Trạng thái",
        "So tuần trước (%)",
        "Ghi chú",
    ]
    detail_rows: list[list[Any]] = []
    for block_key in BLOCK_KEYS:
        block = (dashboard.get("blocks") or {}).get(block_key) or {}
        for m in block.get("metrics") or []:
            target = m.get("target")
            target_str = _format_metric_export({"value": target, "format": m.get("format")}) if target is not None else ""
            detail_rows.append([
                block.get("label") or block_key,
                m.get("label") or m.get("key"),
                _format_metric_export(m),
                target_str,
                m.get("status_label") or m.get("status"),
                m.get("delta_pct") if m.get("delta_pct") is not None else "",
                m.get("note") or "",
            ])

    action_headers = ["Khối", "Chỉ số", "Mức", "Gợi ý", "Bước điều tra"]
    action_rows: list[list[Any]] = []
    for action in brief.get("actions") or []:
        steps = action.get("steps") or []
        action_rows.append([
            action.get("block_label") or "",
            action.get("metric_label") or "",
            action.get("status_label") or action.get("status") or "",
            action.get("hint") or "",
            " | ".join(str(s) for s in steps[:5]),
        ])

    return [
        ("Tom tat", ["Chỉ số", "Giá trị"], summary_rows),
        ("Chi tiet", detail_headers, detail_rows),
        ("Hanh dong", action_headers, action_rows),
    ]
