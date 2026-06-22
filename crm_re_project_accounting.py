"""Kế toán chuyên sâu theo dự án BĐS — dòng tiền, thu chi, P&L, marketing."""
from __future__ import annotations

import csv
import io
import re
import sqlite3
from datetime import datetime
from typing import Any

from crm_re_projects import (
    BUDGET_CATEGORIES,
    BUDGET_CATEGORY_LABELS,
    RISK_LEVEL_LABELS,
    default_business_plan,
    default_marketing_plan,
    default_sales_plan,
    fetch_project,
    list_budget_lines,
    list_products,
    list_risks,
    save_risk,
)

CASH_FLOW_TYPES = ("inflow", "outflow")
CASH_FLOW_TYPE_LABELS = {"inflow": "Thu", "outflow": "Chi"}

CASH_FLOW_STATUSES = ("planned", "confirmed", "paid", "cancelled")
CASH_FLOW_STATUS_LABELS = {
    "planned": "Kế hoạch",
    "confirmed": "Đã xác nhận",
    "paid": "Đã thanh toán",
    "cancelled": "Đã hủy",
}

CASH_FLOW_SOURCES = ("manual", "plan_sync", "inventory", "import")
CASH_FLOW_SOURCE_LABELS = {
    "manual": "Nhập tay",
    "plan_sync": "Đồng bộ KH",
    "inventory": "Tồn kho",
    "import": "Import CSV",
}

MARKETING_SUB_CATEGORIES = (
    "fb_ads",
    "google_ads",
    "zalo_ads",
    "tiktok_ads",
    "event",
    "content",
    "agency",
    "influencer",
    "ooh",
    "other",
)
MARKETING_SUB_CATEGORY_LABELS = {
    "fb_ads": "Facebook / Meta Ads",
    "google_ads": "Google Ads",
    "zalo_ads": "Zalo Ads",
    "tiktok_ads": "TikTok Ads",
    "event": "Sự kiện / Activation",
    "content": "Content / Sáng tạo",
    "agency": "Agency / Dịch vụ",
    "influencer": "KOL / Influencer",
    "ooh": "OOH / Bảng quảng cáo",
    "other": "Khác",
}


def _now_ts() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _norm(text: str) -> str:
    s = str(text or "").lower()
    s = re.sub(r"[àáạảãâầấậẩẫăằắặẳẵ]", "a", s)
    s = re.sub(r"[èéẹẻẽêềếệểễ]", "e", s)
    s = re.sub(r"[ìíịỉĩ]", "i", s)
    s = re.sub(r"[òóọỏõôồốộổỗơờớợởỡ]", "o", s)
    s = re.sub(r"[ùúụủũưừứựửữ]", "u", s)
    s = re.sub(r"[ỳýỵỷỹ]", "y", s)
    s = re.sub(r"[đ]", "d", s)
    return s


def ensure_accounting_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS crm_re_project_cash_flow_lines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL REFERENCES crm_re_projects(id) ON DELETE CASCADE,
            flow_type TEXT NOT NULL DEFAULT 'outflow',
            category TEXT NOT NULL DEFAULT 'other',
            sub_category TEXT NOT NULL DEFAULT '',
            line_item TEXT NOT NULL DEFAULT '',
            amount_vnd INTEGER NOT NULL DEFAULT 0,
            period_month TEXT NOT NULL DEFAULT '',
            transaction_date TEXT NOT NULL DEFAULT '',
            due_date TEXT NOT NULL DEFAULT '',
            paid_date TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'planned',
            source_type TEXT NOT NULL DEFAULT 'manual',
            source_ref TEXT NOT NULL DEFAULT '',
            counterparty TEXT NOT NULL DEFAULT '',
            notes TEXT NOT NULL DEFAULT '',
            created_by TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_crm_re_cash_flow_project "
        "ON crm_re_project_cash_flow_lines(project_id, period_month, status)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_crm_re_cash_flow_category "
        "ON crm_re_project_cash_flow_lines(project_id, category, flow_type)"
    )
    cols = {r[1] for r in conn.execute("PRAGMA table_info(crm_re_project_budget_lines)").fetchall()}
    for col, ddl in (
        ("sub_category", "TEXT NOT NULL DEFAULT ''"),
        ("source_type", "TEXT NOT NULL DEFAULT 'manual'"),
        ("source_ref", "TEXT NOT NULL DEFAULT ''"),
    ):
        if col not in cols:
            conn.execute(f"ALTER TABLE crm_re_project_budget_lines ADD COLUMN {col} {ddl}")


def _cash_flow_row(row: sqlite3.Row | dict[str, Any]) -> dict[str, Any]:
    d = dict(row)
    ft = str(d.get("flow_type") or "outflow")
    if ft not in CASH_FLOW_TYPES:
        ft = "outflow"
    st = str(d.get("status") or "planned")
    if st not in CASH_FLOW_STATUSES:
        st = "planned"
    cat = str(d.get("category") or "other")
    sub = str(d.get("sub_category") or "")
    src = str(d.get("source_type") or "manual")
    return {
        "id": int(d["id"]),
        "project_id": int(d["project_id"]),
        "flow_type": ft,
        "flow_type_label": CASH_FLOW_TYPE_LABELS.get(ft, ft),
        "category": cat,
        "category_label": BUDGET_CATEGORY_LABELS.get(cat, cat),
        "sub_category": sub,
        "sub_category_label": MARKETING_SUB_CATEGORY_LABELS.get(sub, sub) if sub else "",
        "line_item": str(d.get("line_item") or ""),
        "amount_vnd": int(d.get("amount_vnd") or 0),
        "period_month": str(d.get("period_month") or ""),
        "transaction_date": str(d.get("transaction_date") or ""),
        "due_date": str(d.get("due_date") or ""),
        "paid_date": str(d.get("paid_date") or ""),
        "status": st,
        "status_label": CASH_FLOW_STATUS_LABELS.get(st, st),
        "source_type": src,
        "source_type_label": CASH_FLOW_SOURCE_LABELS.get(src, src),
        "source_ref": str(d.get("source_ref") or ""),
        "counterparty": str(d.get("counterparty") or ""),
        "notes": str(d.get("notes") or ""),
        "created_by": str(d.get("created_by") or ""),
        "created_at": str(d.get("created_at") or ""),
        "updated_at": str(d.get("updated_at") or ""),
    }


def list_cash_flow_lines(
    conn: sqlite3.Connection,
    project_id: int,
    *,
    flow_type: str | None = None,
    category: str | None = None,
    status: str | None = None,
) -> list[dict[str, Any]]:
    clauses = ["project_id = ?"]
    params: list[Any] = [int(project_id)]
    if flow_type and flow_type in CASH_FLOW_TYPES:
        clauses.append("flow_type = ?")
        params.append(flow_type)
    if category and category in BUDGET_CATEGORIES:
        clauses.append("category = ?")
        params.append(category)
    if status and status in CASH_FLOW_STATUSES:
        clauses.append("status = ?")
        params.append(status)
    where = " AND ".join(clauses)
    rows = conn.execute(
        f"SELECT * FROM crm_re_project_cash_flow_lines WHERE {where} "
        "ORDER BY COALESCE(NULLIF(transaction_date,''), period_month) DESC, id DESC",
        params,
    ).fetchall()
    return [_cash_flow_row(r) for r in rows]


