"""Phân quyền chi tiết các hạng mục CMS / Admin nội dung."""
from __future__ import annotations

from typing import Any

# Hành động chuẩn trên từng hạng mục
CMS_ACTIONS: tuple[str, ...] = (
    "view",
    "edit",
    "create",
    "delete",
    "export",
    "configure",
    "approve",
)

CMS_ACTION_LABELS_VI: dict[str, str] = {
    "view": "Xem",
    "edit": "Sửa",
    "create": "Tạo",
    "delete": "Xóa",
    "export": "Xuất file",
    "configure": "Cấu hình",
    "approve": "Duyệt / phê duyệt",
}

# Mục menu CRM (sidebar trái) — id trùng data-admin-nav / ma trận chức vụ
CMS_CRM_NAV_MODULES: tuple[dict[str, Any], ...] = (
    {
        "id": "crm_board_kanban",
        "label": "Bảng CSKH",
        "group": "CRM · Chăm sóc KH",
        "description": "Menu → /crm — Kanban yêu cầu chăm sóc.",
        "routes": ["/crm"],
    },
    {
        "id": "crm_board_customers",
        "label": "Khách hàng",
        "group": "CRM · Chăm sóc KH",
        "description": "Menu → /crm/customers — hồ sơ khách hàng.",
        "routes": ["/crm/customers"],
    },
    {
        "id": "crm_leads",
        "label": "Quản lý Lead",
        "group": "CRM · Chăm sóc KH",
        "description": "Menu → /crm/leads — pipeline lead.",
        "routes": ["/crm/leads"],
    },
    {
        "id": "crm_hub_campaigns",
        "label": "Hub · Hợp đồng",
        "group": "CRM · Marketing",
        "description": "Menu → /crm/hub — chiến dịch và hợp đồng.",
        "routes": ["/crm/hub"],
    },
    {
        "id": "crm_mktplan",
        "label": "Kế hoạch marketing",
        "group": "CRM · Marketing",
        "description": "Menu → /crm/marketing-plan.",
        "routes": ["/crm/marketing-plan"],
    },
    {
        "id": "crm_business_dashboard",
        "label": "Business Dashboard",
        "group": "CRM · Marketing",
        "description": "Menu → /crm/business-dashboard — KPI executive, trend, cảnh báo.",
        "routes": ["/crm/business-dashboard", "/crm/financials"],
    },
    {
        "id": "crm_owner_weekly_dashboard",
        "label": "Dashboard tuần (Chủ DN)",
        "group": "CRM · Marketing",
        "description": "Menu → /crm/owner-weekly — 4 khối Tiền/KD/Hiệu quả/Rủi ro + RAG.",
        "routes": [
            "/crm/owner-weekly",
            "/api/crm/owner-weekly",
            "/api/crm/owner-weekly/config",
            "/api/crm/owner-weekly/export",
            "/api/crm/owner-weekly/inbox/sync",
            "/api/crm/owner-weekly/alert-cron",
        ],
    },
    {
        "id": "crm_sop_runs",
        "label": "Quy trình SOP",
        "group": "CRM · Marketing",
        "description": "Menu → /crm/sop — tiến trình SOP.",
        "routes": ["/crm/sop"],
    },
    {
        "id": "crm_sales_overview",
        "label": "Kinh doanh",
        "group": "CRM · Kinh doanh",
        "description": "Menu → /crm/sales — tổng quan kinh doanh.",
        "routes": ["/crm/sales"],
    },
    {
        "id": "crm_re_projects",
        "label": "Dự án BĐS",
        "group": "CRM · Kinh doanh",
        "description": "Menu → /crm/re-projects.",
        "routes": ["/crm/re-projects"],
    },
    {
        "id": "crm_staff_roster",
        "label": "Nhân viên",
        "group": "CRM · Nhân sự",
        "description": "Menu → /crm/staff — danh sách nhân viên.",
        "routes": ["/crm/staff"],
    },
    {
        "id": "crm_daily_work_report",
        "label": "BC công việc",
        "group": "CRM · Nhân sự",
        "description": "Menu → /crm/daily-reports — báo cáo ngày.",
        "routes": ["/crm/daily-reports"],
    },
    {
        "id": "crm_kpi_records",
        "label": "KPI",
        "group": "CRM · Nhân sự",
        "description": "Menu → /crm/kpi — chỉ tiêu nhân viên.",
        "routes": ["/crm/kpi"],
    },
    {
        "id": "crm_staff_kpi_am_sp",
        "label": "KPI AM/SP",
        "group": "CRM · Nhân sự",
        "description": "Menu → /crm/staff-kpi — KPI AM/SP/Lead tự động từ CRM.",
        "routes": ["/crm/staff-kpi", "/api/crm/staff-kpi"],
    },
    {
        "id": "crm_hdsd",
        "label": "HDSD",
        "group": "CRM · Hướng dẫn",
        "description": "Menu → /crm/hdsd — đọc & tải tài liệu docs/.",
        "routes": ["/crm/hdsd", "/api/crm/hdsd"],
    },
    {
        "id": "crm_payroll_attendance",
        "label": "Chấm công & lương",
        "group": "CRM · Nhân sự",
        "description": "Menu → /crm/payroll.",
        "routes": ["/crm/payroll"],
    },
)

