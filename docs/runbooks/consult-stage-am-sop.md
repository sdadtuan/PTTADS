# SOP: Giai đoạn Tư vấn (Consult) — Account Manager

**Phiên bản:** 1.0 · 2026-06-30  
**Phạm vi:** Service Lifecycle CRM — stage `consult` (12 dịch vụ agency)  
**Spec:** [2026-06-30-consult-stage-system-design.md](../specs/2026-06-30-consult-stage-system-design.md)  
**Phụ lục task:** [consult-stage-service-tasks.md](./consult-stage-service-tasks.md)

---

## 1. Mục đích

Giai đoạn **Tư vấn** chuyển lead từ *“đã qualify sơ bộ”* sang *“đủ dữ liệu để báo giá”* — audit/discovery chuyên môn, ghi vào CRM, rồi chuyển **Báo giá (Proposal)**.

**Không nhầm với:**

| Giai đoạn | Công cụ CRM | Nội dung |
|-----------|-------------|----------|
| **Lead** | Lead Intake (PHẦN A gọi / PHẦN B gặp) + task Lead | BANT+, Go/Nurture/No-Go, qualify, cam kết KH |
| **Tư vấn** | Task Consult trên workflow | Audit, phân tích hiện trạng, scope cho proposal |
| **Báo giá** | Task Proposal + Proposal AI | Giá, KPI cam kết, timeline HĐ |

**Chính sách doanh thu:** PTT **không thu phí tư vấn/audit** ở giai đoạn Consult. Buổi tư vấn là **miễn phí** (pre-sales). **Không** ghi nhận doanh thu PTT trên CRM ở stage này — doanh thu chỉ bắt đầu sau **ký hợp đồng** (Onboard+) và thu tiền theo payment. Field **Ngân sách/tháng** trên Lead/Proposal là ngân sách **KH sẵn sàng chi**, không phải tiền PTT đã thu.

---

## 2. Điều kiện vào Consult

1. Lifecycle đang ở stage **Lead**.
2. **100% task Lead** đã tick ✓ (engine CRM bắt buộc).
3. Bấm **「Chuyển → Tư vấn」** trên `/crm/service-delivery/<id>`.
4. Lead care sync sang bước **Khai thác nhu cầu** (`qualify`).

**Khuyến nghị nghiệp vụ (trước khi chuyển):**

- Có **Lead Intake completed** với `decision` đã chọn.
- Nếu **Go**: nên có Intake **gặp trực tiếp (PHẦN B)** trước audit sâu.
- Nếu **No-Go**: không chuyển Consult sâu (chờ gate C3 + Director override).

---

## 3. Quy trình Consult (5 bước)

```
Đọc output Lead → Thu tài liệu L2 → Làm task Consult → AI review → ✓ → Chuyển Báo giá
```

| Bước | Việc làm | SLA |
|------|----------|-----|
| 1 | Đọc task Lead + Intake sessions + notes | Ngay khi vào Consult |
| 2 | Thu tài liệu KH (URL, GSC, GBP, Ads…) theo dịch vụ | Trước buổi audit |
| 3 | Họp audit/discovery; điền **form Consult** trên workflow | 3–7 ngày |
| 4 | **AI Hỗ trợ** (`consult_analysis`); chỉnh notes | Cùng buổi tư vấn |
| 5 | Tick ✓ task Consult → **Chuyển → Báo giá** | **≤48h** sau meeting |

---

## 4. Quyết định Lead → hành vi Consult

| Decision | BANT (sau khi C3) | Hành vi Consult |
|----------|-------------------|-----------------|
| **Go** | ≥22/30 | Consult đầy đủ — **bắt buộc** Intake PHẦN B trước audit sâu |
| **Nurture** | 16–21 | **Không chuyển Consult** — nurture đến Go |
| **No-Go** | <16 | **Block** Consult — Director override |

> Cho đến Phase C3, CRM chưa gate tự động — AM tuân SOP thủ công. Code BANT gợi ý UI vẫn 24/18 tạm thời.

