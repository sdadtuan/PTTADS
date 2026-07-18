"""Finance KPI alerts + export — nhóm 6 (sau exec metrics)."""
from __future__ import annotations

import os
import sqlite3
from datetime import datetime
from typing import Any

from crm_lead_kpi_metrics import get_unified_lead_kpi_summary
from crm_svc_exec_metrics import get_cac_metrics, get_exec_metrics, get_mrr_arr_metrics
from crm_svc_finance import get_ar_aging, get_recurring_revenue_summary, get_service_package_rollup
from crm_svc_portfolio import get_concentration_metrics, get_portfolio_metrics
from crm_svc_retention import get_retention_metrics

ALERT_CRITICAL = "critical"
ALERT_WARNING = "warning"

THRESHOLD_DEFAULTS: dict[str, float | int] = {
    "top2_warn_pct": 50.0,
    "top1_warn_pct": 40.0,
    "top2_critical_pct": 70.0,
    "top1_critical_pct": 55.0,
    "ar_overdue_critical_vnd": 50_000_000,
    "ontime_warn_pct": 80.0,
    "ontime_min_decided": 2,
    "renewal_warn_pct": 70.0,
    "customer_churn_warn_pct": 10.0,
    "customer_churn_min_prev": 3,
    "close_rate_warn_pct": 25.0,
    "close_rate_min_qualified": 5,
    "low_margin_warn_pct": 20.0,
    "capacity_warn_util_pct": 85.0,
}

THRESHOLD_ENV_KEYS: dict[str, str] = {
    "top2_warn_pct": "PTT_KPI_ALERT_TOP2_WARN_PCT",
    "top1_warn_pct": "PTT_KPI_ALERT_TOP1_WARN_PCT",
    "top2_critical_pct": "PTT_KPI_ALERT_TOP2_CRITICAL_PCT",
    "top1_critical_pct": "PTT_KPI_ALERT_TOP1_CRITICAL_PCT",
    "ar_overdue_critical_vnd": "PTT_KPI_ALERT_AR_OVERDUE_CRITICAL_VND",
    "ontime_warn_pct": "PTT_KPI_ALERT_ONTIME_WARN_PCT",
    "ontime_min_decided": "PTT_KPI_ALERT_ONTIME_MIN_DECIDED",
    "renewal_warn_pct": "PTT_KPI_ALERT_RENEWAL_WARN_PCT",
    "customer_churn_warn_pct": "PTT_KPI_ALERT_CHURN_WARN_PCT",
    "customer_churn_min_prev": "PTT_KPI_ALERT_CHURN_MIN_PREV",
    "close_rate_warn_pct": "PTT_KPI_ALERT_CLOSE_RATE_WARN_PCT",
    "close_rate_min_qualified": "PTT_KPI_ALERT_CLOSE_RATE_MIN_QUALIFIED",
    "low_margin_warn_pct": "PTT_KPI_ALERT_LOW_MARGIN_WARN_PCT",
    "capacity_warn_util_pct": "PTT_KPI_ALERT_CAPACITY_WARN_PCT",
}


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


