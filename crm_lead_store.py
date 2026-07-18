"""Quản lý Lead thông minh — thu thập, chấm điểm, phân loại, gán owner, truy xuất."""
from __future__ import annotations

import json
import re
import sqlite3
from datetime import datetime
from typing import Any

from crm_sales_pipeline import round_robin_assign
from crm_project_leads import _UNSET
from crm_care import (
    CRM_CARE_CONTACT_LABELS_VI,
    CRM_CARE_STATUS_LABELS_VI,
    normalize_care_contact,
    normalize_care_status,
)

CRM_CARE_CONTACT_TO_ACTIVITY: dict[str, str] = {
    "goi_dien": "call",
    "zalo": "message",
    "email": "email",
    "gap_mat": "meeting",
    "sms": "message",
    "khac": "note",
}

# --- Trạng thái pipeline = 8 bước chăm sóc (+ lost / chờ làm sạch) ---
from crm_lead_care_pipeline import (
    CARE_STAGE_KEYS,
    CARE_STAGE_STATUS_LABELS,
    legacy_status_to_care_stage,
)

LEAD_STATUSES: tuple[str, ...] = (
    *CARE_STAGE_KEYS,
    "lost",
    "pending_cleanup",
)

LEAD_STATUS_LABELS: dict[str, str] = {
    **CARE_STAGE_STATUS_LABELS,
    "lost": "Mất",
    "pending_cleanup": "Chờ làm sạch",
}

TERMINAL_STATUSES: frozenset[str] = frozenset({"lost", "post_sale"})

LEAD_LEVELS: tuple[str, ...] = ("hot", "warm", "cold")
LEAD_LEVEL_LABELS: dict[str, str] = {
    "hot": "Hot",
    "warm": "Warm",
    "cold": "Cold",
    "unclassified": "Chưa phân hạng",
}

ACTIVITY_TYPES: tuple[str, ...] = (
    "call",
    "email",
    "message",
    "meeting",
    "note",
    "proposal",
    "task",
    "reminder",
    "system",
)

ACTIVITY_TYPE_LABELS: dict[str, str] = {
    "call": "Gọi điện",
    "email": "Email",
    "message": "Tin nhắn",
    "meeting": "Họp",
    "note": "Ghi chú",
    "proposal": "Báo giá",
    "task": "Công việc",
    "reminder": "Nhắc việc",
    "system": "Hệ thống",
}

# Activity liên hệ khách — tự chuyển trạng thái lead sang «contacted» nếu còn «Mới»/chưa liên hệ.
OUTREACH_ACTIVITY_TYPES: frozenset[str] = frozenset({"call", "email", "message", "meeting"})
AUTO_CONTACTED_FROM_STATUSES: frozenset[str] = frozenset({"intake", "pending_cleanup", "nurture"})

LEAD_SOURCES: tuple[str, ...] = (
    "website",
    "facebook",
    "zalo",
    "google_ads",
    "referral",
    "import",
    "api",
    "manual",
    "email",
    "other",
)

LEAD_SOURCE_LABELS: dict[str, str] = {
    "website": "Website / Form",
    "facebook": "Facebook",
    "zalo": "Zalo",
    "google_ads": "Google Ads",
    "referral": "Giới thiệu",
    "import": "Import file",
    "api": "API",
    "manual": "Nhập tay",
    "email": "Email",
    "other": "Khác",
}

# SLA giờ theo bước chăm sóc
STATUS_SLA_HOURS: dict[str, int] = {
    "intake": 8,           # Phase 2 cao cấp: cần 8h chuẩn bị tài liệu ngách
    "first_contact": 48,   # 2 ngày gửi bộ tài liệu sau cuộc gọi đầu
    "qualify": 168,        # 7 ngày qualify sản phẩm giá trị cao
    "advise": 336,         # 14 ngày tư vấn + mời sự kiện / tham quan thực tế
    "nurture": 720,        # 30 ngày nuôi dưỡng (chu kỳ Phase 2: 30–90 ngày)
    "negotiate": 504,      # 21 ngày đàm phán shophouse / biệt thự / liền kề
    "closing": 336,        # 14 ngày hoàn tất thủ tục pháp lý phức tạp hơn Phase 1
    "post_sale": 0,
    "pending_cleanup": 48,
    "lost": 0,
}

ASSIGNMENT_POOL = "lead_round_robin"
_PHONE_RE = re.compile(r"\D+")
_PHONE_FORMAT_RE = re.compile(r"^0\d{8,10}$")
_EMAIL_FORMAT_RE = re.compile(r"^[a-z0-9._%+\-]+@[a-z0-9.\-]+\.[a-z]{2,}$")

DUPLICATE_MATCH_LABELS: dict[str, str] = {
    "phone": "trùng số điện thoại",
    "email": "trùng email",
    "both": "trùng số điện thoại và email",
}


def normalize_status(raw: str | None) -> str:
    s = str(raw or "intake").strip().lower().replace(" ", "_")
    if s in ("lost", "pending_cleanup"):
        return s
    if s in CARE_STAGE_KEYS:
        return s
    mapped = legacy_status_to_care_stage(s)
    if mapped in CARE_STAGE_KEYS:
        return mapped
    return "intake"


def normalize_level(raw: str | None, conn: sqlite3.Connection | None = None) -> str:
    from crm_lead_tiers import UNCLASSIFIED_TIER_ID, fetch_level_tiers

    s = str(raw or UNCLASSIFIED_TIER_ID).strip().lower()
    if s in LEAD_LEVELS or s == UNCLASSIFIED_TIER_ID:
        return s
    if conn is not None:
        ids = {str(t["id"]) for t in fetch_level_tiers(conn)}
        if s in ids:
            return s
    return UNCLASSIFIED_TIER_ID


def classify_level(
    score: int,
    *,
    status: str | None = None,
    conn: sqlite3.Connection | None = None,
) -> str:
    """FR-04: Phân loại theo ngưỡng điểm cấu hình."""
    st = normalize_status(status) if status else ""
    if st in ("negotiate", "closing", "post_sale"):
        return "hot"
    if st in ("lost", "nurture"):
        return "cold"
    from crm_lead_tiers import classify_score_to_tier, fetch_level_tiers

    tiers = fetch_level_tiers(conn)
    return classify_score_to_tier(score, tiers)


def normalize_source(raw: str | None) -> str:
    s = str(raw or "other").strip().lower().replace(" ", "_")
    aliases = {
        "web": "website",
        "form": "website",
        "google": "google_ads",
        "ads": "google_ads",
        "fb": "facebook",
        "khac": "other",
    }
    s = aliases.get(s, s)
    return s if s in LEAD_SOURCES else "other"


def normalize_phone(raw: str | None) -> str:
    digits = _PHONE_RE.sub("", str(raw or ""))
    if digits.startswith("84") and len(digits) >= 11:
        digits = "0" + digits[2:]
    return digits[:20]


def is_valid_phone_format(raw: str | None) -> bool:
    ph = normalize_phone(raw)
    return bool(ph and _PHONE_FORMAT_RE.match(ph))


def is_valid_email_format(raw: str | None) -> bool:
    em = normalize_email(raw)
    return bool(em and _EMAIL_FORMAT_RE.match(em))


def validate_lead_contacts(*, phone: str = "", email: str = "") -> tuple[str, str]:
    """Validate phone/email khi tạo/cập nhật lead — raise ValueError nếu sai định dạng."""
    ph_raw = str(phone or "").strip()
    em_raw = str(email or "").strip()
    ph_norm = normalize_phone(ph_raw) if ph_raw else ""
    em_norm = normalize_email(em_raw) if em_raw else ""
    if not ph_norm and not em_norm:
        raise ValueError("Cần số điện thoại hoặc email.")
    if ph_raw and not is_valid_phone_format(ph_raw):
        raise ValueError("Số điện thoại không hợp lệ (VD: 0901234567).")
    if em_raw and not is_valid_email_format(em_raw):
        raise ValueError("Email không hợp lệ.")
    return ph_norm, em_norm


def lead_needs_cleanup(
    *,
    full_name: str,
    phone: str,
    email: str,
    need: str = "",
    product_interest: str = "",
) -> tuple[bool, list[str]]:
    """Phát hiện lead thiếu / dữ liệu chưa sạch → pending_cleanup."""
    reasons: list[str] = []
    nm = str(full_name or "").strip()
    if len(nm) < 2:
        reasons.append("Tên quá ngắn")
    generic = {"zalo user", "lead webhook", "khach hang", "test", "n/a", "—"}
    if nm.lower() in generic:
        reasons.append("Tên chưa xác định")
    ph = normalize_phone(phone)
    if ph and not is_valid_phone_format(phone):
        reasons.append("SĐT không hợp lệ")
    em = normalize_email(email)
    if em and not is_valid_email_format(email):
        reasons.append("Email không hợp lệ")
    if not ph and not em:
        reasons.append("Thiếu liên hệ")
    if not str(need or "").strip() and not str(product_interest or "").strip():
        reasons.append("Thiếu nhu cầu / sản phẩm quan tâm")
    return bool(reasons), reasons


def normalize_email(raw: str | None) -> str:
    return str(raw or "").strip().lower()[:240]


