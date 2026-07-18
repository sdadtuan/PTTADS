"""Profit & cost tracking per-lifecycle cho PTTP."""
from __future__ import annotations

import logging
import os
import sqlite3
from datetime import date, datetime
from typing import Any

logger = logging.getLogger(__name__)
_HAIKU = "claude-haiku-4-5-20251001"

COST_PHASE_DELIVERY = "delivery"
COST_PHASE_PRESALES = "presales"
VALID_COST_PHASES: frozenset[str] = frozenset({COST_PHASE_DELIVERY, COST_PHASE_PRESALES})

PRESALES_CATEGORIES: frozenset[str] = frozenset({
    "dien_thoai",
    "di_lai",
    "cong_lead",
    "cong_tu_van",
    "cong_cu",
    "khac_presales",
})

DELIVERY_CATEGORIES: frozenset[str] = frozenset({
    "nhan-cong",
    "cong-cu",
    "quang-cao",
    "outsource",
    "khac",
})

PRESALES_LIFECYCLE_STAGES: frozenset[str] = frozenset({"lead", "consult", "proposal"})

BILLING_TYPE_ONE_OFF = "one_off"
BILLING_TYPE_RECURRING = "recurring"
VALID_BILLING_TYPES: frozenset[str] = frozenset({
    BILLING_TYPE_ONE_OFF,
    BILLING_TYPE_RECURRING,
})
BILLING_TYPE_LABELS: dict[str, str] = {
    BILLING_TYPE_ONE_OFF: "Một lần",
    BILLING_TYPE_RECURRING: "Định kỳ (retainer)",
}

BILLING_CYCLE_MONTHLY = "monthly"
BILLING_CYCLE_QUARTERLY = "quarterly"
BILLING_CYCLE_ANNUAL = "annual"
VALID_BILLING_CYCLES: frozenset[str] = frozenset({
    BILLING_CYCLE_MONTHLY,
    BILLING_CYCLE_QUARTERLY,
    BILLING_CYCLE_ANNUAL,
})
BILLING_CYCLE_LABELS: dict[str, str] = {
    BILLING_CYCLE_MONTHLY: "Theo tháng",
    BILLING_CYCLE_QUARTERLY: "Theo quý",
    BILLING_CYCLE_ANNUAL: "Theo năm",
}

AR_AGING_BUCKET_KEYS: tuple[str, ...] = (
    "not_due",
    "overdue_1_30",
    "overdue_31_60",
    "overdue_61_90",
    "overdue_90_plus",
)
AR_AGING_BUCKET_LABELS: dict[str, str] = {
    "not_due": "Chưa đến hạn",
    "overdue_1_30": "Quá hạn 1–30 ngày",
    "overdue_31_60": "Quá hạn 31–60 ngày",
    "overdue_61_90": "Quá hạn 61–90 ngày",
    "overdue_90_plus": "Quá hạn >90 ngày",
}


class ExpenseValidationError(ValueError):
    """Chi phí không hợp lệ với giai đoạn lifecycle."""


def _ts() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")


def _delivery_phase_sql(column: str = "cost_phase") -> str:
    return f"COALESCE(NULLIF({column}, ''), '{COST_PHASE_DELIVERY}') = '{COST_PHASE_DELIVERY}'"


def _migrate_expense_columns(conn: sqlite3.Connection) -> None:
    cols = {r[1] for r in conn.execute("PRAGMA table_info(crm_svc_expenses)").fetchall()}
    if "cost_phase" not in cols:
        try:
            conn.execute(
                "ALTER TABLE crm_svc_expenses "
                f"ADD COLUMN cost_phase TEXT NOT NULL DEFAULT '{COST_PHASE_DELIVERY}'"
            )
        except Exception:
            pass
    if "lifecycle_stage" not in cols:
        try:
            conn.execute(
                "ALTER TABLE crm_svc_expenses ADD COLUMN lifecycle_stage TEXT NOT NULL DEFAULT ''"
            )
        except Exception:
            pass
    _migrate_expense_lead_presales(conn)


def _migrate_expense_lead_presales(conn: sqlite3.Connection) -> None:
    """L3.2 — chi phí pre-sales gắn lead/presales, lifecycle_id nullable."""
    cols = {r[1] for r in conn.execute("PRAGMA table_info(crm_svc_expenses)").fetchall()}
    if "presales_id" in cols:
        return
    conn.execute(
        """
        CREATE TABLE crm_svc_expenses_new (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            lifecycle_id    INTEGER REFERENCES crm_service_lifecycle(id) ON DELETE CASCADE,
            lead_id         INTEGER,
            presales_id     INTEGER,
            title           TEXT NOT NULL DEFAULT '',
            category        TEXT NOT NULL DEFAULT 'khac',
            amount_vnd      INTEGER NOT NULL DEFAULT 0,
            expense_on      TEXT NOT NULL DEFAULT '',
            notes           TEXT NOT NULL DEFAULT '',
            cost_phase      TEXT NOT NULL DEFAULT 'delivery',
            lifecycle_stage TEXT NOT NULL DEFAULT '',
            created_at      TEXT NOT NULL DEFAULT '',
            updated_at      TEXT NOT NULL DEFAULT ''
        )
        """
    )
    conn.execute(
        """
        INSERT INTO crm_svc_expenses_new
            (id, lifecycle_id, lead_id, presales_id, title, category, amount_vnd,
             expense_on, notes, cost_phase, lifecycle_stage, created_at, updated_at)
        SELECT id, lifecycle_id, NULL, NULL, title, category, amount_vnd,
               expense_on, notes, cost_phase, lifecycle_stage, created_at, updated_at
        FROM crm_svc_expenses
        """
    )
    conn.execute("DROP TABLE crm_svc_expenses")
    conn.execute("ALTER TABLE crm_svc_expenses_new RENAME TO crm_svc_expenses")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_svc_expenses_lifecycle ON crm_svc_expenses(lifecycle_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_svc_expenses_presales ON crm_svc_expenses(presales_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_svc_expenses_lead ON crm_svc_expenses(lead_id)"
    )


def _get_lifecycle_row(
    conn: sqlite3.Connection, lifecycle_id: int
) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT id, stage, status FROM crm_service_lifecycle WHERE id = ?",
        (int(lifecycle_id),),
    ).fetchone()