def ensure_kpi_config_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS crm_finance_kpi_config (
            config_key TEXT PRIMARY KEY,
            config_value TEXT NOT NULL,
            updated_at TEXT NOT NULL DEFAULT ''
        )
        """
    )
    conn.commit()


def get_alert_thresholds(conn: sqlite3.Connection) -> dict[str, float | int]:
    """Ngưỡng cảnh báo — DB ưu tiên, fallback env, rồi default."""
    ensure_kpi_config_schema(conn)
    db_rows = {
        str(r["config_key"]): str(r["config_value"])
        for r in conn.execute(
            "SELECT config_key, config_value FROM crm_finance_kpi_config"
        ).fetchall()
    }
    out: dict[str, float | int] = {}
    for key, default in THRESHOLD_DEFAULTS.items():
        if key in db_rows:
            raw = db_rows[key].strip()
            try:
                out[key] = int(raw) if isinstance(default, int) else float(raw)
                continue
            except ValueError:
                pass
        env_key = THRESHOLD_ENV_KEYS.get(key, "")
        out[key] = _env_number(env_key, default) if env_key else default
    return out


def set_alert_thresholds(
    conn: sqlite3.Connection, updates: dict[str, Any]
) -> dict[str, float | int]:
    ensure_kpi_config_schema(conn)
    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    for key, value in updates.items():
        if key not in THRESHOLD_DEFAULTS:
            continue
        default = THRESHOLD_DEFAULTS[key]
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
            (key, str(val), ts),
        )
    conn.commit()
    return get_alert_thresholds(conn)


def _prev_month(year: int, month: int) -> tuple[int, int]:
    y, m = int(year), int(month)
    if m == 1:
        return y - 1, 12
    return y, m - 1


def _month_points(end_year: int, end_month: int, count: int) -> list[tuple[int, int]]:
    points: list[tuple[int, int]] = []
    y, m = int(end_year), int(end_month)
    for _ in range(max(1, int(count))):
        points.append((y, m))
        y, m = _prev_month(y, m)
    points.reverse()
    return points


def get_finance_kpi_trends(
    conn: sqlite3.Connection,
    *,
    year: int,
    month: int,
    months: int = 6,
) -> dict[str, Any]:
    """Trend MRR, concentration Top-2, CAC — tối đa 6 tháng gần nhất."""
    count = max(2, min(int(months), 12))
    points = _month_points(year, month, count)
    labels: list[str] = []
    mrr_series: list[int] = []
    conc_series: list[float] = []
    cac_series: list[int] = []

    for y, m in points:
        labels.append(f"{m:02d}/{y}")
        mrr = get_mrr_arr_metrics(conn, year=y, month=m)
        conc = get_concentration_metrics(conn, year=y, month=m)
        cac = get_cac_metrics(conn, year=y, month=m)
        mrr_series.append(int(mrr.get("mrr_bookings_vnd") or 0))
        conc_series.append(float(conc.get("top2_concentration_pct") or 0))
        cac_series.append(int(cac.get("cac_vnd") or 0))

    return {
        "year": int(year),
        "month": int(month),
        "months": count,
        "labels": labels,
        "mrr_bookings_vnd": mrr_series,
        "top2_concentration_pct": conc_series,
        "cac_vnd": cac_series,
    }


def load_finance_kpi_bundle(
    conn: sqlite3.Connection,
    *,
    year: int,
    month: int,
) -> dict[str, Any]:
    """Gom toàn bộ KPI financials — dùng chung cho page, alerts, export."""
    return {
        "year": int(year),
        "month": int(month),
        "ar_aging": get_ar_aging(conn),
        "recurring_summary": get_recurring_revenue_summary(conn, year=year, month=month),
        "package_rollup": get_service_package_rollup(conn, year=year, month=month),
        "retention_metrics": get_retention_metrics(conn, year=year, month=month),
        "lead_kpi": get_unified_lead_kpi_summary(
            conn, year=year, month=month, period_cohort=True
        ),
        "portfolio_metrics": get_portfolio_metrics(conn, year=year, month=month),
        "exec_metrics": get_exec_metrics(conn, year=year, month=month),
    }


def _alert(
    *,
    alert_id: str,
    level: str,
    category: str,
    title: str,
    message: str,
    metric_key: str | None = None,
    metric_value: Any = None,
) -> dict[str, Any]:
    return {
        "id": alert_id,
        "level": level,
        "category": category,
        "title": title,
        "message": message,
        "metric_key": metric_key,
        "metric_value": metric_value,
    }


def collect_finance_kpi_alerts(
    conn: sqlite3.Connection,
    *,
    year: int,
    month: int,
    bundle: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Cảnh báo tập trung: concentration, capacity, AR, on-time, retention, lead, margin."""
    data = bundle or load_finance_kpi_bundle(conn, year=year, month=month)
    thresholds = get_alert_thresholds(conn)
    alerts: list[dict[str, Any]] = []

    conc = data["portfolio_metrics"]["concentration"]
    cap = data["portfolio_metrics"]["capacity"]
    ar = data["ar_aging"]
    ot = data["exec_metrics"]["delivery_ontime"]
    rc = data["retention_metrics"]["renewal_cohort"]
    lead = data["lead_kpi"]

    top1 = float(conc.get("top1_share_pct") or 0)
    top2 = float(conc.get("top2_concentration_pct") or 0)
    top2_crit = float(thresholds["top2_critical_pct"])
    top1_crit = float(thresholds["top1_critical_pct"])
    top2_warn = float(thresholds["top2_warn_pct"])
    if top2 >= top2_crit or top1 >= top1_crit:
        alerts.append(
            _alert(
                alert_id="concentration_critical",
                level=ALERT_CRITICAL,
                category="portfolio",
                title="Rủi ro tập trung doanh thu (cao)",
                message=(
                    f"Top-1 {top1:.1f}% · Top-2 {top2:.1f}% tổng thu tháng "
                    f"(ngưỡng cảnh báo Top-2 {top2_warn:.0f}%)."
                ),
                metric_key="top2_concentration_pct",
                metric_value=top2,
            )
        )
    elif top2 >= top2_warn or top1 >= float(thresholds["top1_warn_pct"]):
        alerts.append(
            _alert(
                alert_id="concentration_warning",
                level=ALERT_WARNING,
                category="portfolio",
                title="Rủi ro tập trung doanh thu",
                message=(
                    f"Top-2 KH chiếm {top2:.1f}% doanh thu tháng "
                    f"(ngưỡng {top2_warn:.0f}%)."
                ),
                metric_key="top2_concentration_pct",
                metric_value=top2,
            )
        )

    cap_thresh = float(thresholds["capacity_warn_util_pct"])
    am_u = float(cap.get("am_utilization_pct") or 0)
    sp_u = float(cap.get("sp_utilization_pct") or 0)
    combined_u = float(cap.get("combined_utilization_pct") or 0)
    if (
        combined_u >= cap_thresh
        or am_u >= cap_thresh
        or sp_u >= cap_thresh
    ):
        alerts.append(
            _alert(
                alert_id="capacity_warning",
                level=ALERT_WARNING,
                category="portfolio",
                title="Công suất team gần full",
                message=f"AM {am_u:.1f}% · SP {sp_u:.1f}% utilization (ngưỡng {cap_thresh:.0f}%).",
                metric_key="combined_utilization_pct",
                metric_value=combined_u,
            )
        )

    ar_crit = int(thresholds["ar_overdue_critical_vnd"])
    overdue = int(ar.get("total_overdue_vnd") or 0)
    if overdue >= ar_crit:
        alerts.append(
            _alert(
                alert_id="ar_overdue_critical",
                level=ALERT_CRITICAL,
                category="finance",
                title="AR quá hạn lớn",
                message=f"Tổng AR quá hạn {overdue:,} ₫ (ngưỡng {ar_crit:,} ₫).",
                metric_key="total_overdue_vnd",
                metric_value=overdue,
            )
        )
    elif overdue > 0:
        alerts.append(
            _alert(
                alert_id="ar_overdue_warning",
                level=ALERT_WARNING,
                category="finance",
                title="Có khoản AR quá hạn",
                message=f"Tổng AR quá hạn {overdue:,} ₫.",
                metric_key="total_overdue_vnd",
                metric_value=overdue,
            )
        )

    ontime_min = int(thresholds["ontime_min_decided"])
    ontime_warn = float(thresholds["ontime_warn_pct"])
    decided = int(ot.get("tasks_decided") or 0)
    on_time = float(ot.get("on_time_rate_pct") or 0)
    if decided >= ontime_min and on_time < ontime_warn:
        alerts.append(
            _alert(
                alert_id="delivery_ontime_warning",
                level=ALERT_WARNING,
                category="delivery",
                title="Delivery trễ hạn",
                message=(
                    f"On-time {on_time:.1f}% trên {decided} task "
                    f"(ngưỡng {ontime_warn:.0f}%)."
                ),
                metric_key="on_time_rate_pct",
                metric_value=on_time,
            )
        )

    renewal_warn = float(thresholds["renewal_warn_pct"])
    renewal_decided = int(rc.get("contracts_decided") or 0)
    renewal_rate = float(rc.get("renewal_rate_pct") or 0)
    if renewal_decided >= 1 and renewal_rate < renewal_warn:
        alerts.append(
            _alert(
                alert_id="renewal_rate_warning",
                level=ALERT_WARNING,
                category="retention",
                title="Renewal rate thấp",
                message=(
                    f"{renewal_rate:.1f}% HĐ hết hạn đã quyết định được gia hạn "
                    f"({rc.get('renewed', 0)}/{renewal_decided}, ngưỡng {renewal_warn:.0f}%)."
                ),
                metric_key="renewal_rate_pct",
                metric_value=renewal_rate,
            )
        )

    churn_min_prev = int(thresholds["customer_churn_min_prev"])
    churn_warn = float(thresholds["customer_churn_warn_pct"])
    prev_active = int(data["retention_metrics"].get("active_customers_prev") or 0)
    churn_pct = float(data["retention_metrics"].get("customer_churn_pct") or 0)
    if prev_active >= churn_min_prev and churn_pct > churn_warn:
        alerts.append(
            _alert(
                alert_id="customer_churn_warning",
                level=ALERT_WARNING,
                category="retention",
                title="Churn khách hàng MoM cao",
                message=f"Churn {churn_pct:.1f}% so với tháng trước (ngưỡng {churn_warn:.0f}%).",
                metric_key="customer_churn_pct",
                metric_value=churn_pct,
            )
        )

    close_min = int(thresholds["close_rate_min_qualified"])
    close_warn = float(thresholds["close_rate_warn_pct"])
    qualified = int(lead.get("qualified_in_month") or 0)
    close_cohort = float(lead.get("cohort_close_rate_pct") or 0)
    if qualified >= close_min and close_cohort < close_warn:
        alerts.append(
            _alert(
                alert_id="close_rate_warning",
                level=ALERT_WARNING,
                category="sales",
                title="Close rate cohort thấp",
                message=(
                    f"{close_cohort:.1f}% qualified tháng chốt won "
                    f"(ngưỡng {close_warn:.0f}%)."
                ),
                metric_key="cohort_close_rate_pct",
                metric_value=close_cohort,
            )
        )

    margin_warn = float(thresholds["low_margin_warn_pct"])
    for pkg in data["package_rollup"].get("packages") or []:
        recv = int(pkg.get("received_month_vnd") or 0)
        margin = float(pkg.get("gross_margin_month_pct") or 0)
        if recv > 0 and margin < margin_warn:
            slug = str(pkg.get("service_slug") or "")
            alerts.append(
                _alert(
                    alert_id=f"low_margin_{slug or pkg.get('service_label', 'pkg')}",
                    level=ALERT_WARNING,
                    category="margin",
                    title="Gross margin tháng thấp",
                    message=(
                        f"{pkg.get('service_label', slug)}: margin {margin:.1f}% "
                        f"(thu {recv:,} ₫, ngưỡng {margin_warn:.0f}%)."
                    ),
                    metric_key="gross_margin_month_pct",
                    metric_value=margin,
                )
            )

    level_order = {ALERT_CRITICAL: 0, ALERT_WARNING: 1}
    alerts.sort(key=lambda a: (level_order.get(str(a["level"]), 9), str(a["title"])))

    return {
        "year": int(year),
        "month": int(month),
        "alerts": alerts,
        "alert_count": len(alerts),
        "critical_count": sum(1 for a in alerts if a["level"] == ALERT_CRITICAL),
        "warning_count": sum(1 for a in alerts if a["level"] == ALERT_WARNING),
        "has_critical": any(a["level"] == ALERT_CRITICAL for a in alerts),
    }


