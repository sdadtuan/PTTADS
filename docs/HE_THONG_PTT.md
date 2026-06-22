# Tài liệu hệ thống PTT Advertising

> **Cập nhật:** 2026-05 · Flask + SQLite · Local port **5050** · Production **https://pttads.vn**

---

## Bộ tài liệu chính thức

| Tài liệu | Mục đích | Đối tượng |
|----------|----------|-----------|
| **[`SPEC_HE_THONG_PTT.md`](SPEC_HE_THONG_PTT.md)** | **Đặc tả hệ thống đầy đủ** — functional + technical + API + data + deploy | Dev, PM, QA, kiến trúc |
| [`SPEC_UI_UX_PTT.md`](SPEC_UI_UX_PTT.md) | Spec UI/UX, design system, screen inventory | Design, Frontend |
| [`HUONG_DAN_SU_DUNG_PTT.md`](HUONG_DAN_SU_DUNG_PTT.md) | Hướng dẫn sử dụng từng module | Admin, CSKH, Sales, MKT |
| [`PHAN_QUYEN_HUONG_DAN.md`](PHAN_QUYEN_HUONG_DAN.md) | Quy trình gán quyền, onboarding | Quản trị hệ thống |
| [`TEST_CASES_PTT.md`](TEST_CASES_PTT.md) | Test cases UAT + traceability | QA |

> **Roadmap automation/AI:** [`SPEC_HE_THONG_PTT.md` §13](SPEC_HE_THONG_PTT.md#13-roadmap--quy-trình-cần-hoàn-thiện--nâng-cấp-automationai)

> **Bắt đầu tại:** [`SPEC_HE_THONG_PTT.md`](SPEC_HE_THONG_PTT.md) — tài liệu master mô tả toàn bộ hệ thống (304 routes, 50+ bảng DB, leads, RE projects, Facebook, KPI, payroll…).

---

## Tóm tắt nhanh

### Ba lớp người dùng

| Lớp | Đăng nhập | Phạm vi |
|-----|-----------|---------|
| **Khách công khai** | Không | Landing, dự án, tin, dịch vụ, tuyển dụng |
| **Quản trị (Admin)** | `/admin/login` | CMS, Admin, CRM (theo vai trò + chức vụ) |
| **NV portal** | Cùng trang login | CRM giới hạn: lead/case được gán, KPI, chấm công |

### Stack

- **Backend:** Python 3, Flask 3, SQLite (`PTT/data/`)
- **Frontend:** Jinja2, Vanilla JS, CSS
- **Auth:** Session `ptt_session`, PBKDF2-SHA256, login thống nhất (`unified_auth.py`)
- **Deploy:** Gunicorn + systemd `ptt.service` (port **8002** trên VPS)

### Module CRM chính

| Module | Route | File |
|--------|-------|------|
| Bảng CSKH | `/crm` | `crm_sales_pipeline.py`, `crm_care.py` |
| Khách hàng 360° | `/crm/customers` | `crm_customer_360.py` |
| Quản lý Lead | `/crm/leads` | `crm_lead_store.py`, `crm_lead_care_pipeline.py` |
| Hub MKT | `/crm/hub` | `crm_sales_hub.py` |
| Kế hoạch MKT | `/crm/marketing-plan` | `marketing_execution.py` |
| SOP | `/crm/sop` | `crm_sop_seed.py` |
| Kinh doanh | `/crm/sales` | `crm_sales_hub.py` |
| Dự án BĐS | `/crm/re-projects` | `crm_re_projects.py` (+ price, accounting, webhooks) — [§4.5 sequence diagrams](SPEC_HE_THONG_PTT.md#45-re-projects--sequence-diagrams-chi-tiết) |
| Nhân sự | `/crm/staff` | `crm_staff_auth.py` |
| KPI | `/crm/kpi` | KPI schema trong `app.py` |
| Chấm công & lương | `/crm/payroll` | `crm_payroll_engine.py` |
| BC công việc ngày | `/crm/daily-reports` | `crm_daily_work_report.py` |
| Portal NV | `/crm/home` | `crm_staff_dashboard.py` |

### Phân quyền (2 lớp)

1. **Vai trò CMS** (`cms_permissions.py`) — module Website/CMS
2. **Chức vụ CRM** (`admin_page_permissions.py`) — 44 section + UI buttons

Staff portal: **allowlist cố định** (`crm_staff_auth.py`) + scope dữ liệu theo assign.

### Chạy nhanh

```bash
cd PTT && bash restart_flask.sh          # http://127.0.0.1:5050
python3 scripts/build_ptt_assets.py      # minify static
python3 -m unittest discover -s tests -v
```

**Dev login:** `admin` / `changeme`

---

*File này là **mục lục tóm tắt**. Chi tiết đầy đủ nằm trong [`SPEC_HE_THONG_PTT.md`](SPEC_HE_THONG_PTT.md).*
