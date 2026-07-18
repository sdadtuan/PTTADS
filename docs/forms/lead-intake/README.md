# Form tiếp nhận Lead — PTT Service Delivery

Bộ form dùng khi **gọi lead** (15–25 phút) và **gặp trực tiếp** (45–60 phút) để qualify và chốt bước Tư vấn.

## Cấu trúc mỗi form

| Phần | Thời lượng | Nội dung chính |
|------|------------|----------------|
| **PHẦN A — Gọi lead** | 15–25 phút | Script mở đầu, 12–15 câu qualify, red flags, objections, BANT+, Go/Nurture/No-Go |
| **PHẦN B — Gặp trực tiếp** | 45–60 phút | Discovery 15–20 câu, live audit/demo, tài liệu Lead vs Onboard, KPI framing, script chốt Proposal, upsell |

Form **00-form-chung** dùng khi chưa xác định dịch vụ hoặc multi-service. Form riêng dùng khi đã biết slug dịch vụ.

Header có logo PTT (`static/images/ptt-logo.png`).

## Cách dùng

1. Mở file HTML tương ứng dịch vụ trong trình duyệt — hoặc từ **CRM → Service Delivery → Workflow → Lead Intake**.
2. In ra giấy (**Ctrl/Cmd + P**) hoặc Save as PDF.
3. Sau buổi gọi/gặp: nhập tóm tắt vào CRM → task **Lead** (Service Delivery) + Lead care **first_contact**.

**URL trong CRM (Phase 1):** `/crm/forms/lead-intake/<tên-file>.html` (yêu cầu đăng nhập admin).

**Spec & roadmap:** [2026-06-30-lead-intake-system-design.md](../../specs/2026-06-30-lead-intake-system-design.md)

## Danh sách file

| File | Dịch vụ |
|------|---------|
| [00-form-chung.html](00-form-chung.html) | Form chung — mọi dịch vụ |
| [dich-vu-seo-tong-the.html](dich-vu-seo-tong-the.html) | SEO tổng thể |
| [dich-vu-aeo.html](dich-vu-aeo.html) | AEO |
| [dich-vu-seo-local.html](dich-vu-seo-local.html) | SEO Local |
| [dich-vu-seo-audit.html](dich-vu-seo-audit.html) | SEO Audit |
| [dich-vu-quan-tri-website.html](dich-vu-quan-tri-website.html) | Quản trị website |
| [thiet-ke-website.html](thiet-ke-website.html) | Thiết kế website |
| [thiet-ke-website-tron-goi.html](thiet-ke-website-tron-goi.html) | Website trọn gói |
| [thiet-ke-landing-page.html](thiet-ke-landing-page.html) | Landing page |
| [quang-cao-facebook.html](quang-cao-facebook.html) | Facebook Ads |
| [quang-cao-google.html](quang-cao-google.html) | Google Ads |
| [thue-tai-khoan-quang-cao.html](thue-tai-khoan-quang-cao.html) | Thuê tài khoản QC |
| [tiep-thi-noi-dung.html](tiep-thi-noi-dung.html) | Tiếp thị nội dung |

## Tạo lại sau khi chỉnh nội dung

```bash
python3 PTTADS/scripts/generate_lead_intake_forms.py
```
