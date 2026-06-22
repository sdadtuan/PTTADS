"""CRM Kinh doanh — kế hoạch, chỉ tiêu, đối tác, đào tạo, thị trường, giao dịch."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from typing import Any

from crm_sales_pipeline import (
    SALES_PIPELINE_LABELS_VI,
    SALES_PIPELINE_STAGES,
    TERMINAL_STAGES,
    compute_funnel_stats,
    normalize_pipeline_stage,
    pipeline_stage_label,
)

PLAN_STATUSES = ("draft", "active", "closed")
PLAN_STATUS_LABELS_VI = {
    "draft": "Nháp",
    "active": "Đang triển khai",
    "closed": "Đã đóng",
}

PARTNER_TYPES = ("dai_ly", "ctv", "doi_tac")
PARTNER_TYPE_LABELS_VI = {
    "dai_ly": "Đại lý",
    "ctv": "Cộng tác viên",
    "doi_tac": "Đối tác",
}

PARTNER_STATUSES = ("active", "inactive", "pending")
PARTNER_STATUS_LABELS_VI = {
    "active": "Hoạt động",
    "inactive": "Ngưng",
    "pending": "Chờ duyệt",
}

TRAINING_STATUSES = ("planned", "done", "cancelled")
TRAINING_STATUS_LABELS_VI = {
    "planned": "Dự kiến",
    "done": "Đã tổ chức",
    "cancelled": "Hủy",
}

MARKET_STATUSES = ("draft", "published", "archived")
MARKET_STATUS_LABELS_VI = {
    "draft": "Nháp",
    "published": "Đã ban hành",
    "archived": "Lưu trữ",
}

TX_TYPES = ("ban", "mua", "cho_thue")
TX_TYPE_LABELS_VI = {
    "ban": "Bán",
    "mua": "Mua",
    "cho_thue": "Cho thuê",
}

TX_STAGES = ("tu_van", "dam_phan", "hop_dong", "thu_tuc", "hoan_tat")
TX_STAGE_LABELS_VI = {
    "tu_van": "Tư vấn",
    "dam_phan": "Đàm phán",
    "hop_dong": "Hợp đồng",
    "thu_tuc": "Thủ tục",
    "hoan_tat": "Hoàn tất",
}

TARGET_TYPES = ("revenue", "deals", "leads", "kpi")
TARGET_TYPE_LABELS_VI = {
    "revenue": "Doanh thu",
    "deals": "Số deal chốt",
    "leads": "Lead mới",
    "kpi": "KPI khác",
}

SALES_SECTION_IDS = (
    "crm_sales_overview",
    "crm_sales_plans",
    "crm_sales_funnel",
    "crm_sales_prospects",
    "crm_sales_deals",
    "crm_sales_training",
    "crm_sales_market",
    "crm_sales_reports",
)


def _now_ts() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def ensure_sales_hub_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS crm_sales_plans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            fiscal_year INTEGER NOT NULL DEFAULT 0,
            period_start TEXT NOT NULL DEFAULT '',
            period_end TEXT NOT NULL DEFAULT '',
            revenue_target_vnd INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'draft',
            summary TEXT NOT NULL DEFAULT '',
            strategy_notes TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS crm_sales_targets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            plan_id INTEGER REFERENCES crm_sales_plans(id) ON DELETE SET NULL,
            staff_id INTEGER REFERENCES crm_staff(id) ON DELETE SET NULL,
            department_id INTEGER REFERENCES crm_departments(id) ON DELETE SET NULL,
            target_type TEXT NOT NULL DEFAULT 'revenue',
            metric_name TEXT NOT NULL DEFAULT '',
            target_value REAL NOT NULL DEFAULT 0,
            actual_value REAL NOT NULL DEFAULT 0,
            unit TEXT NOT NULL DEFAULT 'vnd',
            period_month TEXT NOT NULL DEFAULT '',
            notes TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS crm_sales_partners (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            partner_type TEXT NOT NULL DEFAULT 'ctv',
            name TEXT NOT NULL,
            phone TEXT NOT NULL DEFAULT '',
            email TEXT NOT NULL DEFAULT '',
            company TEXT NOT NULL DEFAULT '',
            territory TEXT NOT NULL DEFAULT '',
            commission_pct REAL,
            status TEXT NOT NULL DEFAULT 'active',
            assigned_staff_id INTEGER REFERENCES crm_staff(id) ON DELETE SET NULL,
            notes TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS crm_sales_trainings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            training_date TEXT NOT NULL DEFAULT '',
            trainer_name TEXT NOT NULL DEFAULT '',
            topic TEXT NOT NULL DEFAULT '',
            content_summary TEXT NOT NULL DEFAULT '',
            materials_url TEXT NOT NULL DEFAULT '',
            attendee_staff_ids TEXT NOT NULL DEFAULT '[]',
            status TEXT NOT NULL DEFAULT 'planned',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS crm_sales_market_research (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            research_date TEXT NOT NULL DEFAULT '',
            area TEXT NOT NULL DEFAULT '',
            property_type TEXT NOT NULL DEFAULT '',
            competitor_notes TEXT NOT NULL DEFAULT '',
            price_analysis TEXT NOT NULL DEFAULT '',
            strategy_proposal TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'draft',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS crm_sales_transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            case_id INTEGER REFERENCES crm_cases(id) ON DELETE SET NULL,
            contract_id INTEGER REFERENCES crm_contracts(id) ON DELETE SET NULL,
            customer_id INTEGER REFERENCES crm_customers(id) ON DELETE SET NULL,
            transaction_type TEXT NOT NULL DEFAULT 'ban',
            property_ref TEXT NOT NULL DEFAULT '',
            stage TEXT NOT NULL DEFAULT 'tu_van',
            deal_value_vnd INTEGER NOT NULL DEFAULT 0,
            assigned_staff_id INTEGER REFERENCES crm_staff(id) ON DELETE SET NULL,
            notes TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_crm_sales_plans_year ON crm_sales_plans(fiscal_year, status)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_crm_sales_targets_plan ON crm_sales_targets(plan_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_crm_sales_partners_type ON crm_sales_partners(partner_type, status)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_crm_sales_tx_stage ON crm_sales_transactions(stage, transaction_type)"
    )
    _seed_sales_demo_if_empty(conn)
    seed_sales_section_permissions(conn)


def _seed_sales_demo_if_empty(conn: sqlite3.Connection) -> None:
    n = conn.execute("SELECT COUNT(*) AS n FROM crm_sales_plans").fetchone()
    if not n or int(n["n"]) > 0:
        return
    ts = _now_ts()
    y = datetime.now().year
    conn.execute(
        """
        INSERT INTO crm_sales_plans (
            title, fiscal_year, period_start, period_end, revenue_target_vnd,
            status, summary, strategy_notes, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            f"Kế hoạch kinh doanh {y}",
            y,
            f"{y}-01-01",
            f"{y}-12-31",
            5_000_000_000,
            "active",
            "Chỉ tiêu doanh thu và phát triển khách hàng BĐS năm nay.",
            "Tập trung lead digital, đại lý khu vực, chăm sóc pipeline SQL trở lên.",
            ts,
            ts,
        ),
    )


