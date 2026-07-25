# 03 — Hướng dẫn Portal khách hàng (Client Portal)

> **Phiên bản:** 1.0 · **Ngày:** 2026-07-25  
> **URL:** https://portal.pttads.vn · **Đăng nhập:** `/login`  
> **Tham chiếu:** [01-TONG-QUAN-HE-THONG.md](01-TONG-QUAN-HE-THONG.md)

---

## 1. Giới thiệu Portal

**Client Portal** là cổng thông tin dành cho **khách hàng của agency PTT** — không phải nhân viên nội bộ. Portal cho phép:

- Xem **báo cáo hiệu suất** (Meta, SEO, Email) theo phạm vi client được cấp
- **Duyệt** creative, campaign, nội dung trước khi go-live (vai trò approver)
- Tải **export CSV/PDF** self-serve (tuỳ module bật)

**Phân tách bảo mật:** JWT portal scoped theo `client_id` — khách **không** thấy dữ liệu client khác.

---

## 2. Đăng nhập & tài khoản

### 2.1. Truy cập

1. Mở https://portal.pttads.vn/login
2. Nhập email và mật khẩu do PTT cấp tại buổi bàn giao
3. Sau đăng nhập → **Dashboard** tổng quan

### 2.2. Vai trò portal

| Vai trò | Quyền |
|---------|-------|
| **Viewer** | Xem dashboard, báo cáo, export read-only |
| **Approver** | Viewer + duyệt/từ chối trong approval inbox |

### 2.3. Quên mật khẩu & đổi mật khẩu

| Luồng | URL | Mô tả |
|-------|-----|-------|
| Quên MK | `/forgot-password` | Nhập email → nhận link (email webhook hoặc dev link staging) |
| Đặt MK mới | `/reset-password?token=…` | Link one-time, TTL mặc định 60 phút |
| Đổi MK (đã login) | `/settings` | Nhập MK cũ + MK mới |
| AM reset | ops `/agency/clients/[id]?tab=portal` | Nút **Reset MK** |

**Env production:** `PTT_PORTAL_PUBLIC_URL`, `PTT_PORTAL_EMAIL_NOTIFY=1`, DDL `2026-07-25-postgresql-ddl-v3-portal-password-reset.sql`

### 2.4. Hỗ trợ & bảo mật tài khoản

- Lần đầu đăng nhập: **đổi mật khẩu** tại `/settings` nếu PTT yêu cầu
- Quên mật khẩu: self-serve `/forgot-password` hoặc liên hệ AM reset trên ops-web
- **Không** chia sẻ tài khoản approver — mỗi approver một login để audit

> Mật khẩu ban đầu ghi trên form [`ban-giao-tai-khoan-credentials-a4.html`](../forms/ban-giao-tai-khoan-credentials-a4.html) — bản giao vault, không email plain text.

---

## 3. Dashboard (`/dashboard`)

Sau đăng nhập, dashboard hiển thị widget theo **dịch vụ đang chạy** cho client:

| Widget | Điều kiện hiện | Nội dung |
|--------|----------------|----------|
| Meta performance | Meta pilot bật | Spend, leads, CPL snapshot T-1 |
| SEO summary | Portal SEO bật | GSC clicks, content status |
| Email summary | Portal Email bật | Campaign stats, pending approvals |
| Pending approvals | Có item chờ duyệt | Link nhanh approval inbox |

Dữ liệu cập nhật **T-1** (ngày hôm trước) trừ KPI real-time stub.

---

## 4. Meta — Báo cáo & export (`/meta`)

> Yêu cầu: client đã map Meta ad account + sync insights OK.

### 4.1. Xem performance

1. Menu **Meta** hoặc widget dashboard
2. Chọn khoảng thời gian (7 / 28 / 30 ngày)
3. Xem KPI cards: **Chi tiêu Meta**, **Lead CRM**, **CPL**, **ROAS** (nếu có dữ liệu sale)

### 4.2. Giải thích KPI (client-safe)

