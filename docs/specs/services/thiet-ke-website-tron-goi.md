# Spec Dịch vụ Thiết kế Website Trọn gói

**Slug:** `thiet-ke-website-tron-goi`
**Nhóm:** Thiết kế
**Mô tả:** Gói trọn từ ý tưởng, thiết kế đến triển khai và go-live — một đầu mối, một hợp đồng, ra sản phẩm hoàn chỉnh.

---

## 1. Tổng quan

**Đối tượng khách hàng:**
- Doanh nghiệp cần website hoàn chỉnh, không có IT nội bộ
- Startup / SME muốn nhanh chóng ra website chuẩn marketing
- KH không muốn làm việc với nhiều vendor (designer, developer, host riêng)

**Gói tham chiếu:** Dự án theo milestone (thiết kế → code → go-live → bàn giao).

**Cam kết cốt lõi:** Go-live đúng ngày cam kết, đủ mốc bàn giao theo HĐ.

---

## 2. Vòng đời khách hàng

### Giai đoạn 1 — Lead & Tiếp nhận (Ngày 0)
- KH liên hệ: cần làm website từ đầu đến cuối, cần 1 đơn vị làm hết
- **AI (crm_ai_qualify.py):** Chấm điểm, gán tag `thiet-ke-tron-goi`, phân loại quy mô (landing / brochure / e-commerce)
- AM phản hồi **≤ 2h**

### Giai đoạn 2 — Tư vấn & Phân tích nhu cầu (Ngày 1–3)
- AM meeting: ngành, mục tiêu website, tính năng cần có, nền tảng (WordPress / custom), hosting
- **AI (Claude):** Phân tích yêu cầu, gợi ý stack kỹ thuật phù hợp, benchmark 3 website tham khảo trong ngành
- SP Designer + Developer cùng tham gia nếu cần tư vấn kỹ thuật

### Giai đoạn 3 — Báo giá & Ký hợp đồng (Ngày 3–7)
- AM soạn proposal: sitemap, tính năng, timeline 8–12 tuần, mốc thanh toán
- **AI (Claude):** Draft proposal, bảng milestone chi tiết, checklist tính năng
- DIR duyệt → ký HĐ → nhận đặt cọc

### Giai đoạn 4 — Onboarding & Kickoff (Ngày 1–2 sau ký)
- Thu thập: brand guideline, nội dung, domain, hosting info
- **AI (Claude):** Tạo brief tổng hợp, kế hoạch triển khai chi tiết theo tuần, agenda kickoff
- Kickoff meeting: xác nhận sitemap cuối, tech stack, lịch milestone và kênh liên lạc

### Giai đoạn 5 — Triển khai (Tuần 1–10)
- **Tuần 1–2 — Wireframe & Sitemap:** SP Designer tạo wireframe, xác nhận luồng trang
- **AI (Claude):** Review wireframe UX, gợi ý cải thiện chuyển đổi, tạo copy placeholder
- **Tuần 3–5 — UI Design:** Thiết kế hoàn chỉnh, KH duyệt
- **Tuần 6–8 — Development:** Developer code theo design đã duyệt
- **AI (Claude):** Review code quality cơ bản, kiểm tra SEO on-page tự động, generate meta/alt text
- **Tuần 9–10 — Testing & go-live prep:** QA toàn diện, KH UAT, sửa bug, cài tracking

### Giai đoạn 6 — Nghiệm thu & Go-live
- QA final checklist: tốc độ, mobile, form, tracking, SSL
- **AI (Claude):** Báo cáo go-live readiness, so sánh vs checklist HĐ
- Go-live → KH ký biên bản → bàn giao access đầy đủ
- Upsell: Quản trị website, SEO tổng thể, Google Ads

### Giai đoạn 7 — Chăm sóc & Bảo hành (30–90 ngày)
- Bảo hành bug miễn phí theo HĐ
- **AI (crm_care.py):** Monitor uptime, alert lỗi, nhắc hết bảo hành và gợi ý gói quản trị
- AM follow-up sau 30 ngày go-live

---

## 3. Phân công (RACI)

| Giai đoạn | AM | SP Designer | SP Dev | AI | QA | DIR |
|-----------|----|----|----|----|----|----|
| Lead tiếp nhận | R | — | — | C | — | I |
| Tư vấn | R | C | C | C | — | I |
| Báo giá | R | C | C | C | — | A |
| Ký HĐ | R | — | — | I | — | A |
| Onboarding / Kickoff | R | C | C | C | — | I |
| Wireframe | I | R | — | C | A | I |
| UI Design | I | R | — | C | A | I |
| Development | I | C | R | C | A | I |
| Testing & UAT | C | C | R | C | A | I |
| Go-live | R | C | R | C | A | A |
| Bảo hành | I | — | R | C | A | I |

---

## 4. AI Integration

| Giai đoạn | AI làm gì | Tool |
|-----------|-----------|------|
| Lead | Chấm điểm, phân loại quy mô | `crm_ai_qualify.py` |
| Tư vấn | Phân tích yêu cầu, benchmark, gợi ý stack | Claude API |
| Proposal | Draft proposal, milestone, checklist tính năng | Claude API |
| Onboarding | Brief tổng hợp, kế hoạch tuần | Claude API |
| Wireframe | Review UX, gợi ý luồng chuyển đổi | Claude API |
| Development | Review code cơ bản, SEO on-page, meta/alt text | Claude API |
| Go-live | Báo cáo readiness, checklist so sánh | Claude API |
| Bảo hành | Monitor uptime, alert lỗi, nhắc upsell | `crm_care.py` |

---

## 5. SLA & Timeline

| Mốc | Thời gian |
|-----|-----------|
| Phản hồi lead | ≤ 2h giờ hành chính |
| Gửi proposal | ≤ 3 ngày |
| Kickoff → Wireframe | **2 tuần** |
| Wireframe → Design duyệt | **3 tuần** |
| Design → Code hoàn chỉnh | **3 tuần** |
| Code → Go-live | **2 tuần** |
| Tổng timeline | **8–12 tuần** |
| Bảo hành sau go-live | 30–90 ngày (theo HĐ) |

---

## 6. KPI Nội bộ (Team)

| KPI | Người chịu trách nhiệm | Ngưỡng tốt |
|-----|----------------------|------------|
| Convert lead → HĐ | AM | ≥ 35% |
| On-time milestone | SP + QA | ≥ 90% |
| Go-live đúng ngày cam kết | SP Dev + QA | ≥ 90% |
| CSAT sau go-live | AM | ≥ 4.3/5 |
| Upsell sang quản trị / SEO | AM | ≥ 60% |
| Bug post-launch trong bảo hành | SP Dev | ≤ 5 bug minor |

---

## 7. KPI Cam kết với Khách hàng

| KPI | Ngưỡng cam kết | Đo bằng |
|-----|---------------|---------|
| Go-live đúng ngày | Đúng ngày trong HĐ ±3 ngày | Timeline |
| PageSpeed mobile | ≥ 85 | PageSpeed Insights |
| Responsive | 100% trang trên mobile/tablet/desktop | QA checklist |
| SSL & HTTPS | 100% trang | Browser check |
| Form & tracking hoạt động | 100% | QA test |
| Bàn giao access đầy đủ | 100% (host, domain, CMS, analytics) | Checklist |
