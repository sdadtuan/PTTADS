"""Chăm sóc khách hàng theo nhân viên — báo cáo tình trạng CSKH."""
from __future__ import annotations

import sqlite3
from typing import Any

CRM_CARE_CONTACT_TYPES: tuple[str, ...] = (
    "goi_dien",
    "zalo",
    "email",
    "gap_mat",
    "sms",
    "khac",
)

CRM_CARE_CONTACT_LABELS_VI: dict[str, str] = {
    "goi_dien": "Gọi điện",
    "zalo": "Zalo / chat",
    "email": "Email",
    "gap_mat": "Gặp trực tiếp",
    "sms": "SMS",
    "khac": "Khác",
}

CRM_CARE_STATUS_TYPES: tuple[str, ...] = (
    "da_phan_loai",
    "da_lien_he_thanh_cong",
    "khong_goi_duoc",
    "khong_nghe_may",
    "khach_khong_tra_loi",
    "cho_phan_hoi_khach",
    "khach_hen_goi_lai",
    "khong_lien_lac_duoc",
    "so_sai",
    "da_tu_van_xong",
    "chuyen_cap_truong",
    "hoan_tat",
)

CRM_CARE_STATUS_LABELS_VI: dict[str, str] = {
    "da_phan_loai": "Đã phân loại xong",
    "da_lien_he_thanh_cong": "Đã liên hệ thành công",
    "khong_goi_duoc": "Không gọi được",
    "khong_nghe_may": "Không nghe máy",
    "khach_khong_tra_loi": "Khách không trả lời",
    "cho_phan_hoi_khach": "Chờ phản hồi khách",
    "khach_hen_goi_lai": "Khách hẹn gọi lại",
    "khong_lien_lac_duoc": "Không liên lạc được",
    "so_sai": "Số sai / không tồn tại",
    "da_tu_van_xong": "Đã tư vấn xong",
    "chuyen_cap_truong": "Chuyển cấp / escalation",
    "hoan_tat": "Hoàn tất chăm sóc",
}


def normalize_care_contact(raw: str | None) -> str:
    s = str(raw or "").strip().lower()
    return s if s in CRM_CARE_CONTACT_TYPES else "goi_dien"


def normalize_care_status(raw: str | None) -> str:
    s = str(raw or "").strip().lower()
    return s if s in CRM_CARE_STATUS_TYPES else "da_lien_he_thanh_cong"


def ensure_care_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS crm_care_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            case_id INTEGER NOT NULL,
            staff_id INTEGER,
            staff_name TEXT NOT NULL DEFAULT '',
            contact_type TEXT NOT NULL DEFAULT 'goi_dien',
            care_status TEXT NOT NULL DEFAULT 'da_lien_he_thanh_cong',
            summary TEXT NOT NULL DEFAULT '',
            next_action TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            FOREIGN KEY (case_id) REFERENCES crm_cases(id) ON DELETE CASCADE,
            FOREIGN KEY (staff_id) REFERENCES crm_staff(id) ON DELETE SET NULL
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_crm_care_reports_case "
        "ON crm_care_reports(case_id, created_at DESC)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_crm_care_reports_staff "
        "ON crm_care_reports(staff_id, created_at DESC)"
    )


def format_care_event_body(
    *,
    contact_type: str,
    care_status: str,
    summary: str,
    next_action: str = "",
    staff_name: str = "",
) -> str:
    ct = CRM_CARE_CONTACT_LABELS_VI.get(contact_type, contact_type)
    st = CRM_CARE_STATUS_LABELS_VI.get(care_status, care_status)
    parts = [f"[Báo cáo CSKH] {st} · {ct}"]
    if staff_name:
        parts.append(f"NV: {staff_name}")
    if summary:
        parts.append(summary)
    if next_action:
        parts.append(f"Bước tiếp: {next_action}")
    return " — ".join(parts)


def care_report_row_to_dict(row: sqlite3.Row | dict[str, Any]) -> dict[str, Any]:
    d = dict(row)
    ct = str(d.get("contact_type") or "")
    cs = str(d.get("care_status") or "")
    d["contact_type_label"] = CRM_CARE_CONTACT_LABELS_VI.get(ct, ct)
    d["care_status_label"] = CRM_CARE_STATUS_LABELS_VI.get(cs, cs)
    return d


def fetch_last_care_reports_map(
    conn: sqlite3.Connection, case_ids: list[int]
) -> dict[int, dict[str, Any]]:
    if not case_ids:
        return {}
    placeholders = ",".join("?" * len(case_ids))
    rows = conn.execute(
        f"""
        SELECT r.* FROM crm_care_reports r
        INNER JOIN (
            SELECT case_id, MAX(id) AS max_id
            FROM crm_care_reports
            WHERE case_id IN ({placeholders})
            GROUP BY case_id
        ) latest ON latest.max_id = r.id
        """,
        case_ids,
    ).fetchall()
    out: dict[int, dict[str, Any]] = {}
    for r in rows:
        d = care_report_row_to_dict(r)
        out[int(d["case_id"])] = d
    return out


def get_lifecycle_stage_context(conn: sqlite3.Connection, customer_id: int) -> str:
    """Trả về chuỗi context lifecycle để thêm vào AI prompt. Trả '' nếu không có."""
    try:
        from crm_service_lifecycle import get_stage_context
        ctx = get_stage_context(conn, customer_id)
        if ctx:
            stage_labels = {
                "lead": "Lead", "consult": "Tư vấn", "proposal": "Báo giá",
                "onboard": "Onboarding", "deliver": "Triển khai",
                "handover": "Nghiệm thu", "retain": "Chăm sóc",
            }
            stage_label = stage_labels.get(ctx["stage"], ctx["stage"])
            return (
                f"Dịch vụ: {ctx['service_slug']} · "
                f"Giai đoạn: {stage_label} ({ctx['stage_days']} ngày). "
                f"Ưu tiên chăm sóc phù hợp giai đoạn này."
            )
    except Exception:
        pass
    return ""