| Thuật ngữ | Ý nghĩa |
|-----------|---------|
| Chi tiêu Meta | Số tiền thực tế từ Meta Ads Manager (VND) |
| Lead CRM | Lead hợp lệ trên hệ thống PTT (đã loại trùng/spam) |
| CPL | Chi tiêu ÷ Lead CRM cùng kỳ |
| ROAS | Doanh thu chốt sale ÷ Chi tiêu (khi có dữ liệu) |
| Chưa map campaign | Chi tiêu chưa gắn campaign CRM — CPL có thể lệch |

### 4.3. Export CSV

- Nút **Export** trên bảng campaign (self-serve)
- File CSV tải về local — không lưu trên portal quá 24h (policy agency)

### 4.4. Báo cáo PDF tuần (RPT-M3)

Nếu HĐ enterprise bao gồm **Weekly Meta PDF**:

- Gửi email **Thứ 2 08:00** (timezone VN)
- Nội dung: executive summary, KPI cards, trend 7d, top/bottom campaigns
- Liên hệ AM nếu không nhận được sau 2 tuần pilot

---

## 5. SEO — Portal client (`/seo`)

> Yêu cầu: `PTT_PORTAL_SEO_ENABLED=1` + map client.

### 5.1. Tính năng viewer

- Tóm tắt organic performance (GSC clicks, impressions)
- Trạng thái content pipeline (stage, không expose nội bộ writer notes)
- Export PDF báo cáo tháng (nếu schedule bật)

### 5.2. Approval (approver)

1. Mở **Approvals** hoặc link email notification
2. Xem preview nội dung / meta SEO
3. **Approve** hoặc **Reject** kèm comment
4. Sau approve → staff publish theo workflow nội bộ

---

## 6. Email — Portal client (`/email`)

> Yêu cầu: `PTT_EMAIL_PORTAL_ENABLED=1` (Gate A B3).

### 6.1. Dashboard email

- KPI sent, open rate, click rate (aggregate client)
- Campaign list với status

### 6.2. Approval campaign (P-EMAIL-02)

1. `/email/approvals` — danh sách campaign chờ duyệt
2. Click campaign → **preview** email (desktop/mobile)
3. Approve → campaign chuyển `approved` → staff schedule send
4. Reject → comment → strategist chỉnh lại

**SLA duyệt khuyến nghị:** ≤ 24h giờ hành chính (theo HĐ).

---

## 7. Creative & approvals chung (`/creatives`, `/approvals`)

Tuỳ cấu hình HĐ, portal có thể gom approval creative Meta / multi-channel:

1. Inbox thống nhất item chờ duyệt
2. Preview asset (image/video/copy)
3. Approve / Reject có lý do
4. Lịch sử duyệt lưu audit — không xóa

---

## 8. FAQ khách hàng

| Câu hỏi | Trả lời |
|---------|---------|
| Số liệu cập nhật khi nào? | Meta/SEO T-1 sau sync đêm; email near-real-time sau send |
| Tại sao CPL cao bất thường? | Có thể do unmapped spend — liên hệ AM |
| Tôi duyệt rồi nhưng ads chưa chạy? | Còn Launch QA / governance nội bộ — AM sẽ confirm |
| Tôi thấy số lead khác Meta? | CRM dedup spam/trùng; định nghĩa "lead hợp lệ" theo SOP PTT |
| Quên mật khẩu? | Liên hệ AM — không tự reset trên portal (trừ khi bật flow reset) |

---

## 9. Bảo mật phía khách hàng

- Chỉ truy cập HTTPS `portal.pttads.vn`
- Không forward link approval có token cho bên thứ ba
- Đăng xuất khi dùng máy shared
- Báo AM ngay nếu nghi ngờ truy cập trái phép

Chi tiết: [05-PHAN-QUYEN-BAO-MAT-SLA.md](05-PHAN-QUYEN-BAO-MAT-SLA.md)

---

## 10. Liên hệ

| Nhu cầu | Liên hệ |
|---------|---------|
| Truy cập / mật khẩu | AM phụ trách |
| Giải thích số liệu | AM / Media Buyer |
| Duyệt gấp ngoài giờ | Hotline trong HĐ (nếu có) |
| Sự cố hệ thống | PTT support tier theo HĐ |

Form ghi nhận bàn giao tài khoản: [`ban-giao-tai-khoan-credentials-a4.html`](../forms/ban-giao-tai-khoan-credentials-a4.html)
