# Hướng dẫn sử dụng hệ thống PTT Advertising

> **Phiên bản tài liệu:** 2026-05 · **Hệ thống:** PTT Website Suite (Landing + CMS + CRM)  
> **URL production:** `https://pttads.vn` · **Đăng nhập:** `/admin/login`

Tài liệu này hướng dẫn **toàn bộ** hệ thống PTT cho quản trị viên, marketing, kinh doanh, CSKH và nhân viên portal. Một file — đọc theo mục lục hoặc tra cứu nhanh ở Phụ lục.

---

## Mục lục

1. [Giới thiệu hệ thống](#1-giới-thiệu-hệ-thống)
2. [Đăng nhập & tài khoản](#2-đăng-nhập--tài-khoản)
3. [Phân quyền](#3-phân-quyền)
4. [Trang công khai (Landing)](#4-trang-công-khai-landing)
5. [Admin Dashboard](#5-admin-dashboard)
6. [CMS — Quản lý nội dung & Marketing](#6-cms--quản-lý-nội-dung--marketing)
7. [CRM — Tổng quan](#7-crm--tổng-quan)
8. [Bảng CSKH & Khách hàng](#8-bảng-cskh--khách-hàng)
9. [Quản lý Lead](#9-quản-lý-lead)
10. [Lead theo dự án BĐS & Facebook Webhook](#10-lead-theo-dự-án-bđs--facebook-webhook)
11. [Hub, Kế hoạch Marketing & SOP](#11-hub-kế-hoạch-marketing--sop)
12. [CRM Kinh doanh](#12-crm-kinh-doanh)
13. [Dự án BĐS (RE Projects)](#13-dự-án-bđs-re-projects)
14. [Nhân sự CRM](#14-nhân-sự-crm)
15. [KPI nhân viên](#15-kpi-nhân-viên)
16. [Chấm công & Lương](#16-chấm-công--lương)
17. [Báo cáo công việc ngày](#17-báo-cáo-công-việc-ngày)
18. [Portal nhân viên](#18-portal-nhân-viên)
19. [Xuất / Nhập dữ liệu](#19-xuất--nhập-dữ-liệu)
20. [Phụ lục — Tra cứu nhanh & Xử lý sự cố](#20-phụ-lục--tra-cứu-nhanh--xử-lý-sự-cố)

---

## 1. Giới thiệu hệ thống

PTT là nền tảng **website công ty + quản trị nội dung + CRM nội bộ** trong một ứng dụng duy nhất.

| Thành phần | Mô tả ngắn |
|------------|------------|
| **Landing** | Trang web công khai: dịch vụ, dự án portfolio, tin tức, tuyển dụng, form liên hệ |
| **Admin** | Quản lý dự án portfolio & tin tức hiển thị trên landing |
| **CMS** | Cài đặt thương hiệu, menu dịch vụ, chat marketing AI, phân quyền |
| **CRM** | Chăm sóc khách hàng, lead, kinh doanh, dự án BĐS, nhân sự, KPI, lương |

### Ba loại người dùng

| Loại | Đăng nhập | Giao diện | Phạm vi |
|------|-----------|-----------|---------|
| **Khách website** | Không cần | Trang công khai | Xem nội dung, gửi liên hệ, ứng tuyển |
| **Quản trị viên** | `/admin/login` | Sidebar đầy đủ | CMS + CRM theo vai trò & chức vụ |
| **Nhân viên portal** | Cùng `/admin/login` | Thanh nav gọn | Lead/case được gán, KPI, báo cáo ngày, chấm công |

---

## 2. Đăng nhập & tài khoản

### 2.1. Đăng nhập

1. Mở trình duyệt → truy cập **`https://pttads.vn/admin/login`** (local: `http://127.0.0.1:5050/admin/login`).
2. Nhập **Tên đăng nhập** và **Mật khẩu**.
3. Nhấn **Đăng nhập**.

**Sau khi đăng nhập:**

| Loại tài khoản | Chuyển đến |
|----------------|------------|
| Admin / CMS | `/admin` hoặc trang `?next=` (nếu có) |
| Nhân viên portal | `/crm/home` — Trang chủ portal |

### 2.2. Một username — một mật khẩu

- Cùng username dùng chung cho CMS admin và portal nhân viên (nếu được liên kết).
- Đổi mật khẩu tại **`/account/password`** → áp dụng mọi nơi.
- Thứ tự ưu tiên khi login: **CMS admin trước** → nếu không có thì **portal nhân viên**.

### 2.3. Đăng xuất

- Nhấn **Đăng xuất** trên thanh menu (admin hoặc portal).
- Hoặc đóng trình duyệt (phiên cookie ~14 ngày).

### 2.4. Tạo tài khoản (quản trị viên)

**Tài khoản admin CMS:**

1. Vào **CMS** → tab **Phân quyền**.
2. Mục **Quản trị viên CMS** → **Thêm user**.
3. Chọn **Vai trò CMS** và (tuỳ chọn) **Chức vụ CRM**.
4. Lưu — gửi username/mật khẩu cho người dùng.

**Tài khoản portal nhân viên:**

1. Vào **CRM → Nhân sự** (`/crm/staff`).
2. Thêm hoặc sửa nhân viên → bật **Cho phép đăng nhập**.
3. Đặt **Username** và **Mật khẩu** → Lưu.

---

## 3. Phân quyền

### 3.1. Hai lớp phân quyền (admin)

| Lớp | Kiểm soát | Cấu hình tại |
|-----|-----------|--------------|
| **Vai trò CMS** | Trang `/cms`, `/admin` | CMS → **Phân quyền** → ma trận **Vai trò** |
| **Chức vụ CRM** | Từng module trong CRM | CMS → **Phân quyền** → ma trận **Chức vụ** |

> `super_admin` và `cms_admin` có **toàn quyền** — bỏ qua giới hạn section.

### 3.2. Hành động (Actions)

| Mã | Ý nghĩa | Ví dụ |
|----|---------|-------|
| `view` | Xem | Mở trang, đọc danh sách |
| `edit` | Sửa | Cập nhật bản ghi |
| `create` | Tạo | Thêm lead, case, chiến dịch |
| `delete` | Xóa | Xóa bản ghi |
| `export` | Xuất file | Excel, PDF, CSV |
| `configure` | Cấu hình | Scoring, webhook, ma trận quyền |

Nút và form bị ẩn/khóa khi thiếu quyền. API backend cũng kiểm tra — không thể vượt quyền bằng cách gọi URL trực tiếp.

### 3.3. Vai trò CMS mặc định

| Mã | Tên | Phạm vi chính |
|----|-----|---------------|
| `super_admin` | Quản trị hệ thống | Toàn quyền |
| `cms_admin` | Quản trị CMS | Full CMS + CRM |
| `content_editor` | Biên tập | Landing, dịch vụ, dự án, tin |
| `marketing_lead` | Trưởng MKT | Chat AI, export Excel, campaign kit |
| `marketing_staff` | NV Marketing | Chat + export |
| `viewer` | Chỉ xem | Đọc CMS, không sửa |

### 3.4. Chức vụ CRM mặc định

| Mã | Tên | Phạm vi chính |
|----|-----|---------------|
| `CSKH-01` | Chăm sóc KH | Bảng CSKH, khách hàng, lead (xem/sửa), báo cáo ngày |
| `KD-01` | Kinh doanh | CSKH + Hub + MKT plan + **Sales** + **Dự án BĐS** + lead (cấu hình/xóa) |
| `VH-01` | Vận hành / HR | SOP, nhân sự, chấm công, lương |

---

## 4. Trang công khai (Landing)

**Không cần đăng nhập.**

| Trang | URL | Nội dung |
|-------|-----|----------|
| Trang chủ | `/` | Hero, dịch vụ, dự án nổi bật, liên hệ |
| Chi tiết dự án | `/du-an/<id>` | Portfolio dự án đã triển khai |
| Tin tức | `/tin-tuc/<id>` | Bài viết |
| Dịch vụ | `/services/<slug>` | Trang dịch vụ chi tiết |
| Tuyển dụng | `/career` | Danh sách vị trí |
| Chính sách | `/chinh-sach-bao-mat` | Privacy policy |

**Form liên hệ / tư vấn** trên landing có thể tạo lead hoặc case trong CRM (tuỳ cấu hình ingest).

**Quản lý nội dung landing:** xem mục [CMS](#6-cms--quản-lý-nội-dung--marketing) và [Admin Dashboard](#5-admin-dashboard).

---

## 5. Admin Dashboard

**URL:** `/admin`

| Mục | Chức năng |
|-----|-----------|
| **Dự án portfolio** | CRUD dự án hiển thị trên landing (`/du-an/...`) |
| **Tin tức** | CRUD bài tin tức |
| **Kênh CRM** | Danh sách kênh lead dùng trên Bảng CSKH |

### Hướng dẫn nhanh — Thêm tin tức

1. Đăng nhập admin → `/admin`.
2. Chọn tab **Tin tức** → **Thêm tin**.
3. Nhập tiêu đề, nội dung, ảnh → **Lưu**.
4. Kiểm tra trên landing: `/tin-tuc/<id>`.

---

## 6. CMS — Quản lý nội dung & Marketing

**URL:** `/cms`

### 6.1. Các tab chính

| Tab | Mục đích |
|-----|----------|
| **Cài đặt trang** | Logo, hero, thông tin liên hệ, footer, legal |
| **Dịch vụ** | Danh mục & trang dịch vụ (`/services/...`) |
| **Chat Marketing** | Chatbox AI, chiến lược marketing, export kế hoạch |
| **Phân quyền** | Vai trò CMS, chức vụ CRM, tài khoản admin |

### 6.2. Cài đặt trang (Landing settings)

1. Vào `/cms` → **Cài đặt trang**.
2. Cập nhật: tên công ty, slogan, hotline, email, địa chỉ, mạng xã hội.
3. **Lưu** → refresh landing để kiểm tra.

### 6.3. Dịch vụ

1. Tab **Dịch vụ** → thêm **Danh mục** (nếu cần).
2. Thêm **Mục dịch vụ**: slug, mô tả, icon, nội dung chi tiết.
3. Trang công khai: `/services/<slug>`.

### 6.4. Chat Marketing AI

1. Tab **Chat Marketing** → cấu hình chatbox (màu, vị trí, lời chào).
2. Bắt đầu phiên chat → trả lời 7 bước chiến lược (AI hỗ trợ).
3. **Xuất:** Markdown, HTML, JSON hoặc Excel (kế hoạch tuần, đa kênh, KPI).
4. **Campaign kit:** tải file KHMKT + KPI mẫu.

### 6.5. Phân quyền

1. Tab **Phân quyền**.
2. **Ma trận Vai trò** — tick quyền từng module CMS.
3. **Ma trận Chức vụ** — tick quyền từng section CRM.
4. **Quản trị viên** — thêm/sửa user, gán vai trò + chức vụ.

---

## 7. CRM — Tổng quan

**Menu CRM** (sidebar admin) gồm:

| # | Module | URL | Ai dùng |
|---|--------|-----|---------|
| 1 | Bảng CSKH | `/crm` | Admin + Staff |
| 2 | Khách hàng | `/crm/customers` | Admin + Staff (hạn chế) |
| 3 | Quản lý Lead | `/crm/leads` | Admin + Staff |
| 4 | Hub MKT & HĐ | `/crm/hub` | Admin |
| 5 | Kế hoạch MKT | `/crm/marketing-plan` | Admin |
| 6 | Quy trình SOP | `/crm/sop` | Admin |
| 7 | CRM Kinh doanh | `/crm/sales` | Admin |
| 8 | Dự án BĐS | `/crm/re-projects` | Admin |
| 9 | Nhân sự | `/crm/staff` | Admin |
| 10 | Báo cáo ngày | `/crm/daily-reports` | Admin + Staff |
| 11 | KPI | `/crm/kpi` | Admin + Staff |
| 12 | Chấm công & Lương | `/crm/payroll` | Admin + Staff |

**Trợ lý AI CRM** (widget) có trên Bảng CSKH — gợi ý hành động, playbook.

---

## 8. Bảng CSKH & Khách hàng

### 8.1. Bảng CSKH (`/crm`)

**Mục đích:** Quản lý hồ sơ chăm sóc khách hàng theo Kanban + phễu.

**Pipeline (7 giai đoạn):** Mới → Đang liên hệ → MQL → SQL → Báo giá → Chốt / Mất

#### Quy trình — Admin

1. Mở `/crm` → xem **phễu** và thống kê.
2. **Tạo hồ sơ mới** (+): chọn/tạo khách hàng, kênh, mô tả nhu cầu.
3. Kéo thả hoặc cập nhật **trạng thái** trên Kanban.
4. Mở hồ sơ → ghi **sự kiện**, **báo cáo CSKH** (care report).
5. Dùng **Playbook 6 bước** để theo quy trình chuẩn.
6. Hỏi **Trợ lý AI** khi cần gợi ý bước tiếp theo.

#### Quy trình — Nhân viên portal

1. Mở `/crm` từ nav portal.
2. Chỉ thấy hồ sơ **được gán cho mình**, chưa kết thúc.
3. Cập nhật trạng thái, ghi báo cáo CSKH.
4. **Không** tạo hồ sơ mới (trừ khi được cấp quyền create).

### 8.2. Khách hàng (`/crm/customers`)

**Mục đích:** Hồ sơ khách hàng 360° — quan hệ, mua hàng, sự cố, timeline.

1. Tìm khách theo tên/SĐT/email.
2. Mở hồ sơ → xem timeline case & chăm sóc.
3. Thêm quan hệ (người liên hệ), lịch sử mua, ticket hỗ trợ.
4. Tạo khách mới cần quyền **create** trên section Khách hàng.

---

## 9. Quản lý Lead

**URL:** `/crm/leads`

### 9.1. Tổng quan

Module quản lý **lead đa nguồn**: website, Facebook, Zalo, Google Ads, giới thiệu, import, nhập tay.

**Tính năng chính:**

- Dashboard thống kê (theo trạng thái, nguồn, hạng, SLA)
- Lọc: trạng thái, hạng (Hot/Warm/Cold), nguồn, **dự án BĐS**, owner
- Tạo/sửa lead, ghi hoạt động (gọi, email, meeting…)
- Chấm điểm & phân hạng tự động
- Phân công owner (thủ công hoặc auto-assign)
- Phát hiện trùng SĐT/email → gộp lead
- Import CSV, Export XLSX/PDF
- AI: tìm kiếm, tóm tắt, gợi ý, phân loại
- Chuyển lead **Chốt** → khách hàng
- Cấu hình scoring, tier, chiến lược phân công, Facebook

### 9.2. Trạng thái lead

| Trạng thái | Ý nghĩa |
|------------|---------|
| Mới | Vừa tạo, chưa liên hệ |
| Chờ làm sạch | Thiếu SĐT/email hoặc thông tin |
| Đã liên hệ | Đã gọi/lời nhắn lần đầu |
| Qualified | Đủ điều kiện chăm sóc sâu |
| Hot / Warm / Cold | Phân hạng theo điểm |
| Đã gửi báo giá | Đang báo giá |
| Đang đàm phán | Negotiation |
| Chốt | Won |
| Mất | Lost |
| Nuôi dưỡng | Nurture dài hạn |

### 9.3. Quy trình hàng ngày — Admin / KD

1. Mở `/crm/leads` → xem **cảnh báo SLA** (lead quá hạn).
2. Lọc **Hot** hoặc **chưa gán owner** → xử lý ưu tiên.
3. Mở lead → **Gọi lần đầu** trong 4h (Hot) / 24h (Warm).
4. Ghi **hoạt động** sau mỗi lần liên hệ.
5. Cập nhật **trạng thái** theo tiến độ.
6. Lead **Chốt** → **Chuyển khách hàng** (Convert).
7. Cuối ngày: export báo cáo hoặc dùng AI tóm tắt.

### 9.4. Quy trình — Nhân viên portal

1. Vào **Lead của tôi** (`/crm/leads`).
2. Chỉ thấy lead thuộc **dự án mình tham gia**:
   - **Sales:** lead được gán cho mình.
   - **Manager/Viewer dự án:** mọi lead trong dự án.
3. Cập nhật trạng thái, ghi hoạt động.
4. Tạo lead mới → **bắt buộc chọn dự án** mình tham gia.
5. Không có quyền: cấu hình global, xóa lead, phân công lại owner.

### 9.5. Phân công tự động (Auto-assign)

Cấu hình tại **Cấu hình Lead** (drawer trên trang leads, cần quyền `configure`):

| Chiến lược | Mô tả |
|------------|-------|
| Round-robin | Luân phiên NV |
| Skill-based | Theo hạng lead ↔ cấp NV |
| Region/Product | Theo khu vực / sản phẩm quan tâm |
| Performance | Ưu tiên NV có tỉ lệ chốt cao |
| Hybrid | Kết hợp nhiều chiến lược |

Khi lead gắn **dự án BĐS**, auto-assign chỉ chọn NV trong **pool dự án** (`crm_re_project_staff`).

### 9.6. Import / Export lead

**Import CSV:**

1. Chuẩn bị file CSV (cột: họ tên, SĐT, email, nguồn, nhu cầu…).
2. Trang leads → **Import** → chọn file → xác nhận.
3. Hệ thống tạo lead + auto-assign (nếu bật).

**Export:**

1. Lọc danh sách cần xuất.
2. **Xuất** → chọn **XLSX** hoặc **PDF**.

### 9.7. AI trên Lead

| Chức năng | Cách dùng | Ví dụ câu hỏi |
|-----------|-----------|---------------|
| **Tìm kiếm** | Ô AI Search | "lead quá hạn SLA", "lead hot", "lead chưa gán owner" |
| **Tóm tắt** | Mở lead → AI Summary | Tóm tắt lịch sử, blocker |
| **Gợi ý** | AI Recommend | Bước tiếp theo, NV nên phân công |
| **Phân loại** | AI Classify | Gợi ý Hot/Warm/Cold |

Câu hỏi đặc biệt (Phase 3+): *"form facebook chưa map"* → liệt kê Form ID pending chưa gán dự án.

### 9.8. Cấu hình Lead (Admin)

Mở drawer **Cấu hình** trên `/crm/leads`:

| Mục | Nội dung |
|-----|----------|
| **Chấm điểm** | Rubric D1–D6, rule legacy |
| **Phân hạng** | Ngưỡng Hot/Warm/Cold/VIP |
| **Phân công** | Bật/tắt auto-assign, chọn chiến lược |
| **Trùng lặp** | Policy: reject / link / allow |
| **Facebook global** | Page ID, Form IDs, bật webhook, auto-sync |

---

## 10. Lead theo dự án BĐS & Facebook Webhook

> Tính năng **Lead theo dự án** — mỗi dự án BĐS = pipeline lead riêng, webhook Facebook riêng, pool NV riêng.

### 10.1. Kiến trúc (5 phase)

| Phase | Nội dung |
|-------|----------|
| **1** | Gắn `re_project_id` lên lead; lọc/dedup theo dự án |
| **2** | Nhân viên dự án; auto-assign scoped pool |
| **3** | Webhook slug + map Form ID → dự án |
| **4** | Portal NV chỉ thấy lead dự án tham gia; KPI `RE_LEADS_NEW` auto-count |
| **5** | Script migration dữ liệu cũ |

### 10.2. Thiết lập dự án — Nhân viên Lead

1. Vào **Dự án BĐS** → `/crm/re-projects`.
2. Chọn dự án → tab **Tổng quan**.
3. Card **Nhân viên Lead dự án** → **＋ Thêm NV**.
4. Chọn NV, vai trò (`sales` / `manager` / `marketing` / `viewer`).
5. Bật **Nhận lead** (`assign_enabled`) cho NV sales.

> Chỉ NV trong pool mới được auto-assign và phân lead thủ công cho dự án đó.

### 10.3. Thiết lập — Lead & Webhook Facebook

1. Cùng trang Tổng quan → card **Lead & Webhook Facebook**.
2. **Copy Webhook URL** (URL riêng theo dự án, dạng `.../webhooks/facebook/<slug>`).
3. **Copy Verify token** → dán vào Meta Developer Console.
4. Nhập **Page ID Facebook** của dự án.
5. **＋ Form** → thêm Form ID (vd. `2814926042203269`).
6. Bật: **Nhận lead dự án**, **Bật webhook**, **Auto-assign NV dự án**.
7. **Lưu cấu hình**.

### 10.4. Đăng ký webhook trên Meta

1. Vào [Meta Developer Console](https://developers.facebook.com/) → App → Webhooks.
2. Object: **Page** → Subscribe: **leadgen**.
3. **Callback URL:** URL slug đã copy (hoặc URL global nếu dùng chung).
4. **Verify token:** token từ card cấu hình dự án (hoặc token global trong `.env`).
5. Subscribe Page cần nhận lead.
6. Test bằng script (trên VPS):

```bash
cd /var/www/ptt
python3 scripts/ptt_fb_webhook_probe.py
python3 scripts/ptt_fb_diagnose.py
```

### 10.5. Luồng webhook → lead

```
Meta gửi leadgen
  → POST /api/crm/integration/webhooks/facebook/{slug}
  → Xác minh chữ ký HMAC
  → Trả 200 OK ngay (Meta yêu cầu)
  → Worker nền: gọi Graph API lấy SĐT/email
  → Map Form ID → dự án BĐS
  → Tạo lead (re_project_id = dự án)
  → Chấm điểm + phân hạng
  → Auto-assign NV trong pool dự án (round-robin)
  → Cập nhật KPI RE_LEADS_NEW
  → Toast thông báo trên trang Quản lý Lead
```

### 10.6. Migration dữ liệu cũ (Phase 5)

Chạy **một lần** trên VPS sau deploy:

```bash
cd /var/www/ptt

# Xem trước (không ghi DB)
python3 scripts/migrate_project_leads_phase5.py \
  --form-id 2814926042203269 \
  --project-code <MA_DU_AN> \
  --backfill-leads \
  --assign-from-owners \
  --refresh-kpi \
  --dry-run

# Chạy thật
python3 scripts/migrate_project_leads_phase5.py \
  --form-id 2814926042203269 \
  --project-code <MA_DU_AN> \
  --backfill-leads \
  --assign-from-owners \
  --refresh-kpi
```

| Flag | Tác dụng |
|------|----------|
| `--form-id` | Map Form Facebook → dự án |
| `--project-code` | Mã dự án đích (vd. `DA-A`) |
| `--backfill-leads` | Gán `re_project_id` cho lead cũ có form_id khớp |
| `--assign-from-owners` | Thêm owner lead hiện có vào `crm_re_project_staff` |
| `--staff-ids 1,2,3` | Gán NV cụ thể vào dự án |
| `--refresh-kpi` | Cập nhật KPI RE_LEADS_NEW |

---

## 11. Hub, Kế hoạch Marketing & SOP

### 11.1. Hub (`/crm/hub`)

| Tab | Chức năng |
|-----|-----------|
| **Chiến dịch** | Quản lý campaign marketing |
| **Hợp đồng** | Hợp đồng khách hàng, ngày hết hạn |
| **Nhắc việc** | Reminder follow-up, renewals |

### 11.2. Kế hoạch Marketing (`/crm/marketing-plan`)

3 phân khúc vòng đời:

| Segment | URL | Mục đích |
|---------|-----|----------|
| KHTN | `/crm/marketing-plan/segment/khtn` | Khách hàng tiềm năng — 5 bước pipeline |
| KHQT | `.../khqt` | Khách hàng quan tâm |
| CSKH | `.../cskh` | Chăm sóc sau bán |

**Quy trình:** Chọn segment → Tạo kế hoạch năm/quý → Gắn campaign & milestone → Theo dõi tiến độ.

### 11.3. Quy trình SOP (`/crm/sop`)

1. **Mẫu SOP** — định nghĩa các bước chuẩn.
2. **Chạy SOP** — khởi tạo cho dự án/chiến dịch cụ thể.
3. Giao task cho NV → theo dõi hoàn thành.
4. Xem **hàng đợi quá hạn**.

---

## 12. CRM Kinh doanh

**URL:** `/crm/sales`

| Mục | Chức năng |
|-----|-----------|
| **Tổng quan** | Dashboard doanh số, phễu |
| **Kế hoạch** | Plan theo kỳ |
| **Chỉ tiêu** | Target theo NV/khu vực |
| **Đối tác / Prospect** | Pipeline đối tác |
| **Đào tạo** | Log training |
| **Nghiên cứu TT** | Ghi chú thị trường |
| **Giao dịch** | Log deals |
| **Báo cáo** | Sales reports |

**Quy trình KD hàng tháng:**

1. Đặt plan & target đầu tháng.
2. Cập nhật prospect/deals trong tháng.
3. Cuối tháng: xem báo cáo, đối chiếu KPI.

---

## 13. Dự án BĐS (RE Projects)

**URL:** `/crm/re-projects`

### 13.1. Quy trình 8 bước

| Bước | Giai đoạn | Nội dung chính |
|------|-----------|----------------|
| 1 | Khởi tạo | Thông tin dự án, loại hình, vị trí |
| 2 | Chiến lược | Kế hoạch KD, MKT, bán hàng |
| 3 | Tài chính | Ngân sách, P&L |
| 4 | Sản phẩm | Tồn kho căn/ lô (master data) |
| 5 | Bán hàng | Kế hoạch bán, tiến độ |
| 6 | GTM | Go-to-market |
| 7 | KPI | Chỉ tiêu vận hành, sync NV |
| 8 | Quản trị rủi ro | Risk register |

Thanh **Quy trình vận hành** trên trang dự án hiển thị % hoàn thành và bước tiếp theo.

### 13.2. Tạo dự án mới

1. `/crm/re-projects` → **＋ Dự án mới**.
2. Nhập: mã, tên, loại hình (căn hộ, nhà phố…), địa chỉ, số căn, mục tiêu doanh thu.
3. Lưu → bắt đầu điền từng tab kế hoạch.

### 13.3. KPI dự án

1. Tab **KPI** → thêm chỉ tiêu (hoặc từ mẫu).
2. Gán **NV phụ trách**, kỳ (tháng), target.
3. **↑ Đẩy sang KPI NV** — sync sang module KPI nhân sự.
4. **↓ Kéo từ KPI NV** — lấy actual từ NV.
5. **`RE_LEADS_NEW`** — tự động đếm lead mới trong tháng (Phase 4).
6. Refresh thủ công: `POST /api/crm/re-projects/{id}/kpis/refresh-leads-new`.

### 13.4. Xuất báo cáo dự án

Nút **Xuất báo cáo ▾** trên header dự án:

- Báo cáo tổng hợp (Excel)
- Tóm tắt / Quy trình / Kế hoạch / KPI / Tồn kho / Rủi ro / Ngân sách (CSV/Excel)

---

## 14. Nhân sự CRM

**URL:** `/crm/staff`

| Mục | Chức năng |
|-----|-----------|
| **Phòng ban** | CRUD phòng ban |
| **Chức vụ** | CRUD chức vụ (gắn phân quyền CRM) |
| **Danh sách NV** | Hồ sơ, cấp bậc sales, ghi chú skill |
| **Đăng nhập portal** | Username, mật khẩu, bật/tắt |
| **Năng lực** | Competency scoring |
| **Import/Export** | CSV/XLSX roster |

### Quy trình — Thêm NV mới

1. `/crm/staff` → **Thêm nhân viên**.
2. Nhập: họ tên, mã NV, phòng ban, chức vụ, cấp sales (S/A/B/C).
3. Ghi **notes** skill (vd. "q.7 căn hộ facebook") — dùng cho auto-assign.
4. Bật **Cho phép đăng nhập** → đặt username/password.
5. (Tuỳ chọn) Thêm NV vào **dự án BĐS** tại `/crm/re-projects`.

---

## 15. KPI nhân viên

**URL:** `/crm/kpi`

### Admin

1. Định nghĩa **chỉ tiêu** (`crm_kpi_metrics`) — mã, tên, đơn vị.
2. Nhập **target/actual** theo tháng cho từng NV.
3. Xem biểu đồ achievement & cảnh báo.
4. Export XLSX.

### Nhân viên portal

1. Vào **KPI** từ nav.
2. Xem KPI tháng hiện tại.
3. Cập nhật actual (nếu được phép).

**Liên kết dự án BĐS:** KPI dự án (`RE_LEADS_NEW`, v.v.) sync hai chiều với KPI NV qua nút Đẩy/Kéo trên trang dự án.

---

## 16. Chấm công & Lương

**URL:** `/crm/payroll` ( `/crm/attendance` redirect về đây )

| Mục | Chức năng |
|-----|-----------|
| **Chấm công** | Bảng công theo ngày/NV |
| **Import XLSX** | Nhập công từ file |
| **Thiết bị vân tay** | API `/iclock/cdata` cho máy chấm công |
| **Chính sách lương** | Policy, hệ số theo chức vụ |
| **Tính lương** | Compute payroll theo kỳ |
| **Export** | CSV/XLSX bảng lương |

### Quy trình tính lương tháng

1. Import/đồng bộ chấm công.
2. Kiểm tra & sửa công bất thường.
3. **Tính lương** cho kỳ (tháng/năm).
4. Review từng dòng → **Khóa** khi OK.
5. Export bảng lương.

---

## 17. Báo cáo công việc ngày

**URL:** `/crm/daily-reports`

### Nhân viên (hàng ngày)

1. Mở **Báo cáo ngày** từ portal nav.
2. Chọn ngày → điền:
   - Công việc đã làm
   - Số giờ
   - Kế hoạch ngày mai
   - Khó khăn/blocker
3. **Gửi báo cáo**.

### Quản lý

1. Lọc theo NV, khoảng ngày.
2. Review, chỉnh sửa (nếu cần).
3. Tải **mẫu Excel** tại CRM Nhân sự nếu cần import hàng loạt.

---

## 18. Portal nhân viên

**Trang chủ:** `/crm/home`

### Menu portal

| Mục | URL |
|-----|-----|
| Trang chủ | `/crm/home` |
| Lead của tôi | `/crm/leads` |
| KPI | `/crm/kpi` |
| Báo cáo ngày | `/crm/daily-reports` |
| Chăm sóc KH | `/crm` |
| Khách hàng | `/crm/customers` |
| Chấm công | `/crm/payroll` |
| Đổi mật khẩu | `/account/password` |

### Trang chủ portal hiển thị

- Snapshot KPI tháng này
- Lead mới được gán
- Trạng thái báo cáo ngày

### Phạm vi dữ liệu portal

| Module | Quy tắc |
|--------|---------|
| **Case CSKH** | Chỉ hồ sơ gán cho mình, chưa kết thúc |
| **Lead** | Chỉ dự án tham gia; sales = lead của mình; manager/viewer = mọi lead dự án |
| **KPI / Chấm công / Lương** | Chỉ bản ghi của mình |
| **Báo cáo ngày** | Chỉ báo cáo của mình |

### Checklist hàng ngày — NV kinh doanh

- [ ] Mở `/crm/home` — xem lead mới qua đêm
- [ ] Xử lý lead Hot / quá hạn SLA trên `/crm/leads`
- [ ] Ghi hoạt động sau mỗi cuộc gọi
- [ ] Cập nhật trạng thái lead
- [ ] Gửi **báo cáo ngày** trước cuối ca
- [ ] Kiểm tra KPI tháng trên `/crm/kpi`

---

## 19. Xuất / Nhập dữ liệu

| Tính năng | Cách thực hiện | Định dạng |
|-----------|----------------|-----------|
| Xuất danh sách NV | CRM Nhân sự → Export | CSV, XLSX |
| Import NV | CRM Nhân sự → Import | XLSX |
| Mẫu báo cáo ngày | CRM Nhân sự → Tải mẫu | XLSX |
| Xuất lead | CRM Lead → Xuất (sau lọc) | XLSX, PDF |
| Import lead | CRM Lead → Import | CSV |
| Xuất KPI | CRM KPI → Export | XLSX |
| Xuất lương | CRM Lương → Export | CSV, XLSX |
| Xuất dự án BĐS | RE Projects → Xuất báo cáo | CSV, XLSX |
| Xuất chat MKT | CMS Chat → Export | MD, HTML, JSON |
| Excel kế hoạch MKT | CMS Chat → Tải Excel | XLSX |
| Campaign kit | CMS Chat → Campaign kit | XLSX |
| Import chấm công | CRM Lương → Import | XLSX |

> Cần quyền **export** hoặc **create** tương ứng trên từng section.

---

## 20. Phụ lục — Tra cứu nhanh & Xử lý sự cố

### 20.1. Bảng URL nội bộ

| URL | Module |
|-----|--------|
| `/admin/login` | Đăng nhập |
| `/admin` | Admin dashboard |
| `/cms` | CMS |
| `/crm` | Bảng CSKH |
| `/crm/home` | Portal NV |
| `/crm/customers` | Khách hàng |
| `/crm/leads` | Quản lý Lead |
| `/crm/hub` | Hub |
| `/crm/marketing-plan` | Kế hoạch MKT |
| `/crm/sop` | SOP |
| `/crm/sales` | Kinh doanh |
| `/crm/re-projects` | Dự án BĐS |
| `/crm/staff` | Nhân sự |
| `/crm/daily-reports` | Báo cáo ngày |
| `/crm/kpi` | KPI |
| `/crm/payroll` | Chấm công & Lương |
| `/account/password` | Đổi mật khẩu |

### 20.2. Webhook Facebook — URL

| Loại | URL |
|------|-----|
| Global | `https://pttads.vn/api/crm/integration/webhooks/facebook` |
| Theo dự án | `https://pttads.vn/api/crm/integration/webhooks/facebook/<slug>` |

Verify token: lấy từ cấu hình dự án hoặc biến môi trường `CRM_FACEBOOK_VERIFY_TOKEN`.

### 20.3. Xử lý sự cố thường gặp

| Triệu chứng | Nguyên nhân có thể | Cách xử lý |
|-------------|-------------------|------------|
| **403 Forbidden** trên CRM | Thiếu quyền section | Kiểm tra chức vụ CRM tại CMS → Phân quyền |
| Portal redirect về login | `login_enabled=0` hoặc sai mật khẩu | CRM Nhân sự → bật login, reset password |
| Lead Facebook không vào CRM | Webhook chưa subscribe / sai token | Chạy `ptt_fb_diagnose.py`; kiểm tra Meta Console |
| Lead vào CRM nhưng không gán NV | Không có NV trong pool dự án | RE Projects → thêm NV, bật assign_enabled |
| Lead không gán dự án | Form ID chưa map | RE Projects → Lead & Webhook → thêm Form ID |
| NV portal không thấy lead | Không thuộc dự án / không phải owner | Thêm NV vào dự án; manager thấy mọi lead dự án |
| Toast "Form chưa map" | Form ID lạ từ Meta | Map form trong cấu hình dự án hoặc global |
| KPI RE_LEADS_NEW = 0 | Chưa refresh / lead không có re_project_id | Chạy refresh-leads-new API hoặc migration Phase 5 |
| Meta báo webhook fail | Server trả ≠200 hoặc verify sai | Luôn trả 200; kiểm tra verify token khớp |
| Rate limit Graph API | Quá nhiều request Facebook | Chờ 15 phút; hệ thống tự retry pending queue |

### 20.4. Deploy & cập nhật (IT)

```bash
cd /var/www/ptt
git pull
sudo systemctl restart ptt
python3 scripts/build_ptt_assets.py   # minify JS/CSS
```

### 20.5. Biến môi trường quan trọng

| Biến | Mục đích |
|------|----------|
| `ADMIN_USERNAME` / `ADMIN_PASSWORD` | Bootstrap admin lần đầu |
| `CRM_FACEBOOK_VERIFY_TOKEN` | Verify webhook Meta (global) |
| `CRM_FACEBOOK_APP_SECRET` | Chữ ký webhook HMAC |
| `CRM_FACEBOOK_PAGE_ACCESS_TOKEN` | Graph API lấy lead |
| `CRM_MARKETING_INGEST_SECRET` | API ingest marketing ngoài |
| `SESSION_COOKIE_SECURE` | Bật cookie secure trên HTTPS |

### 20.6. Tài liệu kỹ thuật bổ sung

| File | Nội dung |
|------|----------|
| `docs/HE_THONG_PTT.md` | Kiến trúc, API, schema DB |
| `docs/PHAN_QUYEN_HUONG_DAN.md` | Chi tiết ma trận phân quyền |
| `README.md` | Quick start dev |

---

## Lịch sử cập nhật tài liệu

| Ngày | Nội dung |
|------|----------|
| 2026-05 | Bản đầu — gộp toàn bộ hướng dẫn: Landing, CMS, CRM, Lead theo dự án BĐS (Phase 1–5), Portal, Facebook webhook, KPI |

---

*Tài liệu nội bộ PTT Advertising Solutions. Liên hệ quản trị hệ thống khi cần bổ sung quyền hoặc hỗ trợ kỹ thuật.*