def is_presales_lifecycle(stage: str, status: str) -> bool:
    st = str(stage or "lead")
    stat = str(status or "draft")
    if stat == "draft":
        return True
    if st in PRESALES_LIFECYCLE_STAGES and stat != "active":
        return True
    return st in PRESALES_LIFECYCLE_STAGES


def resolve_default_cost_phase(
    conn: sqlite3.Connection, lifecycle_id: int
) -> tuple[str, str]:
    row = _get_lifecycle_row(conn, lifecycle_id)
    if row is None:
        return COST_PHASE_DELIVERY, ""
    stage = str(row["stage"] or "lead")
    status = str(row["status"] or "draft")
    if is_presales_lifecycle(stage, status):
        return COST_PHASE_PRESALES, stage
    return COST_PHASE_DELIVERY, stage


def validate_expense(
    conn: sqlite3.Connection,
    lifecycle_id: int,
    *,
    cost_phase: str,
    lifecycle_stage: str,
    category: str,
) -> None:
    phase = str(cost_phase or COST_PHASE_DELIVERY).strip()
    if phase not in VALID_COST_PHASES:
        raise ExpenseValidationError(f"cost_phase không hợp lệ: {phase}")
    row = _get_lifecycle_row(conn, lifecycle_id)
    if row is None:
        raise ExpenseValidationError("Không tìm thấy lifecycle.")
    stage = str(row["stage"] or "lead")
    status = str(row["status"] or "draft")
    cat = str(category or "khac").strip()

    if phase == COST_PHASE_PRESALES:
        if not is_presales_lifecycle(stage, status):
            raise ExpenseValidationError(
                "Chỉ ghi chi phí pre-sales khi lifecycle ở Lead/Consult/Proposal (draft)."
            )
        if cat not in PRESALES_CATEGORIES:
            raise ExpenseValidationError(
                f"Category pre-sales không hợp lệ: {cat}"
            )
        st = str(lifecycle_stage or stage).strip()
        if st and st not in PRESALES_LIFECYCLE_STAGES:
            raise ExpenseValidationError(f"lifecycle_stage không hợp lệ: {st}")
    elif cat in PRESALES_CATEGORIES:
        raise ExpenseValidationError(
            "Category pre-sales chỉ dùng với cost_phase=presales."
        )


def _get_presales_row(
    conn: sqlite3.Connection, presales_id: int
) -> sqlite3.Row | None:
    try:
        return conn.execute(
            "SELECT id, lead_id, stage, status FROM crm_lead_presales WHERE id = ?",
            (int(presales_id),),
        ).fetchone()
    except sqlite3.OperationalError:
        return None


def resolve_presales_id(
    conn: sqlite3.Connection,
    *,
    presales_id: int | None = None,
    lead_id: int | None = None,
) -> tuple[int, int]:
    """Trả (presales_id, lead_id) — một trong hai tham số bắt buộc."""
    if presales_id:
        row = _get_presales_row(conn, int(presales_id))
        if row is None:
            raise ExpenseValidationError("Không tìm thấy pre-sales.")
        return int(row["id"]), int(row["lead_id"])
    if lead_id:
        row = conn.execute(
            "SELECT id, lead_id FROM crm_lead_presales WHERE lead_id = ?",
            (int(lead_id),),
        ).fetchone()
        if row is None:
            raise ExpenseValidationError("Lead chưa có pre-sales — bắt đầu pre-sales trước.")
        return int(row["id"]), int(row["lead_id"])
    raise ExpenseValidationError("Cần presales_id hoặc lead_id.")


def validate_presales_expense(
    conn: sqlite3.Connection,
    presales_id: int,
    *,
    category: str,
    lifecycle_stage: str,
) -> None:
    row = _get_presales_row(conn, presales_id)
    if row is None:
        raise ExpenseValidationError("Không tìm thấy pre-sales.")
    status = str(row["status"] or "")
    if status != "active":
        raise ExpenseValidationError(
            "Chỉ ghi chi phí pre-sales khi pre-sales đang active (trước ký HĐ)."
        )
    stage = str(row["stage"] or "lead")
    if stage not in PRESALES_LIFECYCLE_STAGES:
        raise ExpenseValidationError(
            "Chỉ ghi chi phí pre-sales ở giai đoạn Lead/Consult/Proposal."
        )
    cat = str(category or "khac").strip()
    if cat not in PRESALES_CATEGORIES:
        raise ExpenseValidationError(f"Category pre-sales không hợp lệ: {cat}")
    st = str(lifecycle_stage or stage).strip()
    if st and st not in PRESALES_LIFECYCLE_STAGES:
        raise ExpenseValidationError(f"lifecycle_stage không hợp lệ: {st}")


