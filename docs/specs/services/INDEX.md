# PTTP — Specs Quy trình Dịch vụ

**Phiên bản:** 1.0 — 2026-06-22
**Chuẩn:** Creative Martech, AI-first (Claude API xuyên suốt mọi giai đoạn)

---

## Cấu trúc mỗi Spec

Mỗi file gồm 7 phần đồng nhất:

| Phần | Nội dung |
|------|---------|
| 1. Tổng quan | Mục tiêu, đối tượng KH, cam kết cốt lõi |
| 2. Vòng đời KH | 7 giai đoạn: Lead → Tư vấn → Ký HĐ → Onboarding → Triển khai → Nghiệm thu → Chăm sóc |
| 3. Phân công (RACI) | AM / Specialist / AI / QA / DIR |
| 4. AI Integration | AI làm gì ở từng giai đoạn, module nào |
| 5. SLA & Timeline | Thời gian phản hồi, deadline, chu kỳ báo cáo |
| 6. KPI Nội bộ | Chỉ số team: convert rate, on-time, CSAT, gia hạn |
| 7. KPI Cam kết KH | Chỉ số kết quả PTT hứa với khách hàng |

---

## Vai trò trong RACI

| Ký hiệu | Vai trò | Mô tả |
|---------|---------|-------|
| **AM** | Account Manager | Đầu mối KH, phụ trách toàn bộ vòng đời |
| **SP** | Specialist | Chuyên gia theo dịch vụ (SEO / Designer / Ads / Content / Dev) |
| **AI** | Claude + modules | Hỗ trợ toàn bộ quy trình theo Creative Martech |
| **QA** | Quality Assurance | Kiểm tra chất lượng trước khi gửi KH |
| **DIR** | Director | Duyệt giá, escalate, quyết định chiến lược |

*R=Responsible, A=Accountable, C=Consulted, I=Informed*

---

## Danh sách Spec theo Nhóm

### Tìm kiếm tự nhiên

| Dịch vụ | File | Timeline triển khai |
|---------|------|---------------------|
| Dịch vụ AEO | [dich-vu-aeo.md](dich-vu-aeo.md) | 4 tuần |
| Dịch vụ SEO tổng thể | [dich-vu-seo-tong-the.md](dich-vu-seo-tong-the.md) | 6 tuần (audit + roadmap) |
| Dịch vụ SEO local | [dich-vu-seo-local.md](dich-vu-seo-local.md) | 2 tuần setup |
| Dịch vụ SEO Audit | [dich-vu-seo-audit.md](dich-vu-seo-audit.md) | 2–3 tuần |
| Dịch vụ Quản trị website | [dich-vu-quan-tri-website.md](dich-vu-quan-tri-website.md) | 3 ngày onboarding |

### Thiết kế

| Dịch vụ | File | Timeline triển khai |
|---------|------|---------------------|
| Thiết kế website | [thiet-ke-website.md](thiet-ke-website.md) | 5–7 tuần |
| Thiết kế website trọn gói | [thiet-ke-website-tron-goi.md](thiet-ke-website-tron-goi.md) | 8–12 tuần |
| Thiết kế landing page | [thiet-ke-landing-page.md](thiet-ke-landing-page.md) | 1–2 tuần |

### Quảng cáo kỹ thuật số

| Dịch vụ | File | Timeline triển khai |
|---------|------|---------------------|
| Quảng cáo Facebook | [quang-cao-facebook.md](quang-cao-facebook.md) | 3–5 ngày setup |
| Quảng cáo Google | [quang-cao-google.md](quang-cao-google.md) | 3–5 ngày setup |
| Cho thuê tài khoản quảng cáo | [thue-tai-khoan-quang-cao.md](thue-tai-khoan-quang-cao.md) | 1–2 ngày |

### Tiếp thị nội dung

| Dịch vụ | File | Timeline triển khai |
|---------|------|---------------------|
| Tiếp thị nội dung | [tiep-thi-noi-dung.md](tiep-thi-noi-dung.md) | Bài đầu trong 1 tuần |

---

## Lead Intake (Form gọi & gặp KH)

Checklist tiếp nhận lead tại stage **Lead** — gọi điện (PHẦN A) và gặp trực tiếp (PHẦN B).

| Tài liệu | Đường dẫn |
|----------|-----------|
| Design spec | [2026-06-30-lead-intake-system-design.md](../2026-06-30-lead-intake-system-design.md) |
| Kế hoạch triển khai | [2026-06-30-lead-intake-system.md](../../superpowers/plans/2026-06-30-lead-intake-system.md) |
| Form HTML (13 file) | [forms/lead-intake/](../../forms/lead-intake/) |
| Route CRM (Phase 1) | `/crm/forms/lead-intake/<slug>.html` từ Service Workflow |
| Generator | `scripts/generate_lead_intake_forms.py` |

**Roadmap:** Phase 2+ — module `crm_lead_intake.py`, trang `/crm/intake`, lưu session DB, auto-sync task Lead.

---

## SLA Chung (áp dụng mọi dịch vụ)

| Mốc | Thời gian tối đa |
|-----|-----------------|
| Phản hồi lead | ≤ 2h giờ hành chính |
| Gửi proposal sau tư vấn | ≤ 2 ngày làm việc |
| Phản hồi yêu cầu chỉnh sửa | ≤ 1 ngày làm việc |
| Vòng chỉnh sửa tối đa | 2 vòng trong phạm vi HĐ |
| Báo cáo định kỳ | Đúng ngày cam kết ±1 ngày |
| Nhắc gia hạn HĐ | Trước 30 ngày hết hạn |

---

## KPI Nội bộ Chung

| KPI | Ngưỡng tốt |
|-----|------------|
| Convert lead → HĐ | ≥ 30% |
| On-time delivery | ≥ 90% |
| Tỷ lệ > 2 vòng chỉnh sửa | ≤ 20% |
| CSAT sau nghiệm thu | ≥ 4.2/5 |
| Tỷ lệ gia hạn HĐ | ≥ 70% |
| Upsell rate | ≥ 25% |
| AI usage rate | ≥ 80% tasks |
| Thời gian phản hồi lead TB | ≤ 1.5h |

---

## AI Modules tham chiếu

| Module | Vai trò |
|--------|---------|
| `crm_ai_qualify.py` | Chấm điểm và phân loại lead tự động |
| `crm_lead_ai.py` | Phân tích nhu cầu, gợi ý dịch vụ trong tư vấn |
| `crm_daily_work_report.py` | Tạo báo cáo nghiệm thu và báo cáo tháng |
| `crm_care.py` | Alert KPI tụt, nhắc gia hạn, gợi ý upsell |
| Claude API | Proposal, brief, content, review, phân tích xuyên suốt |