def ensure_lead_schema(conn: sqlite3.Connection) -> None:
    from crm_lead_rules import ensure_lead_settings_schema

    ensure_lead_settings_schema(conn)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS crm_leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL DEFAULT '',
            phone TEXT NOT NULL DEFAULT '',
            phone_norm TEXT NOT NULL DEFAULT '',
            email TEXT NOT NULL DEFAULT '',
            email_norm TEXT NOT NULL DEFAULT '',
            source TEXT NOT NULL DEFAULT 'other',
            region TEXT NOT NULL DEFAULT '',
            product_interest TEXT NOT NULL DEFAULT '',
            need TEXT NOT NULL DEFAULT '',
            lead_score INTEGER NOT NULL DEFAULT 0,
            lead_level TEXT NOT NULL DEFAULT 'warm',
            status TEXT NOT NULL DEFAULT 'new',
            owner_id INTEGER REFERENCES crm_staff(id) ON DELETE SET NULL,
            duplicate_of_id INTEGER REFERENCES crm_leads(id) ON DELETE SET NULL,
            is_duplicate INTEGER NOT NULL DEFAULT 0,
            utm_campaign TEXT NOT NULL DEFAULT '',
            meta_json TEXT NOT NULL DEFAULT '{}',
            status_entered_at TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            created_by TEXT NOT NULL DEFAULT '',
            updated_by TEXT NOT NULL DEFAULT ''
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_crm_leads_phone ON crm_leads(phone_norm)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_crm_leads_email ON crm_leads(email_norm)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_crm_leads_owner ON crm_leads(owner_id, status)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_crm_leads_status ON crm_leads(status, status_entered_at)"
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS crm_lead_activities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lead_id INTEGER NOT NULL REFERENCES crm_leads(id) ON DELETE CASCADE,
            user_id INTEGER REFERENCES crm_staff(id) ON DELETE SET NULL,
            activity_type TEXT NOT NULL DEFAULT 'note',
            content TEXT NOT NULL DEFAULT '',
            result TEXT NOT NULL DEFAULT '',
            next_action TEXT NOT NULL DEFAULT '',
            next_action_at TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            created_by TEXT NOT NULL DEFAULT ''
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_crm_lead_act_lead ON crm_lead_activities(lead_id, created_at DESC)"
    )
    act_cols = {r[1] for r in conn.execute("PRAGMA table_info(crm_lead_activities)").fetchall()}
    if "lead_status_at_log" not in act_cols:
        conn.execute(
            "ALTER TABLE crm_lead_activities ADD COLUMN lead_status_at_log TEXT NOT NULL DEFAULT ''"
        )
    if "care_contact_type" not in act_cols:
        conn.execute(
            "ALTER TABLE crm_lead_activities ADD COLUMN care_contact_type TEXT NOT NULL DEFAULT ''"
        )
    if "care_status" not in act_cols:
        conn.execute(
            "ALTER TABLE crm_lead_activities ADD COLUMN care_status TEXT NOT NULL DEFAULT ''"
        )
    if "care_stage_key" not in act_cols:
        conn.execute(
            "ALTER TABLE crm_lead_activities ADD COLUMN care_stage_key TEXT NOT NULL DEFAULT ''"
        )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS crm_lead_status_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lead_id INTEGER NOT NULL REFERENCES crm_leads(id) ON DELETE CASCADE,
            old_status TEXT NOT NULL DEFAULT '',
            new_status TEXT NOT NULL DEFAULT '',
            changed_by TEXT NOT NULL DEFAULT '',
            note TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS crm_lead_assignment_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lead_id INTEGER NOT NULL REFERENCES crm_leads(id) ON DELETE CASCADE,
            from_user_id INTEGER,
            to_user_id INTEGER,
            reason TEXT NOT NULL DEFAULT '',
            created_by TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS crm_lead_ai_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lead_id INTEGER,
            action TEXT NOT NULL DEFAULT '',
            input_text TEXT NOT NULL DEFAULT '',
            output_json TEXT NOT NULL DEFAULT '{}',
            confidence REAL,
            fallback_used INTEGER NOT NULL DEFAULT 0,
            created_by TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL
        )
        """
    )
    cols = {r[1] for r in conn.execute("PRAGMA table_info(crm_leads)").fetchall()}
    if "converted_case_id" not in cols:
        conn.execute(
            "ALTER TABLE crm_leads ADD COLUMN converted_case_id INTEGER REFERENCES crm_cases(id)"
        )
    if "converted_customer_id" not in cols:
        conn.execute(
            "ALTER TABLE crm_leads ADD COLUMN converted_customer_id INTEGER REFERENCES crm_customers(id)"
        )
    from crm_project_leads import ensure_project_leads_schema

    ensure_project_leads_schema(conn)
    from crm_lead_care_pipeline import ensure_lead_care_pipeline_schema

    ensure_lead_care_pipeline_schema(conn)
    if "industry_slug" not in cols:
        conn.execute(
            "ALTER TABLE crm_leads ADD COLUMN industry_slug TEXT NOT NULL DEFAULT ''"
        )
    from crm_lead_catalog import ensure_lead_catalog_schema

    ensure_lead_catalog_schema(conn)
    from crm_lead_assign_scope import ensure_staff_assign_scope_schema

    ensure_staff_assign_scope_schema(conn)


def compute_lead_score(
    conn: sqlite3.Connection | None = None,
    *,
    source: str,
    phone: str,
    email: str,
    need: str,
    product_interest: str,
    region: str,
    activity_count: int = 0,
    full_name: str = "",
    meta: dict[str, Any] | None = None,
    activities: list[dict[str, Any]] | None = None,
) -> int:
    """FR-03: Chấm điểm lead theo rule cấu hình."""
    from crm_lead_scoring import score_lead

    result = score_lead(
        conn,
        source=source,
        phone=phone,
        email=email,
        need=need,
        product_interest=product_interest,
        region=region,
        full_name=full_name,
        meta=meta,
        activities=activities,
        activity_count=activity_count,
    )
    return int(result["score"])


def apply_lead_score(
    conn: sqlite3.Connection,
    lead_id: int,
    *,
    updated_by: str = "",
    ts: str,
) -> dict[str, Any]:
    """Tính lại điểm lead và lưu breakdown vào meta_json."""
    from crm_lead_scoring import score_lead

    row = fetch_lead_by_id(conn, lead_id)
    if row is None:
        raise ValueError("Không tìm thấy lead.")
    d = dict(row)
    meta_raw = d.get("meta_json") or "{}"
    try:
        meta = json.loads(meta_raw) if isinstance(meta_raw, str) else dict(meta_raw or {})
    except json.JSONDecodeError:
        meta = {}
    if not isinstance(meta, dict):
        meta = {}
    acts = fetch_lead_activities(conn, lead_id, limit=200)
    act_dicts = [activity_row_to_dict(a) for a in acts]
    act_count = int(d.get("activity_count") or len(act_dicts))
    result = score_lead(
        conn,
        source=str(d.get("source") or ""),
        phone=str(d.get("phone") or ""),
        email=str(d.get("email") or ""),
        need=str(d.get("need") or ""),
        product_interest=str(d.get("product_interest") or ""),
        region=str(d.get("region") or ""),
        full_name=str(d.get("full_name") or ""),
        meta=meta,
        activities=act_dicts,
        activity_count=act_count,
    )
    score = int(result["score"])
    st = normalize_status(d.get("status"))
    level = classify_level(score, status=st, conn=conn)
    if st in LEAD_LEVELS:
        level = normalize_level(st)
    meta["score_breakdown"] = result["breakdown"]
    meta["score_raw_total"] = result["raw_total"]
    meta["score_updated_at"] = ts
    conn.execute(
        """
        UPDATE crm_leads SET
            lead_score = ?, lead_level = ?, meta_json = ?,
            updated_at = ?, updated_by = ?
        WHERE id = ?
        """,
        (
            score,
            level,
            json.dumps(meta, ensure_ascii=False),
            ts,
            (updated_by or str(d.get("updated_by") or ""))[:120],
            int(lead_id),
        ),
    )
    return {"score": score, "lead_level": level, **result}


def duplicate_match_type(existing: sqlite3.Row | dict[str, Any], *, phone: str, email: str) -> str:
    ph = normalize_phone(phone)
    em = normalize_email(email)
    ex_ph = str(existing["phone_norm"] if isinstance(existing, sqlite3.Row) else existing.get("phone_norm") or "")
    ex_em = str(existing["email_norm"] if isinstance(existing, sqlite3.Row) else existing.get("email_norm") or "")
    phone_match = bool(ph and ex_ph and ph == ex_ph)
    email_match = bool(em and ex_em and em == ex_em)
    if phone_match and email_match:
        return "both"
    if phone_match:
        return "phone"
    if email_match:
        return "email"
    return "unknown"


def find_duplicate_leads(
    conn: sqlite3.Connection,
    *,
    phone: str,
    email: str,
    exclude_id: int | None = None,
    re_project_id: int | None = None,
    scope_project: bool = True,
) -> list[sqlite3.Row]:
    """FR-02: Phát hiện trùng theo phone/email (trong cùng dự án nếu scope_project)."""
    ph = normalize_phone(phone)
    em = normalize_email(email)
    if not ph and not em:
        return []
    clauses: list[str] = ["COALESCE(is_duplicate, 0) = 0"]
    params: list[Any] = []
    if scope_project:
        if re_project_id is not None:
            clauses.append("re_project_id = ?")
            params.append(int(re_project_id))
        else:
            clauses.append("re_project_id IS NULL")
    sub: list[str] = []
    if ph:
        sub.append("phone_norm = ?")
        params.append(ph)
    if em:
        sub.append("email_norm = ?")
        params.append(em)
    clauses.append("(" + " OR ".join(sub) + ")")
    if exclude_id:
        clauses.append("id != ?")
        params.append(int(exclude_id))
    return conn.execute(
        f"SELECT * FROM crm_leads WHERE {' AND '.join(clauses)} ORDER BY id ASC",
        params,
    ).fetchall()


def find_duplicate_matches(
    conn: sqlite3.Connection,
    *,
    phone: str,
    email: str,
    exclude_id: int | None = None,
    re_project_id: int | None = None,
    scope_project: bool = True,
) -> list[dict[str, Any]]:
    """FR-02: Trùng lead kèm loại trùng (phone / email / both)."""
    rows = find_duplicate_leads(
        conn,
        phone=phone,
        email=email,
        exclude_id=exclude_id,
        re_project_id=re_project_id,
        scope_project=scope_project,
    )
    out: list[dict[str, Any]] = []
    for row in rows:
        match_type = duplicate_match_type(row, phone=phone, email=email)
        out.append(
            {
                "lead_id": int(row["id"]),
                "full_name": str(row["full_name"] or ""),
                "phone": str(row["phone"] or ""),
                "email": str(row["email"] or ""),
                "match_type": match_type,
                "match_label": DUPLICATE_MATCH_LABELS.get(match_type, match_type),
                "row": row,
            }
        )
    return out


def _format_score_activity(breakdown: list[dict[str, Any]]) -> str:
    applied = [b for b in breakdown if b.get("applied")]
    if not applied:
        return "Không rule nào khớp."
    parts = [f"{b.get('label', b.get('id', 'rule'))} ({int(b.get('delta') or 0):+d})" for b in applied[:6]]
    extra = len(applied) - 6
    if extra > 0:
        parts.append(f"+{extra} rule khác")
    return "; ".join(parts)


def _level_label(conn: sqlite3.Connection | None, level_id: str) -> str:
    if conn is not None:
        try:
            from crm_lead_tiers import level_labels_map

            labels = {**LEAD_LEVEL_LABELS, **level_labels_map(conn)}
            return labels.get(level_id, level_id)
        except Exception:
            pass
    return LEAD_LEVEL_LABELS.get(level_id, level_id)


def _log_lead_create_pipeline(
    conn: sqlite3.Connection,
    *,
    lead_id: int,
    created_by: str,
    ts: str,
    ph_norm: str,
    em_norm: str,
    dup_matches: list[dict[str, Any]],
    score: int,
    score_result: dict[str, Any],
    level: str,
    src: str,
    needs_clean: bool,
    clean_reasons: list[str],
) -> None:
    """Ghi activity system-generated theo từng bước pipeline tạo lead."""
    contact_bits: list[str] = []
    if ph_norm:
        contact_bits.append("SĐT hợp lệ")
    if em_norm:
        contact_bits.append("Email hợp lệ")
    log_lead_activity(
        conn,
        lead_id=lead_id,
        activity_type="system",
        content="Kiểm tra liên hệ: " + (", ".join(contact_bits) if contact_bits else "—"),
        user_id=None,
        created_by=created_by,
        ts=ts,
    )
    if not dup_matches:
        log_lead_activity(
            conn,
            lead_id=lead_id,
            activity_type="system",
            content="Kiểm tra trùng: Không trùng lead hiện có.",
            created_by=created_by,
            ts=ts,
        )
    else:
        for dm in dup_matches[:5]:
            log_lead_activity(
                conn,
                lead_id=lead_id,
                activity_type="system",
                content=(
                    f"Kiểm tra trùng: Lead #{dm['lead_id']} "
                    f"({dm.get('match_label') or dm.get('match_type')})."
                ),
                created_by=created_by,
                ts=ts,
            )
    log_lead_activity(
        conn,
        lead_id=lead_id,
        activity_type="system",
        content=f"Chấm điểm: {score} điểm. {_format_score_activity(score_result.get('breakdown') or [])}",
        created_by=created_by,
        ts=ts,
    )
    level_label = _level_label(conn, level)
    log_lead_activity(
        conn,
        lead_id=lead_id,
        activity_type="system",
        content=f"Phân hạng: {level_label} (mã {level}).",
        created_by=created_by,
        ts=ts,
    )
    log_lead_activity(
        conn,
        lead_id=lead_id,
        activity_type="system",
        content=f"Lead được tạo từ nguồn {LEAD_SOURCE_LABELS.get(src, src)}.",
        created_by=created_by,
        ts=ts,
    )
    if needs_clean and clean_reasons:
        log_lead_activity(
            conn,
            lead_id=lead_id,
            activity_type="system",
            content="Chờ làm sạch: " + "; ".join(clean_reasons[:5]),
            created_by=created_by,
            ts=ts,
        )


def _staff_workload(conn: sqlite3.Connection, staff_id: int) -> int:
    row = conn.execute(
        """
        SELECT COUNT(*) AS c FROM crm_leads
        WHERE owner_id = ? AND status NOT IN ('won', 'lost')
        """,
        (staff_id,),
    ).fetchone()
    return int(row["c"]) if row else 0


def assign_lead_owner(
    conn: sqlite3.Connection,
    *,
    region: str = "",
    product_interest: str = "",
    industry_slug: str = "",
    prefer_staff_id: int | None = None,
    lead_level: str = "warm",
    lead_score: int = 0,
    source: str = "",
    need: str = "",
    prefer_min_workload: bool = False,
    re_project_id: int | None = None,
    product_line: str = "",
    zone: str = "",
) -> tuple[int | None, str, str]:
    """FR-05: Gán owner theo cấu hình phương pháp phân lead. Trả (staff_id, tên, strategy)."""
    from crm_lead_auto_assign import LeadAssignContext, auto_assign_lead_owner
    from crm_lead_rules import fetch_lead_config

    cfg = fetch_lead_config(conn)
    assign_cfg = cfg.get("assign_config") or {}
    # Tương thích cấu hình cũ: hot_priority_assign → hot_priority_min_load
    if not assign_cfg.get("strategies"):
        assign_cfg = dict(assign_cfg)
        assign_cfg["auto_assign_enabled"] = True
    legacy_hot = bool(cfg.get("hot_priority_assign", True))
    if legacy_hot is False and assign_cfg.get("strategies"):
        strategies = []
        for s in assign_cfg["strategies"]:
            item = dict(s)
            if item.get("id") == "hot_priority_min_load":
                item["enabled"] = False
            strategies.append(item)
        assign_cfg = {**assign_cfg, "strategies": strategies}

    ctx = LeadAssignContext(
        lead_level=str(lead_level or "warm"),
        lead_score=int(lead_score or 0),
        region=str(region or ""),
        product_interest=str(product_interest or ""),
        industry_slug=str(industry_slug or ""),
        source=str(source or ""),
        need=str(need or ""),
        prefer_staff_id=prefer_staff_id,
        prefer_min_workload=prefer_min_workload,
        re_project_id=re_project_id,
        product_line=str(product_line or ""),
        zone=str(zone or ""),
    )
    sid, name, strategy = auto_assign_lead_owner(conn, ctx, config=assign_cfg)
    return sid, name, strategy


def _parse_ts(ts: str | None) -> datetime | None:
    raw = str(ts or "").strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(raw[:19], fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")[:19])
    except ValueError:
        return None


def is_sla_overdue(status: str, status_entered_at: str | None, *, now: datetime | None = None) -> bool:
    st = normalize_status(status)
    sla = STATUS_SLA_HOURS.get(st, 0)
    if sla <= 0 or st in TERMINAL_STATUSES:
        return False
    entered = _parse_ts(status_entered_at)
    if entered is None:
        return False
    ref = now or datetime.now()
    hours = (ref - entered).total_seconds() / 3600.0
    return hours > sla


def lead_row_to_dict(row: sqlite3.Row | dict[str, Any], conn: sqlite3.Connection | None = None) -> dict[str, Any]:
    d = dict(row)
    meta_raw = d.get("meta_json") or "{}"
    try:
        meta = json.loads(meta_raw) if isinstance(meta_raw, str) else meta_raw
    except json.JSONDecodeError:
        meta = {}
    st = normalize_status(d.get("status"))
    lv = normalize_level(d.get("lead_level"), conn)
    level_labels = LEAD_LEVEL_LABELS
    if conn is not None:
        try:
            from crm_lead_tiers import level_labels_map

            level_labels = {**LEAD_LEVEL_LABELS, **level_labels_map(conn)}
        except Exception:
            level_labels = LEAD_LEVEL_LABELS
    sla_status = is_sla_overdue(st, str(d.get("status_entered_at") or ""))
    sla_no_activity = False
    if conn is not None:
        try:
            from crm_lead_rules import fetch_lead_config, is_no_activity_sla_overdue

            if fetch_lead_config(conn).get("activity_sla_enabled"):
                sla_no_activity = is_no_activity_sla_overdue(
                    conn,
                    lead_id=int(d["id"]),
                    status=st,
                    status_entered_at=str(d.get("status_entered_at") or ""),
                    created_at=str(d.get("created_at") or ""),
                )
        except Exception:
            sla_no_activity = False
    received_at = _lead_received_at(
        meta if isinstance(meta, dict) else {},
        created_at=str(d.get("created_at") or ""),
    )
    assigned_at = _lead_assigned_at(
        meta if isinstance(meta, dict) else {},
        owner_id=int(d["owner_id"]) if d.get("owner_id") else None,
        first_assigned_at=str(d.get("first_assigned_at") or ""),
        updated_at=str(d.get("updated_at") or ""),
    )
    pipeline_alert, pipeline_alert_message = lead_pipeline_alert(
        meta if isinstance(meta, dict) else {},
        source=str(d.get("source") or ""),
        owner_id=int(d["owner_id"]) if d.get("owner_id") else None,
        is_duplicate=bool(d.get("is_duplicate")),
        created_by=str(d.get("created_by") or ""),
    )
    from crm_lead_care_pipeline import care_pipeline_state, presales_care_gate_state
    from crm_lead_catalog import get_industry_label, get_service_label
    from crm_lead_review_queue import review_queue_public_state

    care_pipeline = care_pipeline_state(
        status=st,
        care_stage_current=str(d.get("care_stage_current") or ""),
        care_stages_done_json=str(d.get("care_stages_done_json") or ""),
    )
    care_label = str(care_pipeline.get("current_stage_label") or LEAD_STATUS_LABELS.get(st, st))
    if st == "pending_cleanup":
        status_label = f"{care_label} · Chờ làm sạch"
    elif st == "lost":
        status_label = "Mất"
    else:
        status_label = care_label
    result: dict[str, Any] = {
        "id": int(d["id"]),
        "full_name": str(d.get("full_name") or ""),
        "phone": str(d.get("phone") or ""),
        "email": str(d.get("email") or ""),
        "source": normalize_source(d.get("source")),
        "source_label": LEAD_SOURCE_LABELS.get(normalize_source(d.get("source")), "Khác"),
        "region": str(d.get("region") or ""),
        "product_interest": str(d.get("product_interest") or ""),
        "product_interest_label": (
            get_service_label(conn, str(d.get("product_interest") or ""))
            if conn is not None
            else str(d.get("product_interest") or "")
        ),
        "industry_slug": str(d.get("industry_slug") or ""),
        "industry_label": (
            get_industry_label(conn, str(d.get("industry_slug") or ""))
            if conn is not None
            else str(d.get("industry_slug") or "")
        ),
        "need": str(d.get("need") or ""),
        "lead_score": int(d.get("lead_score") or 0),
        "lead_level": lv,
        "lead_level_label": level_labels.get(lv, lv),
        "status": st,
        "status_label": status_label,
        "care_stage_key": care_pipeline.get("current_stage_key") or st,
        "owner_id": int(d["owner_id"]) if d.get("owner_id") else None,
        "owner_name": str(d.get("owner_name") or ""),
        "owner_code": str(d.get("owner_code") or ""),
        "duplicate_of_id": int(d["duplicate_of_id"]) if d.get("duplicate_of_id") else None,
        "is_duplicate": bool(d.get("is_duplicate")),
        "utm_campaign": str(d.get("utm_campaign") or ""),
        "meta": meta if isinstance(meta, dict) else {},
        "status_entered_at": str(d.get("status_entered_at") or ""),
        "sla_overdue": sla_status or sla_no_activity,
        "sla_status_overdue": sla_status,
        "sla_no_activity": sla_no_activity,
        "created_at": str(d.get("created_at") or ""),
        "updated_at": str(d.get("updated_at") or ""),
        "created_by": str(d.get("created_by") or ""),
        "updated_by": str(d.get("updated_by") or ""),
        "activity_count": int(d.get("activity_count") or 0),
        "last_activity_at": str(d.get("last_activity_at") or ""),
        "score_breakdown": meta.get("score_breakdown") if isinstance(meta.get("score_breakdown"), list) else [],
        "score_raw_total": meta.get("score_raw_total"),
        "score_updated_at": str(meta.get("score_updated_at") or ""),
        "ai_qualify_brief": meta.get("ai_qualify_brief") if isinstance(meta.get("ai_qualify_brief"), dict) else None,
        "converted_case_id": int(d["converted_case_id"]) if d.get("converted_case_id") else None,
        "converted_customer_id": int(d["converted_customer_id"]) if d.get("converted_customer_id") else None,
        "re_project_id": int(d["re_project_id"]) if d.get("re_project_id") else None,
        "re_project_name": str(d.get("re_project_name") or ""),
        "re_project_code": str(d.get("re_project_code") or ""),
        "re_project_label": _lead_project_label(d),
        "re_project_full_label": _lead_project_full_label(d),
        "product_line": str(d.get("product_line") or ""),
        "product_line_label": _lead_product_line_label(d),
        "zone": str(d.get("zone") or ""),
        "re_product_id": int(d["re_product_id"]) if d.get("re_product_id") else None,
        "re_product_unit_code": str(d.get("re_product_unit_code") or ""),
        "re_product_status": str(d.get("re_product_status") or ""),
        "re_product_label": _lead_product_label(d),
        "received_at": received_at,
        "facebook_received_at": received_at,
        "assigned_at": assigned_at,
        "pipeline_alert": pipeline_alert,
        "pipeline_alert_message": pipeline_alert_message,
        "care_pipeline": care_pipeline,
        "presales_care_gate": presales_care_gate_state(
            care_stage_current=str(d.get("care_stage_current") or ""),
            care_stages_done_json=str(d.get("care_stages_done_json") or ""),
        ),
        "review_queue": review_queue_public_state(
            meta if isinstance(meta, dict) else {},
            assigned_at=assigned_at,
        ),
    }
    try:
        from crm_lead_industry_addon import lead_industry_addon_payload

        result["industry_addon"] = lead_industry_addon_payload(
            conn, int(d["id"]), industry_slug=str(d.get("industry_slug") or "")
        )
    except Exception:
        result["industry_addon"] = {
            "industry_slug": str(d.get("industry_slug") or ""),
            "pack": None,
            "data": {},
            "has_pack": False,
            "legacy_re_removed": True,
        }
    return result


def activity_row_to_dict(row: sqlite3.Row | dict[str, Any]) -> dict[str, Any]:
    d = dict(row)
    at = str(d.get("activity_type") or "note")
    st = str(d.get("lead_status_at_log") or "").strip()
    ct = str(d.get("care_contact_type") or "").strip()
    cs = str(d.get("care_status") or "").strip()
    from crm_lead_care_pipeline import care_stage_for_status, care_stage_label

    csk = str(d.get("care_stage_key") or "").strip()
    if not csk:
        csk = care_stage_for_status(st)
    return {
        "id": int(d["id"]),
        "lead_id": int(d["lead_id"]),
        "user_id": int(d["user_id"]) if d.get("user_id") else None,
        "user_name": str(d.get("user_name") or ""),
        "activity_type": at,
        "activity_type_label": ACTIVITY_TYPE_LABELS.get(at, at),
        "lead_status_at_log": st,
        "lead_status_at_log_label": LEAD_STATUS_LABELS.get(st, st) if st else "",
        "care_contact_type": ct,
        "care_contact_type_label": CRM_CARE_CONTACT_LABELS_VI.get(ct, ct) if ct else "",
        "care_status": cs,
        "care_status_label": CRM_CARE_STATUS_LABELS_VI.get(cs, cs) if cs else "",
        "care_stage_key": csk,
        "care_stage_label": care_stage_label(csk) if csk else "",
        "content": str(d.get("content") or ""),
        "result": str(d.get("result") or ""),
        "next_action": str(d.get("next_action") or ""),
        "next_action_at": str(d.get("next_action_at") or ""),
        "created_at": str(d.get("created_at") or ""),
        "created_by": str(d.get("created_by") or ""),
    }


_LEAD_SELECT = """
    SELECT l.*,
           s.name AS owner_name,
           s.internal_code AS owner_code,
           p.name AS re_project_name,
           p.code AS re_project_code,
           pr.unit_code AS re_product_unit_code,
           pr.zone AS re_product_zone,
           pr.product_line AS re_product_line,
           pr.status AS re_product_status,
           (SELECT COUNT(*) FROM crm_lead_activities a WHERE a.lead_id = l.id) AS activity_count,
           (SELECT MAX(a.created_at) FROM crm_lead_activities a WHERE a.lead_id = l.id) AS last_activity_at,
           (
             SELECT MIN(a2.created_at)
             FROM crm_lead_assignment_logs a2
             WHERE a2.lead_id = l.id AND a2.to_user_id IS NOT NULL
           ) AS first_assigned_at
    FROM crm_leads l
    LEFT JOIN crm_staff s ON s.id = l.owner_id
    LEFT JOIN crm_re_projects p ON p.id = l.re_project_id
    LEFT JOIN crm_re_project_products pr ON pr.id = l.re_product_id
