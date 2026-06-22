# Spec Dịch vụ Chạy Quảng cáo Google

**Slug:** `quang-cao-google`
**Nhóm:** Quảng cáo kỹ thuật số
**Mô tả:** Tìm kiếm, hiển thị, Performance Max — tư vấn cấu trúc tài khoản và tối ưu liên tục hướng tới mục tiêu chuyển đổi.

---

## 1. Tổng quan

**Đối tượng khách hàng:**
- Doanh nghiệp muốn xuất hiện ngay đầu kết quả tìm kiếm khi KH có nhu cầu
- KH đang chạy Google Ads tự túc nhưng ROAS thấp, chi phí cao
- Thương hiệu cần kết hợp Search + Display + Remarketing theo funnel

**Gói tham chiếu:** Retainer tháng; phí quản lý fixed hoặc % spend.

**Cam kết cốt lõi:** ROAS/CPA theo mục tiêu cam kết, impression share ≥ 60% từ khóa ưu tiên.

---

## 2. Vòng đời khách hàng

### Giai đoạn 1 — Lead & Tiếp nhận (Ngày 0)
- KH liên hệ: muốn chạy Google Ads hoặc đang chạy không hiệu quả
- **AI (crm_ai_qualify.py):** Chấm điểm, gán tag `quang-cao-google`, phân loại (search / shopping / display / PMax)
- AM phản hồi **≤ 2h**

### Giai đoạn 2 — Tư vấn & Phân tích nhu cầu (Ngày 1–3)
- AM meeting: ngành, sản phẩm, website/landing page, ngân sách, mục tiêu (CPA, ROAS, lead)
- **AI (Claude):** Phân tích tài khoản Google Ads hiện tại nếu có, keyword research sơ bộ, ước tính CPL/ROAS theo ngành và ngân sách
- SP Ads tham gia nếu cần tư vấn kỹ thuật cấu trúc tài khoản

### Giai đoạn 3 — Báo giá & Ký hợp đồng (Ngày 3–5)
- AM soạn proposal: cấu trúc campaign, KPI cam kết theo tháng, quy trình báo cáo
- **AI (Claude):** Draft proposal, forecast click/conversion theo ngân sách, bảng từ khóa ưu tiên
- DIR duyệt → ký HĐ

### Giai đoạn 4 — Onboarding & Kickoff (Ngày 1–3 sau ký)
- Thu thập: access Google Ads, GA4, Merchant Center (nếu có), conversion tracking
- **AI (Claude):** Kiểm tra conversion tracking, tạo keyword list phân nhóm, media plan tháng 1, gợi ý cấu trúc campaign
- Kickoff: xác nhận từ khóa ưu tiên, bài trừ, ngân sách phân bổ theo campaign

### Giai đoạn 5 — Triển khai (Ngày 3–5 setup, hàng tháng tối ưu)
- **Tuần 1 — Setup:** Cấu trúc campaign/ad group, từ khóa, bài trừ, ad copy, extensions, tracking
- **AI (Claude):** Viết responsive search ads (headlines + descriptions) cho từng nhóm, gợi ý extensions, kiểm tra Quality Score tiềm năng
- **Tuần 2+ — Tối ưu:** Theo dõi search terms, negative keywords, bid adjustment, Quality Score
- **AI (Claude):** Phân tích search term report, gợi ý negative keyword mới, flagging từ khóa lãng phí
- **Hàng tháng:** Review tổng thể, điều chỉnh strategy theo mùa vụ / thay đổi thị trường

### Giai đoạn 6 — Báo cáo (Hàng tuần + Hàng tháng)
- **AI (Claude + crm_daily_work_report.py):** Báo cáo tuần: impressions, clicks, CTR, CPC, conversions, spend
- **AI:** Báo cáo tháng: so sánh KPI vs cam kết, phân tích nguyên nhân, kế hoạch tháng tiếp
- AM review → bổ sung nhận xét → gửi KH

### Giai đoạn 7 — Chăm sóc & Gia hạn (Hàng tháng)
- **AI (crm_care.py):** Alert khi CPA vượt ngưỡng 20%, Quality Score tụt, impression share giảm → AM xử lý trong 24h
- AM gợi ý tăng budget khi ROAS tốt; đề xuất mở rộng sang Display / PMax / Shopping nếu phù hợp
- Nhắc gia hạn trước 30 ngày

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
| Gia hạn / Scale | R | C | C | — | A |

---

## 4. AI Integration

| Giai đoạn | AI làm gì | Tool |
|-----------|-----------|------|
| Lead | Chấm điểm, phân loại loại campaign | `crm_ai_qualify.py` |
| Tư vấn | Phân tích tài khoản, keyword research, forecast | Claude API |
| Proposal | Draft proposal, keyword list, forecast | Claude API |
| Onboarding | Kiểm tra tracking, keyword phân nhóm, media plan | Claude API |
| Setup | RSA ad copy, extensions, quality score check | Claude API |
| Tối ưu | Search term analysis, negative keywords, flagging | Claude API |
| Báo cáo | Báo cáo tuần/tháng tự động | Claude API + `crm_daily_work_report.py` |
| Chăm sóc | Alert CPA/impression share, nhắc upsell | `crm_care.py` |

---

## 5. SLA & Timeline

| Mốc | Thời gian |
|-----|-----------|
| Phản hồi lead | ≤ 2h giờ hành chính |
| Gửi proposal | ≤ 2 ngày |
| Kickoff → Campaign live | **3–5 ngày** |
| Báo cáo tuần | Thứ Hai hàng tuần |
| Báo cáo tháng | Trước ngày 5 |
| Xử lý alert CPA vượt ngưỡng | ≤ 24h |
| Nhắc gia hạn | Trước 30 ngày |

---

## 6. KPI Nội bộ (Team)

| KPI | Người chịu trách nhiệm | Ngưỡng tốt |
|-----|----------------------|------------|
| Convert lead → HĐ | AM | ≥ 35% |
| Campaign live đúng hạn | SP Ads | ≥ 95% |
| KH đạt KPI CPA/ROAS cam kết | SP Ads | ≥ 70% tháng |
| CSAT tháng | AM | ≥ 4.2/5 |
| Tỷ lệ gia hạn | AM | ≥ 70% |
| Negative keyword được review | SP | 100% tuần |

---

## 7. KPI Cam kết với Khách hàng

| KPI | Ngưỡng cam kết | Đo bằng |
|-----|---------------|---------|
| ROAS hoặc CPA | Theo cam kết HĐ, đạt ≥ 70% tháng | Google Ads |
| Impression share từ khóa ưu tiên | ≥ 60% | Google Ads |
| Spend đúng ngân sách | Sai số ≤ 5% | Google Ads |
| Quality Score từ khóa ưu tiên | ≥ 7/10 | Google Ads |
| Báo cáo tuần đúng hạn | 100% | Lịch gửi |
| Báo cáo tháng đúng hạn | 100% | Lịch gửi |
