# Spec Dịch vụ Thiết kế Website

**Slug:** `thiet-ke-website`
**Nhóm:** Thiết kế
**Mô tả:** Thiết kế giao diện website chuyên nghiệp, tối ưu trải nghiệm người dùng và chuyển đổi cho thương hiệu.

---

## 1. Tổng quan

**Đối tượng khách hàng:**
- Doanh nghiệp cần redesign website cũ không còn phù hợp
- Thương hiệu muốn nâng cấp giao diện theo brand mới
- KH cần website tối ưu chuyển đổi kết hợp với SEO / Ads

**Gói tham chiếu:** Dự án theo milestone (wireframe → design → bàn giao file).

**Cam kết cốt lõi:** Bàn giao đúng milestone, PageSpeed ≥ 85 mobile, chuẩn SEO kỹ thuật cơ bản.

---

## 2. Vòng đời khách hàng

### Giai đoạn 1 — Lead & Tiếp nhận (Ngày 0)
- KH liên hệ: muốn làm mới website, không hài lòng giao diện cũ
- **AI (crm_ai_qualify.py):** Chấm điểm, gán tag `thiet-ke-website`, phát hiện nhu cầu: redesign / mới hoàn toàn
- AM phản hồi **≤ 2h**

### Giai đoạn 2 — Tư vấn & Phân tích nhu cầu (Ngày 1–3)
- AM meeting: ngành, brand guideline hiện có, tham khảo design KH thích, mục tiêu chuyển đổi
- **AI (Claude):** Phân tích website hiện tại KH (nếu có), benchmarking 3 website đối thủ/tham khảo trong ngành, tóm tắt insight cho SP Designer
- SP Designer tham gia nếu cần demo portfolio

### Giai đoạn 3 — Báo giá & Ký hợp đồng (Ngày 3–7)
- AM soạn proposal: phạm vi trang, số vòng chỉnh sửa, timeline milestone
- **AI (Claude):** Draft proposal, tóm tắt yêu cầu từ meeting, checklist deliverable
- DIR duyệt → ký HĐ

### Giai đoạn 4 — Onboarding & Kickoff (Ngày 1–2 sau ký)
- Thu thập: brand guideline, logo, màu sắc, font, ảnh sản phẩm, nội dung trang
- **AI (Claude):** Tạo design brief tổng hợp từ thông tin thu thập, gợi ý tone & mood phù hợp, agenda kickoff
- Kickoff: xác nhận sitemap, trang ưu tiên, lịch milestone

### Giai đoạn 5 — Triển khai (Tuần 1–7)
- **Tuần 1–2 — Wireframe:** SP tạo wireframe từng trang chính
- **AI (Claude):** Review wireframe theo UX best practices, gợi ý cải thiện luồng chuyển đổi
- **Tuần 3–5 — UI Design:** SP thiết kế theo brand, responsive mobile
- **AI (Claude):** Kiểm tra accessibility cơ bản, consistency brand, gợi ý copy cho các section
- **Tuần 6–7 — Handoff & review:** QA kiểm tra file, KH review → chỉnh sửa ≤ 2 vòng

### Giai đoạn 6 — Nghiệm thu & Bàn giao (Cuối tuần 7)
- Bàn giao: file thiết kế (Figma), style guide, hướng dẫn cập nhật nội dung
- **AI (Claude):** Báo cáo nghiệm thu: checklist deliverable, ghi chú kỹ thuật cho developer
- KH ký biên bản nghiệm thu
- Upsell: gợi ý gói Website trọn gói (code + go-live) hoặc Quản trị website

### Giai đoạn 7 — Chăm sóc sau bàn giao
- AM follow-up sau 2 tuần: KH có câu hỏi về handoff không
- **AI:** Gợi ý upsell gói phát triển / quản trị sau 30 ngày
- Hỗ trợ kỹ thuật nhỏ trong 30 ngày bảo hành

---

## 3. Phân công (RACI)

| Giai đoạn | AM | SP Designer | AI | QA | DIR |
|-----------|----|----|----|----|-----|
| Lead tiếp nhận | R | — | C | — | I |
| Tư vấn | R | C | C | — | I |
| Báo giá | R | C | C | — | A |
| Ký HĐ | R | — | I | — | A |
| Onboarding / Brief | R | C | C | — | I |
| Wireframe | I | R | C | A | I |
| UI Design | I | R | C | A | I |
| Review & chỉnh sửa | C | R | C | A | I |
| Nghiệm thu / Bàn giao | R | C | C | A | I |
| Follow-up & upsell | R | I | C | — | A |

---

## 4. AI Integration

| Giai đoạn | AI làm gì | Tool |
|-----------|-----------|------|
| Lead | Chấm điểm, phân loại redesign vs mới | `crm_ai_qualify.py` |
| Tư vấn | Phân tích website KH, benchmark đối thủ | Claude API |
| Proposal | Draft proposal, checklist deliverable | Claude API |
| Onboarding | Design brief tổng hợp, gợi ý tone & mood | Claude API |
| Wireframe | Review UX, gợi ý luồng chuyển đổi | Claude API |
| UI Design | Kiểm tra accessibility, consistency, copy | Claude API |
| Nghiệm thu | Báo cáo, ghi chú kỹ thuật cho developer | Claude API |
| Follow-up | Gợi ý upsell theo thời điểm | Claude API + `crm_care.py` |

---

## 5. SLA & Timeline

| Mốc | Thời gian |
|-----|-----------|
| Phản hồi lead | ≤ 2h giờ hành chính |
| Gửi proposal | ≤ 2 ngày |
| Kickoff → Wireframe đầu tiên | **2 tuần** |
| Wireframe → UI hoàn chỉnh | **3 tuần** |
| Review → Bàn giao | **2 tuần** |
| Tổng timeline | **5–7 tuần** |
| Bảo hành sau bàn giao | 30 ngày |

---

## 6. KPI Nội bộ (Team)

| KPI | Người chịu trách nhiệm | Ngưỡng tốt |
|-----|----------------------|------------|
| Convert lead → HĐ | AM | ≥ 35% |
| On-time milestone | SP + QA | ≥ 90% |
| Tỷ lệ > 2 vòng chỉnh sửa | SP | ≤ 20% |
| CSAT sau nghiệm thu | AM | ≥ 4.3/5 |
| Upsell sang code / quản trị | AM | ≥ 50% |
| AI usage rate | SP | ≥ 80% tasks |

---

## 7. KPI Cam kết với Khách hàng

| KPI | Ngưỡng cam kết | Đo bằng |
|-----|---------------|---------|
| Bàn giao đúng milestone | 100% | Timeline HĐ |
| PageSpeed Score (nếu có code) | ≥ 85 mobile | PageSpeed Insights |
| Responsive trên 3 breakpoint | 100% trang | QA checklist |
| File Figma bàn giao đầy đủ | 100% trang trong phạm vi | Review bởi QA |
| Số vòng chỉnh sửa | ≤ 2 vòng trong HĐ | Lịch sử file |