CMS_CRM_NAV_MODULE_IDS: frozenset[str] = frozenset(m["id"] for m in CMS_CRM_NAV_MODULES)

# Admin ops-web only (public landing/CMS site removed)
CMS_ADMIN_MODULES: tuple[dict[str, Any], ...] = (
    {
        "id": "permissions_matrix",
        "label": "Phân quyền",
        "group": "Hệ thống",
        "description": "Ma trận quyền vai trò và chức vụ — ops-web staff settings.",
        "routes": ["GET/PATCH /api/cms/permissions"],
    },
)

# Public landing/CMS site retired — no core website modules
CMS_CORE_MODULES: tuple[dict[str, Any], ...] = ()

CMS_MODULES: tuple[dict[str, Any], ...] = CMS_ADMIN_MODULES + CMS_CRM_NAV_MODULES

CMS_MODULE_IDS: frozenset[str] = frozenset(m["id"] for m in CMS_MODULES)

# Vai trò mặc định
CMS_ROLES: tuple[dict[str, Any], ...] = (
    {
        "code": "super_admin",
        "name": "Quản trị hệ thống",
        "description": "Toàn quyền CMS, Admin và cấu hình phân quyền.",
        "is_system": True,
    },
    {
        "code": "cms_admin",
        "name": "Quản trị ops-web",
        "description": "Toàn quyền CRM ops-web; không chỉnh ma trận phân quyền.",
        "is_system": True,
    },
    {
        "code": "content_editor",
        "name": "Biên tập CRM",
        "description": "Xem/sửa module CRM ops-web (legacy role id).",
        "is_system": True,
    },
    {
        "code": "marketing_lead",
        "name": "Trưởng nhóm Marketing",
        "description": "Toàn quyền module CRM marketing trên ops-web.",
        "is_system": True,
    },
    {
        "code": "marketing_staff",
        "name": "Nhân viên Marketing",
        "description": "Module CRM marketing ops-web (không cấu hình hệ thống).",
        "is_system": True,
    },
    {
        "code": "viewer",
        "name": "Chỉ xem",
        "description": "Xem CMS và chat (không gửi tin, không lưu).",
        "is_system": True,
    },
)

