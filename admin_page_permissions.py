"""Hạng mục / section trong các trang Admin & CRM — phân quyền theo chức vụ."""
from __future__ import annotations

import sqlite3
from typing import Any

from cms_permissions import CMS_ACTIONS, CMS_ACTION_LABELS_VI, role_can
from ptt_ui_button_permissions import (
    CRM_UI_BUTTONS,
    CRM_UI_BUTTONS_BY_PARENT,
    CRM_UI_BUTTON_BY_ID,
    CRM_UI_BUTTON_IDS,
)

# Section bổ sung (ngoài CMS_MODULES gốc) — map UI + API CRM ops-web
ADMIN_CRM_SECTIONS: tuple[dict[str, Any], ...] = (
    # —— Bảng CSKH ——
    {
        "id": "crm_board_funnel",
        "label": "CSKH — Phễu bán hàng",
        "group": "CRM — Bảng CSKH",
        "page": "/crm",
        "description": "Phễu realtime và thống kê pipeline.",
    },
    {
        "id": "crm_board_workspace",
        "label": "CSKH — Không gian nhân viên",
        "group": "CRM — Bảng CSKH",
        "page": "/crm",
        "description": "Thống kê và lọc theo nhân viên phụ trách.",
    },
    {
        "id": "crm_board_kanban",
        "label": "CSKH — Bảng Kanban",
        "group": "CRM — Bảng CSKH",
        "page": "/crm",
        "description": "Xem và cập nhật yêu cầu chăm sóc khách hàng.",
    },
    {
        "id": "crm_board_create",
        "label": "CSKH — Tạo yêu cầu mới",
        "group": "CRM — Bảng CSKH",
        "page": "/crm",
        "description": "Form tạo case / lead mới trên bảng.",
    },
    {
        "id": "crm_board_playbook",
        "label": "CSKH — Playbook quy trình",
        "group": "CRM — Bảng CSKH",
        "page": "/crm",
        "description": "Hướng dẫn quy trình 6 bước trên bảng CSKH.",
    },
    {
        "id": "crm_board_customers",
        "label": "CSKH — Trang khách hàng",
        "group": "CRM — Bảng CSKH",
        "page": "/crm/customers",
        "description": "Hồ sơ khách hàng, timeline chăm sóc và hợp đồng.",
    },
    {
        "id": "crm_assistant",
        "label": "CSKH — Trợ lý AI",
        "group": "CRM — Bảng CSKH",
        "page": "/crm",
        "description": "Chatbox trợ lý playbook CRM, pipeline và gợi ý xử lý case.",
    },
    # —— Hub ——
    {
        "id": "crm_hub_campaigns",
        "label": "Hub — Chiến dịch",
        "group": "CRM — Marketing Hub",
        "page": "/crm/hub",
        "description": "Danh sách và CRUD chiến dịch marketing.",
    },
    {
        "id": "crm_hub_contracts",
        "label": "Hub — Hợp đồng",
        "group": "CRM — Marketing Hub",
        "page": "/crm/hub",
        "description": "Quản lý hợp đồng khách hàng.",
    },
    {
        "id": "crm_hub_reminders",
        "label": "Hub — Nhắc việc",
        "group": "CRM — Marketing Hub",
        "page": "/crm/hub",
        "description": "Nhắc việc gia hạn, theo dõi.",
    },
    # —— Kế hoạch marketing ——
    {
        "id": "crm_mktplan",
        "label": "Kế hoạch marketing",
        "group": "CRM — Marketing",
        "page": "/crm/marketing-plan",
        "description": "KHTN, KHQT, CSKH — lập và chỉnh kế hoạch.",
    },
    {
        "id": "crm_business_dashboard",
        "label": "Business Dashboard KPI",
        "group": "CRM — Marketing",
        "page": "/crm/business-dashboard",
        "description": "KPI executive, trend, cảnh báo, export.",
    },
    {
        "id": "crm_owner_weekly_dashboard",
        "label": "Dashboard tuần (Chủ DN)",
        "group": "CRM — Marketing",
        "page": "/crm/owner-weekly",
        "description": "4 khối Tiền/KD/Hiệu quả/Rủi ro, RAG, phân tích trước thực thi.",
    },
    # —— SOP ——
    {
        "id": "crm_sop_runs",
        "label": "SOP — Tiến trình đang chạy",
        "group": "CRM — SOP",
        "page": "/crm/sop",
        "description": "Theo dõi và cập nhật run SOP.",
    },
    {
        "id": "crm_sop_templates",
        "label": "SOP — Playbook / Template",
        "group": "CRM — SOP",
        "page": "/crm/sop",
        "description": "Mẫu quy trình và bước SOP.",
    },
    {
        "id": "crm_sop_overdue",
        "label": "SOP — Task quá hạn",
        "group": "CRM — SOP",
        "page": "/crm/sop",
        "description": "Danh sách task SOP quá hạn.",
    },
    # —— Nhân viên ——
    {
        "id": "crm_staff_departments",
        "label": "Nhân sự — Phòng ban",
        "group": "CRM — Nhân sự",
        "page": "/crm/staff",
        "description": "Danh mục phòng ban.",
    },
    {
        "id": "crm_staff_positions",
        "label": "Nhân sự — Chức vụ",
        "group": "CRM — Nhân sự",
        "page": "/crm/staff",
        "description": "Danh mục chức vụ và ma trận phân quyền.",
    },
    {
        "id": "crm_staff_roster",
        "label": "Nhân sự — Hồ sơ nhân viên",
        "group": "CRM — Nhân sự",
        "page": "/crm/staff",
        "description": "Bảng nhân viên, import/export, tài khoản đăng nhập.",
    },
    {
        "id": "crm_leads",
        "label": "Quản lý Lead",
        "group": "CRM — Bảng CSKH",
        "page": "/crm/leads",
        "description": "Thu thập đa nguồn, chấm điểm, phân loại, gán owner, SLA và AI truy xuất.",
    },
    {
        "id": "crm_daily_work_report",
        "label": "Nhân sự — Báo cáo công việc ngày",
        "group": "CRM — Nhân sự",
        "page": "/crm/daily-reports",
        "description": "Nhập và xem lịch sử báo cáo công việc hàng ngày.",
    },
    # —— KPI ——
    {
        "id": "crm_kpi_alerts",
        "label": "KPI — Cảnh báo",
        "group": "CRM — KPI",
        "page": "/crm/kpi",
        "description": "Giám sát cảnh báo KPI trong kỳ.",
    },
    {
        "id": "crm_kpi_chart",
        "label": "KPI — Biểu đồ",
        "group": "CRM — KPI",
        "page": "/crm/kpi",
        "description": "Biểu đồ % đạt theo nhân viên.",
    },
    {
        "id": "crm_kpi_metrics",
        "label": "KPI — Danh mục chỉ tiêu",
        "group": "CRM — KPI",
        "page": "/crm/kpi",
        "description": "Cấu hình chỉ tiêu KPI.",
    },
    {
        "id": "crm_kpi_records",
        "label": "KPI — Bản ghi theo kỳ",
        "group": "CRM — KPI",
        "page": "/crm/kpi",
        "description": "Ghi nhận mục tiêu / thực tế nhân viên.",
    },
    {
        "id": "crm_staff_kpi_am_sp",
        "label": "KPI AM/SP",
        "group": "CRM — KPI",
        "page": "/crm/staff-kpi",
        "description": "KPI AM/SP/Lead tự động — target, AI scan.",
    },
    {
        "id": "crm_hdsd",
        "label": "HDSD — Hướng dẫn sử dụng",
        "group": "CRM — Hướng dẫn",
        "page": "/crm/hdsd",
        "description": "Đọc & tải tài liệu Markdown từ docs/.",
    },
    # —— Chấm công & lương ——
    {
        "id": "crm_payroll_device",
        "label": "Chấm công — Tích hợp thiết bị",
        "group": "CRM — Chấm công",
        "page": "/crm/payroll",
        "description": "API máy vân tay / khuôn mặt.",
    },
    {
        "id": "crm_payroll_attendance",
        "label": "Chấm công — Bảng chấm công",
        "group": "CRM — Chấm công",
        "page": "/crm/payroll",
        "description": "Nhập và xem chấm công theo ngày.",
    },
    {
        "id": "crm_payroll_salary",
        "label": "Chấm công — Bảng lương",
        "group": "CRM — Chấm công",
        "page": "/crm/payroll",
        "description": "Tính lương, khóa kỳ, phụ cấp / khấu trừ.",
    },
    # —— Kinh doanh ——
    {
        "id": "crm_sales_overview",
        "label": "KD — Tổng quan",
        "group": "CRM — Kinh doanh",
        "page": "/crm/sales",
        "description": "Dashboard kinh doanh, phễu và tiến độ chỉ tiêu.",
    },
    {
        "id": "crm_sales_plans",
        "label": "KD — Kế hoạch & chỉ tiêu",
        "group": "CRM — Kinh doanh",
        "page": "/crm/sales",
        "description": "Lập kế hoạch kinh doanh, doanh thu, KPI cá nhân/phòng.",
    },
    {
        "id": "crm_sales_funnel",
        "label": "KD — Phễu bán hàng",
        "group": "CRM — Kinh doanh",
        "page": "/crm/sales",
        "description": "Theo dõi pipeline lead và giai đoạn bán hàng.",
    },
    {
        "id": "crm_sales_prospects",
        "label": "KD — KH tiềm năng & đối tác",
        "group": "CRM — Kinh doanh",
        "page": "/crm/sales",
        "description": "Phát triển khách hàng, đại lý, CTV, đối tác.",
    },
    {
        "id": "crm_sales_deals",
        "label": "KD — Giao dịch & hợp đồng",
        "group": "CRM — Kinh doanh",
        "page": "/crm/sales",
        "description": "Tư vấn, đàm phán, hồ sơ giao dịch BĐS.",
    },
    {
        "id": "crm_sales_training",
        "label": "KD — Đào tạo Sales",
        "group": "CRM — Kinh doanh",
        "page": "/crm/sales",
        "description": "Quản lý và ghi nhận đào tạo nhân viên kinh doanh.",
    },
    {
        "id": "crm_sales_market",
        "label": "KD — Nghiên cứu thị trường",
        "group": "CRM — Kinh doanh",
        "page": "/crm/sales",
        "description": "Phân tích thị trường, đối thủ, đề xuất chiến lược.",
    },
    {
        "id": "crm_sales_reports",
        "label": "KD — Báo cáo kết quả",
        "group": "CRM — Kinh doanh",
        "page": "/crm/sales",
        "description": "Báo cáo doanh số, hiệu quả bán hàng cho quản lý.",
    },
    # —— Dự án BĐS ——
    {
        "id": "crm_re_projects",
        "label": "Dự án BĐS — Tổng quan",
        "group": "CRM — Kinh doanh",
        "page": "/crm/re-projects",
        "description": "Danh sách và tổng quan dự án bất động sản.",
    },
    {
        "id": "crm_re_projects_business",
        "label": "Dự án BĐS — Kế hoạch kinh doanh",
        "group": "CRM — Kinh doanh",
        "page": "/crm/re-projects",
        "description": "SWOT, mục tiêu, cơ cấu chi phí, milestone.",
    },
    {
        "id": "crm_re_projects_marketing",
        "label": "Dự án BĐS — Kế hoạch marketing",
        "group": "CRM — Kinh doanh",
        "page": "/crm/re-projects",
        "description": "Mục tiêu, kênh, ngân sách, lead target.",
    },
    {
        "id": "crm_re_projects_sales",
        "label": "Dự án BĐS — Kế hoạch bán hàng",
        "group": "CRM — Kinh doanh",
        "page": "/crm/re-projects",
        "description": "Chỉ tiêu doanh thu, chính sách hoa hồng, quy trình bán.",
    },
    {
        "id": "crm_re_projects_kpi",
        "label": "Dự án BĐS — Hoạch định KPI",
        "group": "CRM — Kinh doanh",
        "page": "/crm/re-projects",
        "description": "Chỉ tiêu KPI theo kỳ, trọng số, owner.",
    },
    {
        "id": "crm_re_projects_products",
        "label": "Dự án BĐS — Quản lý sản phẩm",
        "group": "CRM — Kinh doanh",
        "page": "/crm/re-projects",
        "description": "Mã căn, diện tích, giá, trạng thái tồn kho.",
    },
    {
        "id": "crm_re_projects_risks",
        "label": "Dự án BĐS — Quản lý rủi ro",
        "group": "CRM — Kinh doanh",
        "page": "/crm/re-projects",
        "description": "Ma trận rủi ro, xác suất, tác động, giảm thiểu.",
    },
    {
        "id": "crm_re_projects_budget",
        "label": "Dự án BĐS — Lợi nhuận & ngân sách",
        "group": "CRM — Kinh doanh",
        "page": "/crm/re-projects",
        "description": "Doanh thu, chi phí, lợi nhuận kế hoạch vs thực tế.",
    },
    {
        "id": "crm_agency",
        "label": "Agency Ops",
        "group": "CRM · Agency Ops",
        "page": "/crm/agency",
        "description": "Client registry, pipeline ingest, thông báo SLA, KPI dictionary.",
    },
    {
        "id": "crm_facebook_ads",
        "label": "Facebook Ads",
        "group": "CRM · Quảng cáo",
        "page": "/crm/facebook-ads",
        "description": "Hub Meta/Facebook — token, CPL, map Hub, truy cập nhanh Lead Ads.",
    },
    {
        "id": "crm_seo_aeo",
        "label": "SEO/AEO Ops — Tổng quan",
        "group": "CRM · SEO/AEO",
        "page": "/crm/seo",
        "description": "Hub cross-client — overview, health, alerts.",
    },
    {
        "id": "crm_seo_aeo_write",
        "label": "SEO/AEO — Nội dung & Nghiên cứu",
        "group": "CRM · SEO/AEO",
        "page": "/crm/seo",
        "description": "Research CRUD, content pipeline create/edit.",
    },
    {
        "id": "crm_seo_aeo_approve",
        "label": "SEO/AEO — Phê duyệt",
        "group": "CRM · SEO/AEO",
        "page": "/crm/seo",
        "description": "Approval stages, publish CMS.",
    },
    {
        "id": "crm_seo_aeo_technical",
        "label": "SEO/AEO — Kỹ thuật",
        "group": "CRM · SEO/AEO",
        "page": "/crm/seo/technical",
        "description": "Technical issues, crawl import, CRM tasks.",
    },
    {
        "id": "crm_seo_aeo_settings",
        "label": "SEO/AEO — Cài đặt client",
        "group": "CRM · SEO/AEO",
        "page": "/crm/seo/clients",
        "description": "Client settings, OAuth GSC/GA4, CMS, schedules.",
    },
    {
        "id": "crm_seo_aeo_reports",
        "label": "SEO/AEO — Báo cáo",
        "group": "CRM · SEO/AEO",
        "page": "/crm/seo/reports",
        "description": "Export PDF, BI, scheduled reports.",
    },
)