def _kv_rows(pairs: list[tuple[str, Any]]) -> list[list[Any]]:
    return [[k, v] for k, v in pairs]


def build_finance_kpi_export_sheets(
    bundle: dict[str, Any],
) -> list[tuple[str, list[str], list[list[Any]]]]:
    """Trả danh sách sheet (title, headers, rows) cho CSV/XLSX."""
    year = int(bundle["year"])
    month = int(bundle["month"])
    ar = bundle["ar_aging"]
    rec = bundle["recurring_summary"]
    pkg = bundle["package_rollup"]
    ret = bundle["retention_metrics"]
    rc = ret["renewal_cohort"]
    lead = bundle["lead_kpi"]
    conc = bundle["portfolio_metrics"]["concentration"]
    cap = bundle["portfolio_metrics"]["capacity"]
    cac = bundle["exec_metrics"]["cac"]
    ot = bundle["exec_metrics"]["delivery_ontime"]
    mrr = bundle["exec_metrics"]["mrr_arr"]

    summary_rows = _kv_rows([
        ("Kỳ", f"{month:02d}/{year}"),
        ("AR chờ thu (VNĐ)", ar.get("total_pending_vnd", 0)),
        ("AR quá hạn (VNĐ)", ar.get("total_overdue_vnd", 0)),
        ("Thu recurring tháng (VNĐ)", rec.get("received_recurring_vnd", 0)),
        ("Retention rate MoM (%)", ret.get("customer_retention_pct", 0)),
        ("Renewal rate (%)", rc.get("renewal_rate_pct", 0)),
        ("Close rate cohort (%)", lead.get("cohort_close_rate_pct", 0)),
        ("Top-2 concentration (%)", conc.get("top2_concentration_pct", 0)),
        ("AM utilization (%)", cap.get("am_utilization_pct", 0)),
        ("CAC (VNĐ)", cac.get("cac_vnd", 0)),
        ("Delivery on-time (%)", ot.get("on_time_rate_pct", 0)),
        ("MRR bookings (VNĐ)", mrr.get("mrr_bookings_vnd", 0)),
        ("ARR bookings (VNĐ)", mrr.get("arr_bookings_vnd", 0)),
    ])

    ar_rows = _kv_rows([
        ("As of", ar.get("as_of", "")),
        ("Tổng chờ thu", ar.get("total_pending_vnd", 0)),
        ("Tổng quá hạn", ar.get("total_overdue_vnd", 0)),
    ])
    for key, label in (ar.get("bucket_labels") or {}).items():
        ar_rows.append([label, ar.get("buckets", {}).get(key, 0)])

    pkg_headers = [
        "Gói dịch vụ",
        "Deal",
        "Thu tháng",
        "Chi delivery tháng",
        "Margin tháng (%)",
        "Thu lifetime",
        "Margin lifetime (%)",
        "AR quá hạn",
    ]
    pkg_rows: list[list[Any]] = []
    for p in pkg.get("packages") or []:
        pkg_rows.append([
            p.get("service_label") or p.get("service_slug"),
            p.get("lifecycle_count", 0),
            p.get("received_month_vnd", 0),
            p.get("delivery_expenses_month_vnd", 0),
            p.get("gross_margin_month_pct", 0),
            p.get("received_lifetime_vnd", 0),
            p.get("gross_margin_lifetime_pct", 0),
            p.get("ar_overdue_vnd", 0),
        ])

    top_headers = ["Khách hàng", "Thu tháng (VNĐ)", "Share (%)"]
    top_rows = [
        [c.get("customer_name"), c.get("received_vnd"), c.get("share_pct")]
        for c in conc.get("top_customers") or []
    ]

    exec_rows = _kv_rows([
        ("CAC (VNĐ)", cac.get("cac_vnd", 0)),
        ("KH mới", cac.get("new_customers", 0)),
        ("Pre-sales (VNĐ)", cac.get("presales_cost_vnd", 0)),
        ("Marketing (VNĐ)", cac.get("marketing_cost_vnd", 0)),
        ("Marketing source", cac.get("marketing_spend_source", "")),
        ("On-time rate (%)", ot.get("on_time_rate_pct", 0)),
        ("Tasks on-time", ot.get("tasks_on_time", 0)),
        ("Tasks decided", ot.get("tasks_decided", 0)),
        ("MRR bookings (VNĐ)", mrr.get("mrr_bookings_vnd", 0)),
        ("MRR cash (VNĐ)", mrr.get("mrr_cash_vnd", 0)),
        ("ARR (VNĐ)", mrr.get("arr_bookings_vnd", 0)),
    ])

    retention_rows = _kv_rows([
        ("KH active tháng", ret.get("active_customers", 0)),
        ("KH active tháng trước", ret.get("active_customers_prev", 0)),
        ("Retention MoM (%)", ret.get("customer_retention_pct", 0)),
        ("Churn MoM (%)", ret.get("customer_churn_pct", 0)),
        ("HĐ hết hạn cohort", rc.get("contracts_ending", 0)),
        ("Renewed", rc.get("renewed", 0)),
        ("Churned", rc.get("churned", 0)),
        ("Renewal rate (%)", rc.get("renewal_rate_pct", 0)),
    ])

    lead_rows = _kv_rows([
        ("Qualified tháng", lead.get("qualified_in_month", 0)),
        ("Won cohort", lead.get("won_from_month_cohort", 0)),
        ("Close rate cohort (%)", lead.get("cohort_close_rate_pct", 0)),
        ("Close rate decided (%)", lead.get("cohort_close_rate_decided_pct", 0)),
        ("Qualified tích lũy", lead.get("qualified_leads", 0)),
        ("Close rate tích lũy (%)", lead.get("close_rate_pct", 0)),
    ])

    return [
        ("Tom tat", ["Chi so", "Gia tri"], summary_rows),
        ("AR Aging", ["Chi so", "Gia tri"], ar_rows),
        ("Goi dich vu", pkg_headers, pkg_rows),
        ("Top KH DT", top_headers, top_rows),
        ("Exec KPI", ["Chi so", "Gia tri"], exec_rows),
        ("Retention", ["Chi so", "Gia tri"], retention_rows),
        ("Lead KPI", ["Chi so", "Gia tri"], lead_rows),
    ]
