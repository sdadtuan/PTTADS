"""Hồ sơ khách hàng 360° — nguồn, nhân khẩu, mua hàng, quan hệ, phản ánh."""
from __future__ import annotations

import sqlite3
from typing import Any

CUSTOMER_LEAD_SOURCES: tuple[str, ...] = (
    "web",
    "facebook",
    "zalo",
    "google",
    "referral",
    "walk_in",
    "phone",
    "email",
    "event",
    "partner",
    "marketing",
    "other",
)

CUSTOMER_LEAD_SOURCE_LABELS_VI: dict[str, str] = {
    "web": "Website / Landing",
    "facebook": "Facebook",
    "zalo": "Zalo",
    "google": "Google / Ads",
    "referral": "Giới thiệu (referral)",
    "walk_in": "Walk-in / Trực tiếp",
    "phone": "Gọi điện",
    "email": "Email",
    "event": "Sự kiện",
    "partner": "Đối tác",
    "marketing": "Chiến dịch marketing",
    "other": "Khác",
}

CUSTOMER_GENDERS: tuple[str, ...] = ("male", "female", "other", "unknown")
CUSTOMER_GENDER_LABELS_VI: dict[str, str] = {
    "male": "Nam",
    "female": "Nữ",
    "other": "Khác",
    "unknown": "Chưa rõ",
}

RELATION_TYPES: tuple[str, ...] = (
    "spouse",
    "parent",
    "child",
    "sibling",
    "colleague",
    "guardian",
    "other",
)
RELATION_TYPE_LABELS_VI: dict[str, str] = {
    "spouse": "Vợ / Chồng",
    "parent": "Cha / Mẹ",
    "child": "Con",
    "sibling": "Anh / Chị / Em",
    "colleague": "Đồng nghiệp",
    "guardian": "Người giám hộ",
    "other": "Khác",
}

PURCHASE_STATUSES: tuple[str, ...] = ("completed", "pending", "cancelled", "refunded")
PURCHASE_STATUS_LABELS_VI: dict[str, str] = {
    "completed": "Hoàn tất",
    "pending": "Đang xử lý",
    "cancelled": "Đã hủy",
    "refunded": "Hoàn tiền",
}

ISSUE_TYPES: tuple[str, ...] = (
    "phan_nan",
    "phan_anh",
    "khieu_nai",
    "ho_tro_ky_thuat",
    "yeu_cau_dich_vu",
    "khac",
)
ISSUE_TYPE_LABELS_VI: dict[str, str] = {
    "phan_nan": "Phàn nàn",
    "phan_anh": "Phản ánh",
    "khieu_nai": "Khiếu nại",
    "ho_tro_ky_thuat": "Hỗ trợ kỹ thuật",
    "yeu_cau_dich_vu": "Yêu cầu dịch vụ",
    "khac": "Khác",
}

ISSUE_STATUSES: tuple[str, ...] = ("moi", "dang_xu_ly", "cho_khach", "da_xu_ly", "dong")
ISSUE_STATUS_LABELS_VI: dict[str, str] = {
    "moi": "Mới",
    "dang_xu_ly": "Đang xử lý",
    "cho_khach": "Chờ phản hồi KH",
    "da_xu_ly": "Đã xử lý",
    "dong": "Đóng",
}

ISSUE_PRIORITIES: tuple[str, ...] = ("thap", "binh_thuong", "cao", "khan_cap")
ISSUE_PRIORITY_LABELS_VI: dict[str, str] = {
    "thap": "Thấp",
    "binh_thuong": "Bình thường",
    "cao": "Cao",
    "khan_cap": "Khẩn cấp",
}

_PROFILE_COLUMNS: list[tuple[str, str]] = [
    ("lead_source", "ALTER TABLE crm_customers ADD COLUMN lead_source TEXT NOT NULL DEFAULT ''"),
    ("lead_source_note", "ALTER TABLE crm_customers ADD COLUMN lead_source_note TEXT NOT NULL DEFAULT ''"),
    ("date_of_birth", "ALTER TABLE crm_customers ADD COLUMN date_of_birth TEXT NOT NULL DEFAULT ''"),
    ("gender", "ALTER TABLE crm_customers ADD COLUMN gender TEXT NOT NULL DEFAULT ''"),
    ("id_number", "ALTER TABLE crm_customers ADD COLUMN id_number TEXT NOT NULL DEFAULT ''"),
    ("occupation", "ALTER TABLE crm_customers ADD COLUMN occupation TEXT NOT NULL DEFAULT ''"),
    ("interests", "ALTER TABLE crm_customers ADD COLUMN interests TEXT NOT NULL DEFAULT ''"),
    ("profile_notes", "ALTER TABLE crm_customers ADD COLUMN profile_notes TEXT NOT NULL DEFAULT ''"),
]

PROFILE_PATCH_KEYS: frozenset[str] = frozenset(
    [
        "name",
        "phone",
        "email",
        "address",
        "company",
        "lead_source",
        "lead_source_note",
        "date_of_birth",
        "gender",
        "id_number",
        "occupation",
        "interests",
        "profile_notes",
    ]
)