# Ma trận mặc định: role_code -> module_id -> actions
_CRM_NAV_VIEW: dict[str, frozenset[str]] = {
    mid: frozenset({"view"}) for mid in CMS_CRM_NAV_MODULE_IDS
}
_CRM_NAV_MARKETING_LEAD: dict[str, frozenset[str]] = {
    **_CRM_NAV_VIEW,
    "crm_board_kanban": frozenset({"view", "export"}),
    "crm_leads": frozenset({"view", "edit", "create", "export", "configure"}),
    "crm_hub_campaigns": frozenset({"view", "edit", "create", "delete"}),
    "crm_mktplan": frozenset({"view", "edit", "create", "export"}),
    "crm_business_dashboard": frozenset({"view", "export", "configure"}),
    "crm_owner_weekly_dashboard": frozenset({"view", "export", "configure"}),
    "crm_sop_runs": frozenset({"view", "edit", "create"}),
    "crm_sales_overview": frozenset({"view", "export"}),
    "crm_re_projects": frozenset({"view", "export"}),
    "crm_kpi_records": frozenset({"view", "edit", "create"}),
    "crm_staff_kpi_am_sp": frozenset({"view", "export", "configure"}),
    "crm_hdsd": frozenset({"view", "export"}),
}
_CRM_NAV_MARKETING_STAFF: dict[str, frozenset[str]] = {
    **_CRM_NAV_VIEW,
    "crm_leads": frozenset({"view", "edit", "create", "export"}),
    "crm_hub_campaigns": frozenset({"view", "edit"}),
    "crm_mktplan": frozenset({"view", "edit", "export"}),
    "crm_business_dashboard": frozenset({"view", "export"}),
    "crm_owner_weekly_dashboard": frozenset({"view", "export"}),
    "crm_sop_runs": frozenset({"view", "edit"}),
    "crm_kpi_records": frozenset({"view", "edit"}),
    "crm_staff_kpi_am_sp": frozenset({"view", "export"}),
    "crm_hdsd": frozenset({"view", "export"}),
}

_DEFAULT_GRANTS: dict[str, dict[str, frozenset[str]]] = {
    "super_admin": {mid: frozenset(CMS_ACTIONS) for mid in CMS_MODULE_IDS},
    "cms_admin": {
        mid: frozenset(CMS_ACTIONS)
        for mid in CMS_MODULE_IDS
        if mid != "permissions_matrix"
    }
    | {
        "permissions_matrix": frozenset({"view"}),
    },
    "content_editor": {
        "permissions_matrix": frozenset({"view"}),
        **_CRM_NAV_VIEW,
    },
    "marketing_lead": {
        "permissions_matrix": frozenset({"view"}),
        **_CRM_NAV_MARKETING_LEAD,
    },
    "marketing_staff": {
        "permissions_matrix": frozenset({"view"}),
        **_CRM_NAV_MARKETING_STAFF,
    },
    "viewer": {
        mid: frozenset({"view"}) for mid in CMS_MODULE_IDS
    },
}


def default_grants_for_role(role_code: str) -> dict[str, list[str]]:
    raw = _DEFAULT_GRANTS.get(role_code, {})
    out: dict[str, list[str]] = {}
    for mid in CMS_MODULE_IDS:
        acts = raw.get(mid, frozenset())
        out[mid] = sorted(a for a in CMS_ACTIONS if a in acts)
    return out


def normalize_action(raw: str | None) -> str | None:
    s = str(raw or "").strip().lower()
    return s if s in CMS_ACTIONS else None


def grants_map_to_rows(
    grants: dict[str, list[str] | frozenset[str] | set[str]],
) -> list[dict[str, Any]]:
    """Chuyển grants dict → danh sách hàng cho API/UI."""
    rows = []
    for mod in CMS_MODULES:
        mid = mod["id"]
        allowed = set(grants.get(mid) or [])
        rows.append(
            {
                "module_id": mid,
                "module_label": mod["label"],
                "group": mod["group"],
                "description": mod.get("description", ""),
                "actions": {a: a in allowed for a in CMS_ACTIONS},
                "allowed_list": sorted(a for a in CMS_ACTIONS if a in allowed),
            }
        )
    return rows


def build_permission_matrix(
    role_grants: dict[str, dict[str, list[str]]],
) -> dict[str, Any]:
    roles_out = []
    for role in CMS_ROLES:
        code = role["code"]
        grants = role_grants.get(code) or default_grants_for_role(code)
        roles_out.append(
            {
                **role,
                "grants": grants_map_to_rows(grants),
            }
        )
    return {
        "actions": [
            {"id": a, "label": CMS_ACTION_LABELS_VI[a]} for a in CMS_ACTIONS
        ],
        "modules": list(CMS_MODULES),
        "roles": roles_out,
    }