Ngưỡng chi tiết: [consult-stage-bant-signoff.md](./consult-stage-bant-signoff.md) (chờ Director ký).

AM **có thể override** decision gợi ý — bắt buộc ghi `decision_reason` trong Lead Intake.

---

## 5. Checklist AM (in / tick khi làm)

**Trước buổi tư vấn**

- [ ] Đã đọc task Lead `form_data` + Intake `#id` (BANT, decision, ai_summary)
- [ ] Biết Decision Maker + 3 cam kết KH (từ Intake)
- [ ] KH đã gửi / hẹn gửi tài liệu L2 (xem mục 6)
- [ ] SP kỹ thuật được mời nếu cần (SEO, Ads, dev)

**Trong buổi tư vấn**

- [ ] Audit/discovery theo **task title** dịch vụ (phụ lục)
- [ ] Điền **đủ form fields** trên task Consult
- [ ] Chạy **AI Hỗ trợ** → đọc output → bổ sung notes

**Sau buổi tư vấn**

- [ ] Tick ✓ task Consult
- [ ] Chuyển **→ Báo giá** trong 48h
- [ ] Ghi timeline case / reminder nếu KH hứa gửi thêm tài liệu

---

## 6. Tài liệu cần thu (lớp L2)

| Nhóm dịch vụ | Tài liệu buổi Consult |
|--------------|------------------------|
| SEO / AEO | URL, GSC read, GA4, danh sách từ khóa, 2–3 đối thủ |
| SEO Local | Link GBP, NAP chi nhánh, ảnh cửa hàng |
| SEO Audit | GSC, GA4, hosting (nếu technical) |
| Quản trị web | Admin WP/hosting, backup status |
| Thiết kế / LP / Web TG | Brand assets, sitemap, refs URL, nội dung draft |
| Facebook / Google Ads | Ads account, pixel/conversion, LP URL, spend history |
| Thuê TK Ads | Lịch sử policy, sản phẩm QC, landing compliance |
| Content | Content hiện có, brand voice, competitor content |

Chi tiết từng dịch vụ: slide **Checklist Lead** trong [Checklist_Tiep_Nhan_Lead_12_Dich_Vu.pptx](../Checklist_Tiep_Nhan_Lead_12_Dich_Vu.pptx).

---

## 7. Thao tác CRM

| Thao tác | Đường dẫn |
|----------|-----------|
| Mở workflow KH | CRM → Service Delivery → click card → `/crm/service-delivery/<id>` |
| Tab **Tư vấn** | Trên workflow → chọn tab Tư vấn |
| Lưu form | Tự lưu khi blur field (debounce) |
| AI Hỗ trợ | Nút trên task card Consult |
| Chuyển stage | Nút **Chuyển → Báo giá** (khi Consult ✓) |

**Sau Phase C1 (code):** panel **Consult Brief** hiển thị tóm tắt Lead — không cần mở lại tab Lead.

---

## 8. Escalation

| Tình huống | Escalate |
|------------|----------|
| Deal > ngưỡng nội bộ / enterprise | Director tham gia Consult |
| No-Go nhưng AM muốn Consult | Director approve + lý do |
| KH không gửi tài liệu >7 ngày | Sales lead + quyết định pause lifecycle |
| Scope vượt budget đã qualify | Họp lại Lead Intake hoặc Proposal scope thu hẹp |

---

## 9. KPI cá nhân (tham chiếu)

- Consult task hoàn thành trong 7 ngày kể từ khi vào stage
- Consult → Proposal ≤48h sau meeting
- Form Consult điền đủ 100% fields trước khi tick ✓

---

## 10. Tài liệu liên quan

- [Training slide deck](../Consult_Stage_Service_Delivery.pptx)
- [Hướng dẫn buổi training](./consult-stage-training-guide.md)
- [Task Consult 12 dịch vụ](./consult-stage-service-tasks.md)
- [Lead Intake forms](../forms/lead-intake/README.md)

---

*PTT Advertising Solutions · CRM Service Delivery*