"""

# Sắp theo ngày đổ về DESC — khớp cột «Đổ về» (_lead_received_at).
_LEAD_SORT_RECEIVED_AT = """
    COALESCE(
        NULLIF(substr(replace(trim(json_extract(l.meta_json, '$.facebook_created_time')), 'T', ' '), 1, 19), ''),
        NULLIF(substr(replace(trim(json_extract(l.meta_json, '$.ingested_at')), 'T', ' '), 1, 19), ''),
        NULLIF(substr(replace(trim(l.created_at), 'T', ' '), 1, 19), ''),
        '1970-01-01 00:00:00'
    )
"""


def _lead_project_label(d: sqlite3.Row | dict[str, Any]) -> str:
    pid = d.get("re_project_id")
    if not pid:
        return ""
    from crm_project_leads import format_project_display_label, format_project_full_label

    return format_project_display_label(
        code=str(d.get("re_project_code") or ""),
        name=str(d.get("re_project_name") or ""),
        project_id=int(pid),
    )


def _lead_project_full_label(d: sqlite3.Row | dict[str, Any]) -> str:
    pid = d.get("re_project_id")
    if not pid:
        return ""
    from crm_project_leads import format_project_full_label

    return format_project_full_label(
        code=str(d.get("re_project_code") or ""),
        name=str(d.get("re_project_name") or ""),
        project_id=int(pid),
    )


def _lead_product_line_label(d: sqlite3.Row | dict[str, Any]) -> str:
    line = str(d.get("product_line") or "").strip()
    if not line:
        return ""
    try:
        from crm_re_projects import PRODUCT_LINE_LABELS

        return PRODUCT_LINE_LABELS.get(line, line)
    except Exception:
        return line


def _lead_product_label(d: sqlite3.Row | dict[str, Any]) -> str:
    unit = str(d.get("re_product_unit_code") or "").strip()
    if not unit:
        pid = d.get("re_product_id")
        return f"#{pid}" if pid else ""
    zone = str(d.get("re_product_zone") or d.get("zone") or "").strip()
    if zone:
        return f"{unit} · {zone}"
    return unit


def _normalize_lead_ts(raw: str | None) -> str:
    s = str(raw or "").strip()
    if not s:
        return ""
    return s.replace("T", " ")[:19]


def _ensure_ingested_at_meta(
    meta: dict[str, Any],
    *,
    ts: str,
    created_by: str,
) -> None:
    """Ghi ingested_at cho ingest tự động (webhook, form) — không ghi đè nếu đã có."""
    if _normalize_lead_ts(str(meta.get("ingested_at") or "")):
        return
    cb = str(created_by or "").strip().lower()
    if cb.startswith("system:") or cb.startswith("webhook:"):
        meta["ingested_at"] = ts


def _lead_received_at(meta: dict[str, Any], *, created_at: str) -> str:
    """Thời điểm lead đổ về — mọi nguồn (FB, Zalo, webform, nhập tay…)."""
    for key in ("facebook_created_time", "ingested_at"):
        v = _normalize_lead_ts(str(meta.get(key) or ""))
        if v:
            return v
    return _normalize_lead_ts(created_at)


def _lead_facebook_received_at(
    meta: dict[str, Any],
    *,
    source: str = "",
    created_at: str = "",
) -> str:
    """Alias cũ — dùng _lead_received_at."""
    _ = source
    return _lead_received_at(meta, created_at=created_at)


def _lead_assigned_at(
    meta: dict[str, Any],
    *,
    owner_id: int | None,
    first_assigned_at: str = "",
    updated_at: str = "",
) -> str:
    for key in ("auto_assigned_at", "facebook_enriched_at"):
        v = _normalize_lead_ts(str(meta.get(key) or ""))
        if v and owner_id:
            return v
    fa = _normalize_lead_ts(first_assigned_at)
    if fa:
        return fa
    if owner_id:
        return _normalize_lead_ts(updated_at)
    return ""


def lead_pipeline_alert(
    meta: dict[str, Any],
    *,
    source: str,
    owner_id: int | None,
    is_duplicate: bool,
    created_by: str = "",
) -> tuple[bool, str]:
    """Lead cần xử lý: lỗi ingest hoặc chưa phân công."""
    if is_duplicate:
        return False, ""
    msgs: list[str] = []

    if meta.get("awaiting_facebook_graph"):
        msgs.append("Chờ dữ liệu Facebook (Graph API)")
    err = str(
        meta.get("_graph_error")
        or meta.get("facebook_pending_error")
        or meta.get("assign_failed_reason")
        or ""
    ).strip()
    if err:
        msgs.append(err[:120])
    if meta.get("assign_failed"):
        msgs.append("Tự động phân công thất bại")
    if not owner_id:
        msgs.append("Chưa gán owner")

    if not msgs:
        return False, ""
    # dedupe preserve order
    seen: set[str] = set()
    uniq: list[str] = []
    for m in msgs:
        if m not in seen:
            seen.add(m)
            uniq.append(m)
    return True, " · ".join(uniq)


def _lead_list_filters(
    *,
    owner_id: int | None = None,
    status: str | None = None,
    level: str | None = None,
    source: str | None = None,
    q: str | None = None,
    re_project_id: int | None | object = _UNSET,
    product_line: str | None = None,
    zone: str | None = None,
    staff_portal_id: int | None = None,
    hide_review_queue: bool = True,
    review_queue_only: bool = False,
) -> tuple[list[str], list[Any]]:
    """Mệnh đề WHERE danh sách lead — dùng chung count + fetch."""
    clauses: list[str] = [
        "("
        "COALESCE(l.is_duplicate, 0) = 0 "
        "OR l.source = 'facebook' "
        "OR COALESCE(json_extract(l.meta_json, '$.facebook_leadgen_id'), '') != ''"
        ")"
    ]
    params: list[Any] = []
    if staff_portal_id is not None:
        from crm_project_leads import lead_portal_scope_sql

        scope_sql, scope_params = lead_portal_scope_sql(int(staff_portal_id), alias="l")
        clauses.append(f"({scope_sql})")
        params.extend(scope_params)
    elif owner_id is not None:
        clauses.append("l.owner_id = ?")
        params.append(int(owner_id))
    if status:
        sk = normalize_status(status)
        if sk in CARE_STAGE_KEYS:
            clauses.append("(l.status = ? OR l.care_stage_current = ?)")
            params.extend([sk, sk])
        else:
            clauses.append("l.status = ?")
            params.append(sk)
    if level:
        clauses.append("l.lead_level = ?")
        params.append(normalize_level(level))
    if source:
        clauses.append("l.source = ?")
        params.append(normalize_source(source))
    if re_project_id is not _UNSET:
        if re_project_id is None:
            clauses.append("l.re_project_id IS NULL")
        else:
            clauses.append("l.re_project_id = ?")
            params.append(int(re_project_id))
    if product_line:
        clauses.append("l.product_line = ?")
        params.append(str(product_line).strip())
    if zone:
        clauses.append("trim(l.zone) = ?")
        params.append(str(zone).strip())
    if q:
        like = f"%{str(q).strip()}%"
        clauses.append(
            "(l.full_name LIKE ? OR l.phone LIKE ? OR l.email LIKE ? OR l.need LIKE ? OR l.product_interest LIKE ?)"
        )
        params.extend([like] * 5)
    if review_queue_only:
        clauses.append("COALESCE(json_extract(l.meta_json, '$.review_queue.active'), '') = 'true'")
    elif hide_review_queue:
        clauses.append("COALESCE(json_extract(l.meta_json, '$.review_queue.active'), '') != 'true'")
    return clauses, params


def count_leads(
    conn: sqlite3.Connection,
    *,
    owner_id: int | None = None,
    status: str | None = None,
    level: str | None = None,
    source: str | None = None,
    q: str | None = None,
    re_project_id: int | None | object = _UNSET,
    product_line: str | None = None,
    zone: str | None = None,
    staff_portal_id: int | None = None,
    hide_review_queue: bool = True,
    review_queue_only: bool = False,
) -> int:
    clauses, params = _lead_list_filters(
        owner_id=owner_id,
        status=status,
        level=level,
        source=source,
        q=q,
        re_project_id=re_project_id,
        product_line=product_line,
        zone=zone,
        staff_portal_id=staff_portal_id,
        hide_review_queue=hide_review_queue,
        review_queue_only=review_queue_only,
    )
    where = " WHERE " + " AND ".join(clauses)
    row = conn.execute(f"SELECT COUNT(*) AS c FROM crm_leads l{where}", params).fetchone()
    return int(row["c"] or 0) if row else 0


def fetch_leads(
    conn: sqlite3.Connection,
    *,
    owner_id: int | None = None,
    status: str | None = None,
    level: str | None = None,
    source: str | None = None,
    q: str | None = None,
    re_project_id: int | None | object = _UNSET,
    product_line: str | None = None,
    zone: str | None = None,
    staff_portal_id: int | None = None,
    sla_overdue_only: bool = False,
    hide_review_queue: bool = True,
    review_queue_only: bool = False,
    limit: int = 100,
    offset: int = 0,
) -> list[sqlite3.Row]:
    clauses, params = _lead_list_filters(
        owner_id=owner_id,
        status=status,
        level=level,
        source=source,
        q=q,
        re_project_id=re_project_id,
        product_line=product_line,
        zone=zone,
        staff_portal_id=staff_portal_id,
        hide_review_queue=hide_review_queue,
        review_queue_only=review_queue_only,
    )
    where = " WHERE " + " AND ".join(clauses)
    lim = max(1, min(int(limit), 1000))
    off = max(0, int(offset))
    # Sắp ngày đổ về mới nhất trước.
    fetch_lim = min(1000, lim * 5) if sla_overdue_only else lim
    rows = conn.execute(
        f"""{_LEAD_SELECT}{where}
        ORDER BY {_LEAD_SORT_RECEIVED_AT} DESC, l.id DESC
        LIMIT ? OFFSET ?""",
        [*params, fetch_lim, off],
    ).fetchall()
    if not sla_overdue_only:
        return rows[:lim]
    enriched: list[sqlite3.Row] = []
    for r in rows:
        d = lead_row_to_dict(r, conn)
        if d.get("sla_overdue"):
            enriched.append(r)
        if len(enriched) >= lim:
            break
    return enriched


def fetch_max_lead_id(conn: sqlite3.Connection) -> int:
    row = conn.execute(
        "SELECT COALESCE(MAX(id), 0) FROM crm_leads WHERE COALESCE(is_duplicate, 0) = 0"
    ).fetchone()
    return int(row[0] or 0) if row else 0


def fetch_max_lead_id_any(conn: sqlite3.Connection) -> int:
    """Max id mọi lead — dùng poll thông báo (Facebook kể cả duplicate)."""
    row = conn.execute("SELECT COALESCE(MAX(id), 0) FROM crm_leads").fetchone()
    return int(row[0] or 0) if row else 0


def fetch_new_assigned_leads(
    conn: sqlite3.Connection,
    *,
    after_id: int = 0,
    owner_id: int | None = None,
    staff_portal_id: int | None = None,
    limit: int = 20,
) -> list[sqlite3.Row]:
    """Lead mới (id > after_id) đã gán owner — thông báo toast (một lần / lead).

    Chỉ lead đã phân công xong (owner_id NOT NULL), không gồm bản ghi trùng.
    Portal NV: scope theo dự án tham gia (Phase 4).
    """
    lim = max(1, min(int(limit), 50))
    aid = max(0, int(after_id))
    clauses = [
        "l.id > ?",
        "l.owner_id IS NOT NULL",
        "COALESCE(l.is_duplicate, 0) = 0",
    ]
    params: list[Any] = [aid]
    if staff_portal_id is not None:
        from crm_project_leads import lead_portal_scope_sql

        scope_sql, scope_params = lead_portal_scope_sql(int(staff_portal_id), alias="l")
        clauses.append(f"({scope_sql})")
        params.extend(scope_params)
    elif owner_id is not None:
        clauses.append("l.owner_id = ?")
        params.append(int(owner_id))
    params.append(lim)
    where = " AND ".join(clauses)
    return conn.execute(
        f"""{_LEAD_SELECT}
        WHERE {where}
        ORDER BY l.id ASC LIMIT ?""",
        params,
    ).fetchall()


def fetch_facebook_webhook_repeat_leads(
    conn: sqlite3.Connection,
    *,
    since_ts: str,
    owner_id: int | None = None,
    limit: int = 10,
) -> list[sqlite3.Row]:
    """Lead Facebook vừa nhận webhook lặp (cùng leadgen_id) — id có thể <= cursor poll."""
    since = str(since_ts or "").strip()[:19]
    if not since:
        return []
    lim = max(1, min(int(limit), 20))
    if owner_id is not None:
        return conn.execute(
            f"""{_LEAD_SELECT}
            WHERE l.source = 'facebook'
              AND COALESCE(l.is_duplicate, 0) = 0
              AND l.owner_id = ?
              AND l.updated_at >= ?
            ORDER BY l.updated_at DESC LIMIT ?""",
            (int(owner_id), since, lim),
        ).fetchall()
    return conn.execute(
        f"""{_LEAD_SELECT}
        WHERE l.source = 'facebook'
          AND l.updated_at >= ?
        ORDER BY l.updated_at DESC LIMIT ?""",
        (since, lim),
    ).fetchall()


def fetch_lead_by_id(conn: sqlite3.Connection, lead_id: int) -> sqlite3.Row | None:
    return conn.execute(f"{_LEAD_SELECT} WHERE l.id = ?", (int(lead_id),)).fetchone()


def fetch_lead_activities(
    conn: sqlite3.Connection, lead_id: int, *, limit: int = 100
) -> list[sqlite3.Row]:
    lim = max(1, min(int(limit), 500))
    return conn.execute(
        """
        SELECT a.*, s.name AS user_name
        FROM crm_lead_activities a
        LEFT JOIN crm_staff s ON s.id = a.user_id
        WHERE a.lead_id = ?
        ORDER BY a.created_at DESC
        LIMIT ?
        """,
        (int(lead_id), lim),
    ).fetchall()


def _auto_status_on_outreach_activity(
    conn: sqlite3.Connection,
    *,
    lead_id: int,
    activity_type: str,
    created_by: str,
    ts: str,
) -> bool:
    """Pipeline chăm sóc quản lý trạng thái — không tự chuyển «contacted»."""
    return False


def log_lead_activity(
    conn: sqlite3.Connection,
    *,
    lead_id: int,
    activity_type: str,
    content: str = "",
    result: str = "",
    next_action: str = "",
    next_action_at: str = "",
    care_contact_type: str = "",
    care_status: str = "",
    care_stage_key: str = "",
    user_id: int | None = None,
    created_by: str = "",
    ts: str,
) -> sqlite3.Row:
    at = str(activity_type or "note").strip().lower()
    if at not in ACTIVITY_TYPES:
        at = "note"
    ct = normalize_care_contact(care_contact_type) if care_contact_type else ""
    cs = normalize_care_status(care_status) if care_status else ""
    from crm_lead_care_pipeline import CARE_STAGE_KEYS, care_stage_for_status

    lead_row = fetch_lead_by_id(conn, lead_id)
    status_snap = normalize_status(lead_row["status"]) if lead_row else "new"
    csk = str(care_stage_key or "").strip()
    if csk not in CARE_STAGE_KEYS:
        csk = str(lead_row["care_stage_current"] or "").strip() if lead_row else ""
    if csk not in CARE_STAGE_KEYS:
        csk = care_stage_for_status(status_snap)
    conn.execute(
        """
        INSERT INTO crm_lead_activities (
            lead_id, user_id, activity_type, content, result,
            next_action, next_action_at, created_at, created_by, lead_status_at_log,
            care_contact_type, care_status, care_stage_key
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            int(lead_id),
            user_id,
            at,
            str(content or "")[:8000],
            str(result or "")[:2000],
            str(next_action or "")[:500],
            str(next_action_at or "")[:40],
            ts,
            created_by[:120],
            status_snap,
            ct,
            cs,
            csk,
        ),
    )
    conn.execute(
        "UPDATE crm_leads SET updated_at = ?, updated_by = ? WHERE id = ?",
        (ts, created_by[:120], int(lead_id)),
    )
    _auto_status_on_outreach_activity(
        conn,
        lead_id=lead_id,
        activity_type=at,
        created_by=created_by,
        ts=ts,
    )
    if ct or cs:
        from crm_lead_care_pipeline import sync_lead_status_to_care_stage

        sync_lead_status_to_care_stage(
            conn,
            lead_id=lead_id,
            stage_key=csk,
            created_by=created_by,
            ts=ts,
            note="Cập nhật khi báo cáo chăm sóc",
        )
    aid = int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])
    row = conn.execute(
        """
        SELECT a.*, s.name AS user_name FROM crm_lead_activities a
        LEFT JOIN crm_staff s ON s.id = a.user_id WHERE a.id = ?
        """,
        (aid,),
    ).fetchone()
    assert row is not None
    try:
        apply_lead_score(conn, lead_id, updated_by=created_by, ts=ts)
    except Exception:
        pass
    return row


