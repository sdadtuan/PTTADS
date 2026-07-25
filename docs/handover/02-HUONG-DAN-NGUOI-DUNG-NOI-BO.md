# 02 — Hướng dẫn sử dụng người dùng nội bộ (Staff)

> **Phiên bản:** 1.0 · **Ngày:** 2026-07-25  
> **URL:** https://ops.pttads.vn · **Đăng nhập:** `/login`  
> **Tham chiếu:** [01-TONG-QUAN-HE-THONG.md](01-TONG-QUAN-HE-THONG.md)

---

## 1. Đăng nhập & điều hướng

### 1.1. Đăng nhập

1. Mở https://ops.pttads.vn/login
2. Nhập email và mật khẩu do Admin HR cấp (bảng `staff_users` trên PostgreSQL)
3. Sau đăng nhập, sidebar **OpsNav** hiển thị menu theo **phân quyền section**

> **Dev/staging only:** stub `staff@demo.local` / `demo123` — **không dùng production**.

### 1.2. Cấu trúc menu chính

| Nhóm sidebar | Module tiêu biểu |
|--------------|------------------|
| **Tổng quan** | Bảng CSKH |
| **Chăm sóc KH** | Lead, Review queue, Catalog, Khách hàng |
| **Marketing** | Hub HĐ, SOP, Launch QA, Creative, Campaign Write, Triển khai DV |
| **Kinh doanh** | Sales, Đề xuất, Dự án BĐS |
| **Nhân sự** | Staff, KPI, Payroll |
| **Tài chính** | Dashboard KD, Tài chính |
| **Agency & Hub** | Agency, Meta Ads, SEO Hub, Email Hub, … |

Menu ẩn nếu user **không có cap** tương ứng — không phải lỗi hệ thống.

---

## 2. CRM & vòng đời dịch vụ

### 2.1. Quản lý Lead (`/crm/leads`)

**Mục đích:** Thu thập, phân loại và chuyển đổi lead từ mọi kênh.

**Thao tác hàng ngày (CSKH / Sales):**

1. Mở **Quản lý Lead** — lọc theo nguồn, trạng thái, owner
2. **Review queue** — xử lý lead mới từ webhook Meta/Zalo/Google/form
3. Cập nhật trạng thái pipeline: New → Contacted → Qualified → Won/Lost
4. Gán owner và ghi chú — mọi thay đổi có audit

**Lead từ webhook:** Meta Lead Ads → Nest webhook → job queue → CRM lead (latency mục tiêu ≤ 30s staging).

### 2.2. Khách hàng (`/crm/customers`)

- Master data khách hàng agency
- Liên kết `customer_id` với client UUID các phân hệ (SEO, Email, Meta)
- Dùng làm điểm xuất phát onboard phân hệ mới

### 2.3. Hub hợp đồng (`/crm/hub`)

- Danh sách hợp đồng / dịch vụ đang chạy
- Drill-down client health cross-module
- Entry point AM khi review portfolio khách hàng

### 2.4. Triển khai dịch vụ (`/crm/service-delivery`)

**Workflow 7 stage:** Lead → Consult → Proposal → **Onboard** → **Deliver** → **Handover** → **Retain**

| Stage | AM / SP làm gì |
|-------|----------------|
| Onboard | Checklist task, gán SP, cấu hình client |
| Deliver | Thực thi dịch vụ (SEO/Meta/Email…) |
| Handover | Bàn giao khách (gate finance nếu công nợ) |
| Retain | Duy trì, renew, báo cáo định kỳ |

**Launch QA** (`/crm/launch-qa`): checklist trước khi campaign ads go-live — warn nếu chưa pass.

### 2.5. Creative & Campaign Write

| Màn | Route | Vai trò |
|-----|-------|---------|
| Creative Hub | `/crm/creatives` | Upload/review creative |
| Campaign Write | `/crm/campaign-writes` | Queue chỉnh campaign Meta có approval |

---

## 3. Meta Enterprise Ops

> Chi tiết: [`huong-dan-meta-enterprise-ops.md`](../huong-dan-meta-enterprise-ops.md)

### 3.1. Meta Ads Hub (`/meta/facebook-ads`)

**AM / Buyer hàng ngày:**

1. Chọn client → xem spend, leads CRM, CPL, ROAS (T-1)
2. Map campaign Meta ↔ CRM nếu chưa map (giảm % unmapped spend)
3. Drill-down campaign underperforming → Ads Ops hoặc Intelligence

### 3.2. Tracking (`/meta/tracking`)

**Tracking/Tech:**

- CAPI health, pixel test, event rules
- Xử lý backlog CAPI pending
- Verify webhook + dedup lead

### 3.3. Ads Ops (`/meta/ads-ops`)