def save_cash_flow_line(
    conn: sqlite3.Connection,
    project_id: int,
    payload: dict[str, Any],
    *,
    line_id: int | None = None,
    created_by: str = "",
    ts: str | None = None,
) -> dict[str, Any]:
    ts_val = ts or _now_ts()
    item = str(payload.get("line_item") or "").strip()
    if not item:
        raise ValueError("Thiếu mô tả dòng tiền.")
    ft = str(payload.get("flow_type") or "outflow")
    if ft not in CASH_FLOW_TYPES:
        ft = "outflow"
    cat = str(payload.get("category") or "other")
    if cat not in BUDGET_CATEGORIES:
        cat = "other"
    st = str(payload.get("status") or "planned")
    if st not in CASH_FLOW_STATUSES:
        st = "planned"
    src = str(payload.get("source_type") or "manual")
    if src not in CASH_FLOW_SOURCES:
        src = "manual"
    amount = max(0, int(payload.get("amount_vnd") or 0))
    if line_id:
        conn.execute(
            """
            UPDATE crm_re_project_cash_flow_lines SET
                flow_type=?, category=?, sub_category=?, line_item=?, amount_vnd=?,
                period_month=?, transaction_date=?, due_date=?, paid_date=?,
                status=?, source_type=?, source_ref=?, counterparty=?, notes=?, updated_at=?
            WHERE id=? AND project_id=?
            """,
            (
                ft,
                cat,
                str(payload.get("sub_category") or "")[:40],
                item[:200],
                amount,
                str(payload.get("period_month") or "")[:7],
                str(payload.get("transaction_date") or "")[:10],
                str(payload.get("due_date") or "")[:10],
                str(payload.get("paid_date") or "")[:10],
                st,
                src,
                str(payload.get("source_ref") or "")[:120],
                str(payload.get("counterparty") or "")[:120],
                str(payload.get("notes") or "")[:2000],
                ts_val,
                int(line_id),
                int(project_id),
            ),
        )
        rid = int(line_id)
    else:
        cur = conn.execute(
            """
            INSERT INTO crm_re_project_cash_flow_lines (
                project_id, flow_type, category, sub_category, line_item, amount_vnd,
                period_month, transaction_date, due_date, paid_date, status,
                source_type, source_ref, counterparty, notes, created_by, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                int(project_id),
                ft,
                cat,
                str(payload.get("sub_category") or "")[:40],
                item[:200],
                amount,
                str(payload.get("period_month") or "")[:7],
                str(payload.get("transaction_date") or "")[:10],
                str(payload.get("due_date") or "")[:10],
                str(payload.get("paid_date") or "")[:10],
                st,
                src,
                str(payload.get("source_ref") or "")[:120],
                str(payload.get("counterparty") or "")[:120],
                str(payload.get("notes") or "")[:2000],
                str(created_by or "")[:80],
                ts_val,
                ts_val,
            ),
        )
        rid = int(cur.lastrowid)
    row = conn.execute("SELECT * FROM crm_re_project_cash_flow_lines WHERE id = ?", (rid,)).fetchone()
    assert row is not None
    return _cash_flow_row(row)


def delete_cash_flow_line(conn: sqlite3.Connection, project_id: int, line_id: int) -> None:
    conn.execute(
        "DELETE FROM crm_re_project_cash_flow_lines WHERE id = ? AND project_id = ?",
        (int(line_id), int(project_id)),
    )


def _upsert_budget_by_ref(
    conn: sqlite3.Connection,
    project_id: int,
    *,
    category: str,
    line_item: str,
    planned_vnd: int,
    source_ref: str,
    source_type: str = "plan_sync",
    sub_category: str = "",
    ts: str,
) -> tuple[str, int]:
    """Trả về ('created'|'updated'|'skipped', line_id)."""
    ref = str(source_ref or "").strip()
    if not ref:
        return "skipped", 0
    existing = conn.execute(
        "SELECT id, planned_vnd FROM crm_re_project_budget_lines WHERE project_id = ? AND source_ref = ?",
        (int(project_id), ref),
    ).fetchone()
    if existing:
        eid = int(existing["id"])
        if int(existing["planned_vnd"] or 0) == int(planned_vnd):
            return "skipped", eid
        conn.execute(
            """
            UPDATE crm_re_project_budget_lines
            SET category=?, line_item=?, planned_vnd=?, source_type=?, sub_category=?, updated_at=?
            WHERE id=? AND project_id=?
            """,
            (category, line_item[:200], int(planned_vnd), source_type, sub_category[:40], ts, eid, int(project_id)),
        )
        return "updated", eid
    cur = conn.execute(
        """
        INSERT INTO crm_re_project_budget_lines (
            project_id, category, line_item, period_month, planned_vnd, actual_vnd,
            notes, sub_category, source_type, source_ref, created_at, updated_at
        ) VALUES (?, ?, ?, '', ?, 0, '', ?, ?, ?, ?, ?)
        """,
        (
            int(project_id),
            category,
            line_item[:200],
            int(planned_vnd),
            sub_category[:40],
            source_type,
            ref,
            ts,
            ts,
        ),
    )
    return "created", int(cur.lastrowid)


def sync_budget_from_plans(
    conn: sqlite3.Connection,
    project_id: int,
    *,
    ts: str | None = None,
) -> dict[str, Any]:
    proj = fetch_project(conn, project_id)
    if proj is None:
        raise ValueError("Không tìm thấy dự án.")
    ts_val = ts or _now_ts()
    bp = proj.get("business_plan") or default_business_plan()
    mp = proj.get("marketing_plan") or default_marketing_plan()
    sp = proj.get("sales_plan") or default_sales_plan()
    fp = bp.get("financial_plan") or {}
    created = updated = skipped = 0

    seeds: list[tuple[str, str, int, str, str]] = [
        ("revenue", "Doanh thu mục tiêu (KH kinh doanh)", int(bp.get("revenue_target_vnd") or 0), "plan:business:revenue", ""),
        ("revenue", "Doanh thu mục tiêu (KH bán hàng)", int(sp.get("revenue_target_vnd") or 0), "plan:sales:revenue", ""),
        ("cogs", "Chi phí đất (KH tài chính)", int(fp.get("land_cost_vnd") or 0), "plan:financial:land", ""),
        ("cogs", "Chi phí xây dựng (KH tài chính)", int(fp.get("construction_cost_vnd") or 0), "plan:financial:construction", ""),
        ("marketing", "Marketing (KH tài chính)", int(fp.get("marketing_cost_vnd") or 0), "plan:financial:marketing", ""),
        ("sales", "Chi phí bán hàng (KH tài chính)", int(fp.get("sales_cost_vnd") or 0), "plan:financial:sales", ""),
        ("marketing", "Ngân sách MKT tổng (KH marketing)", int(mp.get("budget_total_vnd") or 0), "plan:marketing:total", ""),
    ]
    for cat, label, amount, ref, sub in seeds:
        if amount <= 0:
            skipped += 1
            continue
        action, _ = _upsert_budget_by_ref(
            conn, project_id, category=cat, line_item=label, planned_vnd=amount, source_ref=ref, sub_category=sub, ts=ts_val
        )
        if action == "created":
            created += 1
        elif action == "updated":
            updated += 1
        else:
            skipped += 1

    for i, row in enumerate(mp.get("budget_breakdown") or []):
        if not isinstance(row, dict):
            continue
        channel = str(row.get("channel") or row.get("name") or f"Kênh {i + 1}")[:80]
        amount = int(row.get("amount_vnd") or row.get("budget_vnd") or 0)
        if amount <= 0:
            continue
        sub = str(row.get("sub_category") or "other")[:40]
        ref = f"plan:marketing:breakdown:{i}:{_norm(channel)[:30]}"
        action, _ = _upsert_budget_by_ref(
            conn,
            project_id,
            category="marketing",
            line_item=f"MKT — {channel}",
            planned_vnd=amount,
            source_ref=ref,
            sub_category=sub,
            ts=ts_val,
        )
        if action == "created":
            created += 1
        elif action == "updated":
            updated += 1

    return {"created": created, "updated": updated, "skipped": skipped}


def sync_revenue_from_inventory(
    conn: sqlite3.Connection,
    project_id: int,
    *,
    ts: str | None = None,
    created_by: str = "",
) -> dict[str, Any]:
    products = list_products(conn, project_id)
    sold = [p for p in products if str(p.get("status") or "") == "sold"]
    total = sum(int(p.get("net_price_vnd") or p.get("list_price_vnd") or 0) for p in sold)
    ts_val = ts or _now_ts()
    period = datetime.now().strftime("%Y-%m")

    existing = conn.execute(
        "SELECT id FROM crm_re_project_budget_lines WHERE project_id = ? AND source_ref = ?",
        (int(project_id), "inventory:revenue"),
    ).fetchone()
    if existing:
        conn.execute(
            """
            UPDATE crm_re_project_budget_lines
            SET actual_vnd=?, line_item=?, updated_at=?
            WHERE id=? AND project_id=?
            """,
            (total, f"Doanh thu từ tồn kho ({len(sold)} căn đã bán)", ts_val, int(existing["id"]), int(project_id)),
        )
        budget_action = "updated"
    else:
        conn.execute(
            """
            INSERT INTO crm_re_project_budget_lines (
                project_id, category, line_item, period_month, planned_vnd, actual_vnd,
                notes, sub_category, source_type, source_ref, created_at, updated_at
            ) VALUES (?, 'revenue', ?, ?, 0, ?, '', '', 'inventory', 'inventory:revenue', ?, ?)
            """,
            (int(project_id), f"Doanh thu từ tồn kho ({len(sold)} căn đã bán)", period, total, ts_val, ts_val),
        )
        budget_action = "created"

    cf_existing = conn.execute(
        "SELECT id FROM crm_re_project_cash_flow_lines WHERE project_id = ? AND source_ref = ?",
        (int(project_id), "inventory:revenue:inflow"),
    ).fetchone()
    cf_payload = {
        "flow_type": "inflow",
        "category": "revenue",
        "line_item": f"Thu từ bán hàng tồn kho ({len(sold)} căn)",
        "amount_vnd": total,
        "period_month": period,
        "status": "confirmed" if total > 0 else "planned",
        "source_type": "inventory",
        "source_ref": "inventory:revenue:inflow",
        "notes": f"Tự động từ {len(sold)} sản phẩm status=sold",
    }
    if cf_existing:
        save_cash_flow_line(conn, project_id, cf_payload, line_id=int(cf_existing["id"]), created_by=created_by, ts=ts_val)
        cash_action = "updated"
    elif total > 0:
        save_cash_flow_line(conn, project_id, cf_payload, created_by=created_by, ts=ts_val)
        cash_action = "created"
    else:
        cash_action = "skipped"

    return {
        "sold_units": len(sold),
        "revenue_vnd": total,
        "budget_action": budget_action,
        "cash_flow_action": cash_action,
    }


def import_cash_flow_csv(
    conn: sqlite3.Connection,
    project_id: int,
    csv_text: str,
    *,
    created_by: str = "",
    ts: str | None = None,
) -> dict[str, int]:
    ts_val = ts or _now_ts()
    reader = csv.DictReader(io.StringIO(csv_text.lstrip("\ufeff")))
    created = updated = errors = 0
    for row in reader:
        try:
            ft_raw = str(row.get("flow_type") or row.get("loai") or "outflow").strip().lower()
            ft = "inflow" if ft_raw in ("inflow", "thu", "in") else "outflow"
            cat = str(row.get("category") or row.get("hang_muc") or "other").strip().lower()
            if cat not in BUDGET_CATEGORIES:
                cat = "marketing" if "mkt" in cat or "marketing" in cat else "other"
            item = str(row.get("line_item") or row.get("mo_ta") or row.get("description") or "").strip()
            if not item:
                errors += 1
                continue
            amount = int(float(str(row.get("amount_vnd") or row.get("so_tien") or "0").replace(",", "") or 0))
            payload = {
                "flow_type": ft,
                "category": cat,
                "sub_category": str(row.get("sub_category") or row.get("kenh") or "")[:40],
                "line_item": item,
                "amount_vnd": amount,
                "period_month": str(row.get("period_month") or row.get("ky") or "")[:7],
                "transaction_date": str(row.get("transaction_date") or row.get("ngay") or "")[:10],
                "status": str(row.get("status") or "planned").strip().lower() or "planned",
                "counterparty": str(row.get("counterparty") or row.get("doi_tac") or "")[:120],
                "notes": str(row.get("notes") or row.get("ghi_chu") or "")[:2000],
                "source_type": "import",
            }
            ref = str(row.get("source_ref") or row.get("ma") or "").strip()
            if ref:
                payload["source_ref"] = ref
                ex = conn.execute(
                    "SELECT id FROM crm_re_project_cash_flow_lines WHERE project_id = ? AND source_ref = ?",
                    (int(project_id), ref),
                ).fetchone()
                if ex:
                    save_cash_flow_line(
                        conn, project_id, payload, line_id=int(ex["id"]), created_by=created_by, ts=ts_val
                    )
                    updated += 1
                    continue
            save_cash_flow_line(conn, project_id, payload, created_by=created_by, ts=ts_val)
            created += 1
        except (ValueError, TypeError):
            errors += 1
    return {"created": created, "updated": updated, "errors": errors}


def compute_accounting_dashboard(conn: sqlite3.Connection, project_id: int) -> dict[str, Any]:
    budget = list_budget_lines(conn, project_id)
    cash = list_cash_flow_lines(conn, project_id)
    products = list_products(conn, project_id)
    sold = [p for p in products if p.get("status") == "sold"]
    inventory_revenue = sum(int(p.get("net_price_vnd") or p.get("list_price_vnd") or 0) for p in sold)

    pnl_by_category: dict[str, dict[str, int]] = {}
    for cat in BUDGET_CATEGORIES:
        lines = [b for b in budget if b.get("category") == cat]
        pl = sum(int(b.get("planned_vnd") or 0) for b in lines)
        ac = sum(int(b.get("actual_vnd") or 0) for b in lines)
        pnl_by_category[cat] = {
            "category": cat,
            "category_label": BUDGET_CATEGORY_LABELS.get(cat, cat),
            "planned_vnd": pl,
            "actual_vnd": ac,
            "variance_vnd": ac - pl,
        }

    rev_pl = sum(v["planned_vnd"] for k, v in pnl_by_category.items() if k == "revenue")
    rev_ac = sum(v["actual_vnd"] for k, v in pnl_by_category.items() if k == "revenue")
    cost_pl = sum(v["planned_vnd"] for k, v in pnl_by_category.items() if k != "revenue")
    cost_ac = sum(v["actual_vnd"] for k, v in pnl_by_category.items() if k != "revenue")

    def _sum_cash(*, flow_type: str, statuses: tuple[str, ...]) -> int:
        return sum(
            int(c.get("amount_vnd") or 0)
            for c in cash
            if c.get("flow_type") == flow_type and c.get("status") in statuses
        )

    inflow_paid = _sum_cash(flow_type="inflow", statuses=("paid",))
    inflow_confirmed = _sum_cash(flow_type="inflow", statuses=("confirmed", "paid"))
    outflow_paid = _sum_cash(flow_type="outflow", statuses=("paid",))
    outflow_confirmed = _sum_cash(flow_type="outflow", statuses=("confirmed", "paid"))
    inflow_planned = _sum_cash(flow_type="inflow", statuses=("planned", "confirmed", "paid"))
    outflow_planned = _sum_cash(flow_type="outflow", statuses=("planned", "confirmed", "paid"))

    marketing_cash = [c for c in cash if c.get("category") == "marketing" and c.get("flow_type") == "outflow"]
    marketing_by_sub: dict[str, dict[str, Any]] = {}
    for c in marketing_cash:
        sub = str(c.get("sub_category") or "other")
        bucket = marketing_by_sub.setdefault(
            sub,
            {
                "sub_category": sub,
                "sub_category_label": MARKETING_SUB_CATEGORY_LABELS.get(sub, sub or "Khác"),
                "planned_vnd": 0,
                "paid_vnd": 0,
                "total_vnd": 0,
            },
        )
        amt = int(c.get("amount_vnd") or 0)
        bucket["total_vnd"] += amt
        if c.get("status") in ("planned", "confirmed"):
            bucket["planned_vnd"] += amt
        if c.get("status") == "paid":
            bucket["paid_vnd"] += amt

    mkt_budget_pl = pnl_by_category.get("marketing", {}).get("planned_vnd", 0)
    mkt_budget_ac = pnl_by_category.get("marketing", {}).get("actual_vnd", 0)
    mkt_cash_paid = sum(b.get("paid_vnd") or 0 for b in marketing_by_sub.values())
    mkt_cash_total = sum(b.get("total_vnd") or 0 for b in marketing_by_sub.values())

    monthly: dict[str, dict[str, int]] = {}
    for c in cash:
        if c.get("status") == "cancelled":
            continue
        mo = str(c.get("period_month") or c.get("transaction_date") or "")[:7] or "—"
        bucket = monthly.setdefault(mo, {"inflow_vnd": 0, "outflow_vnd": 0, "net_vnd": 0})
        amt = int(c.get("amount_vnd") or 0)
        if c.get("flow_type") == "inflow":
            bucket["inflow_vnd"] += amt
        else:
            bucket["outflow_vnd"] += amt
        bucket["net_vnd"] = bucket["inflow_vnd"] - bucket["outflow_vnd"]

    monthly_trend = [
        {"period_month": k, **v}
        for k, v in sorted(monthly.items(), key=lambda x: x[0])
    ]

    roi_denominator = mkt_cash_paid or mkt_budget_ac or mkt_budget_pl
    marketing_roi_pct = round((rev_ac - mkt_cash_paid) / roi_denominator * 100, 1) if roi_denominator else 0.0

    return {
        "pnl": {
            "revenue_planned_vnd": rev_pl,
            "revenue_actual_vnd": rev_ac,
            "cost_planned_vnd": cost_pl,
            "cost_actual_vnd": cost_ac,
            "profit_planned_vnd": rev_pl - cost_pl,
            "profit_actual_vnd": rev_ac - cost_ac,
            "by_category": list(pnl_by_category.values()),
        },
        "cash_flow": {
            "inflow_paid_vnd": inflow_paid,
            "inflow_confirmed_vnd": inflow_confirmed,
            "outflow_paid_vnd": outflow_paid,
            "outflow_confirmed_vnd": outflow_confirmed,
            "inflow_planned_vnd": inflow_planned,
            "outflow_planned_vnd": outflow_planned,
            "net_cash_paid_vnd": inflow_paid - outflow_paid,
            "net_cash_confirmed_vnd": inflow_confirmed - outflow_confirmed,
            "line_count": len(cash),
        },
        "marketing": {
            "budget_planned_vnd": mkt_budget_pl,
            "budget_actual_vnd": mkt_budget_ac,
            "cash_paid_vnd": mkt_cash_paid,
            "cash_total_vnd": mkt_cash_total,
            "roi_pct": marketing_roi_pct,
            "by_channel": sorted(marketing_by_sub.values(), key=lambda x: -int(x.get("total_vnd") or 0)),
        },
        "inventory": {
            "sold_units": len(sold),
            "revenue_vnd": inventory_revenue,
            "available_units": sum(1 for p in products if p.get("status") == "available"),
        },
        "monthly_trend": monthly_trend,
    }


def ai_project_finance_query(
    conn: sqlite3.Connection,
    question: str,
    *,
    re_project_id: int,
    created_by: str = "",
    ts: str = "",
) -> dict[str, Any]:
    """AI tra cứu P&L, dòng tiền, marketing theo dự án."""
    from crm_lead_ai import log_ai_action

    q = _norm(question)
    dash = compute_accounting_dashboard(conn, int(re_project_id))
    pnl = dash.get("pnl") or {}
    cf = dash.get("cash_flow") or {}
    mkt = dash.get("marketing") or {}
    inv = dash.get("inventory") or {}

    def _fmt(n: int) -> str:
        return f"{int(n):,}".replace(",", ".")

    answer = ""
    focus = "overview"
    fallback = False

    if any(k in q for k in ("marketing", "mkt", "quang cao", "ads", "chi phi marketing")):
        focus = "marketing"
        channels = mkt.get("by_channel") or []
        ch_txt = ""
        if channels:
            top = channels[:4]
            ch_txt = "; ".join(f"{c.get('sub_category_label')}: {_fmt(c.get('total_vnd') or 0)}" for c in top)
        answer = (
            f"**Marketing** — KH: {_fmt(mkt.get('budget_planned_vnd') or 0)} VND, "
            f"TT ngân sách: {_fmt(mkt.get('budget_actual_vnd') or 0)} VND, "
            f"đã chi (dòng tiền): {_fmt(mkt.get('cash_paid_vnd') or 0)} VND. "
            f"ROI ước tính: **{mkt.get('roi_pct', 0)}%**."
        )
        if ch_txt:
            answer += f" Phân bổ: {ch_txt}."
    elif any(k in q for k in ("dong tien", "cash flow", "thu chi", "tien mat", "luu chuyen")):
        focus = "cash_flow"
        answer = (
            f"**Dòng tiền** — Thu đã TT: {_fmt(cf.get('inflow_paid_vnd') or 0)} VND, "
            f"Chi đã TT: {_fmt(cf.get('outflow_paid_vnd') or 0)} VND, "
            f"**Ròng đã TT: {_fmt(cf.get('net_cash_paid_vnd') or 0)}** VND. "
            f"Dự kiến thu: {_fmt(cf.get('inflow_planned_vnd') or 0)}, chi: {_fmt(cf.get('outflow_planned_vnd') or 0)}."
        )
    elif any(k in q for k in ("loi nhuan", "profit", "p&l", "pl", "lai lo")):
        focus = "pnl"
        answer = (
            f"**P&L** — DT KH {_fmt(pnl.get('revenue_planned_vnd') or 0)} / TT {_fmt(pnl.get('revenue_actual_vnd') or 0)} VND. "
            f"Chi KH {_fmt(pnl.get('cost_planned_vnd') or 0)} / TT {_fmt(pnl.get('cost_actual_vnd') or 0)}. "
            f"**LN KH {_fmt(pnl.get('profit_planned_vnd') or 0)} / TT {_fmt(pnl.get('profit_actual_vnd') or 0)}** VND."
        )
    elif any(k in q for k in ("ton kho", "da ban", "doanh thu ban")):
        focus = "inventory"
        answer = (
            f"**Tồn kho** — {inv.get('sold_units', 0)} căn đã bán, "
            f"doanh thu ước tính {_fmt(inv.get('revenue_vnd') or 0)} VND "
            f"({inv.get('available_units', 0)} căn còn trống)."
        )
    elif any(k in q for k in ("so sanh", "chenh lech", "kh vs tt", "ke hoach vs")):
        focus = "variance"
        var_rev = int(pnl.get("revenue_actual_vnd") or 0) - int(pnl.get("revenue_planned_vnd") or 0)
        var_cost = int(pnl.get("cost_actual_vnd") or 0) - int(pnl.get("cost_planned_vnd") or 0)
        answer = (
            f"**Chênh lệch KH vs TT** — Doanh thu: {'+' if var_rev >= 0 else ''}{_fmt(var_rev)} VND, "
            f"Chi phí: {'+' if var_cost >= 0 else ''}{_fmt(var_cost)} VND. "
            f"LN TT so với KH: {'+' if (pnl.get('profit_actual_vnd') or 0) >= (pnl.get('profit_planned_vnd') or 0) else ''}"
            f"{_fmt(int(pnl.get('profit_actual_vnd') or 0) - int(pnl.get('profit_planned_vnd') or 0))} VND."
        )
    elif any(k in q for k in ("rui ro", "risk", "nguy co", "canh bao", "du doan rui ro")):
        focus = "risk"
        risk_pack = predict_financial_risks(conn, int(re_project_id), dash=dash)
        sm = risk_pack.get("summary") or {}
        top = (risk_pack.get("risks") or [])[:3]
        answer = (
            f"**Rủi ro tài chính** — Chỉ số: **{sm.get('risk_index_label')}** "
            f"({sm.get('total', 0)} rủi ro: {sm.get('critical', 0)} nghiêm trọng, {sm.get('high', 0)} cao)."
        )
        if top:
            answer += " Top: " + "; ".join(f"{r.get('title')} ({r.get('risk_level_label')})" for r in top) + "."
        else:
            answer += " Chưa phát hiện rủi ro đáng kẽ từ dữ liệu hiện tại."
        dash = {**dash, "risk_predictions": risk_pack}
    elif any(k in q for k in ("du bao", "du doan", "forecast", "runway", "3 thang", "tien do")):
        focus = "forecast"
        fc = forecast_financial_outlook(conn, int(re_project_id), dash=dash)
        answer = (
            f"**Dự báo {fc.get('months_ahead', 3)} tháng** — {fc.get('outlook_label')}. "
            f"Ròng TB/tháng: {_fmt(int(fc.get('avg_monthly_net_vnd') or 0))} VND. "
            f"LN dự phóng: {_fmt(int(fc.get('projected_profit_vnd') or 0))} VND."
        )
        if fc.get("runway_months") is not None:
            answer += f" Runway ~**{fc['runway_months']}** tháng."
        dash = {**dash, "forecast": fc}
    else:
        fallback = True
        answer = (
            f"Tổng quan kế toán dự án: DT TT {_fmt(pnl.get('revenue_actual_vnd') or 0)} VND, "
            f"LN TT {_fmt(pnl.get('profit_actual_vnd') or 0)} VND, "
            f"dòng tiền ròng {_fmt(cf.get('net_cash_paid_vnd') or 0)} VND, "
            f"MKT đã chi {_fmt(mkt.get('cash_paid_vnd') or 0)} VND. "
            "Hỏi cụ thể: «dòng tiền», «lợi nhuận», «chi phí marketing», «so sánh KH vs TT»."
        )

    out = {
        "answer": answer,
        "focus": focus,
        "dashboard": dash,
        "confidence": 0.85 if not fallback else 0.65,
        "fallback_used": fallback,
    }
    if ts:
        log_ai_action(
            conn,
            lead_id=None,
            action="project_finance_query",
            input_text=question[:500],
            output={"answer": answer, "focus": focus},
            confidence=out["confidence"],
            fallback_used=fallback,
            created_by=created_by,
            ts=ts,
        )
    return out


def _risk_level_from_score(probability_pct: float, impact_pct: float) -> str:
    score = float(probability_pct) * float(impact_pct) / 100.0
    if score >= 56:
        return "critical"
    if score >= 36:
        return "high"
    if score >= 16:
        return "medium"
    return "low"


def _risk_item(
    *,
    code: str,
    title: str,
    description: str,
    category: str = "finance",
    probability_pct: float,
    impact_pct: float,
    recommendation: str,
    indicators: list[str] | None = None,
) -> dict[str, Any]:
    lv = _risk_level_from_score(probability_pct, impact_pct)
    return {
        "code": code,
        "title": title,
        "description": description,
        "category": category,
        "category_label": {"finance": "Tài chính", "sales": "Bán hàng", "market": "Thị trường"}.get(category, category),
        "probability_pct": round(probability_pct, 1),
        "impact_pct": round(impact_pct, 1),
        "risk_level": lv,
        "risk_level_label": RISK_LEVEL_LABELS.get(lv, lv),
        "score": round(probability_pct * impact_pct / 100, 1),
        "recommendation": recommendation,
        "indicators": indicators or [],
    }


def forecast_financial_outlook(
    conn: sqlite3.Connection,
    project_id: int,
    *,
    months_ahead: int = 3,
    dash: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Dự báo dòng tiền / lợi nhuận dựa trên xu hướng gần nhất."""
    dash = dash or compute_accounting_dashboard(conn, project_id)
    pnl = dash.get("pnl") or {}
    cf = dash.get("cash_flow") or {}
    trend = [t for t in (dash.get("monthly_trend") or []) if str(t.get("period_month") or "") not in ("", "—")]
    recent = trend[-3:] if trend else []
    avg_in = round(sum(int(t.get("inflow_vnd") or 0) for t in recent) / len(recent)) if recent else 0
    avg_out = round(sum(int(t.get("outflow_vnd") or 0) for t in recent) / len(recent)) if recent else 0
    avg_net = avg_in - avg_out

    projections: list[dict[str, Any]] = []
    base_month = datetime.now().strftime("%Y-%m")
    y, m = (int(base_month[:4]), int(base_month[5:7])) if len(base_month) >= 7 else (datetime.now().year, datetime.now().month)
    for i in range(1, max(1, int(months_ahead)) + 1):
        nm = m + i
        ny = y + (nm - 1) // 12
        nm = ((nm - 1) % 12) + 1
        period = f"{ny:04d}-{nm:02d}"
        projections.append(
            {
                "period_month": period,
                "projected_inflow_vnd": avg_in,
                "projected_outflow_vnd": avg_out,
                "projected_net_vnd": avg_net,
            }
        )

    net_cash = int(cf.get("net_cash_paid_vnd") or 0)
    runway_months: float | None = None
    if avg_net < 0 and net_cash > 0:
        runway_months = round(net_cash / abs(avg_net), 1)
    elif avg_net < 0 and net_cash <= 0:
        runway_months = 0.0

    rev_gap = max(0, int(pnl.get("revenue_planned_vnd") or 0) - int(pnl.get("revenue_actual_vnd") or 0))
    profit_actual = int(pnl.get("profit_actual_vnd") or 0)
    projected_profit = profit_actual + avg_net * int(months_ahead)

    if avg_net < 0 and (runway_months is not None and runway_months < 2):
        outlook = "critical"
        outlook_label = "Nguy cơ cao — dòng tiền âm"
    elif avg_net < 0 or projected_profit < 0:
        outlook = "at_risk"
        outlook_label = "Cần theo dõi — áp lực tài chính"
    elif rev_gap > int(pnl.get("revenue_planned_vnd") or 0) * 0.3:
        outlook = "neutral"
        outlook_label = "Ổn định nhưng chưa đạt DT KH"
    else:
        outlook = "positive"
        outlook_label = "Tích cực"

    return {
        "months_ahead": int(months_ahead),
        "avg_monthly_inflow_vnd": avg_in,
        "avg_monthly_outflow_vnd": avg_out,
        "avg_monthly_net_vnd": avg_net,
        "projected_profit_vnd": projected_profit,
        "revenue_gap_vnd": rev_gap,
        "runway_months": runway_months,
        "outlook": outlook,
        "outlook_label": outlook_label,
        "projections": projections,
        "data_points": len(recent),
    }


def predict_financial_risks(
    conn: sqlite3.Connection,
    project_id: int,
    *,
    dash: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Phân tích rule-based + dự báo — rủi ro tài chính thông minh."""
    proj = fetch_project(conn, project_id)
    if proj is None:
        raise ValueError("Không tìm thấy dự án.")
    dash = dash or compute_accounting_dashboard(conn, project_id)
    forecast = forecast_financial_outlook(conn, project_id, dash=dash)
    pnl = dash.get("pnl") or {}
    cf = dash.get("cash_flow") or {}
    mkt = dash.get("marketing") or {}
    inv = dash.get("inventory") or {}
    sp = proj.get("sales_plan") or default_sales_plan()

    rev_pl = int(pnl.get("revenue_planned_vnd") or 0)
    rev_ac = int(pnl.get("revenue_actual_vnd") or 0)
    cost_pl = int(pnl.get("cost_planned_vnd") or 0)
    cost_ac = int(pnl.get("cost_actual_vnd") or 0)
    profit_pl = int(pnl.get("profit_planned_vnd") or 0)
    profit_ac = int(pnl.get("profit_actual_vnd") or 0)

    risks: list[dict[str, Any]] = []

    net_paid = int(cf.get("net_cash_paid_vnd") or 0)
    if net_paid < 0:
        risks.append(
            _risk_item(
                code="cash_negative",
                title="Dòng tiền ròng âm",
                description=f"Dòng tiền đã thanh toán âm {_fmt_vnd(abs(net_paid))} VND — chi vượt thu.",
                probability_pct=85,
                impact_pct=90,
                recommendation="Rà soát chi phí không cần thiết, đẩy thu cọc/đợt thanh toán, hoãn chi MKT không hiệu quả.",
                indicators=[f"Ròng TT: {net_paid:,} VND"],
            )
        )

    gap_planned = int(cf.get("inflow_planned_vnd") or 0) - int(cf.get("outflow_planned_vnd") or 0)
    if gap_planned < 0:
        risks.append(
            _risk_item(
                code="cash_gap_planned",
                title="Thiếu hụt dòng tiền dự kiến",
                description="Tổng chi dự kiến vượt thu dự kiến trong sổ dòng tiền.",
                probability_pct=70,
                impact_pct=75,
                recommendation="Lập lịch thu theo milestone bán hàng; đối soát cam kết chi với ngân sách đã duyệt.",
                indicators=[f"Chênh thu-chi KH: {gap_planned:,} VND"],
            )
        )

    if rev_pl > 0 and rev_ac < rev_pl * 0.65:
        pct = round((1 - rev_ac / rev_pl) * 100, 1)
        risks.append(
            _risk_item(
                code="revenue_shortfall",
                title="Doanh thu chậm so với kế hoạch",
                description=f"DT thực tế chỉ đạt {round(rev_ac / rev_pl * 100, 1)}% kế hoạch (thiếu ~{pct}%).",
                category="sales",
                probability_pct=min(95, 50 + pct / 2),
                impact_pct=80,
                recommendation="Tăng tốc chốt deal, review giá/chính sách, đồng bộ KPI sales với tồn kho còn hàng.",
                indicators=[f"DT KH: {rev_pl:,}", f"DT TT: {rev_ac:,}"],
            )
        )

    if cost_pl > 0 and cost_ac > cost_pl * 1.12:
        over = round((cost_ac / cost_pl - 1) * 100, 1)
        risks.append(
            _risk_item(
                code="cost_overrun",
                title="Chi phí vượt ngân sách",
                description=f"Chi phí thực tế vượt kế hoạch ~{over}%.",
                probability_pct=min(90, 40 + over),
                impact_pct=70,
                recommendation="Freeze chi không gắn doanh thu; phân loại COGS vs OPEX; báo cáo variance hàng tuần.",
                indicators=[f"Chi KH: {cost_pl:,}", f"Chi TT: {cost_ac:,}"],
            )
        )

    mkt_pl = int(mkt.get("budget_planned_vnd") or 0)
    mkt_paid = int(mkt.get("cash_paid_vnd") or 0)
    if mkt_pl > 0 and mkt_paid > mkt_pl * 1.1:
        risks.append(
            _risk_item(
                code="marketing_overspend",
                title="Chi marketing vượt ngân sách",
                description=f"Đã chi MKT {_fmt_vnd(mkt_paid)} so với KH {_fmt_vnd(mkt_pl)}.",
                category="market",
                probability_pct=75,
                impact_pct=55,
                recommendation="Tạm dừng kênh ROI thấp; A/B test creative; gắn chi MKT với CPL/CAC thực tế.",
                indicators=[f"MKT chi TT: {mkt_paid:,}", f"MKT KH: {mkt_pl:,}"],
            )
        )

    if mkt_paid > 0 and float(mkt.get("roi_pct") or 0) < 0:
        risks.append(
            _risk_item(
                code="marketing_negative_roi",
                title="ROI marketing âm",
                description=f"ROI marketing ước tính {mkt.get('roi_pct')} — chi MKT chưa tạo DT tương xứng.",
                category="market",
                probability_pct=65,
                impact_pct=60,
                recommendation="Đo lại attribution lead→deal; tối ưu funnel trước khi tăng ngân sách quảng cáo.",
                indicators=[f"ROI: {mkt.get('roi_pct')}%"],
            )
        )

    if profit_pl > 0 and profit_ac < profit_pl * 0.45:
        risks.append(
            _risk_item(
                code="profit_erosion",
                title="Lợi nhuận suy giảm so với KH",
                description=f"LN thực tế {_fmt_vnd(profit_ac)} so với KH {_fmt_vnd(profit_pl)}.",
                probability_pct=70,
                impact_pct=85,
                recommendation="Phân tích biên lợi nhuận theo phân khu; điều chỉnh mix sản phẩm bán; kiểm soát chi cố định.",
                indicators=[f"LN KH: {profit_pl:,}", f"LN TT: {profit_ac:,}"],
            )
        )

    units_target = int(sp.get("units_target") or 0)
    sold = int(inv.get("sold_units") or 0)
    total_units = int(proj.get("total_units") or 0)
    if units_target > 0 and sold < units_target * 0.35:
        risks.append(
            _risk_item(
                code="sales_velocity_low",
                title="Tốc độ bán chậm",
                description=f"Chỉ bán {sold}/{units_target} căn mục tiêu KH bán hàng.",
                category="sales",
                probability_pct=60,
                impact_pct=75,
                recommendation="Review pipeline lead, chính sách hoa hồng, event mở bán; đối chiếu giá với đối thủ.",
                indicators=[f"Đã bán: {sold}", f"Mục tiêu KH: {units_target}"],
            )
        )
    elif total_units > 0 and sold / total_units < 0.08 and str(proj.get("status") or "") in ("presale", "selling", "active"):
        risks.append(
            _risk_item(
                code="sell_through_low",
                title="Tiến độ bán/tồn kho thấp",
                description=f"Sell-through {round(sold / total_units * 100, 1)}% ({sold}/{total_units} căn).",
                category="sales",
                probability_pct=55,
                impact_pct=70,
                recommendation="Kích hoạt chiến dịch ưu đãi phân khu tồn cao; training đội sales theo segment.",
                indicators=[f"Đã bán: {sold}/{total_units}"],
            )
        )

    trend = [t for t in (dash.get("monthly_trend") or []) if str(t.get("period_month") or "") not in ("", "—")]
    if len(trend) >= 2:
        last_two = trend[-2:]
        if all(int(t.get("net_vnd") or 0) < 0 for t in last_two):
            risks.append(
                _risk_item(
                    code="cash_trend_declining",
                    title="Xu hướng dòng tiền âm liên tiếp",
                    description="2 tháng gần nhất dòng tiền ròng âm — xu hướng xấu.",
                    probability_pct=72,
                    impact_pct=68,
                    recommendation="Họp cash committee tuần; ưu tiên thu nợ/cọc; cắt chi OPEX không thiết yếu.",
                    indicators=[f"{t.get('period_month')}: {t.get('net_vnd'):,}" for t in last_two],
                )
            )

    runway = forecast.get("runway_months")
    if runway is not None and runway < 3:
        risks.append(
            _risk_item(
                code="cash_runway_short",
                title="Runway dòng tiền ngắn",
                description=f"Ước tính còn ~{runway} tháng trước khi cạn dòng tiền (theo burn rate hiện tại).",
                probability_pct=80 if runway == 0 else 68,
                impact_pct=92,
                recommendation="Kế hoạch huy động vốn ngắn hạn; đàm phán lùi chi xây dựng/MKT; đẩy thu đợt 1 khách hàng.",
                indicators=[f"Runway: {runway} tháng", f"Burn TB: {forecast.get('avg_monthly_net_vnd'):,}/tháng"],
            )
        )

    risks.sort(key=lambda r: (-float(r.get("score") or 0), r.get("code", "")))
    level_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    for r in risks:
        lv = str(r.get("risk_level") or "medium")
        if lv in level_counts:
            level_counts[lv] += 1
    top_score = float(risks[0]["score"]) if risks else 0.0
    if level_counts["critical"] >= 1 or top_score >= 50:
        index_label = "Rất cao"
        risk_index = "critical"
    elif level_counts["high"] >= 2 or top_score >= 35:
        index_label = "Cao"
        risk_index = "high"
    elif risks:
        index_label = "Trung bình"
        risk_index = "medium"
    else:
        index_label = "Thấp"
        risk_index = "low"

    return {
        "risks": risks,
        "forecast": forecast,
        "summary": {
            "total": len(risks),
            "critical": level_counts["critical"],
            "high": level_counts["high"],
            "medium": level_counts["medium"],
            "low": level_counts["low"],
            "risk_index": risk_index,
            "risk_index_label": index_label,
            "top_score": top_score,
        },
    }


def _fmt_vnd(n: int) -> str:
    return f"{int(n):,}".replace(",", ".")


def apply_predicted_risks_to_register(
    conn: sqlite3.Connection,
    project_id: int,
    *,
    codes: list[str] | None = None,
    ts: str | None = None,
) -> dict[str, int]:
    """Ghi rủi ro dự đoán vào Risk Register (bỏ qua trùng tiêu đề)."""
    ts_val = ts or _now_ts()
    pack = predict_financial_risks(conn, project_id)
    want = {c.strip() for c in (codes or []) if str(c).strip()}
    existing = {str(r.get("title") or "").strip() for r in list_risks(conn, project_id)}
    applied = skipped = 0
    for risk in pack.get("risks") or []:
        code = str(risk.get("code") or "")
        if want and code not in want:
            continue
        title = str(risk.get("title") or "").strip()
        if not title or title in existing:
            skipped += 1
            continue
        desc = str(risk.get("description") or "")
        marker = f"[AI-KT:{code}]"
        if marker not in desc:
            desc = f"{desc}\n{marker}"
        save_risk(
            conn,
            project_id,
            {
                "category": risk.get("category") or "finance",
                "title": title,
                "description": desc[:4000],
                "probability_pct": risk.get("probability_pct"),
                "impact_pct": risk.get("impact_pct"),
                "risk_level": risk.get("risk_level"),
                "mitigation": str(risk.get("recommendation") or "")[:2000],
                "status": "open",
            },
            ts=ts_val,
        )
        existing.add(title)
        applied += 1
    return {"applied": applied, "skipped": skipped}


def accounting_export_summary_rows(
    proj: dict[str, Any],
    dash: dict[str, Any],
    forecast: dict[str, Any],
    risk_pack: dict[str, Any],
) -> list[list[Any]]:
    pnl = dash.get("pnl") or {}
    cf = dash.get("cash_flow") or {}
    mkt = dash.get("marketing") or {}
    sm = risk_pack.get("summary") or {}
    return [
        ["Dự án", proj.get("name")],
        ["Mã", proj.get("code")],
        ["DT kế hoạch (VND)", pnl.get("revenue_planned_vnd")],
        ["DT thực tế (VND)", pnl.get("revenue_actual_vnd")],
        ["Chi KH (VND)", pnl.get("cost_planned_vnd")],
        ["Chi TT (VND)", pnl.get("cost_actual_vnd")],
        ["LN kế hoạch (VND)", pnl.get("profit_planned_vnd")],
        ["LN thực tế (VND)", pnl.get("profit_actual_vnd")],
        ["Thu đã TT (VND)", cf.get("inflow_paid_vnd")],
        ["Chi đã TT (VND)", cf.get("outflow_paid_vnd")],
        ["Dòng tiền ròng TT (VND)", cf.get("net_cash_paid_vnd")],
        ["MKT đã chi (VND)", mkt.get("cash_paid_vnd")],
        ["MKT ROI (%)", mkt.get("roi_pct")],
        ["Chỉ số rủi ro", sm.get("risk_index_label")],
        ["Số rủi ro dự đoán", sm.get("total")],
        ["Dự báo — outlook", forecast.get("outlook_label")],
        ["Dự báo — LN 3 tháng (VND)", forecast.get("projected_profit_vnd")],
        ["Dự báo — runway (tháng)", forecast.get("runway_months")],
    ]


def accounting_export_cash_flow_rows(lines: list[dict[str, Any]]) -> tuple[list[str], list[list[Any]]]:
    headers = [
        "Mô tả", "Thu/Chi", "Hạng mục", "Kênh MKT", "Số tiền", "Kỳ", "Ngày GD",
        "Trạng thái", "Đối tác", "Nguồn", "Ghi chú",
    ]
    rows = [
        [
            c.get("line_item"),
            c.get("flow_type_label"),
            c.get("category_label"),
            c.get("sub_category_label"),
            c.get("amount_vnd"),
            c.get("period_month"),
            c.get("transaction_date"),
            c.get("status_label"),
            c.get("counterparty"),
            c.get("source_type_label"),
            c.get("notes"),
        ]
        for c in lines
    ]
    return headers, rows


def accounting_export_marketing_rows(mkt: dict[str, Any]) -> tuple[list[str], list[list[Any]]]:
    headers = ["Kênh", "Dự kiến (VND)", "Đã chi TT (VND)", "Tổng ghi nhận (VND)"]
    rows = [
        [c.get("sub_category_label"), c.get("planned_vnd"), c.get("paid_vnd"), c.get("total_vnd")]
        for c in (mkt.get("by_channel") or [])
    ]
    return headers, rows


def accounting_export_trend_rows(trend: list[dict[str, Any]]) -> tuple[list[str], list[list[Any]]]:
    headers = ["Kỳ", "Thu (VND)", "Chi (VND)", "Ròng (VND)"]
    rows = [[t.get("period_month"), t.get("inflow_vnd"), t.get("outflow_vnd"), t.get("net_vnd")] for t in trend]
    return headers, rows


def accounting_export_forecast_rows(forecast: dict[str, Any]) -> tuple[list[str], list[list[Any]]]:
    headers = ["Kỳ", "Thu dự báo", "Chi dự báo", "Ròng dự báo"]
    rows = [
        [p.get("period_month"), p.get("projected_inflow_vnd"), p.get("projected_outflow_vnd"), p.get("projected_net_vnd")]
        for p in (forecast.get("projections") or [])
    ]
    return headers, rows


def accounting_export_risk_rows(risks: list[dict[str, Any]]) -> tuple[list[str], list[list[Any]]]:
    headers = [
        "Mã", "Tiêu đề", "Mô tả", "Loại", "Xác suất (%)", "Tác động (%)",
        "Mức", "Điểm", "Khuyến nghị", "Chỉ báo",
    ]
    rows = [
        [
            r.get("code"),
            r.get("title"),
            r.get("description"),
            r.get("category_label"),
            r.get("probability_pct"),
            r.get("impact_pct"),
            r.get("risk_level_label"),
            r.get("score"),
            r.get("recommendation"),
            "; ".join(r.get("indicators") or []),
        ]
        for r in risks
    ]
    return headers, rows


def build_accounting_export_sheets(conn: sqlite3.Connection, project_id: int) -> list[tuple[str, list[str], list[list[Any]]]]:
    proj = fetch_project(conn, project_id)
    if proj is None:
        raise ValueError("Không tìm thấy dự án.")
    dash = compute_accounting_dashboard(conn, project_id)
    forecast = forecast_financial_outlook(conn, project_id, dash=dash)
    risk_pack = predict_financial_risks(conn, project_id, dash=dash)
    budget = list_budget_lines(conn, project_id)
    cash = list_cash_flow_lines(conn, project_id)
    from crm_re_projects import project_export_budget_rows

    bud_h, bud_r = project_export_budget_rows(budget)
    cf_h, cf_r = accounting_export_cash_flow_rows(cash)
    mkt_h, mkt_r = accounting_export_marketing_rows(dash.get("marketing") or {})
    tr_h, tr_r = accounting_export_trend_rows(dash.get("monthly_trend") or [])
    fc_h, fc_r = accounting_export_forecast_rows(forecast)
    rk_h, rk_r = accounting_export_risk_rows(risk_pack.get("risks") or [])
    summary = accounting_export_summary_rows(proj, dash, forecast, risk_pack)
    return [
        ("Tổng quan KT", ["Trường", "Giá trị"], summary),
        ("P&L Ngân sách", bud_h, bud_r),
        ("Dòng tiền", cf_h, cf_r),
        ("Marketing", mkt_h, mkt_r),
        ("Xu hướng", tr_h, tr_r),
        ("Dự báo", fc_h, fc_r),
        ("Rủi ro AI", rk_h, rk_r),
    ]