def ensure_customer_360_schema(conn: sqlite3.Connection) -> None:
    cols = {r[1] for r in conn.execute("PRAGMA table_info(crm_customers)")}
    for col_name, ddl in _PROFILE_COLUMNS:
        if col_name not in cols:
            try:
                conn.execute(ddl)
            except sqlite3.Error:
                pass

    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS crm_customer_relations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER NOT NULL REFERENCES crm_customers(id) ON DELETE CASCADE,
            relation_type TEXT NOT NULL DEFAULT 'other',
            full_name TEXT NOT NULL DEFAULT '',
            phone TEXT NOT NULL DEFAULT '',
            email TEXT NOT NULL DEFAULT '',
            notes TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS crm_customer_purchases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER NOT NULL REFERENCES crm_customers(id) ON DELETE CASCADE,
            order_date TEXT NOT NULL DEFAULT '',
            product_name TEXT NOT NULL DEFAULT '',
            amount_vnd INTEGER NOT NULL DEFAULT 0,
            quantity INTEGER NOT NULL DEFAULT 1,
            status TEXT NOT NULL DEFAULT 'completed',
            reference_code TEXT NOT NULL DEFAULT '',
            notes TEXT NOT NULL DEFAULT '',
            contract_id INTEGER REFERENCES crm_contracts(id),
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS crm_customer_issues (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER NOT NULL REFERENCES crm_customers(id) ON DELETE CASCADE,
            case_id INTEGER REFERENCES crm_cases(id),
            issue_type TEXT NOT NULL DEFAULT 'phan_anh',
            priority TEXT NOT NULL DEFAULT 'binh_thuong',
            status TEXT NOT NULL DEFAULT 'moi',
            title TEXT NOT NULL DEFAULT '',
            description TEXT NOT NULL DEFAULT '',
            resolution TEXT NOT NULL DEFAULT '',
            assigned_staff_id INTEGER REFERENCES crm_staff(id),
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            resolved_at TEXT NOT NULL DEFAULT ''
        );

        CREATE INDEX IF NOT EXISTS idx_crm_cu_rel_customer ON crm_customer_relations(customer_id);
        CREATE INDEX IF NOT EXISTS idx_crm_cu_purchase_customer ON crm_customer_purchases(customer_id);
        CREATE INDEX IF NOT EXISTS idx_crm_cu_issue_customer ON crm_customer_issues(customer_id);
        CREATE INDEX IF NOT EXISTS idx_crm_cu_issue_status ON crm_customer_issues(status);
        """
    )


def normalize_lead_source(raw: str | None) -> str:
    code = str(raw or "").strip().lower()
    return code if code in CUSTOMER_LEAD_SOURCES else "other" if code else ""


def normalize_gender(raw: str | None) -> str:
    code = str(raw or "").strip().lower()
    return code if code in CUSTOMER_GENDERS else ""


def normalize_relation_type(raw: str | None) -> str:
    code = str(raw or "").strip().lower()
    return code if code in RELATION_TYPES else "other"


def normalize_purchase_status(raw: str | None) -> str:
    code = str(raw or "").strip().lower()
    return code if code in PURCHASE_STATUSES else "completed"


def normalize_issue_type(raw: str | None) -> str:
    code = str(raw or "").strip().lower()
    return code if code in ISSUE_TYPES else "phan_anh"


def normalize_issue_status(raw: str | None) -> str:
    code = str(raw or "").strip().lower()
    return code if code in ISSUE_STATUSES else "moi"


def normalize_issue_priority(raw: str | None) -> str:
    code = str(raw or "").strip().lower()
    return code if code in ISSUE_PRIORITIES else "binh_thuong"


def enrich_customer_row(row: sqlite3.Row | dict[str, Any]) -> dict[str, Any]:
    d = dict(row)
    ls = str(d.get("lead_source") or "")
    d["lead_source_label"] = CUSTOMER_LEAD_SOURCE_LABELS_VI.get(ls, ls) if ls else ""
    g = str(d.get("gender") or "")
    d["gender_label"] = CUSTOMER_GENDER_LABELS_VI.get(g, g) if g else ""
    return d


def _relation_row(row: sqlite3.Row) -> dict[str, Any]:
    d = dict(row)
    rt = str(d.get("relation_type") or "")
    d["relation_type_label"] = RELATION_TYPE_LABELS_VI.get(rt, rt)
    return d


def _purchase_row(row: sqlite3.Row) -> dict[str, Any]:
    d = dict(row)
    st = str(d.get("status") or "")
    d["status_label"] = PURCHASE_STATUS_LABELS_VI.get(st, st)
    return d


def _issue_row(row: sqlite3.Row) -> dict[str, Any]:
    d = dict(row)
    it = str(d.get("issue_type") or "")
    st = str(d.get("status") or "")
    pr = str(d.get("priority") or "")
    d["issue_type_label"] = ISSUE_TYPE_LABELS_VI.get(it, it)
    d["status_label"] = ISSUE_STATUS_LABELS_VI.get(st, st)
    d["priority_label"] = ISSUE_PRIORITY_LABELS_VI.get(pr, pr)
    if d.get("assigned_staff_id") is not None:
        try:
            d["assigned_staff_id"] = int(d["assigned_staff_id"])
        except (TypeError, ValueError):
            pass
    return d


def fetch_customer_relations(conn: sqlite3.Connection, customer_id: int) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT * FROM crm_customer_relations
        WHERE customer_id = ?
        ORDER BY id ASC
        """,
        (customer_id,),
    ).fetchall()
    return [_relation_row(r) for r in rows]