def log_status_change(
    conn: sqlite3.Connection,
    *,
    lead_id: int,
    old_status: str,
    new_status: str,
    changed_by: str,
    note: str,
    ts: str,
) -> None:
    conn.execute(
        """
        INSERT INTO crm_lead_status_logs (lead_id, old_status, new_status, changed_by, note, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (int(lead_id), old_status, new_status, changed_by[:120], note[:2000], ts),
    )


def log_assignment(
    conn: sqlite3.Connection,
    *,
    lead_id: int,
    from_user_id: int | None,
    to_user_id: int | None,
    reason: str,
    created_by: str,
    ts: str,
) -> None:
    conn.execute(
        """
        INSERT INTO crm_lead_assignment_logs
            (lead_id, from_user_id, to_user_id, reason, created_by, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (int(lead_id), from_user_id, to_user_id, reason[:500], created_by[:120], ts),
    )


def create_lead(
    conn: sqlite3.Connection,
    *,
    full_name: str,
    phone: str = "",
    email: str = "",
    source: str = "manual",
    region: str = "",
    product_interest: str = "",
    need: str = "",
    status: str = "new",
    owner_id: int | None = None,
    re_project_id: int | None = None,
    product_line: str = "",
    zone: str = "",
    re_product_id: int | None = None,
    utm_campaign: str = "",
    industry_slug: str = "",
    meta: dict[str, Any] | None = None,
    auto_assign: bool = True,
    duplicate_policy: str | None = None,
    created_by: str = "",
    ts: str,
) -> tuple[sqlite3.Row, list[sqlite3.Row], list[dict[str, Any]]]:
    """Tạo lead mới; trả (lead, duplicates_found, duplicate_matches)."""
    from crm_lead_catalog import normalize_industry_slug, normalize_product_interest
    from crm_lead_industry_addon import reject_re_legacy_lead_input
    from crm_lead_rules import merge_incoming_into_primary, resolve_duplicate_policy

    reject_re_legacy_lead_input(
        re_project_id=re_project_id,
        product_line=product_line,
        zone=zone,
        re_product_id=re_product_id,
    )
    re_project_id = None
    product_line = ""
    zone = ""
    re_product_id = None

    if not str(source or "").strip():
        raise ValueError("Lead phải có nguồn (source).")
    if not str(full_name or "").strip():
        raise ValueError("Thiếu họ tên lead.")
    ph_norm, em_norm = validate_lead_contacts(phone=phone, email=email)
    prod_interest = normalize_product_interest(conn, product_interest)
    industry_key = normalize_industry_slug(conn, industry_slug)

    needs_clean, clean_reasons = lead_needs_cleanup(
        full_name=full_name,
        phone=phone,
        email=email,
        need=need,
        product_interest=prod_interest,
    )
    dup_matches = find_duplicate_matches(
        conn, phone=phone, email=email, re_project_id=re_project_id
    )
    dups = [m["row"] for m in dup_matches]
    policy = resolve_duplicate_policy(conn, duplicate_policy)
    st = normalize_status(status)
    if needs_clean and st not in ("lost",):
        st = "pending_cleanup"
    elif st not in ("lost", "pending_cleanup"):
        st = "intake" if st not in CARE_STAGE_KEYS else st
    src = normalize_source(source)
    act_count = 0
    meta_obj = dict(meta or {})
    _ensure_ingested_at_meta(meta_obj, ts=ts, created_by=created_by)
    from crm_lead_scoring import score_lead

    score_result = score_lead(
        conn,
        source=src,
        phone=phone,
        email=email,
        need=need,
        product_interest=prod_interest,
        region=region,
        full_name=full_name,
        meta=meta_obj,
        activity_count=act_count,
    )
    meta_obj["score_breakdown"] = score_result["breakdown"]
    meta_obj["score_raw_total"] = score_result["raw_total"]
    meta_obj["score_updated_at"] = ts
    score = int(score_result["score"])
    level = classify_level(score, status=st, conn=conn)

    dup_of: int | None = None
    is_dup = 0
    if dups:
        if policy == "reject":
            raise ValueError(f"Lead trùng với #{dups[0]['id']}.")
        if policy == "merge":
            merged = merge_incoming_into_primary(
                conn,
                int(dups[0]["id"]),
                full_name=full_name,
                phone=phone,
                email=email,
                source=source,
                region=region,
                product_interest=prod_interest,
                need=need,
                utm_campaign=utm_campaign,
                merged_by=created_by,
                ts=ts,
                note=f"Lead trùng (phone/email) — gộp theo policy merge.",
            )
            return merged, dups, dup_matches
        dup_of = int(dups[0]["id"])
        is_dup = 1

    final_owner = owner_id
    assign_strategy = ""
    if final_owner is None and auto_assign and not is_dup:
        final_owner, _owner_name, assign_strategy = assign_lead_owner(
            conn,
            region=region,
            product_interest=prod_interest,
            industry_slug=industry_key,
            lead_level=level,
            lead_score=score,
            source=src,
            need=need,
        )
        if assign_strategy and final_owner:
            meta_obj["assign_strategy"] = assign_strategy
            meta_obj["auto_assigned_at"] = ts
        elif auto_assign and not is_dup:
            meta_obj["assign_failed"] = True
            meta_obj["assign_failed_at"] = ts
            if assign_strategy == "no_scope_staff":
                meta_obj["assign_failed_reason"] = (
                    "Không có AM phụ trách ngành × dịch vụ này"
                )
            else:
                meta_obj["assign_failed_reason"] = (
                    "Không tìm được nhân viên phù hợp"
                    if assign_strategy in ("", "none")
                    else f"Phân công thất bại ({assign_strategy})"
                )

    cur = conn.execute(
        """
        INSERT INTO crm_leads (
            full_name, phone, phone_norm, email, email_norm, source, region,
            product_interest, industry_slug, need, lead_score, lead_level, status, owner_id,
            re_project_id, product_line, zone, re_product_id,
            duplicate_of_id, is_duplicate, utm_campaign, meta_json,
            status_entered_at, created_at, updated_at, created_by, updated_by,
            care_stage_current, care_stages_done_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            str(full_name).strip()[:240],
            str(phone).strip()[:80],
            ph_norm,
            str(email).strip()[:240],
            em_norm,
            src,
            str(region).strip()[:120],
            prod_interest[:300],
            industry_key[:80],
            str(need).strip()[:2000],
            score,
            level,
            st,
            final_owner,
            None,
            "",
            "",
            None,
            dup_of,
            is_dup,
            str(utm_campaign).strip()[:200],
            json.dumps(meta_obj, ensure_ascii=False),
            ts,
            ts,
            ts,
            created_by[:120],
            created_by[:120],
            "first_contact",
            "{}",
        ),
    )
    lid = int(cur.lastrowid)
    _log_lead_create_pipeline(
        conn,
        lead_id=lid,
        created_by=created_by,
        ts=ts,
        ph_norm=ph_norm,
        em_norm=em_norm,
        dup_matches=dup_matches,
        score=score,
        score_result=score_result,
        level=level,
        src=src,
        needs_clean=needs_clean,
        clean_reasons=clean_reasons,
    )
    if final_owner:
        log_assignment(
            conn,
            lead_id=lid,
            from_user_id=None,
            to_user_id=final_owner,
            reason="Tự động gán khi tạo",
            created_by=created_by,
            ts=ts,
        )
    row = fetch_lead_by_id(conn, lid)
    assert row is not None
    if final_owner:
        try:
            from crm_service_lifecycle import sync_assigned_am_for_lead

            sync_assigned_am_for_lead(conn, lid, overwrite=False)
        except Exception:
            pass
    if re_project_id is not None:
        try:
            from crm_re_projects import refresh_project_re_leads_new_kpi

            lead_ts = str(ts or "")[:19]
            period = lead_ts[:7] if len(lead_ts) >= 7 else ""
            refresh_project_re_leads_new_kpi(
                conn,
                int(re_project_id),
                period_month=period,
                ts=ts,
            )
        except Exception:
            pass
    return row, dups, dup_matches


def update_lead(
    conn: sqlite3.Connection,
    lead_id: int,
    *,
    full_name: str | None = None,
    phone: str | None = None,
    email: str | None = None,
    source: str | None = None,
    region: str | None = None,
    product_interest: str | None = None,
    need: str | None = None,
    status: str | None = None,
    owner_id: int | None = None,
    lead_level: str | None = None,
    re_project_id: int | None | object = _UNSET,
    product_line: str | None = None,
    zone: str | None = None,
    re_product_id: int | None | object = _UNSET,
    industry_slug: str | None = None,
    updated_by: str = "",
    ts: str,
    status_note: str = "",
    status_override: bool = False,
) -> sqlite3.Row:
    from crm_lead_catalog import normalize_industry_slug, normalize_product_interest
    from crm_lead_industry_addon import reject_re_legacy_lead_input, sync_addon_on_industry_change
    from crm_lead_rules import validate_status_transition

    if re_project_id is not _UNSET:
        reject_re_legacy_lead_input(re_project_id=re_project_id)
    if product_line is not None:
        reject_re_legacy_lead_input(product_line=product_line)
    if zone is not None:
        reject_re_legacy_lead_input(zone=zone)
    if re_product_id is not _UNSET:
        reject_re_legacy_lead_input(re_product_id=re_product_id)

    prev = fetch_lead_by_id(conn, lead_id)
    if prev is None:
        raise ValueError("Không tìm thấy lead.")
    pd = dict(prev)
    nm = str(full_name if full_name is not None else pd["full_name"]).strip()[:240]
    ph = str(phone if phone is not None else pd["phone"]).strip()[:80]
    em = str(email if email is not None else pd["email"]).strip()[:240]
    src = normalize_source(source if source is not None else pd["source"])
    if source is not None and not str(source).strip():
        raise ValueError("Lead phải có nguồn (source).")
    reg = str(region if region is not None else pd["region"]).strip()[:120]
    prod = str(product_interest if product_interest is not None else pd["product_interest"]).strip()[:300]
    prod = normalize_product_interest(conn, prod)
    industry_val = str(industry_slug if industry_slug is not None else pd.get("industry_slug") or "").strip()
    industry_val = normalize_industry_slug(conn, industry_val) if industry_val else ""
    nd = str(need if need is not None else pd["need"]).strip()[:2000]
    old_st = normalize_status(pd["status"])
    new_st = normalize_status(status) if status is not None else old_st
    needs_clean, _ = lead_needs_cleanup(
        full_name=nm, phone=ph, email=em, need=nd, product_interest=prod
    )
    validate_status_transition(
        old_st,
        new_st,
        needs_cleanup=needs_clean,
        allow_override=status_override,
    )
    if needs_clean and new_st not in TERMINAL_STATUSES and new_st not in ("pending_cleanup",):
        if new_st == "new":
            new_st = "pending_cleanup"
    elif not needs_clean and new_st == "pending_cleanup":
        new_st = "new"
    act_count = int(pd.get("activity_count") or 0)
    meta_raw = pd.get("meta_json") or "{}"
    try:
        meta_obj = json.loads(meta_raw) if isinstance(meta_raw, str) else dict(meta_raw or {})
    except json.JSONDecodeError:
        meta_obj = {}
    if not isinstance(meta_obj, dict):
        meta_obj = {}
    from crm_lead_scoring import score_lead

    score_result = score_lead(
        conn,
        source=src,
        phone=ph,
        email=em,
        need=nd,
        product_interest=prod,
        region=reg,
        full_name=nm,
        meta=meta_obj,
        activity_count=act_count,
    )
    meta_obj["score_breakdown"] = score_result["breakdown"]
    meta_obj["score_raw_total"] = score_result["raw_total"]
    meta_obj["score_updated_at"] = ts
    score = int(score_result["score"])
    level = normalize_level(lead_level, conn) if lead_level is not None else classify_level(score, status=new_st, conn=conn)
    if new_st in LEAD_LEVELS:
        level = normalize_level(new_st)
    old_owner = int(pd["owner_id"]) if pd.get("owner_id") else None
    new_owner = old_owner if owner_id is None else (int(owner_id) if owner_id else None)
    new_project_id = None
    new_line = ""
    new_zone = ""
    new_product_id = None
    old_industry = str(pd.get("industry_slug") or "").strip()
    status_entered = str(pd.get("status_entered_at") or ts)
    if new_st != old_st:
        status_entered = ts
        log_status_change(
            conn,
            lead_id=lead_id,
            old_status=old_st,
            new_status=new_st,
            changed_by=updated_by,
            note=status_note,
            ts=ts,
        )
    if new_owner != old_owner:
        log_assignment(
            conn,
            lead_id=lead_id,
            from_user_id=old_owner,
            to_user_id=new_owner,
            reason=status_note or "Cập nhật owner",
            created_by=updated_by,
            ts=ts,
        )
    conn.execute(
        """
        UPDATE crm_leads SET
            full_name = ?, phone = ?, phone_norm = ?, email = ?, email_norm = ?,
            source = ?, region = ?, product_interest = ?, industry_slug = ?, need = ?,
            lead_score = ?, lead_level = ?, status = ?, owner_id = ?,
            re_project_id = ?, product_line = ?, zone = ?, re_product_id = ?,
            meta_json = ?, status_entered_at = ?, updated_at = ?, updated_by = ?
        WHERE id = ?
        """,
        (
            nm,
            ph,
            normalize_phone(ph),
            em,
            normalize_email(em),
            src,
            reg,
            prod,
            industry_val[:80],
            nd,
            score,
            level,
            new_st,
            new_owner,
            new_project_id,
            new_line,
            new_zone,
            new_product_id,
            json.dumps(meta_obj, ensure_ascii=False),
            status_entered,
            ts,
            updated_by[:120],
            int(lead_id),
        ),
    )
    row = fetch_lead_by_id(conn, lead_id)
    assert row is not None
    if new_st != old_st:
        from crm_cross_module import on_lead_status_changed

        on_lead_status_changed(
            conn,
            lead_id,
            old_st,
            new_st,
            updated_by=updated_by,
            ts=ts,
        )
        row = fetch_lead_by_id(conn, lead_id)
        assert row is not None
    if new_owner != old_owner:
        try:
            from crm_service_lifecycle import sync_assigned_am_for_lead

            sync_assigned_am_for_lead(conn, int(lead_id), overwrite=True)
        except Exception:
            pass
    if industry_slug is not None and industry_val != old_industry:
        sync_addon_on_industry_change(conn, int(lead_id), industry_val)
    return row


def assign_lead(
    conn: sqlite3.Connection,
    lead_id: int,
    *,
    to_user_id: int,
    reason: str,
    assigned_by: str,
    ts: str,
) -> sqlite3.Row:
    prev = fetch_lead_by_id(conn, lead_id)
    if prev is None:
        raise ValueError("Không tìm thấy lead.")
    from_id = int(prev["owner_id"]) if prev["owner_id"] else None
    to_id = int(to_user_id)
    staff = conn.execute(
        "SELECT id FROM crm_staff WHERE id = ? AND COALESCE(active, 1) = 1", (to_id,)
    ).fetchone()
    if staff is None:
        raise ValueError("Nhân viên không hợp lệ hoặc đã ngưng.")
    pd = dict(prev)
    project_id = int(pd["re_project_id"]) if pd.get("re_project_id") else None
    if project_id:
        from crm_project_leads import assert_staff_in_project

        assert_staff_in_project(conn, project_id, to_id)
    conn.execute(
        "UPDATE crm_leads SET owner_id = ?, updated_at = ?, updated_by = ? WHERE id = ?",
        (to_id, ts, assigned_by[:120], int(lead_id)),
    )
    log_assignment(
        conn,
        lead_id=lead_id,
        from_user_id=from_id,
        to_user_id=to_id,
        reason=reason,
        created_by=assigned_by,
        ts=ts,
    )
    log_lead_activity(
        conn,
        lead_id=lead_id,
        activity_type="system",
        content=f"Phân lại lead: {reason}",
        user_id=to_id,
        created_by=assigned_by,
        ts=ts,
    )
    row = fetch_lead_by_id(conn, lead_id)
    assert row is not None
    try:
        from crm_service_lifecycle import sync_assigned_am_for_lead

        sync_assigned_am_for_lead(conn, int(lead_id), overwrite=True)
    except Exception:
        pass
    return row


def delete_lead(
    conn: sqlite3.Connection,
    lead_id: int,
    *,
    deleted_by: str,
    force: bool = False,
) -> dict[str, Any]:
    """Xóa lead và dữ liệu liên quan (activity, log, reminder)."""
    row = fetch_lead_by_id(conn, lead_id)
    if row is None:
        raise ValueError("Không tìm thấy lead.")
    lid = int(lead_id)
    case_id = int(row["converted_case_id"]) if row["converted_case_id"] else None
    cust_id = int(row["converted_customer_id"]) if row["converted_customer_id"] else None
    if (case_id or cust_id) and not force:
        parts: list[str] = []
        if case_id:
            parts.append(f"Case #{case_id}")
        if cust_id:
            parts.append(f"KH #{cust_id}")
        raise ValueError(
            f"Lead đã chuyển sang {' / '.join(parts)}. "
            "Không thể xóa trực tiếp — xác nhận force nếu chắc chắn."
        )

    snapshot = {
        "deleted_id": lid,
        "full_name": str(row["full_name"] or ""),
        "phone": str(row["phone"] or ""),
        "email": str(row["email"] or ""),
        "source": str(row["source"] or ""),
        "owner_id": int(row["owner_id"]) if row["owner_id"] else None,
        "converted_case_id": case_id,
        "converted_customer_id": cust_id,
        "deleted_by": deleted_by[:120],
    }

    conn.execute(
        "UPDATE crm_leads SET duplicate_of_id = NULL, is_duplicate = 0 WHERE duplicate_of_id = ?",
        (lid,),
    )
    conn.execute(
        "DELETE FROM crm_reminders WHERE scope = 'lead' AND ref_id = ?",
        (lid,),
    )
    conn.execute("DELETE FROM crm_lead_ai_logs WHERE lead_id = ?", (lid,))
    conn.execute("DELETE FROM crm_lead_activities WHERE lead_id = ?", (lid,))
    conn.execute("DELETE FROM crm_lead_status_logs WHERE lead_id = ?", (lid,))
    conn.execute("DELETE FROM crm_lead_assignment_logs WHERE lead_id = ?", (lid,))
    conn.execute("DELETE FROM crm_leads WHERE id = ?", (lid,))
    return snapshot


def fetch_lead_stats(
    conn: sqlite3.Connection,
    *,
    owner_id: int | None = None,
    re_project_id: int | None | object = _UNSET,
    staff_portal_id: int | None = None,
    status: str | None = None,
    level: str | None = None,
    source: str | None = None,
    q: str | None = None,
    product_line: str | None = None,
    zone: str | None = None,
    sla_overdue_only: bool = False,
    hide_review_queue: bool = True,
    review_queue_only: bool = False,
) -> dict[str, Any]:
    """FR-09: Thống kê theo nguồn, owner, trạng thái — cùng bộ lọc danh sách lead."""
    clauses, params = _lead_list_filters(
        owner_id=owner_id if staff_portal_id is None else None,
        status=status,
        level=level,
        source=source,
        q=q,
        re_project_id=re_project_id,
        product_line=product_line,
        zone=zone,
        staff_portal_id=staff_portal_id,
        hide_review_queue=hide_review_queue,
        review_queue_only=review_queue_only,
    )
    where = " WHERE " + " AND ".join(clauses)
    by_status = conn.execute(
        f"""
        SELECT l.status, COUNT(*) AS c FROM crm_leads l
        {where}
        GROUP BY l.status
        """,
        params,
    ).fetchall()
    by_source = conn.execute(
        f"""
        SELECT l.source, COUNT(*) AS c FROM crm_leads l
        {where}
        GROUP BY l.source
        """,
        params,
    ).fetchall()
    by_level = conn.execute(
        f"""
        SELECT l.lead_level, COUNT(*) AS c FROM crm_leads l
        {where}
        GROUP BY l.lead_level
        """,
        params,
    ).fetchall()
    total = conn.execute(
        f"SELECT COUNT(*) AS c FROM crm_leads l{where}",
        params,
    ).fetchone()
    id_rows = conn.execute(
        f"SELECT l.id FROM crm_leads l{where}",
        params,
    ).fetchall()
    from crm_lead_kpi_metrics import summarize_leads_kpi

    kpi = summarize_leads_kpi(conn, [int(r["id"]) for r in id_rows])
    rows = fetch_leads(
        conn,
        owner_id=owner_id if staff_portal_id is None else None,
        re_project_id=re_project_id,
        staff_portal_id=staff_portal_id,
        status=status,
        level=level,
        source=source,
        q=q,
        product_line=product_line,
        zone=zone,
        sla_overdue_only=sla_overdue_only,
        hide_review_queue=hide_review_queue,
        review_queue_only=review_queue_only,
        limit=5000 if sla_overdue_only else 500,
    )
    if sla_overdue_only:
        overdue = len(rows)
    else:
        overdue = sum(1 for r in rows if lead_row_to_dict(r, conn).get("sla_overdue"))
    t = int(total["c"]) if total else 0
    w = int(kpi["won_leads"])
    q = int(kpi["qualified_leads"])
    return {
        "total": t,
        "won": w,
        "qualified_leads": q,
        "conversion_rate": kpi["close_rate_pct"],
        "close_rate_pct": kpi["close_rate_pct"],
        "close_rate_decided_pct": kpi["close_rate_decided_pct"],
        "sla_overdue": overdue,
        "by_status": {str(r["status"]): int(r["c"]) for r in by_status},
        "by_source": {str(r["source"]): int(r["c"]) for r in by_source},
        "by_level": {str(r["lead_level"]): int(r["c"]) for r in by_level},
    }


def fetch_lead_stats_extended(
    conn: sqlite3.Connection,
    *,
    owner_id: int | None = None,
    re_project_id: int | None | object = _UNSET,
    staff_portal_id: int | None = None,
    status: str | None = None,
    level: str | None = None,
    source: str | None = None,
    q: str | None = None,
    product_line: str | None = None,
    zone: str | None = None,
    sla_overdue_only: bool = False,
    hide_review_queue: bool = True,
    review_queue_only: bool = False,
    ts: str | None = None,
) -> dict[str, Any]:
    """Thống kê đầy đủ kèm SLA sync, cảnh báo và theo owner."""
    from crm_lead_review_queue import count_review_queue_leads, sync_b2_review_queue
    from crm_lead_sla import (
        fetch_lead_owner_stats,
        fetch_lead_sla_alerts,
        reassign_leads_from_inactive_owners,
        sync_lead_sla_reminders,
    )

    if ts:
        reassign_leads_from_inactive_owners(conn, ts=ts, actor="system:maintenance")
        sync_lead_sla_reminders(conn, ts=ts)
        sync_b2_review_queue(conn, ts=ts, actor="system:b2_review")
    list_kw = dict(
        owner_id=owner_id,
        re_project_id=re_project_id,
        staff_portal_id=staff_portal_id,
        status=status,
        level=level,
        source=source,
        q=q,
        product_line=product_line,
        zone=zone,
        sla_overdue_only=sla_overdue_only,
        hide_review_queue=hide_review_queue,
        review_queue_only=review_queue_only,
    )
    base = fetch_lead_stats(conn, **list_kw)
    base["by_owner"] = fetch_lead_owner_stats(conn, **list_kw)
    base["review_queue_count"] = count_review_queue_leads(conn)
    sla_owner = int(staff_portal_id) if staff_portal_id is not None else owner_id
    base["sla_alerts"] = fetch_lead_sla_alerts(conn, owner_id=sla_owner, limit=30)
    return base


def fetch_lead_status_logs(
    conn: sqlite3.Connection, lead_id: int, *, limit: int = 100
) -> list[dict[str, Any]]:
    lim = max(1, min(int(limit), 200))
    rows = conn.execute(
        """
        SELECT id, lead_id, old_status, new_status, changed_by, note, created_at
        FROM crm_lead_status_logs
        WHERE lead_id = ?
        ORDER BY created_at DESC
        LIMIT ?
        """,
        (int(lead_id), lim),
    ).fetchall()
    out: list[dict[str, Any]] = []
    for r in rows:
        d = dict(r)
        out.append(
            {
                "id": int(d["id"]),
                "lead_id": int(d["lead_id"]),
                "old_status": str(d.get("old_status") or ""),
                "old_status_label": LEAD_STATUS_LABELS.get(str(d.get("old_status") or ""), ""),
                "new_status": str(d.get("new_status") or ""),
                "new_status_label": LEAD_STATUS_LABELS.get(str(d.get("new_status") or ""), ""),
                "changed_by": str(d.get("changed_by") or ""),
                "note": str(d.get("note") or ""),
                "created_at": str(d.get("created_at") or ""),
            }
        )
    return out


def fetch_lead_assignment_logs(
    conn: sqlite3.Connection, lead_id: int, *, limit: int = 100
) -> list[dict[str, Any]]:
    lim = max(1, min(int(limit), 200))
    rows = conn.execute(
        """
        SELECT a.*,
               fs.name AS from_name,
               ts.name AS to_name
        FROM crm_lead_assignment_logs a
        LEFT JOIN crm_staff fs ON fs.id = a.from_user_id
        LEFT JOIN crm_staff ts ON ts.id = a.to_user_id
        WHERE a.lead_id = ?
        ORDER BY a.created_at DESC
        LIMIT ?
        """,
        (int(lead_id), lim),
    ).fetchall()
    out: list[dict[str, Any]] = []
    for r in rows:
        d = dict(r)
        out.append(
            {
                "id": int(d["id"]),
                "lead_id": int(d["lead_id"]),
                "from_user_id": int(d["from_user_id"]) if d.get("from_user_id") else None,
                "from_name": str(d.get("from_name") or "—"),
                "to_user_id": int(d["to_user_id"]) if d.get("to_user_id") else None,
                "to_name": str(d.get("to_name") or "—"),
                "reason": str(d.get("reason") or ""),
                "created_by": str(d.get("created_by") or ""),
                "created_at": str(d.get("created_at") or ""),
            }
        )
    return out


def log_ai_action(
    conn: sqlite3.Connection,
    *,
    lead_id: int | None,
    action: str,
    input_text: str,
    output: dict[str, Any],
    confidence: float | None,
    fallback_used: bool,
    created_by: str,
    ts: str,
) -> None:
    conn.execute(
        """
        INSERT INTO crm_lead_ai_logs
            (lead_id, action, input_text, output_json, confidence, fallback_used, created_by, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            lead_id,
            action[:80],
            input_text[:4000],
            json.dumps(output, ensure_ascii=False),
            confidence,
            1 if fallback_used else 0,
            created_by[:120],
            ts,
        ),
    )
