# Phê duyệt ngưỡng BANT+ — Giai đoạn Lead & Consult

**Phiên bản đề xuất:** 1.0 · 2026-06-30  
**Liên quan:** Lead Intake (`crm_lead_intake.py`) · Consult gate (triển khai C3)

---

## 1. Mục đích

Xác nhận chính thức ngưỡng **Go / Nurture / No-Go** trước khi triển khai gate tự động (Phase C3) và đào tạo AM.

---

## 2. Khung BANT+ (6 tiêu chí)

Mỗi tiêu chí chấm **1–5** (tổng **6–30**):

| Key | Tiêu chí |
|-----|----------|
| budget | Ngân sách / khả năng chi trả |
| authority | Quyền quyết định / access DM |
| need | Nhu cầu / pain rõ |
| timeline | Thời điểm triển khai |
| fit | Fit ICP / dịch vụ PTT |
| history | Lịch sử agency / kỳ vọng realistic |

---

## 3. Ngưỡng đã xác nhận (2026-06-30)

| Tổng điểm | Decision | Hành động Consult |
|-----------|----------|-------------------|
| **≥ 22** | **Go** | Consult đầy đủ → Proposal ≤48h |
| **16 – 21** | **Nurture** | **Không chuyển Consult** — nurture đến Go |
| **< 16** | **No-Go** | Không Consult sâu |
| **≥ 3 red flags** (Intake) | **No-Go** (gợi ý) | Block Consult (Director override) |

> **Chính sách vận hành code (xác nhận 2026-06-30):** Giữ `GO_THRESHOLDS` **24/18** trong CRM (Intake gợi ý, Consult Brief gate hiển thị, C3 gate khi triển khai) **đến khi Director ký §6** sign-off chính thức. Sau ký: cập nhật code thành **22/16** theo Q1 (cùng lúc hoặc ngay trước bật gate C3).

**Nguồn code hiện tại:** `GO_THRESHOLDS = {"go": 24, "nurture_min": 18}` (`crm_lead_intake_definitions.py`).

---

## 4. Quy tắc override

- AM có thể chọn decision khác gợi ý hệ thống.
- **Bắt buộc** điền `decision_reason` trong Lead Intake.
- **No-Go → Consult** (hoặc Go với BANT thấp): cần **Director** approve (gate C3).

---

## 5. Quyết định đã xác nhận (2026-06-30)

| # | Câu hỏi | Quyết định |
|---|---------|------------|
| Q1 | Ngưỡng BANT | **Nới lỏng (mục tiêu sau ký):** Go ≥22 · Nurture 16–21 · No-Go <16 — **code giữ 24/18 đến khi Director ký §6** |
| Q2 | Nurture có được chuyển Consult? | **Không** — block đến khi Go |
| Q3 | No-Go block Lead→Consult? | **Có** — chỉ Director override |
| Q4 | Deal enterprise Director tham gia Consult? | *Chưa xác nhận — bổ sung khi có ngưỡng VND* |
| Q5 | Bắt buộc Intake in_person trước Consult (Go)? | **Có** — block Consult sâu đến khi có PHẦN B completed |
| Q6 | Tư vấn/audit có thu phí riêng? | **Không** — Consult miễn phí; doanh thu PTT chỉ sau ký HĐ |

---

## 6. Phê duyệt

| Vai trò | Họ tên | Chữ ký | Ngày |
|---------|--------|--------|------|
| Director / GM | | | |
| Sales lead | | | |
| CRM admin (tech) | | *(policy ghi nhận qua CRM chat 2026-06-30)* | 2026-06-30 |

**Ghi chú sau họp:**

- 2026-06-30: CRM team xác nhận **giữ ngưỡng code 24/18** cho Intake + Consult Brief + C3 gate cho đến khi Director ký §6. SOP đào tạo AM vẫn dùng khung **22/16** (policy nội bộ).

---

*Sau khi Director ký §6: cập nhật `GO_THRESHOLDS` → 22/16 (nếu Q1 không đổi) rồi bật gate Phase C3.*