def role_can(
    grants: dict[str, list[str] | frozenset[str]],
    module_id: str,
    action: str,
    *,
    is_super: bool = False,
) -> bool:
    if is_super:
        return True
    mid = str(module_id or "").strip()
    act = normalize_action(action)
    if not mid or not act or mid not in CMS_MODULE_IDS:
        return False
    allowed = set(grants.get(mid) or [])
    return act in allowed


def parse_grants_payload(raw: Any) -> dict[str, list[str]] | None:
    """Validate PATCH body: { module_id: [actions] }."""
    if not isinstance(raw, dict):
        return None
    out: dict[str, list[str]] = {}
    for mid, acts in raw.items():
        if mid not in CMS_MODULE_IDS:
            continue
        if not isinstance(acts, list):
            return None
        norm = []
        for a in acts:
            na = normalize_action(str(a))
            if na:
                norm.append(na)
        out[mid] = sorted(set(norm))
    return out


CMS_GRANTS_CUSTOMIZED_BACKFILL_KEY = "cms_grants_customized_backfill_v1"
POSITION_GRANTS_CUSTOMIZED_BACKFILL_KEY = "position_grants_customized_backfill_v1"


def ensure_role_grants_customized_column(conn: Any) -> None:
    cols = {r[1] for r in conn.execute("PRAGMA table_info(cms_roles)").fetchall()}
    if "grants_customized" not in cols:
        conn.execute(
            "ALTER TABLE cms_roles ADD COLUMN grants_customized INTEGER NOT NULL DEFAULT 0"
        )


def backfill_role_grants_customized(conn: Any) -> None:
    """Một lần: vai trò đã có quyền trong DB = admin đã cấu hình — không seed lại khi restart."""
    row = conn.execute(
        "SELECT value FROM settings WHERE key = ?",
        (CMS_GRANTS_CUSTOMIZED_BACKFILL_KEY,),
    ).fetchone()
    if row and str(row["value"]) == "1":
        return
    for role in CMS_ROLES:
        code = role["code"]
        if code == "super_admin":
            continue
        cnt = conn.execute(
            "SELECT COUNT(*) AS n FROM cms_role_permissions WHERE role_code = ?",
            (code,),
        ).fetchone()
        if cnt and int(cnt["n"]) > 0:
            conn.execute(
                "UPDATE cms_roles SET grants_customized = 1 WHERE code = ?",
                (code,),
            )
    conn.execute(
        "INSERT OR REPLACE INTO settings (key, value) VALUES (?, '1')",
        (CMS_GRANTS_CUSTOMIZED_BACKFILL_KEY,),
    )


def role_grants_were_customized(conn: Any, role_code: str) -> bool:
    row = conn.execute(
        "SELECT grants_customized FROM cms_roles WHERE code = ?",
        (role_code,),
    ).fetchone()
    return bool(row and int(row["grants_customized"] or 0))


def mark_role_grants_customized(conn: Any, role_code: str, *, ts: str = "") -> None:
    updated = ts or ""
    if updated:
        conn.execute(
            "UPDATE cms_roles SET grants_customized = 1, updated_at = ? WHERE code = ?",
            (updated, role_code),
        )
    else:
        conn.execute(
            "UPDATE cms_roles SET grants_customized = 1 WHERE code = ?",
            (role_code,),
        )


def migrate_cms_role_sidebar_modules(conn: Any) -> None:
    """Bổ sung quyền module menu mới — chỉ vai trò chưa được admin lưu ma trận."""
    ensure_role_grants_customized_column(conn)
    for role in CMS_ROLES:
        code = role["code"]
        if role_grants_were_customized(conn, code):
            continue
        rows = conn.execute(
            """
            SELECT DISTINCT module_id FROM cms_role_permissions
            WHERE role_code = ?
            """,
            (code,),
        ).fetchall()
        seen = {str(r["module_id"]) for r in rows}
        defaults = default_grants_for_role(code)
        for mid, acts in defaults.items():
            if mid in seen:
                continue
            for act in acts:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO cms_role_permissions (role_code, module_id, action)
                    VALUES (?, ?, ?)
                    """,
                    (code, mid, act),
                )
