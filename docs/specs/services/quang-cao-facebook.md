# Spec Dịch vụ Chạy Quảng cáo Facebook

**Slug:** `quang-cao-facebook`
**Nhóm:** Quảng cáo kỹ thuật số
**Mô tả:** Lập kế hoạch, triển khai và tối ưu quảng cáo trên hệ thống Meta (Facebook, Instagram) hướng tới mục tiêu chuyển đổi cụ thể.

---

## 1. Tổng quan

**Đối tượng khách hàng:**
- Doanh nghiệp muốn tăng lead / doanh số qua Facebook / Instagram
- KH đang tự chạy nhưng tốn chi phí, không tối ưu được
- Brand mới cần xây dựng nhận diện và thu lead ban đầu

**Gói tham chiếu:** Retainer tháng theo ngân sách Ads; phí quản lý tính theo % spend hoặc fixed fee.

**Cam kết cốt lõi:** CTR ≥ ngưỡng ngành, CPL đạt mục tiêu đã cam kết theo từng giai đoạn.

---

## 2. Vòng đời khách hàng

### Giai đoạn 1 — Lead & Tiếp nhận (Ngày 0)
- KH liên hệ: muốn chạy Facebook Ads, đang chạy không hiệu quả
- **AI (crm_ai_qualify.py):** Chấm điểm, gán tag `quang-cao-facebook`, phân loại mục tiêu (lead / traffic / sales)
- AM phản hồi **≤ 2h**

### Giai đoạn 2 — Tư vấn & Phân tích nhu cầu (Ngày 1–3)
- AM meeting: ngành, sản phẩm, ngân sách, mục tiêu KPI (CPL, ROAS), tài khoản hiện có
- **AI (Claude):** Phân tích tài khoản Ads hiện tại nếu KH share, benchmark CPL ngành, đề xuất cấu trúc campaign sơ bộ, tệp đối tượng
- SP Ads tham gia nếu cần review kỹ thuật tài khoản

### Giai đoạn 3 — Báo giá & Ký hợp đồng (Ngày 3–5)
- AM soạn proposal: phí quản lý, KPI cam kết theo từng tháng, quy trình báo cáo
- **AI (Claude):** Draft proposal, benchmark CPL theo ngành, dự báo kết quả theo ngân sách
- DIR duyệt → ký HĐ

### Giai đoạn 4 — Onboarding & Kickoff (Ngày 1–3 sau ký)
- Thu thập: access Business Manager, pixel, tài sản quảng cáo (ảnh, video), landing page
- **AI (Claude):** Kiểm tra pixel, cấu hình sự kiện, tạo media plan tháng 1, gợi ý creative brief
- Kickoff: xác nhận mục tiêu, ngân sách phân bổ, lịch báo cáo

### Giai đoạn 5 — Triển khai (Ngày 3–5 setup, hàng tháng tối ưu)
- **Tuần 1 — Setup:** Cấu trúc campaign (Awareness / Consideration / Conversion), tệp đối tượng, creative
- **AI (Claude):** Viết ad copy cho từng campaign và mục tiêu, generate variation A/B, gợi ý hook cho video/ảnh
- **Tuần 2+ — Tối ưu:** Theo dõi daily, điều chỉnh ngân sách theo hiệu quả, tắt ad kém, scale ad tốt
- **AI (Claude):** Phân tích performance hàng tuần, flagging bất thường (CPC tăng đột biến, CTR tụt), gợi ý tối ưu cụ thể
- QA review creative và cấu trúc trước khi chạy lần đầu

### Giai đoạn 6 — Báo cáo (Hàng tuần + Hàng tháng)
- **AI (Claude + crm_daily_work_report.py):** Báo cáo tuần tự động: reach, CTR, CPL, spend, lead
- **AI:** Báo cáo tháng đầy đủ: so sánh KPI cam kết vs thực tế, phân tích nguyên nhân, kế hoạch tháng tiếp
- AM review → bổ sung nhận xét → gửi KH

