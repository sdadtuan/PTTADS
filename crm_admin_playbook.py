"""Playbook quản trị CRM PTT — lương, phân quyền, vận hành (cho Trợ lý CRM)."""
from __future__ import annotations

from typing import Any

# --- Xuất & gửi bảng lương từng nhân viên ---
PAYROLL_EXPORT_STEPS: tuple[str, ...] = (
    "Vào **CRM → Chấm công & Lương** (`/crm/payroll`) — section `crm_payroll_salary`.",
    "Chọn **Năm / Tháng** trên thanh công cụ (kỳ cần xuất).",
    "Mục **Bảng lương** → bấm **Tính / cập nhật lương** (nếu kỳ chưa có hoặc chấm công mới).",
    "(Khuyến nghị) **Khóa kỳ** sau khi HR duyệt — tránh sửa nhầm số liệu đã gửi NV.",
    "Mục **Xuất file** → **Kiểu kỳ**: Tháng / Quý / Khoảng thời gian.",
    "Ô **Nhân viên**: gõ tên hoặc mã → chọn đúng 1 người (hoặc để trống = tất cả).",
    "Bấm **Xuất Excel** hoặc **Xuất CSV** — file chỉ chứa dòng lương NV đã chọn.",
    "**Gửi cho NV**: đính kèm file qua email công ty / Zalo / Teams (PTT chưa gửi email tự động).",
    "Hoặc hướng dẫn NV đăng nhập portal → **Chấm công & Lương** xem bảng cá nhân.",
)

PAYROLL_SEND_CHECKLIST: tuple[str, ...] = (
    "NV đã có **Mã PIN chấm công** khớp máy / file import Excel.",
    "Chấm công tháng đã nhập đủ (máy ZKTeco, import Excel, hoặc nhập tay).",
    "Đã **Tính lương** kỳ; kiểm tra cột: ngày công, giờ, phạt trễ, phụ cấp cấp bậc, thưởng, thực lĩnh.",
    "Xuất Excel **lọc đúng 1 NV**; đối chiếu tên + mã nội bộ trên file.",
    "Ghi chú email: kỳ lương, ngày thanh toán, kênh khiếu nại (HR).",
    "Lưu bản Excel vào kho nội bộ (Drive/SharePoint) nếu công ty yêu cầu audit.",
)

PAYROLL_EXPORT_API_HINT = (
    "API xuất (admin, cần quyền `crm_payroll_salary` → export):\n"
    "`GET /api/crm/payroll/export?format=xlsx&period=month&year=YYYY&month=M&staff_id=ID`\n"
    "Hoặc tìm theo tên/mã/PIN: `&q=TenHoacMa`\n"
    "Quý: `period=quarter&year=YYYY&quarter=1..4` · Khoảng: `period=range&from=YYYY-MM-DD&to=YYYY-MM-DD`"
)

# --- Ba loại phiên & phân quyền ---
ADMIN_SESSION_TYPES: tuple[dict[str, str], ...] = (
    {
        "id": "full_admin",
        "label": "Quản trị toàn quyền",
        "detail": "super_admin / cms_admin — mọi CMS + CRM, không bị gating section.",
    },
    {
        "id": "role_position",
        "label": "Admin theo vai trò + chức vụ",
        "detail": "CMS theo vai trò (cms_roles); CRM theo chức vụ (crm_positions). Sidebar/panel ẩn khi thiếu quyền.",
    },
    {
        "id": "staff_portal",
        "label": "Portal nhân viên",
        "detail": "crm_staff — chỉ case được gán, KPI/chấm công cá nhân; không Hub/CMS.",
    },
)

CMS_ACTIONS_VI: tuple[tuple[str, str], ...] = (
    ("view", "Xem trang / danh sách"),
    ("edit", "Sửa bản ghi"),
    ("create", "Tạo mới"),
    ("delete", "Xóa"),
    ("export", "Xuất file Excel/CSV/báo cáo"),
    ("configure", "Cấu hình hệ thống (ma trận quyền, thiết bị chấm công)"),
)