ADMIN_CRM_SECTION_IDS: frozenset[str] = frozenset(s["id"] for s in ADMIN_CRM_SECTIONS)
ADMIN_CRM_PERMISSION_IDS: frozenset[str] = ADMIN_CRM_SECTION_IDS | CRM_UI_BUTTON_IDS

# Các section gắn menu trái CRM — dùng suy ra chế độ «chỉ Lead»
SIDEBAR_CRM_NAV_SECTIONS: tuple[str, ...] = (
    "crm_board_kanban",
    "crm_board_customers",
    "crm_leads",
    "crm_hub_campaigns",
    "crm_mktplan",
    "crm_business_dashboard",
    "crm_owner_weekly_dashboard",
    "crm_sop_runs",
    "crm_sales_overview",
    "crm_re_projects",
    "crm_staff_roster",
    "crm_daily_work_report",
    "crm_kpi_records",
    "crm_staff_kpi_am_sp",
    "crm_hdsd",
    "crm_payroll_attendance",
    "crm_agency",
    "crm_facebook_ads",
    "crm_seo_aeo",
)

# Map section → nhóm trang (để gating nav)
SECTION_PAGE: dict[str, str] = {s["id"]: s["page"] for s in ADMIN_CRM_SECTIONS}

# Quyền mặc định theo mã chức vụ (crm_positions.code)
_POSITION_DEFAULT: dict[str, dict[str, frozenset[str]]] = {
    "CSKH-01": {
        "crm_board_funnel": frozenset({"view"}),
        "crm_board_workspace": frozenset({"view", "edit"}),
        "crm_board_kanban": frozenset({"view", "edit", "create"}),
        "crm_board_create": frozenset({"view", "create"}),
        "crm_board_playbook": frozenset({"view"}),
        "crm_board_customers": frozenset({"view", "edit", "create"}),
        "crm_leads": frozenset({"view", "edit", "create", "export"}),
        "crm_assistant": frozenset({"view", "create", "export"}),
        "crm_hub_reminders": frozenset({"view", "edit"}),
        "crm_kpi_records": frozenset({"view", "edit"}),
        "crm_payroll_attendance": frozenset({"view"}),
        "crm_daily_work_report": frozenset({"view", "create", "edit"}),
        "crm_hdsd": frozenset({"view", "export"}),
    },
    "KD-01": {
        "crm_leads": frozenset({"view", "edit", "create"}),
        "crm_leads__btn_create": frozenset(),
        "crm_leads__btn_export_xlsx": frozenset(),
        "crm_leads__btn_export_pdf": frozenset(),
        "crm_leads__btn_import": frozenset(),
        "crm_leads__btn_fb_sync": frozenset(),
        "crm_leads__btn_config": frozenset(),
        "crm_leads__btn_rules": frozenset(),
        "crm_leads__btn_ai_search": frozenset(),
        "crm_leads__btn_convert": frozenset(),
        "crm_leads__btn_assign": frozenset(),
        "crm_leads__btn_merge": frozenset(),
        "crm_leads__btn_ai_summary": frozenset(),
        "crm_leads__btn_ai_classify": frozenset(),
        "crm_leads__btn_ai_recommend": frozenset(),
        "crm_leads__btn_delete": frozenset(),
        "crm_leads__btn_rescore": frozenset(),
        "crm_leads__btn_save": frozenset(),
        "crm_leads__btn_edit": frozenset({"edit"}),
        "crm_leads__btn_activity": frozenset({"create"}),
        "crm_hdsd": frozenset({"view", "export"}),
        "crm_agency": frozenset({"view", "edit", "create", "configure"}),
        "crm_facebook_ads": frozenset({"view", "edit", "create", "configure"}),
        "crm_seo_aeo": frozenset({"view"}),
        "crm_seo_aeo_settings": frozenset({"view", "edit", "configure"}),
        "crm_seo_aeo_reports": frozenset({"view", "export"}),
    },
    "MKT-01": {
        "crm_hub_campaigns": frozenset({"view", "edit", "create", "delete"}),
        "crm_hub_contracts": frozenset({"view", "edit"}),
        "crm_hub_reminders": frozenset({"view", "edit", "create"}),
        "crm_mktplan": frozenset({"view", "edit", "create", "export"}),
        "crm_business_dashboard": frozenset({"view", "export", "configure"}),
        "crm_owner_weekly_dashboard": frozenset({"view", "export", "configure"}),
        "crm_leads": frozenset({"view", "edit", "create", "export", "configure"}),
        "crm_board_funnel": frozenset({"view", "export"}),
        "crm_assistant": frozenset({"view", "create", "export"}),
        "crm_sop_runs": frozenset({"view", "edit", "create"}),
        "crm_sop_templates": frozenset({"view"}),
        "crm_sop_overdue": frozenset({"view", "edit"}),
        "crm_kpi_alerts": frozenset({"view"}),
        "crm_kpi_chart": frozenset({"view", "export"}),
        "crm_kpi_records": frozenset({"view", "edit", "create"}),
        "crm_sales_overview": frozenset({"view", "export"}),
        "crm_sales_funnel": frozenset({"view", "export"}),
        "crm_sales_market": frozenset({"view", "edit", "create"}),
        "crm_re_projects": frozenset({"view", "export"}),
        "crm_re_projects_business": frozenset({"view"}),
        "crm_re_projects_marketing": frozenset({"view", "edit", "create"}),
        "crm_re_projects_sales": frozenset({"view"}),
        "crm_re_projects_kpi": frozenset({"view", "edit", "create"}),
        "crm_re_projects_products": frozenset({"view"}),
        "crm_re_projects_risks": frozenset({"view", "edit", "create"}),
        "crm_re_projects_budget": frozenset({"view", "edit", "create", "export"}),
        "crm_daily_work_report": frozenset({"view", "edit", "create", "export"}),
        "crm_board_customers": frozenset({"view"}),
        "crm_hdsd": frozenset({"view", "export"}),
        "crm_agency": frozenset({"view", "edit", "create", "configure"}),
        "crm_facebook_ads": frozenset({"view", "edit", "create", "configure"}),
        "crm_seo_aeo": frozenset({"view", "edit", "create", "approve", "configure", "export"}),
        "crm_seo_aeo_write": frozenset({"view", "edit", "create"}),
        "crm_seo_aeo_approve": frozenset({"approve"}),
        "crm_seo_aeo_technical": frozenset({"view", "edit", "create"}),
        "crm_seo_aeo_settings": frozenset({"view", "edit", "configure"}),
        "crm_seo_aeo_reports": frozenset({"view", "export"}),
        "crm_email_mkt": frozenset({"view", "write", "settings", "compliance", "approve", "deliverability", "reports"}),
    },
    "MKT-02": {
        "crm_hub_campaigns": frozenset({"view", "edit", "create"}),
        "crm_hub_reminders": frozenset({"view", "edit"}),
        "crm_mktplan": frozenset({"view", "edit"}),
        "crm_leads": frozenset({"view", "edit", "export"}),
        "crm_board_funnel": frozenset({"view"}),
        "crm_assistant": frozenset({"view", "create"}),
        "crm_sop_runs": frozenset({"view", "edit", "create"}),
        "crm_sop_templates": frozenset({"view"}),
        "crm_sop_overdue": frozenset({"view"}),
        "crm_kpi_records": frozenset({"view", "edit"}),
        "crm_re_projects": frozenset({"view"}),
        "crm_re_projects_marketing": frozenset({"view", "edit"}),
        "crm_re_projects_budget": frozenset({"view", "edit", "create"}),
        "crm_re_projects_kpi": frozenset({"view", "edit"}),
        "crm_daily_work_report": frozenset({"view", "create"}),
        "crm_hdsd": frozenset({"view", "export"}),
        "crm_seo_aeo": frozenset({"view"}),
        "crm_seo_aeo_write": frozenset({"view", "edit", "create"}),
        "crm_seo_aeo_reports": frozenset({"view"}),
        "crm_email_mkt": frozenset({"view", "write", "reports"}),
    },
    "VH-01": {
        "crm_board_kanban": frozenset({"view"}),
        "crm_board_workspace": frozenset({"view"}),
        "crm_board_customers": frozenset({"view"}),
        "crm_sop_runs": frozenset({"view", "edit", "create"}),
        "crm_sop_templates": frozenset({"view", "edit", "configure"}),
        "crm_sop_overdue": frozenset({"view", "edit"}),
        "crm_staff_departments": frozenset({"view"}),
        "crm_staff_positions": frozenset({"view"}),
        "crm_staff_roster": frozenset({"view", "edit", "export"}),
        "crm_payroll_device": frozenset({"view", "configure"}),
        "crm_payroll_attendance": frozenset({"view", "edit", "create"}),
        "crm_payroll_salary": frozenset({"view", "edit", "export"}),
        "crm_assistant": frozenset({"view", "create", "export"}),
        "crm_daily_work_report": frozenset({"view", "edit", "create", "export", "delete"}),
        "crm_kpi_alerts": frozenset({"view"}),
        "crm_kpi_records": frozenset({"view", "edit"}),
        "crm_hdsd": frozenset({"view", "export"}),
    },
}