def fetch_customer_purchases(conn: sqlite3.Connection, customer_id: int) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT * FROM crm_customer_purchases
        WHERE customer_id = ?
        ORDER BY datetime(COALESCE(NULLIF(order_date,''), created_at)) DESC, id DESC
        """,
        (customer_id,),
    ).fetchall()
    return [_purchase_row(r) for r in rows]


def fetch_customer_issues(
    conn: sqlite3.Connection,
    customer_id: int,
    *,
    portal_staff_id: int | None = None,
) -> list[dict[str, Any]]:
    sql = """
        SELECT i.*, st.name AS assigned_staff_name
        FROM crm_customer_issues i
        LEFT JOIN crm_staff st ON st.id = i.assigned_staff_id
        WHERE i.customer_id = ?
    """
    params: list[Any] = [customer_id]
    if portal_staff_id is not None:
        sql += " AND (i.assigned_staff_id = ? OR i.assigned_staff_id IS NULL)"
        params.append(portal_staff_id)
    sql += " ORDER BY CASE i.status WHEN 'moi' THEN 0 WHEN 'dang_xu_ly' THEN 1 WHEN 'cho_khach' THEN 2 ELSE 9 END, i.id DESC"
    rows = conn.execute(sql, params).fetchall()
    return [_issue_row(r) for r in rows]


def compute_lead_sources(
    conn: sqlite3.Connection,
    customer_id: int,
    customer_row: dict[str, Any],
    channel_labels: dict[str, str],
) -> list[dict[str, str]]:
    """Tổng hợp nguồn khách: hồ sơ + kênh/campaign từ các case."""
    seen: set[str] = set()
    out: list[dict[str, str]] = []

    def add(code: str, label: str, origin: str) -> None:
        key = f"{code}|{label}|{origin}"
        if key in seen or not label.strip():
            return
        seen.add(key)
        out.append({"code": code, "label": label, "origin": origin})

    ls = str(customer_row.get("lead_source") or "").strip()
    if ls:
        add(ls, CUSTOMER_LEAD_SOURCE_LABELS_VI.get(ls, ls), "Hồ sơ khách hàng")
    note = str(customer_row.get("lead_source_note") or "").strip()
    if note:
        add("note", note[:200], "Ghi chú nguồn")

    case_rows = conn.execute(
        """
        SELECT c.channel, c.created_at, camp.name AS campaign_name, camp.code AS campaign_code
        FROM crm_cases c
        LEFT JOIN crm_campaigns camp ON camp.id = c.campaign_id
        WHERE c.customer_id = ?
        ORDER BY c.id ASC
        LIMIT 20
        """,
        (customer_id,),
    ).fetchall()
    for cr in case_rows:
        ch = str(cr["channel"] or "")
        ch_label = channel_labels.get(ch, ch)
        if ch_label:
            add(f"case_channel:{ch}", ch_label, "Hồ sơ CSKH")
        camp = str(cr["campaign_name"] or cr["campaign_code"] or "").strip()
        if camp:
            add(f"campaign:{camp}", camp, "Chiến dịch")

    return out


def apply_profile_patch(merged: dict[str, Any], payload: dict[str, Any]) -> None:
    for key in PROFILE_PATCH_KEYS:
        if key not in payload:
            continue
        val = payload[key]
        if val is None:
            merged[key] = ""
            continue
        if not isinstance(val, str):
            continue
        s = val.strip()
        if key == "phone":
            merged[key] = s[:64]
        elif key == "address":
            merged[key] = s[:500]
        elif key in ("interests", "profile_notes", "lead_source_note"):
            merged[key] = s[:4000]
        elif key == "id_number":
            merged[key] = s[:32]
        elif key == "date_of_birth":
            merged[key] = s[:32]
        elif key == "lead_source":
            merged[key] = normalize_lead_source(s) if s else ""
        elif key == "gender":
            merged[key] = normalize_gender(s) if s else ""
        else:
            merged[key] = s[:240]


def profile_update_sql_values(merged: dict[str, Any]) -> tuple[Any, ...]:
    return (
        merged["name"],
        merged["phone"],
        merged["email"],
        merged.get("address", ""),
        merged["company"],
        merged.get("lead_source", ""),
        merged.get("lead_source_note", ""),
        merged.get("date_of_birth", ""),
        merged.get("gender", ""),
        merged.get("id_number", ""),
        merged.get("occupation", ""),
        merged.get("interests", ""),
        merged.get("profile_notes", ""),
    )


PROFILE_INSERT_COLS = (
    "name, phone, email, address, company, lead_source, lead_source_note, "
    "date_of_birth, gender, id_number, occupation, interests, profile_notes, created_at"
)