def seed_sales_section_permissions(conn: sqlite3.Connection) -> None:
    """Bổ sung quyền section mới cho chức vụ KD (DB đã có permissions)."""
    try:
        from admin_page_permissions import default_grants_for_position
    except ImportError:
        return
    pos_rows = conn.execute(
        "SELECT id, code FROM crm_positions WHERE active = 1 AND code IN ('KD-01', 'VH-01', 'CSKH-01')"
    ).fetchall()
    for prow in pos_rows:
        pid = int(prow["id"])
        pcode = str(prow["code"])
        defaults = default_grants_for_position(pcode)
        for sid in SALES_SECTION_IDS:
            for act in defaults.get(sid, ()):
                conn.execute(
                    """
                    INSERT OR IGNORE INTO crm_position_section_permissions
                    (position_id, section_id, action)
                    VALUES (?, ?, ?)
                    """,
                    (pid, sid, act),
                )


def _parse_attendee_ids(raw: Any) -> list[int]:
    if isinstance(raw, list):
        out = []
        for x in raw:
            try:
                out.append(int(x))
            except (TypeError, ValueError):
                pass
        return out
    if isinstance(raw, str) and raw.strip():
        try:
            data = json.loads(raw)
            return _parse_attendee_ids(data)
        except json.JSONDecodeError:
            pass
    return []


def _row_plan(d: dict[str, Any]) -> dict[str, Any]:
    st = str(d.get("status") or "draft")
    d["status_label"] = PLAN_STATUS_LABELS_VI.get(st, st)
    return d


def _row_partner(d: dict[str, Any]) -> dict[str, Any]:
    pt = str(d.get("partner_type") or "ctv")
    st = str(d.get("status") or "active")
    d["partner_type_label"] = PARTNER_TYPE_LABELS_VI.get(pt, pt)
    d["status_label"] = PARTNER_STATUS_LABELS_VI.get(st, st)
    return d


