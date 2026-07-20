"""Orchestration cross-module — Lead ↔ Case ↔ RE inventory ↔ KPI ↔ Issues."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta
from typing import Any

from crm_lead_convert import LEAD_STATUS_TO_PIPELINE, convert_lead_to_crm
from crm_lead_store import (
    TERMINAL_STATUSES,
    fetch_lead_by_id,
    log_lead_activity,
    normalize_source,
    normalize_status,
)
from crm_sales_pipeline import legacy_status_for_stage, normalize_pipeline_stage, pipeline_stage_label

WON_STATUSES: frozenset[str] = frozenset({"won", "post_sale"})
LOST_STATUSES: frozenset[str] = frozenset({"lost"})

ISSUE_SLA_HOURS: dict[str, int] = {
    "cao": 4,
    "khan_cap": 2,
    "binh_thuong": 24,
    "thap": 72,
}


def _now_ts() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def ensure_cross_module_schema(conn: sqlite3.Connection) -> None:
    """Migration cột phục vụ liên kết cross-module."""
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    if "crm_customer_issues" in tables:
        issue_cols = {r[1] for r in conn.execute("PRAGMA table_info(crm_customer_issues)").fetchall()}
        for col, ddl in (
            ("lead_id", "ALTER TABLE crm_customer_issues ADD COLUMN lead_id INTEGER REFERENCES crm_leads(id) ON DELETE SET NULL"),
            ("sla_due_at", "ALTER TABLE crm_customer_issues ADD COLUMN sla_due_at TEXT NOT NULL DEFAULT ''"),
            ("escalated_at", "ALTER TABLE crm_customer_issues ADD COLUMN escalated_at TEXT NOT NULL DEFAULT ''"),
        ):
            if col not in issue_cols:
                try:
                    conn.execute(ddl)
                except sqlite3.Error:
                    pass
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_crm_cu_issue_lead ON crm_customer_issues(lead_id)"
        )
    if "crm_re_project_products" in tables:
        prod_cols = {r[1] for r in conn.execute("PRAGMA table_info(crm_re_project_products)").fetchall()}
        for col, ddl in (
            ("sold_lead_id", "ALTER TABLE crm_re_project_products ADD COLUMN sold_lead_id INTEGER REFERENCES crm_leads(id) ON DELETE SET NULL"),
            ("sold_at", "ALTER TABLE crm_re_project_products ADD COLUMN sold_at TEXT NOT NULL DEFAULT ''"),
        ):
            if col not in prod_cols:
                try:
                    conn.execute(ddl)
                except sqlite3.Error:
                    pass


def sync_lead_to_linked_case(
    conn: sqlite3.Connection,
    lead_id: int,
    *,
    ts: str,
    actor: str = "",
) -> dict[str, Any] | None:
    """Đồng bộ pipeline case khi lead đổi trạng thái (nếu đã convert)."""
    row = fetch_lead_by_id(conn, lead_id)
    if row is None:
        return None
    ld = dict(row)
    case_id = ld.get("converted_case_id")
    if not case_id:
        return None
    st = normalize_status(ld.get("status"))
    pipeline = normalize_pipeline_stage(LEAD_STATUS_TO_PIPELINE.get(st, "moi"))
    if st in LOST_STATUSES:
        pipeline = "mat"
    elif st in WON_STATUSES:
        pipeline = "chot"
    conn.execute(
        """
        UPDATE crm_cases SET
            pipeline_stage = ?, stage_entered_at = ?, status = ?, updated_at = ?
        WHERE id = ?
        """,
        (pipeline, ts, legacy_status_for_stage(pipeline), ts, int(case_id)),
    )
    conn.execute(
        """
        INSERT INTO crm_case_events (case_id, kind, body, created_at)
        VALUES (?, 'he_thong', ?, ?)
        """,
        (
            int(case_id),
            f"Đồng bộ từ Lead #{lead_id} → pipeline «{pipeline_stage_label(pipeline)}».",
            ts,
        ),
    )
    return {"case_id": int(case_id), "pipeline_stage": pipeline}


def mark_product_sold_for_lead(
    conn: sqlite3.Connection,
    lead_id: int,
    *,
    updated_by: str = "",
    ts: str | None = None,
) -> dict[str, Any]:
    from crm_project_deep import fetch_product_by_id, release_product_hold
    from crm_re_project_accounting import sync_revenue_from_inventory

    ts_val = ts or _now_ts()
    lead = fetch_lead_by_id(conn, lead_id)
    if lead is None:
        raise ValueError("Không tìm thấy lead.")
    ld = dict(lead)
    project_id = ld.get("re_project_id")
    product_id = ld.get("re_product_id")
    if not project_id or not product_id:
        raise ValueError("Lead chưa gán dự án BĐS hoặc sản phẩm — không thể chốt căn.")
    prod = fetch_product_by_id(conn, int(project_id), int(product_id))
    if prod is None:
        raise ValueError("Sản phẩm không tồn tại.")
    pd = dict(prod)
    st = str(pd.get("status") or "available")
    if st == "sold" and int(pd.get("sold_lead_id") or 0) == int(lead_id):
        return {"product_id": int(product_id), "already_sold": True}
    if st not in ("available", "hold", "booked"):
        raise ValueError(f"Sản phẩm đang «{st}» — không thể đánh dấu đã bán.")
    if st == "hold" and int(pd.get("hold_lead_id") or 0) not in (0, int(lead_id)):
        raise ValueError("Sản phẩm đang giữ chỗ bởi lead khác.")
    price = int(pd.get("net_price_vnd") or pd.get("list_price_vnd") or 0)
    conn.execute(
        """
        UPDATE crm_re_project_products SET
            status = 'sold', hold_lead_id = NULL, hold_at = '',
            sold_lead_id = ?, sold_at = ?, updated_at = ?
        WHERE id = ? AND project_id = ?
        """,
        (int(lead_id), ts_val, ts_val, int(product_id), int(project_id)),
    )
    sold_count = conn.execute(
        "SELECT COUNT(*) AS c FROM crm_re_project_products WHERE project_id = ? AND status = 'sold'",
        (int(project_id),),
    ).fetchone()
    conn.execute(
        "UPDATE crm_re_projects SET sold_units = ?, updated_at = ? WHERE id = ?",
        (int(sold_count["c"] if sold_count else 0), ts_val, int(project_id)),
    )
    accounting = sync_revenue_from_inventory(
        conn, int(project_id), ts=ts_val, created_by=updated_by[:120]
    )
    log_lead_activity(
        conn,
        lead_id=int(lead_id),
        activity_type="system",
        content=f"Chốt căn {pd.get('unit_code') or product_id} — {price:,} VND".replace(",", "."),
        created_by=updated_by,
        ts=ts_val,
    )
    return {
        "product_id": int(product_id),
        "unit_code": str(pd.get("unit_code") or ""),
        "price_vnd": price,
        "accounting": accounting,
        "already_sold": False,
    }


def _record_customer_purchase(
    conn: sqlite3.Connection,
    *,
    customer_id: int,
    lead_id: int,
    product_name: str,
    amount_vnd: int,
    ts: str,
) -> int | None:
    existing = conn.execute(
        """
        SELECT id FROM crm_customer_purchases
        WHERE customer_id = ? AND reference_code = ?
        """,
        (int(customer_id), f"lead:{int(lead_id)}"),
    ).fetchone()
    if existing:
        return int(existing["id"])
    short_date = ts[:10] if len(ts) >= 10 else ts
    cur = conn.execute(
        """
        INSERT INTO crm_customer_purchases (
            customer_id, order_date, product_name, amount_vnd, quantity, status,
            reference_code, notes, created_at, updated_at
        ) VALUES (?, ?, ?, ?, 1, 'completed', ?, ?, ?, ?)
        """,
        (
            int(customer_id),
            short_date,
            product_name[:400],
            int(amount_vnd),
            f"lead:{int(lead_id)}",
            f"Tự động khi chốt deal Lead #{lead_id}",
            ts,
            ts,
        ),
    )
    return int(cur.lastrowid)


def complete_deal_closure(
    conn: sqlite3.Connection,
    lead_id: int,
    *,
    actor: str = "",
    ts: str | None = None,
    auto_convert: bool = True,
) -> dict[str, Any]:
    """
    Luồng chốt deal cross-module:
    convert KH/case (nếu cần) → sold product → purchase record → sync case pipeline.
    """
    ts_val = ts or _now_ts()
    lead = fetch_lead_by_id(conn, lead_id)
    if lead is None:
        raise ValueError("Không tìm thấy lead.")
    ld = dict(lead)
    st = normalize_status(ld.get("status"))
    if st not in WON_STATUSES and st not in LOST_STATUSES:
        conn.execute(
            "UPDATE crm_leads SET status = 'post_sale', updated_at = ?, updated_by = ? WHERE id = ?",
            (ts_val, actor[:120], int(lead_id)),
        )
        log_lead_activity(
            conn,
            lead_id=int(lead_id),
            activity_type="system",
            content="Tự động chuyển trạng thái post_sale khi chốt deal.",
            created_by=actor,
            ts=ts_val,
        )

    convert_result: dict[str, Any] | None = None
    if auto_convert and not ld.get("converted_case_id"):
        convert_result = convert_lead_to_crm(conn, lead_id, actor=actor, ts=ts_val)
        lead = fetch_lead_by_id(conn, lead_id)
        assert lead is not None
        ld = dict(lead)

    product_result: dict[str, Any] | None = None
    purchase_id: int | None = None
    if ld.get("re_product_id") and ld.get("re_project_id"):
        try:
            product_result = mark_product_sold_for_lead(
                conn, lead_id, updated_by=actor, ts=ts_val
            )
        except ValueError as exc:
            product_result = {"error": str(exc)}
        cust_id = ld.get("converted_customer_id")
        if cust_id and product_result and not product_result.get("error"):
            from crm_project_deep import fetch_product_by_id

            prod = fetch_product_by_id(
                conn, int(ld["re_project_id"]), int(ld["re_product_id"])
            )
            if prod:
                pd = dict(prod)
                purchase_id = _record_customer_purchase(
                    conn,
                    customer_id=int(cust_id),
                    lead_id=int(lead_id),
                    product_name=str(pd.get("unit_code") or "Căn BĐS"),
                    amount_vnd=int(pd.get("net_price_vnd") or pd.get("list_price_vnd") or 0),
                    ts=ts_val,
                )

    case_sync = sync_lead_to_linked_case(conn, lead_id, ts=ts_val, actor=actor)

    if ld.get("re_project_id"):
        try:
            from crm_re_projects import refresh_project_re_leads_new_kpi

            refresh_project_re_leads_new_kpi(
                conn, int(ld["re_project_id"]), ts=ts_val, sync_staff=False
            )
        except Exception:
            pass

    return {
        "lead_id": int(lead_id),
        "convert": convert_result,
        "product": product_result,
        "purchase_id": purchase_id,
        "case_sync": case_sync,
    }


def on_lead_status_changed(
    conn: sqlite3.Connection,
    lead_id: int,
    old_status: str,
    new_status: str,
    *,
    updated_by: str = "",
    ts: str,
) -> dict[str, Any]:
    """Hook sau update_lead — đồng bộ case; auto deal closure khi won."""
    result: dict[str, Any] = {"lead_id": int(lead_id)}
    old_s = normalize_status(old_status)
    new_s = normalize_status(new_status)
    if old_s == new_s:
        return result
    result["case_sync"] = sync_lead_to_linked_case(
        conn, lead_id, ts=ts, actor=updated_by
    )
    if new_s in LOST_STATUSES and dict(fetch_lead_by_id(conn, lead_id) or {}).get("re_product_id"):
        from crm_project_deep import release_product_hold

        try:
            release_product_hold(conn, lead_id, updated_by=updated_by, ts=ts)
            result["released_product"] = True
        except ValueError:
            result["released_product"] = False
    if new_s in WON_STATUSES and old_s not in WON_STATUSES:
        result["deal_closure"] = complete_deal_closure(
            conn, lead_id, actor=updated_by, ts=ts, auto_convert=True
        )
    return result


def onboard_new_staff(
    conn: sqlite3.Connection,
    staff_id: int,
    *,
    re_project_ids: list[int] | None = None,
    actor: str = "",
    ts: str | None = None,
) -> dict[str, Any]:
    """Onboarding: gán pool dự án BĐS + KPI mẫu tháng hiện tại."""
    from crm_project_leads import add_project_staff

    ts_val = ts or _now_ts()
    staff = conn.execute(
        "SELECT id, name, job_title, position_id FROM crm_staff WHERE id = ?",
        (int(staff_id),),
    ).fetchone()
    if staff is None:
        raise ValueError("Không tìm thấy nhân viên.")
    sd = dict(staff)
    project_ids = list(re_project_ids or [])
    if not project_ids:
        rows = conn.execute(
            """
            SELECT id FROM crm_re_projects
            WHERE COALESCE(status, 'active') NOT IN ('archived', 'closed')
            ORDER BY id DESC LIMIT 3
            """
        ).fetchall()
        project_ids = [int(r["id"]) for r in rows]
    pools: list[dict[str, Any]] = []
    for pid in project_ids:
        try:
            pools.append(
                add_project_staff(
                    conn,
                    int(pid),
                    staff_id=int(staff_id),
                    role="sales",
                    assign_enabled=True,
                    ts=ts_val,
                )
            )
        except ValueError:
            continue
    year = datetime.now().year
    month = datetime.now().month
    ts_d = datetime.now().strftime("%Y-%m-%d")
    kpi_created = 0
    try:
        metric_rows = conn.execute(
            """
            SELECT id, code, name FROM crm_kpi_metrics
            WHERE active = 1 AND code LIKE 'RE_%'
            ORDER BY sort_order ASC, id ASC LIMIT 2
            """
        ).fetchall()
    except sqlite3.Error:
        metric_rows = []
    for m in metric_rows:
        mid = int(m["id"])
        exists = conn.execute(
            """
            SELECT id FROM crm_staff_kpi
            WHERE staff_id = ? AND metric_id = ? AND year = ? AND month = ?
            """,
            (int(staff_id), mid, year, month),
        ).fetchone()
        if exists:
            continue
        try:
            conn.execute(
                """
                INSERT INTO crm_staff_kpi (
                    staff_id, metric_id, year, month,
                    target_value, actual_value, status, note, created_at, updated_at
                ) VALUES (?, ?, ?, ?, 0, 0, 'draft', ?, ?, ?)
                """,
                (
                    int(staff_id),
                    mid,
                    year,
                    month,
                    f"Onboarding tự động — {actor[:80]}",
                    ts_d,
                    ts_val,
                ),
            )
            kpi_created += 1
        except sqlite3.Error:
            pass
    return {
        "staff_id": int(staff_id),
        "staff_name": str(sd.get("name") or ""),
        "project_pools": pools,
        "kpi_rows_created": kpi_created,
    }


def compute_marketing_loop_metrics(
    conn: sqlite3.Connection,
    *,
    re_project_id: int | None = None,
    period_month: str = "",
    utm_campaign: str = "",
) -> dict[str, Any]:
    """Closed-loop MKT: lead count, won, CPL proxy từ chi phí marketing cash-flow."""
    pm = str(period_month or "").strip()[:7] or datetime.now().strftime("%Y-%m")
    placeholders_exclude = ", ".join("?" for _ in ("lost", "junk", "spam", "duplicate"))
    lead_where = [
        "COALESCE(is_duplicate, 0) = 0",
        f"status NOT IN ({placeholders_exclude})",
        "substr(COALESCE(created_at, ''), 1, 7) = ?",
    ]
    lead_params: list[Any] = ["lost", "junk", "spam", "duplicate", pm]
    if re_project_id is not None:
        lead_where.append("re_project_id = ?")
        lead_params.append(int(re_project_id))
    if utm_campaign.strip():
        lead_where.append("lower(trim(COALESCE(meta_json, ''))) LIKE ?")
        lead_params.append(f"%{utm_campaign.strip().lower()}%")
    lead_sql = f"SELECT COUNT(*) AS c FROM crm_leads WHERE {' AND '.join(lead_where)}"
    lead_row = conn.execute(lead_sql, lead_params).fetchone()
    leads_new = int(lead_row["c"] if lead_row else 0)

    won_where = list(lead_where)
    won_where.append("status IN ('post_sale', 'won')")
    won_sql = f"SELECT COUNT(*) AS c FROM crm_leads WHERE {' AND '.join(won_where)}"
    won_row = conn.execute(won_sql, lead_params).fetchone()
    won = int(won_row["c"] if won_row else 0)

    spend_vnd = 0
    if re_project_id is not None:
        cf = conn.execute(
            """
            SELECT COALESCE(SUM(amount_vnd), 0) AS s FROM crm_re_project_cash_flow_lines
            WHERE project_id = ? AND flow_type = 'outflow' AND category = 'marketing'
              AND substr(COALESCE(period_month, transaction_date, ''), 1, 7) = ?
            """,
            (int(re_project_id), pm),
        ).fetchone()
        spend_vnd = int(cf["s"] if cf else 0)
    else:
        cf = conn.execute(
            """
            SELECT COALESCE(SUM(amount_vnd), 0) AS s FROM crm_re_project_cash_flow_lines
            WHERE flow_type = 'outflow' AND category = 'marketing'
              AND substr(COALESCE(period_month, transaction_date, ''), 1, 7) = ?
            """,
            (pm,),
        ).fetchone()
        spend_vnd = int(cf["s"] if cf else 0)

    cpl = round(spend_vnd / leads_new) if leads_new > 0 else None
    win_rate = round(won * 100.0 / leads_new, 1) if leads_new > 0 else 0.0

    by_source_rows = conn.execute(
        f"""
        SELECT source, COUNT(*) AS c FROM crm_leads
        WHERE {' AND '.join(lead_where)}
        GROUP BY source ORDER BY c DESC LIMIT 12
        """,
        lead_params,
    ).fetchall()
    by_source = [
        {
            "source": str(r["source"] or ""),
            "leads": int(r["c"]),
            "share_pct": round(int(r["c"]) * 100.0 / leads_new, 1) if leads_new else 0,
        }
        for r in by_source_rows
    ]

    return {
        "period_month": pm,
        "re_project_id": re_project_id,
        "utm_campaign": utm_campaign.strip() or None,
        "leads_new": leads_new,
        "won": won,
        "win_rate_pct": win_rate,
        "marketing_spend_vnd": spend_vnd,
        "cpl_vnd": cpl,
        "by_source": by_source,
    }


def _issue_sla_due(priority: str, created_at: str) -> str:
    hours = ISSUE_SLA_HOURS.get(str(priority or "binh_thuong"), 24)
    try:
        base = datetime.strptime(str(created_at)[:19], "%Y-%m-%d %H:%M:%S")
    except ValueError:
        base = datetime.now()
    return (base + timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M:%S")


def on_customer_issue_created(
    conn: sqlite3.Connection,
    issue_id: int,
    *,
    ts: str,
) -> None:
    """Gắn SLA + nhắc việc Hub khi tạo issue."""
    ensure_cross_module_schema(conn)
    row = conn.execute("SELECT * FROM crm_customer_issues WHERE id = ?", (int(issue_id),)).fetchone()
    if row is None:
        return
    d = dict(row)
    if str(d.get("status") or "") in ("da_xu_ly", "dong"):
        return
    due = _issue_sla_due(str(d.get("priority") or ""), str(d.get("created_at") or ts))
    conn.execute(
        "UPDATE crm_customer_issues SET sla_due_at = ?, updated_at = ? WHERE id = ?",
        (due, ts, int(issue_id)),
    )
    staff_id = int(d["assigned_staff_id"]) if d.get("assigned_staff_id") else None
    title = f"[Issue] {str(d.get('title') or '')[:100]}"
    body = str(d.get("description") or "")[:2000]
    meta = json.dumps({"issue_id": int(issue_id), "customer_id": int(d["customer_id"])}, ensure_ascii=False)
    conn.execute(
        """
        INSERT INTO crm_reminders (
            scope, ref_id, reminder_kind, title, body, remind_at,
            status, staff_id, meta_json, created_at, updated_at
        ) VALUES ('customer_issue', ?, 'sla', ?, ?, ?, 'pending', ?, ?, ?, ?)
        """,
        (int(issue_id), title, body, due, staff_id, meta, ts, ts),
    )


def sync_customer_issue_sla(conn: sqlite3.Connection, *, ts: str) -> dict[str, int]:
    """Escalate issue quá SLA — tạo nhắc việc cho manager."""
    ensure_cross_module_schema(conn)
    rows = conn.execute(
        """
        SELECT i.*, s.reports_to_id AS manager_id
        FROM crm_customer_issues i
        LEFT JOIN crm_staff s ON s.id = i.assigned_staff_id
        WHERE i.status NOT IN ('da_xu_ly', 'dong')
          AND i.sla_due_at != ''
          AND i.sla_due_at < ?
          AND (i.escalated_at IS NULL OR i.escalated_at = '')
        """,
        (ts,),
    ).fetchall()
    escalated = 0
    for row in rows:
        d = dict(row)
        manager_id = d.get("manager_id")
        conn.execute(
            "UPDATE crm_customer_issues SET escalated_at = ?, updated_at = ? WHERE id = ?",
            (ts, ts, int(d["id"])),
        )
        if manager_id:
            conn.execute(
                """
                INSERT INTO crm_reminders (
                    scope, ref_id, reminder_kind, title, body, remind_at,
                    status, staff_id, meta_json, created_at, updated_at
                ) VALUES ('customer_issue', ?, 'escalation', ?, ?, ?, 'pending', ?, ?, ?, ?)
                """,
                (
                    int(d["id"]),
                    f"[Escalate] Issue #{d['id']} quá SLA",
                    str(d.get("title") or "")[:500],
                    ts,
                    int(manager_id),
                    json.dumps({"issue_id": int(d["id"])}, ensure_ascii=False),
                    ts,
                    ts,
                ),
            )
        escalated += 1
    return {"escalated": escalated, "checked": len(rows)}
