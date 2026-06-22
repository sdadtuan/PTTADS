# Spec Dịch vụ SEO Audit

**Slug:** `dich-vu-seo-audit`
**Nhóm:** Tìm kiếm tự nhiên
**Mô tả:** Rà soát toàn diện website, chỉ rõ ưu tiên kỹ thuật và nội dung cần sửa để cải thiện khả năng index và ranking.

---

## 1. Tổng quan

**Đối tượng khách hàng:**
- Doanh nghiệp đang chạy SEO nhưng không thấy kết quả rõ
- Website mới muốn kiểm tra nền tảng trước khi đầu tư SEO
- KH sau sự cố (update thuật toán, traffic tụt đột ngột)

**Gói tham chiếu:** Dự án 1 lần (one-time), có thể đi kèm gói triển khai SEO tổng thể.

**Cam kết cốt lõi:** Bàn giao bảng ưu tiên hành động đầy đủ đúng hạn, 100% lỗi critical được chỉ rõ.

---

## 2. Vòng đời khách hàng

### Giai đoạn 1 — Lead & Tiếp nhận (Ngày 0)
- KH liên hệ: traffic tụt, không biết vì sao, muốn review lại SEO
- **AI (crm_ai_qualify.py):** Chấm điểm, gán tag `seo-audit`, phát hiện dấu hiệu urgency (traffic tụt / penalty)
- AM phản hồi **≤ 2h**

### Giai đoạn 2 — Tư vấn & Phân tích nhu cầu (Ngày 1–3)
- AM meeting: lịch sử website, vấn đề đang gặp, quy mô site (số trang)
- **AI (Claude):** Crawl sơ bộ website, phát hiện 5–10 lỗi nhanh để show KH trong meeting, đánh giá độ phức tạp audit
- Xác định phạm vi audit: technical only hay bao gồm content, backlink

### Giai đoạn 3 — Báo giá & Ký hợp đồng (Ngày 3–5)
- AM soạn proposal: phạm vi audit, timeline 2–3 tuần, format bàn giao
- **AI (Claude):** Draft proposal, ước tính khối lượng theo quy mô site
- Ký HĐ → bắt đầu ngay

### Giai đoạn 4 — Onboarding & Kickoff (Ngày 1 sau ký)
- Thu thập: access GSC, GA4, CMS (nếu cần), danh sách trang ưu tiên
- **AI (Claude):** Checklist audit, soạn kế hoạch kiểm tra chi tiết theo từng hạng mục
- Kickoff brief: xác nhận phạm vi, deadline từng phần

### Giai đoạn 5 — Triển khai Audit (Tuần 1–3)
- **Tuần 1 — Technical:** Crawl toàn site, kiểm tra index, redirect, sitemap, robots, tốc độ, mobile
- **AI (Claude):** Tổng hợp lỗi, phân loại critical/warning/info, viết mô tả và hướng dẫn fix từng lỗi
- **Tuần 2 — On-page & Content:** Kiểm tra meta, heading, trùng lặp, internal link, từ khóa
- **AI (Claude):** Đánh giá chất lượng nội dung, phát hiện thin content, đề xuất cải thiện
- **Tuần 3 — Backlink & Tổng hợp:** Phân tích profile backlink, so sánh đối thủ, tổng hợp bảng ưu tiên
- **AI (Claude):** Tạo bảng ưu tiên hành động theo ma trận impact × effort, draft tóm tắt điều hành

### Giai đoạn 6 — Nghiệm thu & Bàn giao (Cuối tuần 3)
- **AI (Claude):** Tạo báo cáo audit hoàn chỉnh: tóm tắt, bảng ưu tiên, phụ lục kỹ thuật
- AM present kết quả với KH (meeting 60 phút)
- KH ký biên bản nghiệm thu
- Upsell: gợi ý gói SEO tổng thể để triển khai theo bảng ưu tiên

### Giai đoạn 7 — Chăm sóc sau bàn giao
- AM follow-up sau 2 tuần: KH có câu hỏi về báo cáo không
- **AI:** Gợi ý upsell gói SEO tổng thể nếu KH chưa triển khai sau 30 ngày
- Gửi email nhắc kiểm tra lại sau 3 tháng (health check nhẹ)

---

## 3. Phân công (RACI)

| Giai đoạn | AM | SP SEO | AI | QA | DIR |
|-----------|----|----|----|----|-----|
| Lead tiếp nhận | R | — | C | — | I |
| Tư vấn | R | C | C | — | I |
| Báo giá | R | C | C | — | A |
| Ký HĐ | R | — | I | — | A |
| Onboarding | R | C | C | — | I |
| Technical audit | I | R | C | A | I |
| Content audit | I | R | C | A | I |
| Tổng hợp & bảng ưu tiên | I | R | C | A | I |
| Present & nghiệm thu | R | C | C | — | I |
| Follow-up & upsell | R | I | C | — | A |

---

## 4. AI Integration

| Giai đoạn | AI làm gì | Tool |
|-----------|-----------|------|
| Lead | Chấm điểm, phát hiện urgency | `crm_ai_qualify.py` |
| Tư vấn | Crawl sơ bộ, phát hiện lỗi nhanh | Claude API |
| Proposal | Draft proposal, ước tính khối lượng | Claude API |
| Onboarding | Checklist audit chi tiết | Claude API |
| Technical | Phân loại lỗi, mô tả + hướng dẫn fix | Claude API |
| Content | Đánh giá chất lượng, phát hiện thin content | Claude API |
| Tổng hợp | Bảng ưu tiên impact×effort, tóm tắt điều hành | Claude API |
| Follow-up | Gợi ý upsell theo thời điểm | Claude API + `crm_care.py` |

---

## 5. SLA & Timeline

| Mốc | Thời gian |
|-----|-----------|
| Phản hồi lead | ≤ 2h giờ hành chính |
| Gửi proposal | ≤ 2 ngày |
| Kickoff → Bàn giao báo cáo | **2–3 tuần** (tùy quy mô site) |
| Follow-up sau bàn giao | 2 tuần |
| Nhắc health check | 3 tháng sau |

---

## 6. KPI Nội bộ (Team)

| KPI | Người chịu trách nhiệm | Ngưỡng tốt |
|-----|----------------------|------------|
| Convert lead → HĐ | AM | ≥ 35% |
| Bàn giao đúng hạn | SP + QA | ≥ 95% |
| CSAT sau present | AM | ≥ 4.3/5 |
| Upsell sang SEO tổng thể | AM | ≥ 40% KH audit |
| AI usage rate | SP | ≥ 80% tasks |

---

## 7. KPI Cam kết với Khách hàng

| KPI | Ngưỡng cam kết | Đo bằng |
|-----|---------------|---------|
| Báo cáo bàn giao đúng hạn | 100% | Timeline HĐ |
| 100% lỗi critical được chỉ rõ | 0 bỏ sót critical | QA checklist |
| Bảng ưu tiên đầy đủ | ≥ 20 hành động có impact/effort | Audit report |
| Hướng dẫn fix rõ ràng | Mỗi lỗi critical có hướng dẫn cụ thể | Review bởi QA |
| Present kết quả | Có meeting giải thích (không chỉ gửi file) | Lịch CRM |