def _row_training(d: dict[str, Any]) -> dict[str, Any]:
    st = str(d.get("status") or "planned")
    d["status_label"] = TRAINING_STATUS_LABELS_VI.get(st, st)
    ids = _parse_attendee_ids(d.get("attendee_staff_ids"))
    d["attendee_staff_ids_list"] = ids
    return d


def _row_market(d: dict[str, Any]) -> dict[str, Any]:
    st = str(d.get("status") or "draft")
    d["status_label"] = MARKET_STATUS_LABELS_VI.get(st, st)
    return d


def _row_tx(d: dict[str, Any]) -> dict[str, Any]:
    tt = str(d.get("transaction_type") or "ban")
    st = str(d.get("stage") or "tu_van")
    d["transaction_type_label"] = TX_TYPE_LABELS_VI.get(tt, tt)
    d["stage_label"] = TX_STAGE_LABELS_VI.get(st, st)
    return d


def _row_target(d: dict[str, Any]) -> dict[str, Any]:
    tt = str(d.get("target_type") or "revenue")
    d["target_type_label"] = TARGET_TYPE_LABELS_VI.get(tt, tt)
    tv = float(d.get("target_value") or 0)
    av = float(d.get("actual_value") or 0)
    d["achievement_pct"] = round(100.0 * av / tv, 1) if tv > 0 else None
    return d


def fetch_sales_summary(conn: sqlite3.Connection) -> dict[str, Any]:
    funnel = compute_funnel_stats(conn)
    plan_row = conn.execute(
        """
        SELECT * FROM crm_sales_plans
        WHERE status = 'active'
        ORDER BY fiscal_year DESC, id DESC LIMIT 1
        """
    ).fetchone()
    plan = dict(plan_row) if plan_row else None
    if plan:
        plan = _row_plan(plan)
        tgt = conn.execute(
            """
            SELECT COALESCE(SUM(target_value), 0) AS t,
                   COALESCE(SUM(actual_value), 0) AS a
            FROM crm_sales_targets WHERE plan_id = ?
            """,
            (plan["id"],),
        ).fetchone()
        plan["targets_sum"] = float(tgt["t"]) if tgt else 0
        plan["actuals_sum"] = float(tgt["a"]) if tgt else 0
        rev = int(plan.get("revenue_target_vnd") or 0)
        won = funnel.get("totals", {}).get("won") or 0
        plan["revenue_progress_pct"] = round(100.0 * won / rev, 1) if rev > 0 else None

    partners_active = conn.execute(
        "SELECT COUNT(*) AS n FROM crm_sales_partners WHERE status = 'active'"
    ).fetchone()
    tx_open = conn.execute(
        """
        SELECT COUNT(*) AS n FROM crm_sales_transactions
        WHERE stage NOT IN ('hoan_tat')
        """
    ).fetchone()
    trainings_upcoming = conn.execute(
        """
        SELECT COUNT(*) AS n FROM crm_sales_trainings
        WHERE status = 'planned' AND training_date >= date('now')
        """
    ).fetchone()
    market_published = conn.execute(
        "SELECT COUNT(*) AS n FROM crm_sales_market_research WHERE status = 'published'"
    ).fetchone()

    kd_staff = conn.execute(
        """
        SELECT COUNT(*) AS n FROM crm_staff st
        JOIN crm_departments d ON d.id = st.department_id
        WHERE st.active = 1 AND (lower(d.code) = 'kd' OR d.name LIKE '%kinh doanh%')
        """
    ).fetchone()

    return {
        "funnel": funnel,
        "active_plan": plan,
        "counts": {
            "partners_active": int(partners_active["n"]) if partners_active else 0,
            "transactions_open": int(tx_open["n"]) if tx_open else 0,
            "trainings_upcoming": int(trainings_upcoming["n"]) if trainings_upcoming else 0,
            "market_reports": int(market_published["n"]) if market_published else 0,
            "kd_staff": int(kd_staff["n"]) if kd_staff else 0,
        },
        "pipeline_labels": SALES_PIPELINE_LABELS_VI,
        "pipeline_stages": list(SALES_PIPELINE_STAGES),
    }


def list_plans(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT * FROM crm_sales_plans ORDER BY fiscal_year DESC, id DESC"
    ).fetchall()
    return [_row_plan(dict(r)) for r in rows]