### Giai đoạn 7 — Chăm sóc & Gia hạn (Hàng tháng)
- **AI (crm_care.py):** Alert khi CPL vượt ngưỡng 20% so cam kết → AM xử lý trong 24h
- Alert khi tài khoản có dấu hiệu vi phạm chính sách → xử lý ngay
- AM gợi ý tăng ngân sách khi ROAS tốt; scale creative winner
- Nhắc gia hạn trước 30 ngày, gợi ý gói Google Ads bổ sung

---

## 3. Phân công (RACI)

| Giai đoạn | AM | SP Ads | AI | QA | DIR |
|-----------|----|----|----|----|-----|
| Lead tiếp nhận | R | — | C | — | I |
| Tư vấn | R | C | C | — | I |
| Báo giá | R | C | C | — | A |
| Ký HĐ | R | — | I | — | A |
| Onboarding / Kickoff | R | C | C | — | I |
| Setup campaign | I | R | C | A | I |
| Tối ưu hàng tuần | I | R | C | A | I |
| Báo cáo tuần | R | C | C | — | I |
| Báo cáo tháng | R | C | C | — | A |
| Xử lý vi phạm chính sách | R | R | C | — | A |
| Gia hạn / Scale | R | C | C | — | A |

---

## 4. AI Integration

| Giai đoạn | AI làm gì | Tool |
|-----------|-----------|------|
| Lead | Chấm điểm, phân loại mục tiêu | `crm_ai_qualify.py` |
| Tư vấn | Phân tích tài khoản, benchmark CPL, cấu trúc sơ bộ | Claude API |
| Proposal | Draft proposal, dự báo kết quả | Claude API |
| Onboarding | Kiểm tra pixel, media plan, creative brief | Claude API |
| Setup | Ad copy, A/B variation, gợi ý hook | Claude API |
| Tối ưu | Phân tích performance, flagging bất thường | Claude API |
| Báo cáo | Báo cáo tuần/tháng tự động | Claude API + `crm_daily_work_report.py` |
| Chăm sóc | Alert CPL vượt ngưỡng, vi phạm chính sách | `crm_care.py` |

---

## 5. SLA & Timeline

| Mốc | Thời gian |
|-----|-----------|
| Phản hồi lead | ≤ 2h giờ hành chính |
| Gửi proposal | ≤ 2 ngày |
| Kickoff → Campaign live | **3–5 ngày** |
| Báo cáo tuần | Thứ Hai hàng tuần |
| Báo cáo tháng | Trước ngày 5 |
| Xử lý alert CPL vượt ngưỡng | ≤ 24h |
| Xử lý vi phạm chính sách | ≤ 4h |
| Nhắc gia hạn | Trước 30 ngày |

---

## 6. KPI Nội bộ (Team)

| KPI | Người chịu trách nhiệm | Ngưỡng tốt |
|-----|----------------------|------------|
| Convert lead → HĐ | AM | ≥ 35% |
| Campaign live đúng hạn | SP Ads | ≥ 95% |
| Tỷ lệ KH đạt KPI CPL cam kết | SP Ads | ≥ 70% tháng |
| CSAT tháng | AM | ≥ 4.2/5 |
| Tỷ lệ gia hạn | AM | ≥ 70% |
| AI copy usage rate | SP | 100% campaigns |
| Thời gian xử lý vi phạm | SP | ≤ 4h |

---

## 7. KPI Cam kết với Khách hàng

| KPI | Ngưỡng cam kết | Đo bằng |
|-----|---------------|---------|
| CTR | ≥ ngưỡng ngành (thường ≥ 1.5% với traffic) | Meta Ads Manager |
| CPL (Cost per Lead) | Theo cam kết trong HĐ, đạt ≥ 70% tháng | Meta Ads Manager |
| Spend đúng ngân sách | Sai số ≤ 5% so kế hoạch | Meta Ads Manager |
| Báo cáo tuần đúng hạn | 100% | Lịch gửi |
| Báo cáo tháng đúng hạn | 100% | Lịch gửi |
| 0 vi phạm chính sách do lỗi setup | 0 | Account health |