**Launch / Edit wizard** — chỉ sau governance approve:

1. Chọn client + objective
2. Creative + audience + budget
3. Submit → Temporal approval (nếu bật)
4. Launch sau pass Launch QA

### 3.4. Intelligence (`/meta/intelligence`)

- Anomaly detection (spend spike, CPL drift)
- Forecast, recommendations
- Owner weekly digest (nội bộ GDKD)

---

## 4. SEO/AEO Enterprise Ops

> Chi tiết: [`huong-dan-seo-aeo-ops.md`](../huong-dan-seo-aeo-ops.md)

### 4.1. Luồng hàng ngày Head SEO (15–20 phút)

1. `/seo/hub` — sync GSC/GA4 OK? client health?
2. Drill-down client đỏ/vàng → workspace
3. `/seo/technical` — critical issues
4. `/seo/content` — overdue cards
5. `/seo/automations` — ack alerts

### 4.2. Onboard client SEO mới

1. `/seo/clients/:id` Settings — domain, tier, approvers
2. `/seo/technical` — OAuth GSC + GA4
3. `/seo/research` — import keywords
4. Hub KPI hiển thị T+1 sau sync

### 4.3. Content pipeline

13 stage workflow — publish bị **governance block** nếu thiếu metadata (khi `PTT_SEO_GOVERNANCE_ENABLED=1`).

**Checklist in A4:** [`seo-aeo-ops-checklist-a4.html`](../forms/seo-aeo-ops-checklist-a4.html)

---

## 5. Email Marketing Enterprise Ops

> Chi tiết: [`huong-dan-email-marketing-ops.md`](../huong-dan-email-marketing-ops.md)

### 5.1. Luồng AM onboard Email client

1. `/email/clients/:id?tab=settings` — workspace, ESP, caps
2. `/email/deliverability` — **Domain wizard** 3 bước (DNS → Verify)
3. `/email/contacts` — import CSV
4. `/email/consent` — verify opted-in

### 5.2. Luồng Strategist broadcast

1. `/email/segments` — Lifecycle / RFM / Behavior → **Compute**
2. `/email/templates` — HTML + `{{unsubscribe_url}}`
3. `/email/campaigns` — draft → preflight → approve → schedule
4. `/email/hub` — monitor complaint, queue lag

### 5.3. Governance & compliance

- `/email/governance` — global rules (frequency cap, quiet hours)
- `/email/suppression` — master list
- Audit log 50 bản ghi gần nhất

**Checklist in A4:** [`email-marketing-ops-checklist-a4.html`](../forms/email-marketing-ops-checklist-a4.html)

---

## 6. Agency module (`/agency`)

| Trang | Chức năng |
|-------|-----------|
| Agency home | Tổng quan channel accounts |
| Ingest | Monitor webhook / ingest health |
| KPI definitions | Định nghĩa KPI cross-client |
| Client detail | `/agency/clients/:id` — map Meta ad account, tokens |

---

## 7. Thao tác chung & mẹo UX

### 7.1. Lọc theo client

Hầu hết màn hình phân hệ (SEO, Email, Meta) có **client filter** hoặc query `?client_id=` — luôn chọn đúng client trước thao tác.

### 7.2. Export & báo cáo

- Meta: CSV export trên hub / portal
- SEO: PDF export `/seo/reports`
- Email: ClickHouse export + scheduled PDF `/email/reports`

### 7.3. Phím tắt & mobile

- Desktop-first (enterprise B2B)
- Tablet: AM review portal/campaign OK
- Mobile smoke: hub load được — không khuyến nghị thao tác phức tạp

---

## 8. Ai làm gì — ma trận nhanh

| Việc | Vai trò | Màn hình |
|------|---------|----------|
| Xử lý lead mới | CSKH | `/crm/leads` |
| Ký HĐ / lifecycle | AM | `/crm/hub`, service-delivery |
| Launch campaign Meta | Buyer + Creative | Launch QA → Ads Ops |
| Publish content SEO | Writer + Approver | `/seo/content/:id` |
| Gửi email broadcast | Email Strategist | `/email/campaigns` |
| DNS domain email | Deliverability | `/email/deliverability` |
| Duyệt quyền staff | Admin | Admin phân quyền |
| Báo cáo tuần client | AM | Portal + export |

---

## 9. Tài liệu liên quan

| Tài liệu | Nội dung |
|----------|----------|
| [03-HUONG-DAN-PORTAL-KHACH-HANG.md](03-HUONG-DAN-PORTAL-KHACH-HANG.md) | Hướng dẫn phía khách |
| [05-PHAN-QUYEN-BAO-MAT-SLA.md](05-PHAN-QUYEN-BAO-MAT-SLA.md) | Caps chi tiết |
| Module ops guides | SEO, Email, Meta (link README) |
