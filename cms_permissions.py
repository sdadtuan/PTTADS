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
)

CMS_ACTION_LABELS_VI: dict[str, str] = {
    "view": "Xem",
    "edit": "Sửa",
    "create": "Tạo",
    "delete": "Xóa",
    "export": "Xuất file",
    "configure": "Cấu hình",
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

# Hạng mục CMS / Admin — map với menu sidebar trái và API
CMS_CORE_MODULES: tuple[dict[str, Any], ...] = (
    {
        "id": "admin_dashboard",
        "label": "Bảng điều khiển",
        "group": "Tổng quan",
        "description": "Menu → /admin — dự án, tin tức, kênh CRM.",
        "routes": ["/admin"],
    },
    {
        "id": "landing_settings",
        "label": "Cài đặt trang",
        "group": "Website",
        "description": "Menu → /cms — thương hiệu, hero, liên hệ, chân trang.",
        "routes": ["/cms", "PUT /api/settings"],
    },
    {
        "id": "services_builder",
        "label": "Dịch vụ",
        "group": "Website",
        "description": "Menu → /cms — category và item dịch vụ landing.",
        "routes": ["/cms", "PUT /api/services"],
    },
    {
        "id": "mk_chat_config",
        "label": "Chat Marketing",
        "group": "Website",
        "description": "Menu → /cms — bật/tắt chat, tiêu đề, lời chào.",
        "routes": ["/cms", "PUT /api/settings (mk_chat_*)"],
    },
    {
        "id": "mk_chat_conversation",
        "label": "↳ Hội thoại chatbox",
        "group": "Website — Chi tiết Chat Marketing",
        "description": "Gửi tin, module 7 bước, chiến lược marketing.",
        "routes": ["POST /api/cms/marketing-chat/send"],
    },
    {
        "id": "mk_chat_export",
        "label": "↳ Xuất tài liệu chat",
        "group": "Website — Chi tiết Chat Marketing",
        "description": "Export Markdown, HTML, JSON hội thoại.",
        "routes": ["POST /api/cms/marketing-chat/export"],
    },
    {
        "id": "mk_chat_excel",
        "label": "↳ Excel kế hoạch marketing",
        "group": "Website — Chi tiết Chat Marketing",
        "description": "Tuần (XLS), đa kênh (ĐK), KPI chiến lược.",
        "routes": [
            "GET /api/cms/marketing-chat/weekly-plan.xlsx",
            "GET /api/cms/marketing-chat/multichannel-plan.xlsx",
            "GET /api/cms/marketing-chat/kpi-strategy.xlsx",
        ],
    },
    {
        "id": "mk_chat_campaign_kit",
        "label": "↳ Bộ KHMKT + KPI chiến dịch",
        "group": "Website — Chi tiết Chat Marketing",
        "description": "Tạo và tải bộ file chiến dịch (KHMKT, KPI.xlsx).",
        "routes": [
            "POST /api/cms/marketing-chat/campaign-kit",
            "GET /api/cms/marketing-chat/campaign-kit/*/khmkt.xlsx",
            "GET /api/cms/marketing-chat/campaign-kit/*/kpi.xlsx",
        ],
    },
    {
        "id": "permissions_matrix",
        "label": "Phân quyền",
        "group": "Website",
        "description": "Menu → /cms — ma trận quyền vai trò và chức vụ.",
        "routes": ["/cms#cms-permissions", "GET/PATCH /api/cms/permissions"],
    },
    {
        "id": "landing_content",
        "label": "Nội dung Landing page",
        "group": "Nội dung site",
        "description": "Menu → /cms/landing — hero slides, capabilities, CTA strip.",
        "routes": ["/cms/landing", "PUT /api/settings"],
    },
    {
        "id": "landing_media",
        "label": "Media Library",
        "group": "Nội dung site",
        "description": "Menu → /cms/landing#media — upload và quản lý ảnh.",
        "routes": [
            "POST /api/cms/media/upload",
            "GET /api/cms/media",
            "DELETE /api/cms/media/<filename>",
        ],
    },
    {
        "id": "live_chat",
        "label": "Live Chat",
        "group": "Website",
        "description": "Menu → /cms/live-chat — hộp thư chat khách truy cập, trả lời nhân viên / AI.",
        "routes": [
            "GET /cms/live-chat",
            "GET /api/cms/live-chat/conversations",
            "GET /api/cms/live-chat/messages/<id>",
            "POST /api/cms/live-chat/reply",
            "PUT /api/cms/live-chat/conversation/<id>",
            "PUT /api/cms/live-chat/settings",
        ],
    },
    {
        "id": "projects",
        "label": "Dự án portfolio",
        "group": "Nội dung site",
        "description": "Menu → /cms/landing — dự án hiển thị landing.",
        "routes": ["/cms/landing", "POST/DELETE /api/projects"],
    },
    {
        "id": "news",
        "label": "Blog / Tin tức",
        "group": "Nội dung site",
        "description": "Menu → /cms/landing — tin tức và blog landing.",
        "routes": ["/cms/landing", "POST/DELETE /api/news"],
    },
    {
        "id": "crm_lead_channels",
        "label": "Kênh CRM",
        "group": "Nội dung site",
        "description": "Menu → /admin — danh mục kênh dropdown CSKH.",
        "routes": ["/admin", "POST/PATCH /api/crm/channels"],
    },
    {
        "id": "recruitment_jobs",
        "label": "Tuyển dụng",
        "group": "Nội dung site",
        "description": "Menu → /cms/recruitment — quản lý vị trí tuyển dụng.",
        "routes": [
            "GET /api/cms/recruitment",
            "POST /api/cms/recruitment",
            "PUT /api/cms/recruitment/<id>",
            "DELETE /api/cms/recruitment/<id>",
        ],
    },
)

CMS_MODULES: tuple[dict[str, Any], ...] = CMS_CORE_MODULES + CMS_CRM_NAV_MODULES

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
        "name": "Quản trị CMS",
        "description": "Full CMS landing + marketing chat; không chỉnh phân quyền.",
        "is_system": True,
    },
    {
        "code": "content_editor",
        "name": "Biên tập nội dung",
        "description": "Settings, dịch vụ, dự án, tin tức — không chat AI / export Excel.",
        "is_system": True,
    },
    {
        "code": "marketing_lead",
        "name": "Trưởng nhóm Marketing",
        "description": "Toàn bộ marketing chat + xem nội dung; không xóa dự án/tin.",
        "is_system": True,
    },
    {
        "code": "marketing_staff",
        "name": "Nhân viên Marketing",
        "description": "Chat, export, Excel; không cấu hình chatbox / settings.",
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
        "admin_dashboard": frozenset({"view"}),
        "landing_settings": frozenset({"view", "edit"}),
        "services_builder": frozenset({"view", "edit", "create", "delete"}),
        "projects": frozenset({"view", "create", "delete"}),
        "news": frozenset({"view", "create", "delete"}),
        "mk_chat_config": frozenset({"view"}),
        "mk_chat_conversation": frozenset({"view"}),
        "mk_chat_export": frozenset(),
        "mk_chat_excel": frozenset(),
        "mk_chat_campaign_kit": frozenset(),
        "crm_lead_channels": frozenset({"view"}),
        "permissions_matrix": frozenset({"view"}),
    },
    "marketing_lead": {
        "admin_dashboard": frozenset({"view"}),
        "landing_settings": frozenset({"view"}),
        "services_builder": frozenset({"view"}),
        "mk_chat_config": frozenset({"view", "edit", "configure"}),
        "mk_chat_conversation": frozenset({"view", "create", "edit"}),
        "mk_chat_export": frozenset({"view", "export"}),
        "mk_chat_excel": frozenset({"view", "export"}),
        "mk_chat_campaign_kit": frozenset({"view", "create", "export"}),
        "projects": frozenset({"view"}),
        "news": frozenset({"view"}),
        "crm_lead_channels": frozenset({"view"}),
        "permissions_matrix": frozenset({"view"}),
        **_CRM_NAV_MARKETING_LEAD,
    },
    "marketing_staff": {
        "admin_dashboard": frozenset({"view"}),
        "landing_settings": frozenset({"view"}),
        "services_builder": frozenset({"view"}),
        "mk_chat_config": frozenset({"view"}),
        "mk_chat_conversation": frozenset({"view", "create", "edit"}),
        "mk_chat_export": frozenset({"view", "export"}),
        "mk_chat_excel": frozenset({"view", "export"}),
        "mk_chat_campaign_kit": frozenset({"view", "create", "export"}),
        "projects": frozenset({"view"}),
        "news": frozenset({"view"}),
        "crm_lead_channels": frozenset({"view"}),
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