def list_presales_expenses(
    conn: sqlite3.Connection, presales_id: int
) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT * FROM crm_svc_expenses
        WHERE presales_id = ? AND cost_phase = ?
        ORDER BY expense_on DESC, id DESC
        """,
        (int(presales_id), COST_PHASE_PRESALES),
    ).fetchall()
    return [dict(r) for r in rows]


def create_presales_expense(
    conn: sqlite3.Connection,
    *,
    title: str,
    category: str,
    amount_vnd: int,
    expense_on: str,
    notes: str = "",
    presales_id: int | None = None,
    lead_id: int | None = None,
    lifecycle_stage: str | None = None,
) -> int:
    """Ghi chi phí pre-sales trên lead — không cần lifecycle (L3.2)."""
    pid, lid = resolve_presales_id(conn, presales_id=presales_id, lead_id=lead_id)
    ps = _get_presales_row(conn, pid)
    assert ps is not None
    stage = str(lifecycle_stage or ps["stage"] or "lead").strip()
    validate_presales_expense(
        conn, pid, category=category, lifecycle_stage=stage
    )
    try:
        from crm_svc_presales import enforce_presales_expense_cap

        enforce_presales_expense_cap(conn, pid, int(amount_vnd))
    except ImportError:
        pass
    ts = _ts()
    cur = conn.execute(
        """
        INSERT INTO crm_svc_expenses
            (lifecycle_id, lead_id, presales_id, title, category, amount_vnd,
             expense_on, notes, cost_phase, lifecycle_stage, created_at, updated_at)
        VALUES (NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            lid,
            pid,
            title,
            category,
            amount_vnd,
            expense_on,
            notes,
            COST_PHASE_PRESALES,
            stage,
            ts,
            ts,
        ),
    )
    conn.commit()
    return int(cur.lastrowid)


def link_presales_expenses_to_lifecycle(
    conn: sqlite3.Connection, presales_id: int, lifecycle_id: int
) -> int:
    """Sau promote: gắn chi phí pre-sales lead → lifecycle (tránh mất KPI/history)."""
    ts = _ts()
    cur = conn.execute(
        """
        UPDATE crm_svc_expenses
        SET lifecycle_id = ?, updated_at = ?
        WHERE presales_id = ? AND cost_phase = ? AND lifecycle_id IS NULL
        """,
        (int(lifecycle_id), ts, int(presales_id), COST_PHASE_PRESALES),
    )
    conn.commit()
    return int(cur.rowcount)


_HEALTH_PROMPT = """Bạn là chuyên gia phân tích tài chính dịch vụ digital marketing.

Dịch vụ: {service_name}
Khách hàng: {customer_name}
Doanh thu kỳ vọng (HĐ): {contract_amount_vnd:,} VND
Doanh thu thực nhận: {received_revenue:,} VND
Chi phí phát sinh: {total_expenses:,} VND
Lợi nhuận: {profit:,} VND
Biên lợi nhuận: {margin_pct:.1f}%

Phân tích ngắn gọn (tối đa 200 từ):
1. Đánh giá tình trạng tài chính hiện tại
2. Cảnh báo nếu chi phí > 70% doanh thu thực nhận
3. Gợi ý cụ thể để cải thiện margin"""

_FORECAST_PROMPT = """Bạn là chuyên gia phân tích tài chính dịch vụ digital marketing.

Dịch vụ: {service_name}
Khách hàng: {customer_name}
Doanh thu kỳ vọng (HĐ): {contract_amount_vnd:,} VND
Doanh thu thực nhận: {received_revenue:,} VND
Chi phí đến nay: {total_expenses:,} VND
Lợi nhuận hiện tại: {profit:,} VND
Biên lợi nhuận: {margin_pct:.1f}%
Số ngày đã triển khai: {days_elapsed} ngày
Tổng thời gian HĐ: {contract_days} ngày

Dự báo ngắn gọn (tối đa 200 từ):
1. Burn rate hiện tại = chi phí / ngày
2. Ước tính tổng chi phí đến cuối HĐ
3. Ước tính lợi nhuận và margin cuối kỳ
4. Cảnh báo nếu dự báo margin < 20%"""


def _migrate_payment_due_on(conn: sqlite3.Connection) -> None:
    cols = {r[1] for r in conn.execute("PRAGMA table_info(crm_svc_payments)").fetchall()}
    if "due_on" not in cols:
        try:
            conn.execute(
                "ALTER TABLE crm_svc_payments ADD COLUMN due_on TEXT NOT NULL DEFAULT ''"
            )
        except Exception:
            pass
    conn.execute(
        """
        UPDATE crm_svc_payments
        SET due_on = received_on
        WHERE status = 'pending' AND COALESCE(due_on, '') = ''
          AND COALESCE(received_on, '') != ''
        """
    )


