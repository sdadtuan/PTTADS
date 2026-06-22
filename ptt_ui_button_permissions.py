"""Catalog nút hành động theo trang CRM — hiển thị trong ma trận phân quyền chức vụ."""
from __future__ import annotations

from typing import Any


def _btn(
    id: str,
    label: str,
    parent: str,
    action: str,
    *,
    page: str = "",
    note: str = "",
) -> dict[str, Any]:
    return {
        "id": id,
        "label": label,
        "parent_section": parent,
        "requires_action": action,
        "page": page,
        "description": note or f"Nút «{label}» trên trang.",
        "kind": "ui_button",
    }


CRM_UI_BUTTONS: tuple[dict[str, Any], ...] = (
    # —— /crm ——
    _btn(
        "crm_board_create__btn_new_case",
        "＋ Yêu cầu mới",
        "crm_board_create",
        "create",
        page="/crm",
        note="Toolbar tạo case CSKH mới.",
    ),
    # —— /crm/leads ——
    _btn("crm_leads__btn_create", "＋ Tạo lead", "crm_leads", "create", page="/crm/leads"),
    _btn("crm_leads__btn_export_xlsx", "Excel", "crm_leads", "export", page="/crm/leads"),
    _btn("crm_leads__btn_export_pdf", "PDF", "crm_leads", "export", page="/crm/leads"),
    _btn("crm_leads__btn_import", "Import CSV", "crm_leads", "create", page="/crm/leads"),
    _btn("crm_leads__btn_fb_sync", "Facebook Lead", "crm_leads", "create", page="/crm/leads"),
    _btn(
        "crm_leads__btn_config",
        "Cấu hình phân lead",
        "crm_leads",
        "configure",
        page="/crm/leads",
    ),
    _btn(
        "crm_leads__btn_rules",
        "Quy tắc điểm & hạng",
        "crm_leads",
        "configure",
        page="/crm/leads",
    ),
    _btn("crm_leads__btn_ai_search", "Tìm kiếm AI", "crm_leads", "view", page="/crm/leads"),
    _btn(
        "crm_leads__btn_convert",
        "→ Case/KH",
        "crm_leads",
        "create",
        page="/crm/leads",
        note="Chuyển lead thành khách hàng + case CSKH.",
    ),
    _btn("crm_leads__btn_assign", "Phân lại owner", "crm_leads", "edit", page="/crm/leads"),
    _btn("crm_leads__btn_merge", "Gộp trùng", "crm_leads", "edit", page="/crm/leads"),
    _btn("crm_leads__btn_ai_summary", "AI Tóm tắt", "crm_leads", "view", page="/crm/leads"),
    _btn("crm_leads__btn_ai_classify", "AI Phân loại", "crm_leads", "edit", page="/crm/leads"),
    _btn("crm_leads__btn_ai_recommend", "Gợi ý", "crm_leads", "view", page="/crm/leads"),
    _btn("crm_leads__btn_edit", "Sửa", "crm_leads", "edit", page="/crm/leads"),
    _btn("crm_leads__btn_delete", "Xóa", "crm_leads", "delete", page="/crm/leads"),
    _btn("crm_leads__btn_rescore", "Chấm lại", "crm_leads", "edit", page="/crm/leads"),
    _btn(
        "crm_leads__btn_activity",
        "＋ Ghi activity",
        "crm_leads",
        "create",
        page="/crm/leads",
        note="Ghi nhận hoạt động chăm sóc lead.",
    ),
    _btn(
        "crm_leads__btn_save",
        "Lưu lead",
        "crm_leads",
        "edit",
        page="/crm/leads",
        note="Nút lưu trong form tạo/sửa lead.",
    ),
    # —— /crm/customers ——
    _btn(
        "crm_board_customers__btn_create",
        "＋ Thêm khách hàng",
        "crm_board_customers",
        "create",
        page="/crm/customers",
    ),
    # —— /crm/hub ——
    _btn(
        "crm_hub_campaigns__btn_create",
        "Chiến dịch mới",
        "crm_hub_campaigns",
        "create",
        page="/crm/hub",
    ),
    _btn(
        "crm_hub_contracts__btn_create",
        "Hợp đồng mới",
        "crm_hub_contracts",
        "create",
        page="/crm/hub",
    ),
    _btn(
        "crm_hub_reminders__btn_create",
        "Thêm nhắc việc",
        "crm_hub_reminders",
        "create",
        page="/crm/hub",
    ),
    # —— /crm/staff ——
    _btn(
        "crm_staff_departments__btn_add",
        "＋ Thêm phòng ban",
        "crm_staff_departments",
        "create",
        page="/crm/staff",
    ),
    _btn(
        "crm_staff_positions__btn_add",
        "＋ Thêm chức vụ",
        "crm_staff_positions",
        "create",
        page="/crm/staff",
    ),
    _btn(
        "crm_staff_roster__btn_add",
        "＋ Thêm nhân viên",
        "crm_staff_roster",
        "create",
        page="/crm/staff",
    ),
    _btn(
        "crm_staff_roster__btn_export_xlsx",
        "Excel nhân viên",
        "crm_staff_roster",
        "export",
        page="/crm/staff",
    ),
    _btn(
        "crm_staff_roster__btn_import",
        "Nhập CSV nhân viên",
        "crm_staff_roster",
        "create",
        page="/crm/staff",
    ),
    # —— /crm/kpi ——
    _btn(
        "crm_kpi_records__btn_save",
        "Lưu bản ghi KPI",
        "crm_kpi_records",
        "edit",
        page="/crm/kpi",
    ),
    _btn(
        "crm_kpi_metrics__btn_save",
        "Lưu chỉ tiêu KPI",
        "crm_kpi_metrics",
        "configure",
        page="/crm/kpi",
    ),
    # —— /crm/re-projects ——
    _btn(
        "crm_re_projects__btn_create",
        "＋ Dự án mới",
        "crm_re_projects",
        "create",
        page="/crm/re-projects",
    ),
    _btn(
        "crm_re_projects_marketing__btn_save",
        "Lưu KH marketing dự án",
        "crm_re_projects_marketing",
        "edit",
        page="/crm/re-projects",
    ),
    _btn(
        "crm_re_projects_products__btn_save",
        "Lưu sản phẩm",
        "crm_re_projects_products",
        "edit",
        page="/crm/re-projects",
    ),
)

CRM_UI_BUTTON_IDS: frozenset[str] = frozenset(b["id"] for b in CRM_UI_BUTTONS)
CRM_UI_BUTTON_BY_ID: dict[str, dict[str, Any]] = {b["id"]: b for b in CRM_UI_BUTTONS}
CRM_UI_BUTTONS_BY_PARENT: dict[str, list[dict[str, Any]]] = {}
for _b in CRM_UI_BUTTONS:
    CRM_UI_BUTTONS_BY_PARENT.setdefault(_b["parent_section"], []).append(_b)