CRM_PAGES_ADMIN: tuple[dict[str, Any], ...] = (
    {
        "path": "/admin",
        "label": "Admin Dashboard",
        "sections": "admin_projects, admin_news",
        "admin_needs": "Quản lý dự án portfolio & tin tức landing.",
    },
    {
        "path": "/cms",
        "label": "CMS",
        "sections": "Landing, dịch vụ, chat MKT, phân quyền, kênh lead",
        "admin_needs": "Nội dung website, trợ lý marketing, ma trận vai trò/chức vụ.",
    },
    {
        "path": "/crm",
        "label": "Bảng CSKH",
        "sections": "crm_board_*",
        "admin_needs": "Kanban, phễu, playbook, trợ lý AI CRM, tạo case.",
    },
    {
        "path": "/crm/customers",
        "label": "Khách hàng 360°",
        "sections": "crm_board_customers",
        "admin_needs": "Hồ sơ KH, timeline, issue, hợp đồng.",
    },
    {
        "path": "/crm/hub",
        "label": "Marketing Hub",
        "sections": "crm_hub_*",
        "admin_needs": "Chiến dịch, hợp đồng, nhắc việc gia hạn.",
    },
    {
        "path": "/crm/marketing-plan",
        "label": "Kế hoạch marketing",
        "sections": "crm_mktplan",
        "admin_needs": "Kế hoạch chiến dịch, phân khúc.",
    },
    {
        "path": "/crm/sop",
        "label": "SOP vận hành",
        "sections": "crm_sop_*",
        "admin_needs": "Template SOP, phiên chạy, quá hạn.",
    },
    {
        "path": "/crm/staff",
        "label": "Nhân sự",
        "sections": "crm_staff_*",
        "admin_needs": "Phòng ban, chức vụ, hồ sơ NV, tài khoản portal, ma trận quyền chức vụ.",
    },
    {
        "path": "/crm/kpi",
        "label": "KPI",
        "sections": "crm_kpi_*",
        "admin_needs": "Chỉ tiêu, bản ghi kỳ, cảnh báo, biểu đồ.",
    },
    {
        "path": "/crm/payroll",
        "label": "Chấm công & Lương",
        "sections": "crm_payroll_device, crm_payroll_attendance, crm_payroll_salary",
        "admin_needs": "Máy chấm công, import Excel, tính lương, khóa kỳ, xuất/gửi bảng lương.",
    },
    {
        "path": "/crm/sales",
        "label": "Kinh doanh",
        "sections": "crm_sales_*",
        "admin_needs": "Kế hoạch KD, phễu, deal, đào tạo, báo cáo.",
    },
)

DEFAULT_POSITIONS: tuple[tuple[str, str, str], ...] = (
    ("CSKH-01", "Chăm sóc KH", "Bảng CSKH, KH, trợ lý AI, KPI bản ghi"),
    ("KD-01", "Kinh doanh", "CSKH + Hub + MKT plan + CRM Sales + KPI"),
    ("VH-01", "Vận hành / HR", "SOP, nhân sự, chấm công/lương, trợ lý AI"),
)

ADMIN_MONTHLY_CHECKLIST: tuple[str, ...] = (
    "Chốt chấm công tháng — import máy / đối soát Excel.",
    "Tính lương → duyệt → khóa kỳ → xuất & gửi từng NV (hoặc thông báo xem portal).",
    "Review KPI kỳ: cảnh báo đỏ, họp 1-1 với NV dưới ngưỡng.",
    "Rà soát case quá SLA trên Bảng CSKH; gán lại lead chưa phụ trách.",
    "Hub: nhắc việc hợp đồng sắp hết hạn.",
    "CMS → Phân quyền: user nghỉ việc → tắt login / vô hiệu CMS.",
)