def migrate_contract_billing_type(conn: sqlite3.Connection) -> None:
    """Thêm billing_type trên crm_contracts — gọi từ app init."""
    tables = {
        r[0]
        for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    if "crm_contracts" not in tables:
        return
    cols = {r[1] for r in conn.execute("PRAGMA table_info(crm_contracts)").fetchall()}
    if "billing_type" not in cols:
        try:
            conn.execute(
                f"ALTER TABLE crm_contracts ADD COLUMN billing_type TEXT NOT NULL "
                f"DEFAULT '{BILLING_TYPE_ONE_OFF}'"
            )
        except Exception:
            pass
    cols = {r[1] for r in conn.execute("PRAGMA table_info(crm_contracts)").fetchall()}
    if "billing_cycle" not in cols:
        try:
            conn.execute(
                f"ALTER TABLE crm_contracts ADD COLUMN billing_cycle TEXT NOT NULL "
                f"DEFAULT '{BILLING_CYCLE_MONTHLY}'"
            )
        except Exception:
            pass
    _backfill_recurring_billing_type(conn)


def _backfill_recurring_billing_type(conn: sqlite3.Connection) -> None:
    """Suy luận billing_type=recurring từ service_slug retainer."""
    cols = {r[1] for r in conn.execute("PRAGMA table_info(crm_contracts)").fetchall()}
    if "service_slug" not in cols:
        return
    try:
        from crm_svc_tasks import RECURRING_DELIVER_SLUGS
    except ImportError:
        return
    if not RECURRING_DELIVER_SLUGS:
        return
    slugs = tuple(sorted(RECURRING_DELIVER_SLUGS))
    placeholders = ",".join("?" * len(slugs))
    conn.execute(
        f"""
        UPDATE crm_contracts
        SET billing_type = ?
        WHERE COALESCE(billing_type, '') = ?
          AND service_slug IN ({placeholders})
        """,
        (BILLING_TYPE_RECURRING, BILLING_TYPE_ONE_OFF, *slugs),
    )


def normalize_billing_type(raw: str | None) -> str:
    val = str(raw or BILLING_TYPE_ONE_OFF).strip().lower()
    return val if val in VALID_BILLING_TYPES else BILLING_TYPE_ONE_OFF


def infer_billing_type_from_service_slug(service_slug: str | None) -> str:
    slug = str(service_slug or "").strip()
    if not slug:
        return BILLING_TYPE_ONE_OFF
    try:
        from crm_svc_tasks import RECURRING_DELIVER_SLUGS
    except ImportError:
        return BILLING_TYPE_ONE_OFF
    return (
        BILLING_TYPE_RECURRING
        if slug in RECURRING_DELIVER_SLUGS
        else BILLING_TYPE_ONE_OFF
    )


def normalize_billing_cycle(raw: str | None) -> str:
    val = str(raw or BILLING_CYCLE_MONTHLY).strip().lower()
    return val if val in VALID_BILLING_CYCLES else BILLING_CYCLE_MONTHLY


def contract_amount_to_mrr_vnd(amount_vnd: int, billing_cycle: str | None) -> int:
    """Quy đổi amount_vnd HĐ recurring → MRR/tháng."""
    amount = max(0, int(amount_vnd or 0))
    cycle = normalize_billing_cycle(billing_cycle)
    if cycle == BILLING_CYCLE_QUARTERLY:
        return int(round(amount / 3))
    if cycle == BILLING_CYCLE_ANNUAL:
        return int(round(amount / 12))
    return amount


def _parse_ymd(text: str) -> date | None:
    raw = str(text or "").strip()[:10]
    if len(raw) != 10:
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return None


def resolve_payment_due_on(payment: dict[str, Any]) -> str:
    """Ngày đến hạn AR — ưu tiên due_on, fallback received_on khi pending."""
    due = str(payment.get("due_on") or "").strip()[:10]
    if due:
        return due
    if str(payment.get("status") or "") == "pending":
        return str(payment.get("received_on") or "").strip()[:10]
    return ""


def _aging_bucket(days_overdue: int) -> str:
    if days_overdue <= 0:
        return "not_due"
    if days_overdue <= 30:
        return "overdue_1_30"
    if days_overdue <= 60:
        return "overdue_31_60"
    if days_overdue <= 90:
        return "overdue_61_90"
    return "overdue_90_plus"


def get_ar_aging(
    conn: sqlite3.Connection,
    *,
    as_of: str | None = None,
    am_id: int | None = None,
) -> dict[str, Any]:
    """AR aging cho thanh toán pending — bucket theo ngày quá hạn."""
    as_of_d = _parse_ymd(as_of or "") or date.today()
    as_of_iso = as_of_d.isoformat()
    where = ["p.status = 'pending'"]
    params: list[Any] = []
    if am_id is not None:
        where.append("lc.assigned_am = ?")
        params.append(int(am_id))
    rows = conn.execute(
        f"""
        SELECT p.id, p.lifecycle_id, p.amount_vnd, p.received_on, p.due_on, p.status,
               p.notes, lc.assigned_am, lc.service_slug, lc.customer_id,
               cu.name AS customer_name,
               COALESCE(ct.billing_type, '{BILLING_TYPE_ONE_OFF}') AS billing_type
        FROM crm_svc_payments p
        INNER JOIN crm_service_lifecycle lc ON lc.id = p.lifecycle_id
        LEFT JOIN crm_customers cu ON cu.id = lc.customer_id
        LEFT JOIN crm_contracts ct ON ct.id = lc.contract_id
        WHERE {' AND '.join(where)}
        ORDER BY p.due_on ASC, p.id ASC
        """,
        params,
    ).fetchall()
    buckets = {key: 0 for key in AR_AGING_BUCKET_KEYS}
    items: list[dict[str, Any]] = []
    total_pending = 0
    total_overdue = 0
    for row in rows:
        d = dict(row)
        amount = int(d.get("amount_vnd") or 0)
        due_iso = resolve_payment_due_on(d)
        due_d = _parse_ymd(due_iso)
        if due_d is None:
            bucket = "not_due"
            days_overdue = 0
        else:
            days_overdue = (as_of_d - due_d).days
            bucket = _aging_bucket(days_overdue)
        buckets[bucket] += amount
        total_pending += amount
        if days_overdue > 0:
            total_overdue += amount
        items.append(
            {
                "payment_id": int(d["id"]),
                "lifecycle_id": int(d["lifecycle_id"]),
                "amount_vnd": amount,
                "due_on": due_iso,
                "days_overdue": max(0, days_overdue),
                "bucket": bucket,
                "customer_name": d.get("customer_name") or "—",
                "service_slug": d.get("service_slug") or "",
                "billing_type": normalize_billing_type(d.get("billing_type")),
                "assigned_am": d.get("assigned_am"),
                "notes": d.get("notes") or "",
            }
        )
    return {
        "as_of": as_of_iso,
        "am_id": am_id,
        "total_pending_vnd": total_pending,
        "total_overdue_vnd": total_overdue,
        "buckets": buckets,
        "bucket_labels": AR_AGING_BUCKET_LABELS,
        "items": items,
    }


def get_recurring_revenue_summary(
    conn: sqlite3.Connection,
    *,
    year: int,
    month: int,
    am_id: int | None = None,
) -> dict[str, Any]:
    """Doanh thu recurring trong tháng + AR pending recurring + HĐ active."""
    month_str = f"{int(year):04d}-{int(month):02d}"
    am_clause = ""
    am_params: list[Any] = []
    if am_id is not None:
        am_clause = " AND lc.assigned_am = ?"
        am_params = [int(am_id)]

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
    received_recurring_vnd = int(recv_row[0] if recv_row else 0)

    pending_row = conn.execute(
        f"""
        SELECT COALESCE(SUM(p.amount_vnd), 0)
        FROM crm_svc_payments p
        INNER JOIN crm_service_lifecycle lc ON lc.id = p.lifecycle_id
        INNER JOIN crm_contracts ct ON ct.id = lc.contract_id
        WHERE ct.billing_type = ?
          AND p.status = 'pending'
          {am_clause}
        """,
        (BILLING_TYPE_RECURRING, *am_params),
    ).fetchone()
    pending_recurring_vnd = int(pending_row[0] if pending_row else 0)

    active_row = conn.execute(
        f"""
        SELECT COUNT(DISTINCT ct.id)
        FROM crm_contracts ct
        INNER JOIN crm_service_lifecycle lc ON lc.contract_id = ct.id
        WHERE ct.billing_type = ?
          AND ct.status IN ('active', 'signed', 'expiring')
          AND lc.status = 'active'
          {am_clause.replace('lc.assigned_am', 'lc.assigned_am') if am_clause else ''}
        """,
        (BILLING_TYPE_RECURRING, *am_params),
    ).fetchone()
    active_recurring_contracts = int(active_row[0] if active_row else 0)

    return {
        "year": int(year),
        "month": int(month),
        "am_id": am_id,
        "received_recurring_vnd": received_recurring_vnd,
        "pending_recurring_vnd": pending_recurring_vnd,
        "active_recurring_contracts": active_recurring_contracts,
    }


def _empty_package_bucket() -> dict[str, Any]:
    return {
        "lifecycle_count": 0,
        "expected_revenue_vnd": 0,
        "received_month_vnd": 0,
        "delivery_expenses_month_vnd": 0,
        "gross_margin_month_pct": 0.0,
        "received_lifetime_vnd": 0,
        "delivery_expenses_lifetime_vnd": 0,
        "gross_margin_lifetime_pct": 0.0,
        "profit_lifetime_vnd": 0,
        "ar_overdue_vnd": 0,
        "outstanding_vnd": 0,
    }


def _pct_margin(revenue: int, cost: int) -> float:
    if revenue <= 0:
        return 0.0
    return round((revenue - cost) / revenue * 100, 2)


def get_service_package_rollup(
    conn: sqlite3.Connection,
    *,
    year: int,
    month: int,
    lifecycle_status: str = "active",
) -> dict[str, Any]:
    """
    Rollup doanh thu + gross margin theo service_slug.

    - received_month / delivery_month: filter theo tháng (doanh thu & chi delivery).
    - lifetime_*: tích lũy trên lifecycle active (cùng logic get_summary).
    """
    month_prefix = f"{int(year):04d}-{int(month):02d}"
    lc_rows = conn.execute(
        """
        SELECT lc.id, lc.service_slug, lc.contract_id
        FROM crm_service_lifecycle lc
        WHERE lc.status = ?
        ORDER BY lc.service_slug, lc.id
        """,
        (str(lifecycle_status or "active"),),
    ).fetchall()

    packages: dict[str, dict[str, Any]] = {}
    for lc in lc_rows:
        slug = str(lc["service_slug"] or "").strip() or "_unknown"
        if slug not in packages:
            packages[slug] = _empty_package_bucket()
        bucket = packages[slug]
        lc_id = int(lc["id"])
        contract_amount = 0
        if lc["contract_id"]:
            c_row = conn.execute(
                "SELECT amount_vnd FROM crm_contracts WHERE id = ?",
                (int(lc["contract_id"]),),
            ).fetchone()
            if c_row:
                contract_amount = int(c_row["amount_vnd"] or 0)

        summary = get_summary(conn, lc_id, contract_amount)

        recv_month = int(
            conn.execute(
                """
                SELECT COALESCE(SUM(amount_vnd), 0) FROM crm_svc_payments
                WHERE lifecycle_id = ? AND status = 'received' AND received_on LIKE ?
                """,
                (lc_id, f"{month_prefix}%"),
            ).fetchone()[0]
        )
        del_month = int(
            conn.execute(
                f"""
                SELECT COALESCE(SUM(amount_vnd), 0) FROM crm_svc_expenses
                WHERE lifecycle_id = ? AND expense_on LIKE ? AND {_delivery_phase_sql()}
                """,
                (lc_id, f"{month_prefix}%"),
            ).fetchone()[0]
        )

        bucket["lifecycle_count"] += 1
        bucket["expected_revenue_vnd"] += contract_amount
        bucket["received_month_vnd"] += recv_month
        bucket["delivery_expenses_month_vnd"] += del_month
        bucket["received_lifetime_vnd"] += int(summary["received_revenue"])
        bucket["delivery_expenses_lifetime_vnd"] += int(summary["delivery_expenses"])
        bucket["profit_lifetime_vnd"] += int(summary["profit"])
        bucket["ar_overdue_vnd"] += int(summary["ar_overdue_vnd"])
        bucket["outstanding_vnd"] += max(0, int(summary["outstanding"]))

    result_packages: list[dict[str, Any]] = []
    for slug, bucket in packages.items():
        bucket["service_slug"] = slug
        bucket["gross_margin_month_pct"] = _pct_margin(
            int(bucket["received_month_vnd"]),
            int(bucket["delivery_expenses_month_vnd"]),
        )
        bucket["gross_margin_lifetime_pct"] = _pct_margin(
            int(bucket["received_lifetime_vnd"]),
            int(bucket["delivery_expenses_lifetime_vnd"]),
        )
        result_packages.append(bucket)

    result_packages.sort(
        key=lambda p: (-int(p["received_month_vnd"]), str(p["service_slug"]))
    )
    totals = _empty_package_bucket()
    for pkg in result_packages:
        for key in totals:
            if key.endswith("_pct"):
                continue
            totals[key] += int(pkg.get(key) or 0)
    totals["gross_margin_month_pct"] = _pct_margin(
        int(totals["received_month_vnd"]),
        int(totals["delivery_expenses_month_vnd"]),
    )
    totals["gross_margin_lifetime_pct"] = _pct_margin(
        int(totals["received_lifetime_vnd"]),
        int(totals["delivery_expenses_lifetime_vnd"]),
    )

    return {
        "year": int(year),
        "month": int(month),
        "lifecycle_status": lifecycle_status,
        "packages": result_packages,
        "totals": totals,
    }


def _lifecycle_ar_totals(
    conn: sqlite3.Connection, lifecycle_id: int, *, as_of: str | None = None
) -> tuple[int, int]:
    """(pending_total, overdue_total) cho một lifecycle."""
    as_of_d = _parse_ymd(as_of or "") or date.today()
    rows = conn.execute(
        """
        SELECT amount_vnd, received_on, due_on, status
        FROM crm_svc_payments
        WHERE lifecycle_id = ? AND status = 'pending'
        """,
        (int(lifecycle_id),),
    ).fetchall()
    pending = overdue = 0
    for row in rows:
        d = dict(row)
        amount = int(d.get("amount_vnd") or 0)
        due_d = _parse_ymd(resolve_payment_due_on(d))
        pending += amount
        if due_d is not None and (as_of_d - due_d).days > 0:
            overdue += amount
    return pending, overdue


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS crm_svc_payments (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            lifecycle_id INTEGER NOT NULL REFERENCES crm_service_lifecycle(id) ON DELETE CASCADE,
            amount_vnd   INTEGER NOT NULL DEFAULT 0,
            received_on  TEXT NOT NULL DEFAULT '',
            due_on       TEXT NOT NULL DEFAULT '',
            status       TEXT NOT NULL DEFAULT 'pending',
            notes        TEXT NOT NULL DEFAULT '',
            created_at   TEXT NOT NULL DEFAULT '',
            updated_at   TEXT NOT NULL DEFAULT ''
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_svc_payments_lifecycle ON crm_svc_payments(lifecycle_id)"
    )
    _migrate_payment_due_on(conn)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_svc_payments_status_due "
        "ON crm_svc_payments(status, due_on)"
    )
    conn.execute("""
        CREATE TABLE IF NOT EXISTS crm_svc_expenses (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            lifecycle_id INTEGER NOT NULL REFERENCES crm_service_lifecycle(id) ON DELETE CASCADE,
            title        TEXT NOT NULL DEFAULT '',
            category     TEXT NOT NULL DEFAULT 'khac',
            amount_vnd   INTEGER NOT NULL DEFAULT 0,
            expense_on   TEXT NOT NULL DEFAULT '',
            notes        TEXT NOT NULL DEFAULT '',
            created_at   TEXT NOT NULL DEFAULT '',
            updated_at   TEXT NOT NULL DEFAULT ''
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_svc_expenses_lifecycle ON crm_svc_expenses(lifecycle_id)"
    )
    _migrate_expense_columns(conn)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS crm_svc_finance_scans (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            lifecycle_id INTEGER NOT NULL REFERENCES crm_service_lifecycle(id) ON DELETE CASCADE,
            ai_output    TEXT NOT NULL DEFAULT '',
            scan_type    TEXT NOT NULL DEFAULT 'health',
            created_at   TEXT NOT NULL DEFAULT ''
        )
    """)
    conn.commit()