def list_targets(conn: sqlite3.Connection, plan_id: int | None = None) -> list[dict[str, Any]]:
    if plan_id:
        rows = conn.execute(
            """
            SELECT t.*, st.name AS staff_name, d.name AS department_name
            FROM crm_sales_targets t
            LEFT JOIN crm_staff st ON st.id = t.staff_id
            LEFT JOIN crm_departments d ON d.id = t.department_id
            WHERE t.plan_id = ?
            ORDER BY t.period_month DESC, t.id DESC
            """,
            (plan_id,),
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT t.*, st.name AS staff_name, d.name AS department_name
            FROM crm_sales_targets t
            LEFT JOIN crm_staff st ON st.id = t.staff_id
            LEFT JOIN crm_departments d ON d.id = t.department_id
            ORDER BY t.id DESC LIMIT 200
            """
        ).fetchall()
    return [_row_target(dict(r)) for r in rows]


def list_partners(conn: sqlite3.Connection, q: str = "") -> list[dict[str, Any]]:
    like = f"%{q.strip()}%"
    if q.strip():
        rows = conn.execute(
            """
            SELECT p.*, st.name AS assigned_staff_name
            FROM crm_sales_partners p
            LEFT JOIN crm_staff st ON st.id = p.assigned_staff_id
            WHERE p.name LIKE ? OR p.phone LIKE ? OR p.company LIKE ?
            ORDER BY p.status = 'active' DESC, p.name COLLATE NOCASE
            """,
            (like, like, like),
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT p.*, st.name AS assigned_staff_name
            FROM crm_sales_partners p
            LEFT JOIN crm_staff st ON st.id = p.assigned_staff_id
            ORDER BY p.status = 'active' DESC, p.name COLLATE NOCASE
            """
        ).fetchall()
    return [_row_partner(dict(r)) for r in rows]


def list_trainings(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT * FROM crm_sales_trainings ORDER BY training_date DESC, id DESC"
    ).fetchall()
    return [_row_training(dict(r)) for r in rows]


def list_market_research(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT * FROM crm_sales_market_research ORDER BY research_date DESC, id DESC"
    ).fetchall()
    return [_row_market(dict(r)) for r in rows]


def list_transactions(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT tx.*, cu.name AS customer_name, st.name AS assigned_staff_name,
               c.title AS case_title
        FROM crm_sales_transactions tx
        LEFT JOIN crm_customers cu ON cu.id = tx.customer_id
        LEFT JOIN crm_staff st ON st.id = tx.assigned_staff_id
        LEFT JOIN crm_cases c ON c.id = tx.case_id
        ORDER BY tx.updated_at DESC, tx.id DESC
        LIMIT 300
        """
    ).fetchall()
    return [_row_tx(dict(r)) for r in rows]


def list_pipeline_cases(conn: sqlite3.Connection, stage: str | None = None) -> list[dict[str, Any]]:
    params: list[Any] = []
    where = ""
    if stage:
        where = "WHERE c.pipeline_stage = ?"
        params.append(normalize_pipeline_stage(stage))
    rows = conn.execute(
        f"""
        SELECT c.id, c.title, c.pipeline_stage, c.deal_value_vnd, c.status,
               c.assigned_staff_id, c.customer_id, c.created_at, c.stage_entered_at,
               cu.name AS customer_name, st.name AS staff_name
        FROM crm_cases c
        LEFT JOIN crm_customers cu ON cu.id = c.customer_id
        LEFT JOIN crm_staff st ON st.id = c.assigned_staff_id
        {where}
        ORDER BY c.updated_at DESC, c.id DESC
        LIMIT 200
        """,
        params,
    ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        stg = normalize_pipeline_stage(d.get("pipeline_stage"))
        d["pipeline_stage"] = stg
        d["pipeline_stage_label"] = pipeline_stage_label(stg)
        d["is_terminal"] = stg in TERMINAL_STAGES
        out.append(d)
    return out


def sales_report_data(conn: sqlite3.Connection) -> dict[str, Any]:
    funnel = compute_funnel_stats(conn)
    by_staff = funnel.get("by_staff") or {}
    staff_rows = []
    for name, stats in sorted(by_staff.items(), key=lambda x: -(x[1].get("won") or 0)):
        staff_rows.append({"name": name, **stats})

    rev_row = conn.execute(
        """
        SELECT COALESCE(SUM(deal_value_vnd), 0) AS v FROM crm_cases
        WHERE pipeline_stage = 'chot'
        """
    ).fetchone()
    tx_row = conn.execute(
        """
        SELECT COALESCE(SUM(deal_value_vnd), 0) AS v FROM crm_sales_transactions
        WHERE stage = 'hoan_tat'
        """
    ).fetchone()
    targets = list_targets(conn)
    return {
        "funnel_totals": funnel.get("totals") or {},
        "staff_performance": staff_rows,
        "revenue_closed_cases": int(rev_row["v"]) if rev_row else 0,
        "revenue_closed_tx": int(tx_row["v"]) if tx_row else 0,
        "targets": targets[:50],
        "bottlenecks": funnel.get("bottlenecks") or [],
    }
