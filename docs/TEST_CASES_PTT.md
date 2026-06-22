# Bộ Test Case — Hệ thống PTT

> **Phiên bản:** 2026-05 · **Phạm vi:** Toàn hệ thống (Landing, CMS, CRM, Portal)  
> **Excel QA:** [`TEST_CASES_PTT.xlsx`](TEST_CASES_PTT.xlsx) · **Dữ liệu đính kèm:** [`tests/fixtures/test_data/`](../tests/fixtures/test_data/)  
> **Automated tests:** [`tests/test_crm_*.py`](../tests/) — 117+ unit/integration tests

Tài liệu này dùng cho **QA manual**, **UAT staging** và **đối chiếu automated test**. Mỗi test case gồm: ID, luồng, tiền điều kiện, bước, dữ liệu test, kết quả mong muốn.

---

## Mục lục

1. [Cách sử dụng](#1-cách-sử-dụng)
2. [Dữ liệu mẫu chung](#2-dữ-liệu-mẫu-chung)
3. [Đăng nhập & Tài khoản](#3-đăng-nhập--tài-khoản)
4. [Phân quyền CMS & CRM](#4-phân-quyền-cms--crm)
5. [CMS — Nội dung & Marketing](#5-cms--nội-dung--marketing)
6. [Bảng CSKH & Khách hàng](#6-bảng-cskh--khách-hàng)
7. [Quản lý Lead](#7-quản-lý-lead)
8. [Lead theo dự án BĐS & Facebook Webhook](#8-lead-theo-dự-án-bđs--facebook-webhook)
9. [Auto-assign & Scoring](#9-auto-assign--scoring)
10. [Dự án BĐS (RE Projects)](#10-dự-án-bđs-re-projects)
11. [Hub, Kế hoạch MKT, SOP, Kinh doanh](#11-hub-kế-hoạch-mkt-sop-kinh-doanh)
12. [Nhân sự CRM](#12-nhân-sự-crm)
13. [KPI, Chấm công, Báo cáo ngày](#13-kpi-chấm-công-báo-cáo-ngày)
14. [Portal nhân viên](#14-portal-nhân-viên)
15. [Import / Export](#15-import--export)
16. [Phụ lục — Ma trận traceability](#16-phụ-lục--ma-trận-traceability)

---

## 1. Cách sử dụng

| Bước | Hành động |
|------|-----------|
| 1 | Chuẩn bị môi trường staging (`http://127.0.0.1:5050` hoặc `https://pttads.vn`) |
| 2 | Mở **[`TEST_CASES_PTT.xlsx`](TEST_CASES_PTT.xlsx)** — sheet **Test Cases** (cột Trạng thái: Pass/Fail/…) |
| 3 | Import/seed dữ liệu mẫu từ `tests/fixtures/test_data/` (sheet **Tài khoản mẫu**, **Dự án mẫu**) |
| 4 | Chạy smoke P0 trên sheet **Smoke P0**; automated: `python3 scripts/build_test_cases_xlsx.py` để tái xuất Excel |
| 5 | Automated backend: `cd PTT && python3 -m unittest discover -s tests -v` |

**Ký hiệu mức ưu tiên:** P0 = bắt buộc trước release · P1 = quan trọng · P2 = bổ sung

---

## 2. Dữ liệu mẫu chung

### 2.1. Tài khoản

File: [`accounts.json`](../tests/fixtures/test_data/accounts.json)

| Key | Username | Vai trò | Landing sau login |
|-----|----------|---------|-------------------|
| `admin_full` | `admin` | super_admin | `/admin` |
| `admin_cskh` | `cskh_lead` | CSKH-01 | `/crm` |
| `admin_kd` | `kd_manager` | KD-01 | `/crm` |
| `portal_sales_a` | `sales_a` | NV sales (id=1) | `/crm/home` |
| `portal_sales_b` | `sales_b` | NV sales/manager (id=2) | `/crm/home` |
| `portal_outsider` | `outsider` | NV không thuộc dự án | `/crm/home` |

### 2.2. Dự án BĐS mẫu

File: [`re_projects_setup.json`](../tests/fixtures/test_data/re_projects_setup.json)

| Mã | Tên | Webhook slug | Form ID |
|----|-----|--------------|---------|
| `DA-A` | Dự án Alpha Tower | `alpha-tower-fb` | `2814926042203269` |
| `DA-B` | Dự án Beta Residence | `beta-residence-fb` | `form_beta_999888` |

---

## 3. Đăng nhập & Tài khoản

| TC-ID | P | Luồng | Tiền điều kiện | Bước thực hiện | Dữ liệu test | Kết quả mong muốn |
|-------|---|-------|----------------|----------------|--------------|-------------------|
| TC-AUTH-01 | P0 | Đăng nhập admin thành công | User `admin_full` tồn tại | 1. Mở `/admin/login` 2. Nhập username/password 3. Submit | `accounts.json` → `admin_full` | Redirect `/admin` hoặc `?next=`; sidebar admin hiển thị đầy đủ |
| TC-AUTH-02 | P0 | Đăng nhập portal NV | User `portal_sales_a` có portal enabled | 1. `/admin/login` 2. Nhập credentials | `accounts.json` → `portal_sales_a` | Redirect `/crm/home`; nav portal gọn (Lead, KPI, Báo cáo…) |
| TC-AUTH-03 | P0 | Đăng nhập sai mật khẩu | — | 1. Nhập username đúng, password sai | `accounts.json` → `invalid_login` | Thông báo lỗi; không tạo session |
| TC-AUTH-04 | P1 | Một username — một mật khẩu | NV liên kết CMS + portal | 1. Đổi mật khẩu tại `/account/password` 2. Logout 3. Login lại portal | Password mới: `NewPass@2026!` | Cả admin (nếu có) và portal dùng cùng password mới |
| TC-AUTH-05 | P1 | Ưu tiên CMS trước portal | User có cả CMS role và crm_staff | 1. Login với user có 2 loại | User admin có staff_id | Vào giao diện admin, không vào portal |
| TC-AUTH-06 | P2 | Đăng xuất | Đã login | 1. Nhấn Đăng xuất | — | Session hết; redirect login; back button không vào được CRM |

---

## 4. Phân quyền CMS & CRM

File: [`permissions_scenarios.json`](../tests/fixtures/test_data/permissions_scenarios.json)

| TC-ID | P | Luồng | Tiền điều kiện | Bước thực hiện | Dữ liệu test | Kết quả mong muốn |
|-------|---|-------|----------------|----------------|--------------|-------------------|
| TC-PERM-01 | P0 | super_admin toàn quyền | Login `admin_full` | Truy cập `/crm/leads`, `/crm/re-projects`, `/cms` | `admin_full` | Tất cả trang mở; không bị ẩn section |
| TC-PERM-02 | P0 | CSKH không vào Sales | Login `admin_cskh` | Mở sidebar → tìm CRM Kinh doanh | `admin_cskh` | Menu `/crm/sales` ẩn hoặc 403 |
| TC-PERM-03 | P0 | content_editor không CRM | User role `content_editor` | Truy cập trực tiếp `/crm/leads` | `permissions_scenarios` → cms_roles[1] | 403 hoặc redirect; không xem lead |
| TC-PERM-04 | P1 | Ma trận chức vụ CRM | super_admin cấu hình | 1. CMS → Phân quyền → Chức vụ 2. Bỏ tick `view` Leads cho CSKH-01 3. Login CSKH | Position CSKH-01 | Menu Lead ẩn; API GET leads → 403 |
| TC-PERM-05 | P1 | API chặn vượt quyền | User thiếu `delete` | `DELETE /api/crm/leads/1` | `permissions_scenarios` → api_denied | HTTP 403 Forbidden |
| TC-PERM-06 | P2 | Nút UI khóa theo action | User chỉ có `view` | Mở trang có nút Xóa/Tạo | CSKH viewer | Nút disabled/ẩn (`admin_section_gating.js`) |

---

## 5. CMS — Nội dung & Marketing

| TC-ID | P | Luồng | Tiền điều kiện | Bước thực hiện | Dữ liệu test | Kết quả mong muốn |
|-------|---|-------|----------------|----------------|--------------|-------------------|
| TC-CMS-01 | P1 | Tạo tin tức | Quyền content_editor+ | 1. `/admin` → Tin tức 2. Thêm bài 3. Publish | Tiêu đề: `Tin test QA 2026`; slug: `tin-test-qa-2026` | Bài hiện landing `/news/tin-test-qa-2026` |
| TC-CMS-02 | P1 | Cấu hình dịch vụ | Quyền CMS | 1. CMS → Dịch vụ 2. Thêm mục | slug: `dich-vu-test`; tên: `Dịch vụ Test` | Trang `/services/dich-vu-test` hiển thị |
| TC-CMS-03 | P2 | Chat Marketing export | marketing_lead | 1. Chat MKT → hoàn thành 7 bước 2. Export Excel | Campaign: `Q3 Test` | File Excel tải về; có sheet KPI |
| TC-CMS-04 | P2 | Phân quyền ma trận | super_admin | 1. CMS → Phân quyền 2. Sửa tick 3. Lưu | Bật `export` cho marketing_staff | User marketing_staff export được |

---

## 6. Bảng CSKH & Khách hàng

File: [`cskh_cases.json`](../tests/fixtures/test_data/cskh_cases.json)

| TC-ID | P | Luồng | Tiền điều kiện | Bước thực hiện | Dữ liệu test | Kết quả mong muốn |
|-------|---|-------|----------------|----------------|--------------|-------------------|
| TC-CSKH-01 | P0 | Tạo hồ sơ CSKH mới | Admin/KD có quyền create | 1. `/crm` 2. + Tạo hồ sơ 3. Điền form 4. Lưu | `cskh_cases.json` → `case_new` | Case xuất hiện cột **Mới** Kanban |
| TC-CSKH-02 | P0 | Chuyển giai đoạn pipeline | Case TC-CSKH-01 | 1. Kéo thả hoặc đổi status 2. Ghi care report | `stage_transition` | Status = **Đang liên hệ**; timeline có báo cáo |
| TC-CSKH-03 | P1 | Portal chỉ thấy case được gán | Login `portal_sales_a` | 1. `/crm` 2. So sánh với admin | `portal_scope` | NV id=1 thấy case gán; id=3 không thấy |
| TC-CSKH-04 | P1 | Tạo khách hàng 360° | Quyền create customers | 1. `/crm/customers` 2. + Khách mới | `customer`: Công ty ABC, 0281234567 | Khách tìm được theo SĐT; timeline trống |
| TC-CSKH-05 | P2 | Playbook 6 bước | Case đang mở | 1. Mở case 2. Chạy Playbook | — | Checklist 6 bước; tick lưu tiến độ |
| TC-CSKH-06 | P2 | AI trợ lý CSKH | Widget AI bật | 1. Mở `/crm` 2. Hỏi AI gợi ý bước tiếp | "Case MQL nên làm gì tiếp?" | Gợi ý hành động phù hợp giai đoạn |

---

## 7. Quản lý Lead

File: [`leads_manual.json`](../tests/fixtures/test_data/leads_manual.json)

| TC-ID | P | Luồng | Tiền điều kiện | Bước thực hiện | Dữ liệu test | Kết quả mong muốn |
|-------|---|-------|----------------|----------------|--------------|-------------------|
| TC-LEAD-01 | P0 | Tạo lead nhập tay (FR-01) | Quyền create lead | 1. `/crm/leads` 2. + Lead 3. Điền form 4. Lưu | `create_valid` | Lead id=1; status **Mới**; score ≥ 10; activities: Kiểm tra liên hệ, trùng, chấm điểm, phân hạng |
| TC-LEAD-02 | P0 | Chấm điểm & phân hạng (FR-03/04) | — | Tạo lead high score | `create_high_score` | score ≥ 20; level likely **hot** hoặc **vip** |
| TC-LEAD-03 | P0 | Phát hiện trùng SĐT (FR-02) | TC-LEAD-01 đã chạy | 1. Tạo lead thứ 2 cùng SĐT | `duplicate_phone` | `is_duplicate=1`; match_type=phone |
| TC-LEAD-04 | P0 | SĐT không hợp lệ | — | Tạo lead phone=123 | `create_invalid_phone` | Lỗi validation; không tạo bản ghi |
| TC-LEAD-05 | P1 | Email không hợp lệ | — | phone OK, email sai | `create_invalid_email` | Lỗi validation |
| TC-LEAD-06 | P1 | Chuyển trạng thái hợp lệ | Lead status Mới | 1. Mở lead 2. Đổi → Đã liên hệ | `status_transitions[0]` | Chuyển thành công; log status |
| TC-LEAD-07 | P1 | Chuyển trạng thái không hợp lệ | Lead status Mới | Đổi thẳng → Chốt | `status_transitions[1]` | Bị chặn; thông báo lỗi |
| TC-LEAD-08 | P1 | Phân công owner thủ công | Lead chưa owner | 1. Assign → chọn NV | `assign_manual` owner=2 | owner_id=2; assignment log |
| TC-LEAD-09 | P1 | Lọc theo trạng thái/hạng | ≥3 lead mixed | 1. Filter Hot 2. Filter chưa gán | — | Danh sách khớp filter |
| TC-LEAD-10 | P2 | Ghi hoạt động (gọi/email) | Lead tồn tại | 1. Mở lead 2. + Hoạt động loại Gọi | Nội dung: "Đã gọi 5 phút, hẹn gặp" | Activity trong timeline |
| TC-LEAD-11 | P2 | AI Search lead | ≥5 lead | 1. Ô AI Search 2. Gõ query | "lead hot chưa gán owner" | Trả về subset đúng |
| TC-LEAD-12 | P2 | AI Summary | Lead có activities | Mở lead → AI Summary | — | Tóm tắt lịch sử, blocker |
| TC-LEAD-13 | P1 | Convert lead → khách hàng | Lead status Chốt | 1. Nút Chuyển KH 2. Xác nhận | Lead TC-LEAD-01 → Chốt | Bản ghi khách hàng mới; lead linked |
| TC-LEAD-14 | P2 | Cảnh báo SLA | Lead Hot quá 4h chưa liên hệ | 1. Dashboard leads | Lead created_at cũ | Badge/cảnh báo SLA trên UI |

**Automated:** `tests/test_crm_leads.py` → `TestLeadFunctionalRequirements`

---

## 8. Lead theo dự án BĐS & Facebook Webhook

Files: [`re_projects_setup.json`](../tests/fixtures/test_data/re_projects_setup.json), [`facebook_webhook_payloads.json`](../tests/fixtures/test_data/facebook_webhook_payloads.json)

| TC-ID | P | Luồng | Tiền điều kiện | Bước thực hiện | Dữ liệu test | Kết quả mong muốn |
|-------|---|-------|----------------|----------------|--------------|-------------------|
| TC-PROJ-01 | P0 | Tạo lead gắn dự án (Phase 1) | Dự án DA-A tồn tại | 1. Tạo lead 2. Chọn dự án Alpha | `create_valid` + `re_project_code=DA-A` | `re_project_id` = id DA-A; label hiện "Alpha" |
| TC-PROJ-02 | P0 | Lọc lead theo dự án | Lead ở DA-A và DA-B | 1. Filter dự án = Alpha | — | Chỉ lead DA-A |
| TC-PROJ-03 | P0 | Dedup scoped theo dự án (Phase 1) | Cùng SĐT 2 dự án | 1. Tạo lead SĐT X ở DA-A 2. Tạo lead SĐT X ở DA-B | `duplicate_scoped_project` | 2 lead riêng; không flag trùng cross-project |
| TC-PROJ-04 | P0 | Thêm NV vào pool dự án (Phase 2) | Dự án + NV tồn tại | 1. RE Projects → DA-A → Nhân viên Lead 2. Thêm sales_a, bật Nhận lead | `re_projects_setup` → staff | NV trong `crm_re_project_staff`; assign_enabled=1 |
| TC-PROJ-05 | P0 | Auto-assign scoped pool (Phase 2) | Pool có 2 NV sales | 1. Tạo lead DA-A auto-assign ON | Lead mới DA-A | owner_id ∈ {1,2}; round-robin pool `project:DA-A` |
| TC-PROJ-06 | P0 | Cấu hình webhook slug (Phase 3) | Admin RE Projects | 1. Card Lead & Webhook 2. Copy URL 3. Thêm Form ID 4. Lưu | slug=`alpha-tower-fb`, form=`2814926042203269` | URL `/webhooks/facebook/alpha-tower-fb`; verify token hiện |
| TC-PROJ-07 | P0 | Webhook verify GET (Phase 3) | Token đúng | GET webhook + hub params | `facebook_webhook_payloads` → verify_get | HTTP 200; body = challenge |
| TC-PROJ-08 | P0 | Webhook leadgen → lead (Phase 3) | Config + pool OK | 1. POST payload leadgen 2. Mock Graph API | `leadgen_project_slug` | created_count=1; re_project=DA-A; owner trong pool; HTTP 200 ngay |
| TC-PROJ-09 | P1 | Form chưa map (Phase 3) | Form ID lạ | POST webhook form unknown | `leadgen_unmapped_form` | created_count=0; AI search "form facebook chưa map" liệt kê |
| TC-PROJ-10 | P1 | Map field tiếng Việt FB | — | normalize field_data | `field_mapping_vn` | full_name, phone, region map đúng |
| TC-PROJ-11 | P0 | Portal sales chỉ lead mình (Phase 4) | sales_a trong DA-A | 1. Login sales_a 2. `/crm/leads` | Lead A assigned id=1; Lead B assigned id=2 | sales_a chỉ thấy lead owner=1 |
| TC-PROJ-12 | P0 | Portal manager thấy mọi lead dự án (Phase 4) | sales_b role manager DA-A | Login sales_b | Lead DA-A mọi owner | sales_b thấy tất cả lead DA-A |
| TC-PROJ-13 | P0 | Outsider không thấy lead dự án (Phase 4) | outsider không trong pool | Login outsider | Lead DA-A tồn tại | Danh sách lead rỗng |
| TC-PROJ-14 | P0 | KPI RE_LEADS_NEW auto (Phase 4) | KPI metric tồn tại | 1. Tạo 2 lead mới DA-A trong tháng 2. Xem tab KPI dự án | `kpi_payroll_daily` → project_kpi | actual RE_LEADS_NEW = 2 |
| TC-PROJ-15 | P1 | Refresh KPI API (Phase 4) | — | POST `/api/crm/re-projects/{id}/kpis/refresh-leads-new` | period_month=2026-06 | JSON `{updated: true, actual: N}` |
| TC-PROJ-16 | P1 | Thông báo lead mới scoped (Phase 4) | 2 lead 2 dự án | API notifications cho sales_a | E2E: lead DA-A + DA-B | Chỉ notify lead thuộc dự án sales_a |
| TC-PROJ-17 | P2 | Migration Phase 5 dry-run | Script trên VPS | `migrate_project_leads_phase5.py --dry-run` | form=`2814926042203269`, code=`DA-A` | In preview; không ghi DB |
| TC-PROJ-18 | P0 | E2E webhook→assign→portal→KPI | Full setup DA-A | Chạy luồng TC-PROJ-08 → login portal → KPI | E2E phone `0907000001` | Lead gán NV; portal thấy; KPI ≥1; notification |

**Automated:** `tests/test_crm_project_leads.py` → Phase 1–4 + `TestProjectLeadsE2EFlow`

---

## 9. Auto-assign & Scoring

| TC-ID | P | Luồng | Tiền điều kiện | Bước thực hiện | Dữ liệu test | Kết quả mong muốn |
|-------|---|-------|----------------|----------------|--------------|-------------------|
| TC-ASSIGN-01 | P0 | Round-robin global | 2 NV active, config RR | Tạo 4 lead liên tiếp (không dự án) | staff 1, 2 | owner luân phiên 1→2→1→2 |
| TC-ASSIGN-02 | P1 | Skill-based Hot→NV cấp A | Lead Hot, NV A+B | Tạo lead Hot auto-assign | sales_level a vs b | Hot ưu tiên NV cấp A |
| TC-ASSIGN-03 | P1 | Region/Product match | notes NV "q.7 căn hộ" | Lead region Q.7, product căn hộ | FB optimize item | Assign NV có notes khớp |
| TC-ASSIGN-04 | P2 | Daily cap | cap=2/NGÀY/NV | Tạo 5 lead cùng ngày | config daily_cap=2 | NV không vượt cap |
| TC-ASSIGN-05 | P1 | Hybrid multi-strategy | config hybrid | Tạo lead mixed | skill + RR | Assign theo thứ tự ưu tiên config |
| TC-SCORE-01 | P1 | Rubric D1–D6 | Default rubric | Score lead đủ/trống field | `test_fr03` data | score thấp < score cao |
| TC-SCORE-02 | P2 | Custom keyword rule | Admin cấu hình keyword +10 | Lead need chứa keyword | keyword="CRM" | score cộng thêm |

**Automated:** `tests/test_crm_lead_auto_assign.py`, `tests/test_crm_lead_scoring_rubric.py`

---

## 10. Dự án BĐS (RE Projects)

| TC-ID | P | Luồng | Tiền điều kiện | Bước thực hiện | Dữ liệu test | Kết quả mong muốn |
|-------|---|-------|----------------|----------------|--------------|-------------------|
| TC-RE-01 | P0 | Tạo dự án mới | Quyền RE Projects | 1. `/crm/re-projects` 2. + Dự án 3. Lưu | code=`DA-TEST`, name=`Dự án Test QA` | Dự án xuất hiện list; workflow 8 bước 0% |
| TC-RE-02 | P1 | Quy trình 8 bước | Dự án TC-RE-01 | Điền từng tab kế hoạch | Chiến lược, Tài chính… | Thanh workflow tăng %; bước tiếp theo cập nhật |
| TC-RE-03 | P1 | KPI dự án — thêm chỉ tiêu | Tab KPI | + KPI; gán NV; target | RE_LEADS_NEW target=50 | KPI row lưu; sync nút Đẩy/Kéo |
| TC-RE-04 | P2 | Xuất báo cáo Excel | Dự án có dữ liệu | Header → Xuất báo cáo ▾ → Tổng hợp | — | File Excel tải về |
| TC-RE-05 | P1 | Master data tồn kho | Tab Sản phẩm | Thêm căn/lô | Mã căn A-01-05, diện tích 75m² | Tồn kho hiển thị |

**Automated:** `tests/test_crm_re_projects.py`

---

## 11. Hub, Kế hoạch MKT, SOP, Kinh doanh

| TC-ID | P | Luồng | Tiền điều kiện | Bước | Dữ liệu test | Kết quả mong muốn |
|-------|---|-------|----------------|------|--------------|-------------------|
| TC-HUB-01 | P1 | Tạo chiến dịch Hub | KD-01 | `/crm/hub` → Chiến dịch → + | Tên: `Campaign Q3 Test` | Campaign list; reminder có thể gắn |
| TC-HUB-02 | P2 | Nhắc việc follow-up | Case/campaign tồn tại | Hub → Nhắc việc → + | remind_at: ngày mai | Reminder pending; notify NV |
| TC-MKT-01 | P2 | Kế hoạch MKT segment KHTN | — | `/crm/marketing-plan/segment/khtn` → + kế hoạch | Năm 2026 Q3 | Pipeline 5 bước KHTN |
| TC-SOP-01 | P2 | Chạy SOP | Mẫu SOP có sẵn | SOP → Chạy → giao task | Template: Onboarding KH | Task queue; theo dõi hoàn thành |
| TC-SALES-01 | P1 | Log giao dịch | KD-01 | `/crm/sales` → Giao dịch → + | Deal 500M, stage negotiation | Deal trong pipeline |
| TC-SALES-02 | P2 | Báo cáo sales tháng | Có deals | Sales → Báo cáo | Tháng 06/2026 | Chart/bảng doanh số |

---

## 12. Nhân sự CRM

| TC-ID | P | Luồng | Tiền điều kiện | Bước | Dữ liệu test | Kết quả mong muốn |
|-------|---|-------|----------------|------|--------------|-------------------|
| TC-STAFF-01 | P0 | Thêm NV mới | Admin nhân sự | `/crm/staff` → + NV | Tên: `Test NV QA`; mã: `TNV-01`; cấp B | NV trong danh sách |
| TC-STAFF-02 | P0 | Bật portal login | NV TC-STAFF-01 | Bật đăng nhập; username/password | username: `test_nv_qa` | Login portal thành công |
| TC-STAFF-03 | P1 | Ghi notes skill auto-assign | — | notes: `q.7 căn hộ facebook` | — | Auto-assign skill-based khớp |
| TC-STAFF-04 | P2 | Import roster CSV | File mẫu | Staff → Import | CSV 3 dòng NV | 3 NV mới hoặc update |
| TC-STAFF-05 | P1 | Competency scoring | Module năng lực | Chấm competency NV | score 1–5 các tiềm năng | Tổng điểm lưu |

**Automated:** `tests/test_crm_staff_levels.py`, `tests/test_crm_staff_competency.py`

---

## 13. KPI, Chấm công, Báo cáo ngày

File: [`kpi_payroll_daily.json`](../tests/fixtures/test_data/kpi_payroll_daily.json)

| TC-ID | P | Luồng | Tiền điều kiện | Bước | Dữ liệu test | Kết quả mong muốn |
|-------|---|-------|----------------|------|--------------|-------------------|
| TC-KPI-01 | P1 | Admin nhập KPI NV | Metric định nghĩa | `/crm/kpi` → chọn NV → nhập actual | `staff_kpi` LEADS_ASSIGNED actual=12 | Biểu đồ achievement ~40% |
| TC-KPI-02 | P1 | Portal xem KPI tháng | Login portal | `/crm/kpi` | sales_a, tháng hiện tại | Chỉ KPI của mình |
| TC-KPI-03 | P0 | Sync KPI dự án ↔ NV | RE Projects KPI | Nút Đẩy sang KPI NV | RE_LEADS_NEW actual=2 | KPI NV cập nhật |
| TC-ATT-01 | P1 | Import chấm công XLSX | File công mẫu | Payroll → Import | `attendance_row` | Bảng công ngày 15/06 |
| TC-ATT-02 | P2 | Tính lương tháng | Công đủ tháng | Tính lương 06/2026 | `payroll_period` | Bảng lương net_pay; có thể Khóa |
| TC-RPT-01 | P0 | NV gửi báo cáo ngày | Login portal | `/crm/daily-reports` → điền → Gửi | `daily_report` | Báo cáo status submitted |
| TC-RPT-02 | P1 | Admin review báo cáo | TC-RPT-01 | Lọc NV + ngày | sales_a, 2026-06-15 | Thấy nội dung báo cáo |

---

## 14. Portal nhân viên

| TC-ID | P | Luồng | Tiền điều kiện | Bước | Dữ liệu test | Kết quả mong muốn |
|-------|---|-------|----------------|------|--------------|-------------------|
| TC-PORTAL-01 | P0 | Trang chủ portal | Login NV | `/crm/home` | sales_a | Widget tóm tắt: lead, KPI, báo cáo |
| TC-PORTAL-02 | P0 | Tạo lead bắt buộc chọn dự án | sales_a trong DA-A | Lead → + → thử lưu không chọn dự án | — | Validation bắt buộc re_project |
| TC-PORTAL-03 | P0 | Không cấu hình global lead | Portal sales | Tìm nút Cấu hình Lead | sales_a | Nút ẩn/khóa |
| TC-PORTAL-04 | P1 | Không xóa lead | Portal sales | Thử xóa lead | — | Không có action hoặc 403 |
| TC-PORTAL-05 | P1 | Toast lead mới từ webhook | Webhook tạo lead assign sales_a | Mở `/crm/leads` (polling) | E2E flow | Toast/badge lead mới |

---

## 15. Import / Export

File: [`leads_import_sample.csv`](../tests/fixtures/test_data/leads_import_sample.csv)

| TC-ID | P | Luồng | Tiền điều kiện | Bước | Dữ liệu test | Kết quả mong muốn |
|-------|---|-------|----------------|------|--------------|-------------------|
| TC-IO-01 | P0 | Import lead CSV | Quyền import | Leads → Import → chọn file | `leads_import_sample.csv` | 3 lead mới (dòng 4 trùng → flag/link theo policy) |
| TC-IO-02 | P1 | Export lead XLSX | Có lead filter | Lọc DA-A → Export XLSX | — | File .xlsx đúng số dòng filter |
| TC-IO-03 | P2 | Export lead PDF | — | Export PDF | — | PDF tải về, có cột chính |
| TC-IO-04 | P2 | Export KPI XLSX | Admin KPI | KPI → Export | Tháng 06/2026 | Excel KPI all NV |

---

## 16. Phụ lục — Ma trận traceability

### 16.1. Test case ↔ Automated test

| TC-ID | Automated test class / method |
|-------|------------------------------|
| TC-LEAD-01 | `TestLeadFunctionalRequirements.test_fr01_create_lead_manual` |
| TC-LEAD-02 | `test_fr03_lead_scoring`, `test_fr04_classify_default_tiers` |
| TC-LEAD-03 | `test_fr02_duplicate_detection` |
| TC-PROJ-01–03 | `TestProjectLeadsPhase1` |
| TC-PROJ-04–05 | `TestProjectLeadsPhase2` |
| TC-PROJ-06–10 | `TestProjectLeadsPhase3` |
| TC-PROJ-11–16 | `TestProjectLeadsPhase4` |
| TC-PROJ-18 | `TestProjectLeadsE2EFlow.test_full_webhook_to_portal_and_kpi` |
| TC-ASSIGN-01–05 | `tests/test_crm_lead_auto_assign.py` |
| TC-PROJ-09 (FB) | `tests/test_crm_facebook_leads.py` |

### 16.2. Checklist smoke P0 (trước mỗi release)

```
[ ] TC-AUTH-01, TC-AUTH-02
[ ] TC-LEAD-01, TC-LEAD-03
[ ] TC-PROJ-01, TC-PROJ-05, TC-PROJ-08
[ ] TC-PROJ-11, TC-PROJ-13, TC-PROJ-14
[ ] TC-PROJ-18 (E2E)
[ ] TC-PORTAL-01, TC-PORTAL-02
[ ] python3 -m unittest discover -s tests -v  → 117+ pass
```

### 16.3. File dữ liệu đính kèm

| File | Mục đích |
|------|----------|
| [`accounts.json`](../tests/fixtures/test_data/accounts.json) | Tài khoản admin + portal |
| [`re_projects_setup.json`](../tests/fixtures/test_data/re_projects_setup.json) | Dự án, webhook, pool NV |
| [`leads_manual.json`](../tests/fixtures/test_data/leads_manual.json) | Tạo/sửa lead, dedup, status |
| [`leads_import_sample.csv`](../tests/fixtures/test_data/leads_import_sample.csv) | Import CSV 4 dòng |
| [`facebook_webhook_payloads.json`](../tests/fixtures/test_data/facebook_webhook_payloads.json) | Webhook verify + leadgen |
| [`cskh_cases.json`](../tests/fixtures/test_data/cskh_cases.json) | Kanban CSKH |
| [`kpi_payroll_daily.json`](../tests/fixtures/test_data/kpi_payroll_daily.json) | KPI, công, báo cáo ngày |
| [`permissions_scenarios.json`](../tests/fixtures/test_data/permissions_scenarios.json) | Ma trận phân quyền |
| [`TEST_CASES_PTT.xlsx`](TEST_CASES_PTT.xlsx) | Excel 6 sheet — tracking QA (Pass/Fail/Tester) |
| [`scripts/build_test_cases_xlsx.py`](../scripts/build_test_cases_xlsx.py) | Tái sinh Excel sau khi sửa registry CSV |

### 16.4. Chạy probe webhook (staging/VPS)

```bash
cd /var/www/ptt
python3 scripts/ptt_fb_webhook_probe.py
python3 scripts/ptt_fb_diagnose.py
```

---

*Tài liệu bổ sung: [`HUONG_DAN_SU_DUNG_PTT.md`](HUONG_DAN_SU_DUNG_PTT.md) · [`PHAN_QUYEN_HUONG_DAN.md`](PHAN_QUYEN_HUONG_DAN.md)*