def get_summary(
    conn: sqlite3.Connection, lifecycle_id: int, contract_amount_vnd: int
) -> dict[str, Any]:
    row = conn.execute(
        """
        SELECT
            COALESCE(SUM(CASE WHEN status = 'received' THEN amount_vnd ELSE 0 END), 0) AS received_revenue,
            COALESCE(SUM(CASE WHEN status = 'pending'  THEN amount_vnd ELSE 0 END), 0) AS pending_revenue
        FROM crm_svc_payments WHERE lifecycle_id = ?
        """,
        (lifecycle_id,),
    ).fetchone()
    received = int(row[0])
    pending = int(row[1])

    delivery_row = conn.execute(
        f"""
        SELECT COALESCE(SUM(amount_vnd), 0) FROM crm_svc_expenses
        WHERE lifecycle_id = ? AND {_delivery_phase_sql()}
        """,
        (lifecycle_id,),
    ).fetchone()
    delivery_expenses = int(delivery_row[0])

    presales_row = conn.execute(
        """
        SELECT COALESCE(SUM(amount_vnd), 0) FROM crm_svc_expenses
        WHERE lifecycle_id = ? AND cost_phase = ?
        """,
        (lifecycle_id, COST_PHASE_PRESALES),
    ).fetchone()
    presales_expenses = int(presales_row[0])

    total_expenses = delivery_expenses + presales_expenses
    profit = received - delivery_expenses
    margin_pct = (profit / received * 100) if received > 0 else 0.0
    outstanding = contract_amount_vnd - received
    ar_pending, ar_overdue = _lifecycle_ar_totals(conn, lifecycle_id)

    return {
        "expected_revenue": contract_amount_vnd,
        "received_revenue": received,
        "pending_revenue": pending,
        "ar_pending_vnd": ar_pending,
        "ar_overdue_vnd": ar_overdue,
        "delivery_expenses": delivery_expenses,
        "presales_expenses": presales_expenses,
        "total_expenses": total_expenses,
        "profit": profit,
        "margin_pct": round(margin_pct, 2),
        "outstanding": outstanding,
    }