PERMISSION_SETUP_STEPS: tuple[str, ...] = (
    "CRM → Nhân sự: tạo phòng ban, chức vụ, hồ sơ NV (+ Mã PIN nếu chấm công).",
    "Bật **Tài khoản đăng nhập** cho NV cần portal (username + mật khẩu).",
    "CMS → Phân quyền → **Users**: thêm admin (nếu cần), gán **vai trò CMS** + **chức vụ CRM**.",
    "Ma trận **Vai trò**: tick module CMS (landing, chat MKT, permissions_matrix…).",
    "Ma trận **Chức vụ**: tick section CRM (Kanban, lương export, KPI…).",
    "User **đăng xuất / đăng nhập lại** (F5) để gating UI cập nhật.",
    "Một mật khẩu cho mọi nơi — đổi tại `/account/password`.",
)


def format_payroll_export_guide(*, staff_hint: str = "", staff_id: int | None = None) -> str:
    lines = [
        "**Xuất bảng lương cho từng nhân viên**\n",
        "| Bước | Việc cần làm |",
        "|---|---|",
    ]
    for i, step in enumerate(PAYROLL_EXPORT_STEPS, 1):
        lines.append(f"| {i} | {step} |")
    lines.append("\n**Trước khi gửi:**")
    for item in PAYROLL_SEND_CHECKLIST:
        lines.append(f"- {item}")
    lines.append(f"\n{PAYROLL_EXPORT_API_HINT}")
    if staff_hint or staff_id:
        lines.append("\n**Lọc nhân viên:**")
        if staff_hint:
            lines.append(f"- Tên/mã: **{staff_hint}**")
        if staff_id:
            lines.append(f"- `staff_id={staff_id}` trên API hoặc chọn trong dropdown xuất file.")
    lines.append(
        "\n**Gửi bảng lương:** PTT xuất file — HR/admin gửi thủ công qua email/Zalo. "
        "NV có thể tự xem tại portal `/crm/payroll` (chỉ dữ liệu của mình)."
    )
    return "\n".join(lines)


def format_admin_overview() -> str:
    lines = [
        "**Quản trị PTT — những gì admin cần biết**\n",
        "### Ba loại đăng nhập",
    ]
    for t in ADMIN_SESSION_TYPES:
        lines.append(f"- **{t['label']}:** {t['detail']}")
    lines.append("\n### Hành động phân quyền (actions)")
    for code, label in CMS_ACTIONS_VI:
        lines.append(f"- `{code}` — {label}")
    lines.append("\n### Trang CRM & việc quản trị")
    lines.append("| Trang | Quản trị cần |")
    lines.append("|---|---|")
    for p in CRM_PAGES_ADMIN:
        lines.append(f"| `{p['path']}` | {p['admin_needs']} |")
    lines.append("\n### Chức vụ mặc định")
    for code, name, scope in DEFAULT_POSITIONS:
        lines.append(f"- **{code}** ({name}): {scope}")
    lines.append("\n### Checklist hàng tháng (HR / vận hành)")
    for item in ADMIN_MONTHLY_CHECKLIST:
        lines.append(f"- [ ] {item}")
    return "\n".join(lines)


def format_permission_guide() -> str:
    lines = ["**Thiết lập phân quyền — quy trình admin**\n"]
    for i, step in enumerate(PERMISSION_SETUP_STEPS, 1):
        lines.append(f"{i}. {step}")
    lines.append(
        "\n**Quy tắc đặc biệt:** Tạo khách hàng cần `crm_board_customers:create` **hoặc** `crm_board_create:create`."
    )
    lines.append(
        "**super_admin / cms_admin** bỏ qua mọi giới hạn section CRM."
    )
    lines.append("Chi tiết: `docs/PHAN_QUYEN_HUONG_DAN.md` · Cấu hình: CMS → tab **Phân quyền**.")
    return "\n".join(lines)
