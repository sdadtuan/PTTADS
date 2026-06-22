# Spec Dịch vụ Thiết kế Landing Page

**Slug:** `thiet-ke-landing-page`
**Nhóm:** Thiết kế
**Mô tả:** Trang đích tập trung chuyển đổi, phù hợp chiến dịch quảng cáo, ra mắt sản phẩm hoặc thu thập lead.

---

## 1. Tổng quan

**Đối tượng khách hàng:**
- KH đang chạy Ads cần landing page tối ưu chuyển đổi
- Doanh nghiệp ra mắt sản phẩm / sự kiện cần trang đích nhanh
- KH muốn test CRO trước khi đầu tư website đầy đủ

**Gói tham chiếu:** Dự án 1 lần, bàn giao nhanh theo lịch media/campaign.

**Cam kết cốt lõi:** Bàn giao đúng lịch campaign, tốc độ tải ≤ 2.5s, form hoạt động 100%.

---

## 2. Vòng đời khách hàng

### Giai đoạn 1 — Lead & Tiếp nhận (Ngày 0)
- KH liên hệ: cần landing page gấp cho chiến dịch Ads sắp chạy
- **AI (crm_ai_qualify.py):** Chấm điểm, gán tag `landing-page`, phát hiện urgency (deadline campaign)
- AM phản hồi **≤ 2h** — nếu deadline gấp < 5 ngày thì phản hồi **≤ 1h**

### Giai đoạn 2 — Tư vấn & Phân tích nhu cầu (Ngày 1)
- AM meeting nhanh (30 phút): mục tiêu chuyển đổi (form / gọi / mua), deadline, ngân sách Ads, brand
- **AI (Claude):** Phân tích 2–3 landing page tham khảo trong ngành, gợi ý cấu trúc trang theo mục tiêu chuyển đổi, copy hero section sơ bộ
- Xác định nhanh: số section, CTA chính, form fields

### Giai đoạn 3 — Báo giá & Ký hợp đồng (Ngày 1–2)
- AM gửi proposal gọn: phạm vi, timeline, giá
- **AI (Claude):** Draft proposal nhanh, wireframe text-based để KH hình dung cấu trúc
- Ký HĐ → bắt đầu ngay

### Giai đoạn 4 — Onboarding & Brief (Ngày 1 sau ký)
- Thu thập: brand guideline, ảnh sản phẩm, nội dung USP, thông tin form, tracking pixel
- **AI (Claude):** Tạo brief thiết kế chi tiết, viết copy đề xuất cho các section, checklist tracking
- Brief duyệt → SP Designer bắt đầu

### Giai đoạn 5 — Triển khai (Tuần 1–2)
- **Ngày 1–3 — Design:** SP Designer thiết kế layout tập trung chuyển đổi
- **AI (Claude):** Viết copy tất cả các section (headline, subheadline, bullet points, CTA), kiểm tra tính nhất quán với Ads creative
- **Ngày 4–7 — Code & tích hợp:** Developer code, cài form, tracking pixel, tốc độ tối ưu
- **Ngày 8–10 — Review & sửa:** KH review → 1–2 vòng chỉnh sửa nhỏ
- QA: mobile, tốc độ, form submit, tracking events

### Giai đoạn 6 — Nghiệm thu & Bàn giao (Cuối tuần 2)
- **AI (Claude):** Báo cáo nghiệm thu: PageSpeed, form test, tracking events checklist
- Bàn giao: URL live, access CMS/code, hướng dẫn cập nhật
- KH ký nghiệm thu

### Giai đoạn 7 — Chăm sóc (30 ngày sau)
- **AI (crm_care.py):** Monitor form submissions, alert nếu form lỗi
- AM follow-up sau 2 tuần: performance campaign, tỷ lệ chuyển đổi
- Gợi ý A/B test hoặc update landing page theo dữ liệu Ads thực tế

---

## 3. Phân công (RACI)

| Giai đoạn | AM | SP Designer | SP Dev | AI | QA | DIR |
|-----------|----|----|----|----|----|----|
| Lead tiếp nhận | R | — | — | C | — | I |
| Tư vấn | R | C | — | C | — | I |
| Báo giá | R | C | — | C | — | A |
| Onboarding / Brief | R | C | — | C | — | I |
| Design | I | R | — | C | A | I |
| Code & tracking | I | — | R | C | A | I |
| Review & sửa | C | R | C | C | A | I |
| Nghiệm thu | R | C | C | C | A | I |
| Follow-up | R | — | — | C | — | I |

---

## 4. AI Integration

| Giai đoạn | AI làm gì | Tool |
|-----------|-----------|------|
| Lead | Chấm điểm, phát hiện deadline gấp | `crm_ai_qualify.py` |
| Tư vấn | Phân tích LP tham khảo, gợi ý cấu trúc, hero copy | Claude API |
| Proposal | Draft proposal nhanh, wireframe text | Claude API |
| Brief | Brief thiết kế, copy đề xuất tất cả section | Claude API |
| Design | Kiểm tra consistency với Ads creative | Claude API |
| Nghiệm thu | Báo cáo: speed, form, tracking | Claude API |
| Chăm sóc | Monitor form, gợi ý A/B test | `crm_care.py` |

---

## 5. SLA & Timeline

| Mốc | Thời gian |
|-----|-----------|
| Phản hồi lead (bình thường) | ≤ 2h giờ hành chính |
| Phản hồi lead (deadline gấp) | ≤ 1h |
| Gửi proposal | ≤ 1 ngày |
| Kickoff → Design draft | **3 ngày** |
| Design → Live | **1 tuần** |
| Tổng timeline chuẩn | **1–2 tuần** |
| Bảo hành sau go-live | 14 ngày |

---

## 6. KPI Nội bộ (Team)

| KPI | Người chịu trách nhiệm | Ngưỡng tốt |
|-----|----------------------|------------|
| Convert lead → HĐ | AM | ≥ 40% |
| Bàn giao đúng lịch campaign | SP + QA | ≥ 95% |
| PageSpeed ≥ 85 | SP Dev | ≥ 95% LP |
| CSAT sau bàn giao | AM | ≥ 4.3/5 |
| Thời gian phản hồi lead urgency | AM | ≤ 1h |
| AI copy usage rate | SP | 100% LP |

---

## 7. KPI Cam kết với Khách hàng

| KPI | Ngưỡng cam kết | Đo bằng |
|-----|---------------|---------|
| Bàn giao đúng lịch campaign | Trước ngày chạy Ads | Timeline HĐ |
| Tốc độ tải | ≤ 2.5s (LCP) | PageSpeed |
| Form hoạt động 100% | 0 lỗi submit | QA test |
| Tracking pixel kích hoạt | 100% events đúng | Meta Pixel Helper / GTM |
| Responsive mobile | 100% | QA checklist |