def list_payments(conn: sqlite3.Connection, lifecycle_id: int) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT * FROM crm_svc_payments WHERE lifecycle_id = ? ORDER BY received_on DESC, id DESC",
        (lifecycle_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def create_payment(
    conn: sqlite3.Connection,
    lifecycle_id: int,
    amount_vnd: int,
    received_on: str,
    status: str = "pending",
    notes: str = "",
    *,
    due_on: str = "",
) -> int:
    ts = _ts()
    stat = str(status or "pending").strip()
    recv = str(received_on or "").strip()[:10]
    due = str(due_on or "").strip()[:10]
    if stat == "pending" and not due:
        due = recv
    cur = conn.execute(
        """
        INSERT INTO crm_svc_payments
            (lifecycle_id, amount_vnd, received_on, due_on, status, notes, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (lifecycle_id, amount_vnd, recv, due, stat, notes, ts, ts),
    )
    conn.commit()
    return int(cur.lastrowid)


def update_payment(
    conn: sqlite3.Connection,
    payment_id: int,
    *,
    amount_vnd: int | None = None,
    received_on: str | None = None,
    due_on: str | None = None,
    status: str | None = None,
    notes: str | None = None,
) -> None:
    ts = _ts()
    sets = ["updated_at = ?"]
    params: list[Any] = [ts]
    if amount_vnd is not None:
        sets.append("amount_vnd = ?")
        params.append(amount_vnd)
    if received_on is not None:
        sets.append("received_on = ?")
        params.append(str(received_on).strip()[:10])
    if due_on is not None:
        sets.append("due_on = ?")
        params.append(str(due_on).strip()[:10])
    if status is not None:
        sets.append("status = ?")
        params.append(str(status).strip())
    if notes is not None:
        sets.append("notes = ?")
        params.append(notes)
    params.append(payment_id)
    conn.execute(f"UPDATE crm_svc_payments SET {', '.join(sets)} WHERE id = ?", params)
    conn.commit()


def delete_payment(conn: sqlite3.Connection, payment_id: int) -> bool:
    cur = conn.execute("DELETE FROM crm_svc_payments WHERE id = ?", (payment_id,))
    conn.commit()
    return cur.rowcount > 0


def list_expenses(
    conn: sqlite3.Connection,
    lifecycle_id: int,
    *,
    cost_phase: str | None = None,
) -> list[dict[str, Any]]:
    if cost_phase == COST_PHASE_PRESALES:
        rows = conn.execute(
            """
            SELECT * FROM crm_svc_expenses
            WHERE lifecycle_id = ? AND cost_phase = ?
            ORDER BY expense_on DESC, id DESC
            """,
            (lifecycle_id, COST_PHASE_PRESALES),
        ).fetchall()
    elif cost_phase == COST_PHASE_DELIVERY:
        rows = conn.execute(
            f"""
            SELECT * FROM crm_svc_expenses
            WHERE lifecycle_id = ? AND {_delivery_phase_sql()}
            ORDER BY expense_on DESC, id DESC
            """,
            (lifecycle_id,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM crm_svc_expenses WHERE lifecycle_id = ? ORDER BY expense_on DESC, id DESC",
            (lifecycle_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def create_expense(
    conn: sqlite3.Connection,
    lifecycle_id: int,
    title: str,
    category: str,
    amount_vnd: int,
    expense_on: str,
    notes: str = "",
    *,
    cost_phase: str | None = None,
    lifecycle_stage: str | None = None,
) -> int:
    if cost_phase is None:
        cost_phase, auto_stage = resolve_default_cost_phase(conn, lifecycle_id)
        if not lifecycle_stage:
            lifecycle_stage = auto_stage
    phase = str(cost_phase or COST_PHASE_DELIVERY).strip()
    stage = str(lifecycle_stage or "").strip()
    validate_expense(
        conn,
        lifecycle_id,
        cost_phase=phase,
        lifecycle_stage=stage,
        category=category,
    )
    if phase == COST_PHASE_PRESALES:
        try:
            from crm_svc_presales import enforce_presales_expense_cap_for_lifecycle

            enforce_presales_expense_cap_for_lifecycle(
                conn, lifecycle_id, int(amount_vnd)
            )
        except ImportError:
            pass
    ts = _ts()
    cur = conn.execute(
        """
        INSERT INTO crm_svc_expenses
            (lifecycle_id, lead_id, presales_id, title, category, amount_vnd, expense_on, notes,
             cost_phase, lifecycle_stage, created_at, updated_at)
        VALUES (?, NULL, NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            lifecycle_id,
            title,
            category,
            amount_vnd,
            expense_on,
            notes,
            phase,
            stage,
            ts,
            ts,
        ),
    )
    conn.commit()
    return int(cur.lastrowid)


def update_expense(
    conn: sqlite3.Connection,
    expense_id: int,
    *,
    title: str | None = None,
    category: str | None = None,
    amount_vnd: int | None = None,
    expense_on: str | None = None,
    notes: str | None = None,
) -> None:
    ts = _ts()
    sets = ["updated_at = ?"]
    params: list[Any] = [ts]
    if title is not None:
        sets.append("title = ?")
        params.append(title)
    if category is not None:
        sets.append("category = ?")
        params.append(category)
    if amount_vnd is not None:
        sets.append("amount_vnd = ?")
        params.append(amount_vnd)
    if expense_on is not None:
        sets.append("expense_on = ?")
        params.append(expense_on)
    if notes is not None:
        sets.append("notes = ?")
        params.append(notes)
    params.append(expense_id)
    conn.execute(f"UPDATE crm_svc_expenses SET {', '.join(sets)} WHERE id = ?", params)
    conn.commit()


def delete_expense(conn: sqlite3.Connection, expense_id: int) -> bool:
    cur = conn.execute("DELETE FROM crm_svc_expenses WHERE id = ?", (expense_id,))
    conn.commit()
    return cur.rowcount > 0


def get_latest_finance_scan(
    conn: sqlite3.Connection, lifecycle_id: int, scan_type: str
) -> str:
    row = conn.execute(
        "SELECT ai_output FROM crm_svc_finance_scans "
        "WHERE lifecycle_id = ? AND scan_type = ? ORDER BY id DESC LIMIT 1",
        (lifecycle_id, scan_type),
    ).fetchone()
    return row[0] if row else ""


def run_ai_finance_scan(
    conn: sqlite3.Connection,
    lifecycle_id: int,
    scan_type: str,
    context: dict,
) -> str:
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return ""
    prompt_template = _HEALTH_PROMPT if scan_type == "health" else _FORECAST_PROMPT
    try:
        prompt = prompt_template.format(**context)
    except (KeyError, ValueError):
        return ""
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model=_HAIKU,
            max_tokens=600,
            messages=[{"role": "user", "content": prompt}],
        )
        output = response.content[0].text.strip()
        conn.execute(
            "INSERT INTO crm_svc_finance_scans "
            "(lifecycle_id, ai_output, scan_type, created_at) VALUES (?, ?, ?, ?)",
            (lifecycle_id, output, scan_type, _ts()),
        )
        conn.commit()
        return output
    except Exception as exc:
        logger.warning("run_ai_finance_scan lỗi lifecycle_id=%s: %s", lifecycle_id, exc)
        return ""