def _button_grant_checked(
    grants: dict[str, list[str] | frozenset[str] | set[str]],
    btn: dict[str, Any],
    *,
    parent_allowed: set[str],
) -> bool:
    bid = btn["id"]
    req = btn["requires_action"]
    if bid in grants:
        return req in set(grants.get(bid) or [])
    return req in parent_allowed


def default_grants_for_position(position_code: str) -> dict[str, list[str]]:
    raw = _POSITION_DEFAULT.get(str(position_code or "").strip(), {})
    out: dict[str, list[str]] = {}
    for sec in ADMIN_CRM_SECTIONS:
        sid = sec["id"]
        acts = raw.get(sid, frozenset())
        out[sid] = sorted(a for a in CMS_ACTIONS if a in acts)
    for btn in CRM_UI_BUTTONS:
        bid = btn["id"]
        req = btn["requires_action"]
        if bid in raw:
            out[bid] = sorted(a for a in CMS_ACTIONS if a in raw[bid])
        else:
            parent = btn["parent_section"]
            if req in set(out.get(parent) or []):
                out[bid] = [req]
            else:
                out[bid] = []
    return out


def grants_map_to_rows(
    grants: dict[str, list[str] | frozenset[str] | set[str]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for sec in ADMIN_CRM_SECTIONS:
        sid = sec["id"]
        allowed = set(grants.get(sid) or [])
        rows.append(
            {
                "section_id": sid,
                "section_label": sec["label"],
                "group": sec["group"],
                "page": sec.get("page", ""),
                "description": sec.get("description", ""),
                "row_kind": "section",
                "actions": {a: a in allowed for a in CMS_ACTIONS},
                "allowed_list": sorted(a for a in CMS_ACTIONS if a in allowed),
            }
        )
        buttons = CRM_UI_BUTTONS_BY_PARENT.get(sid) or []
        if not buttons:
            continue
        page = sec.get("page", "") or buttons[0].get("page", "")
        rows.append(
            {
                "section_id": f"{sid}__buttons",
                "section_label": f"Nút hành động — {page}",
                "group": sec["group"],
                "page": page,
                "description": "",
                "row_kind": "button_group",
                "actions": {a: False for a in CMS_ACTIONS},
                "allowed_list": [],
            }
        )
        for btn in buttons:
            bid = btn["id"]
            req = btn["requires_action"]
            checked = _button_grant_checked(grants, btn, parent_allowed=allowed)
            rows.append(
                {
                    "section_id": bid,
                    "section_label": btn["label"],
                    "group": sec["group"],
                    "page": btn.get("page", page),
                    "description": btn.get("description", ""),
                    "row_kind": "ui_button",
                    "parent_section": sid,
                    "requires_action": req,
                    "actions": {a: (a == req and checked) for a in CMS_ACTIONS},
                    "allowed_list": [req] if checked else [],
                }
            )
    return rows


def build_position_permission_matrix(
    position_rows: list[dict[str, Any]],
    position_grants: dict[int, dict[str, list[str]]],
) -> dict[str, Any]:
    positions_out = []
    for prow in position_rows:
        pid = int(prow["id"])
        code = str(prow.get("code") or "")
        grants = position_grants.get(pid) or default_grants_for_position(code)
        positions_out.append(
            {
                "id": pid,
                "code": code,
                "name": str(prow.get("name") or ""),
                "grants": grants_map_to_rows(grants),
                "grants_dict": grants,
            }
        )
    return {
        "actions": [{"id": a, "label": CMS_ACTION_LABELS_VI[a]} for a in CMS_ACTIONS],
        "sections": list(ADMIN_CRM_SECTIONS),
        "ui_buttons": list(CRM_UI_BUTTONS),
        "positions": positions_out,
    }


def parse_position_grants_payload(raw: Any) -> dict[str, list[str]] | None:
    if not isinstance(raw, dict):
        return None
    out: dict[str, list[str]] = {}
    for sid, acts in raw.items():
        if sid.endswith("__buttons"):
            continue
        if sid not in ADMIN_CRM_PERMISSION_IDS:
            continue
        if not isinstance(acts, list):
            return None
        norm = []
        for a in acts:
            s = str(a or "").strip().lower()
            if s in CMS_ACTIONS:
                norm.append(s)
        out[sid] = sorted(set(norm))
    return out


def position_leads_only_ui(
    grants: dict[str, list[str] | frozenset[str]],
    *,
    is_super: bool = False,
) -> bool:
    """True khi chỉ có quyền xem Lead — menu trái thu gọn «Danh sách lead»."""
    if is_super:
        return False
    if not position_can(grants, "crm_leads", "view", is_super=is_super):
        return False
    others = [s for s in SIDEBAR_CRM_NAV_SECTIONS if s != "crm_leads"]
    return not any(position_can(grants, s, "view", is_super=is_super) for s in others)


def ui_button_can(
    grants: dict[str, list[str] | frozenset[str]],
    button_id: str,
    *,
    is_super: bool = False,
) -> bool:
    if is_super:
        return True
    btn = CRM_UI_BUTTON_BY_ID.get(str(button_id or "").strip())
    if not btn:
        return False
    bid = btn["id"]
    req = btn["requires_action"]
    if bid in grants:
        return req in set(grants.get(bid) or [])
    parent = btn["parent_section"]
    return req in set(grants.get(parent) or [])


def position_can(
    grants: dict[str, list[str] | frozenset[str]],
    section_id: str,
    action: str,
    *,
    is_super: bool = False,
) -> bool:
    if is_super:
        return True
    sid = str(section_id or "").strip()
    act = str(action or "").strip().lower()
    if act not in CMS_ACTIONS:
        return False
    if sid in CRM_UI_BUTTON_IDS:
        btn = CRM_UI_BUTTON_BY_ID.get(sid)
        if not btn or act != btn["requires_action"]:
            return False
        return ui_button_can(grants, sid, is_super=is_super)
    if sid not in ADMIN_CRM_SECTION_IDS:
        return False
    return act in set(grants.get(sid) or [])


MKT_POSITION_SEEDS: tuple[tuple[str, str, str, int], ...] = (
    ("MKT-01", "Trưởng phòng Marketing", "Hub, lead, GTM dự án, KPI và kế toán MKT.", 15),
    ("MKT-02", "Nhân viên Marketing", "Vận hành campaign, lead, nhập chi ads.", 16),
)

POSITION_GRANTS_CUSTOMIZED_BACKFILL_KEY = "position_grants_customized_backfill_v1"


def ensure_position_grants_customized_column(conn) -> None:
    cols = {r[1] for r in conn.execute("PRAGMA table_info(crm_positions)").fetchall()}
    if "grants_customized" not in cols:
        conn.execute(
            "ALTER TABLE crm_positions ADD COLUMN grants_customized INTEGER NOT NULL DEFAULT 0"
        )


def backfill_position_grants_customized(conn) -> None:
    """Một lần: chức vụ đã có quyền trong DB = admin đã cấu hình."""
    row = conn.execute(
        "SELECT value FROM settings WHERE key = ?",
        (POSITION_GRANTS_CUSTOMIZED_BACKFILL_KEY,),
    ).fetchone()
    if row and str(row["value"]) == "1":
        return
    rows = conn.execute("SELECT id FROM crm_positions WHERE active = 1").fetchall()
    for prow in rows:
        pid = int(prow["id"])
        cnt = conn.execute(
            "SELECT COUNT(*) AS n FROM crm_position_section_permissions WHERE position_id = ?",
            (pid,),
        ).fetchone()
        if cnt and int(cnt["n"]) > 0:
            conn.execute(
                "UPDATE crm_positions SET grants_customized = 1 WHERE id = ?",
                (pid,),
            )
    conn.execute(
        "INSERT OR REPLACE INTO settings (key, value) VALUES (?, '1')",
        (POSITION_GRANTS_CUSTOMIZED_BACKFILL_KEY,),
    )


def mark_position_grants_customized(conn, position_id: int, *, ts: str = "") -> None:
    if ts:
        conn.execute(
            "UPDATE crm_positions SET grants_customized = 1, updated_at = ? WHERE id = ?",
            (ts, int(position_id)),
        )
    else:
        conn.execute(
            "UPDATE crm_positions SET grants_customized = 1 WHERE id = ?",
            (int(position_id),),
        )


def apply_position_default_grants(
    conn,
    position_code: str,
    *,
    replace: bool = False,
) -> bool:
    """Ghi ma trận mặc định cho một chức vụ (replace=True → xóa quyền cũ trước)."""
    row = conn.execute(
        """
        SELECT id FROM crm_positions
        WHERE lower(trim(code)) = lower(trim(?)) AND active = 1
        LIMIT 1
        """,
        (position_code,),
    ).fetchone()
    if not row:
        return False
    pid = int(row["id"])
    defaults = default_grants_for_position(position_code)
    if replace:
        conn.execute(
            "DELETE FROM crm_position_section_permissions WHERE position_id = ?",
            (pid,),
        )
    for sid, acts in defaults.items():
        for act in acts:
            conn.execute(
                """
                INSERT OR IGNORE INTO crm_position_section_permissions
                (position_id, section_id, action)
                VALUES (?, ?, ?)
                """,
                (pid, sid, act),
            )
    return True


def migrate_hdsd_position_permissions(conn) -> None:
    """Bổ sung quyền HDSD — menu sidebar/topbar (INSERT OR IGNORE, không ghi đè ma trận cũ)."""
    rows = conn.execute(
        "SELECT id, code FROM crm_positions WHERE active = 1"
    ).fetchall()
    for prow in rows:
        pid = int(prow["id"])
        code = str(prow["code"] or "")
        defaults = default_grants_for_position(code)
        acts = list(defaults.get("crm_hdsd") or [])
        if not acts:
            acts = ["view", "export"]
        for act in acts:
            conn.execute(
                """
                INSERT OR IGNORE INTO crm_position_section_permissions
                (position_id, section_id, action)
                VALUES (?, 'crm_hdsd', ?)
                """,
                (pid, act),
            )


def migrate_kd01_leads_only_permissions(conn) -> None:
    """Seed mặc định KD-01 lần đầu — không ghi đè ma trận admin đã lưu."""
    row = conn.execute(
        "SELECT id FROM crm_positions WHERE lower(trim(code)) = 'kd-01' AND active = 1 LIMIT 1"
    ).fetchone()
    if not row:
        return
    pid = int(row["id"] if hasattr(row, "keys") else row[0])
    customized = conn.execute(
        "SELECT grants_customized FROM crm_positions WHERE id = ?",
        (pid,),
    ).fetchone()
    if customized and int(customized["grants_customized"] if hasattr(customized, "keys") else customized[0] or 0):
        return
    count_row = conn.execute(
        """
        SELECT COUNT(*) AS c FROM crm_position_section_permissions
        WHERE position_id = ?
        """,
        (pid,),
    ).fetchone()
    count = int(count_row["c"] if hasattr(count_row, "keys") else count_row[0])
    if count == 0:
        apply_position_default_grants(conn, "KD-01", replace=False)


def seed_marketing_positions(conn) -> None:
    """Thêm chức vụ MKT-01/MKT-02 và gán quyền mặc định nếu chưa có."""
    from datetime import datetime

    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    date = ts[:10]
    for code, name, desc, sort_order in MKT_POSITION_SEEDS:
        row = conn.execute(
            "SELECT id FROM crm_positions WHERE lower(trim(code)) = lower(trim(?))",
            (code,),
        ).fetchone()
        if not row:
            conn.execute(
                """
                INSERT INTO crm_positions (code, name, description, sort_order, active, created_at, updated_at)
                VALUES (?, ?, ?, ?, 1, ?, ?)
                """,
                (code, name, desc, int(sort_order), date, ts),
            )
            row = conn.execute(
                "SELECT id FROM crm_positions WHERE lower(trim(code)) = lower(trim(?))",
                (code,),
            ).fetchone()
        if not row:
            continue
        pid = int(row["id"])
        customized = conn.execute(
            "SELECT grants_customized FROM crm_positions WHERE id = ?",
            (pid,),
        ).fetchone()
        if customized and int(customized["grants_customized"] or 0):
            continue
        cnt = conn.execute(
            "SELECT COUNT(*) AS n FROM crm_position_section_permissions WHERE position_id = ?",
            (pid,),
        ).fetchone()
        if cnt and int(cnt["n"]) > 0:
            continue
        defaults = default_grants_for_position(code)
        for sid, acts in defaults.items():
            for act in acts:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO crm_position_section_permissions
                    (position_id, section_id, action)
                    VALUES (?, ?, ?)
                    """,
                    (pid, sid, act),
                )
