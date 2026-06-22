# Spec Dịch vụ AEO — Answer Engine Optimization

**Slug:** `dich-vu-aeo`
**Nhóm:** Tìm kiếm tự nhiên
**Mô tả:** Tối ưu nội dung và cấu trúc để thương hiệu xuất hiện trong câu trả lời của Google SGE, AI chatbot và các công cụ tìm kiếm thế hệ mới.

---

## 1. Tổng quan

**Đối tượng khách hàng:**
- Doanh nghiệp đang chạy SEO nhưng muốn mở rộng sang AI search
- Thương hiệu trong ngành cạnh tranh cao (BĐS, tài chính, giáo dục, y tế)
- KH đã có website nội dung nhưng chưa tối ưu cấu trúc FAQ/schema

**Gói tham chiếu:** Theo báo giá từng dự án (audit + roadmap + triển khai theo tháng)

**Cam kết cốt lõi:** Cấu trúc nội dung đúng chuẩn AEO, đo được bằng số URL được AI/SGE trích dẫn.

---

## 2. Vòng đời khách hàng

### Giai đoạn 1 — Lead & Tiếp nhận (Ngày 0)
- KH điền form / nhắn Zalo / gọi điện hỏi về SEO hoặc AI search
- **AI (crm_ai_qualify.py):** Chấm điểm lead, gán tag `aeo`, phân loại nhu cầu tự động
- AM nhận thông báo, phản hồi **≤ 2h** giờ hành chính
- Tạo hồ sơ lead trong CRM với thông tin: ngành, website, mục tiêu sơ bộ

### Giai đoạn 2 — Tư vấn & Phân tích nhu cầu (Ngày 1–3)
- AM gọi điện / meeting khám phá (30–45 phút): ngành, đối thủ, mục tiêu traffic/lead
- **AI (Claude):** Phân tích website KH sơ bộ, đánh giá cấu trúc nội dung hiện có, gợi ý 3 ưu tiên AEO ngay trong cuộc họp
- SP SEO tham gia nếu KH hỏi kỹ thuật chuyên sâu
- AM ghi chú brief vào CRM ngay sau meeting

### Giai đoạn 3 — Báo giá & Ký hợp đồng (Ngày 3–7)
- AM soạn proposal gồm: phạm vi, timeline, deliverable, KPI cam kết
- **AI (Claude):** Draft proposal theo template chuẩn PTT, điền số liệu từ phân tích website KH
- DIR duyệt giá nếu giá trị HĐ vượt ngưỡng
- Gửi proposal → KH duyệt → ký HĐ → tạo project trong CRM

### Giai đoạn 4 — Onboarding & Kickoff (Ngày 1–3 sau ký)
- Thu thập: access Google Search Console, GA4, brand guideline, danh sách từ khóa ưu tiên
- **AI (Claude):** Tạo checklist onboarding AEO tự động, đọc tài liệu KH, soạn agenda kickoff
- Kickoff meeting: xác nhận mục tiêu, lịch làm việc, kênh liên lạc chính

### Giai đoạn 5 — Triển khai (Tuần 1–4 và hàng tháng)
- **Tuần 1–2:** SP kiểm kê nội dung hiện có, xác định URL ưu tiên, lập kế hoạch FAQ/schema
- **Tuần 3–4:** Triển khai cấu trúc câu hỏi–trả lời, FAQ schema, HowTo schema
- **AI (Claude):** Tạo draft FAQ cho từng trang, review cấu trúc trước QA, flagging nội dung mơ hồ
- QA kiểm tra trước khi gửi KH → KH duyệt → triển khai lên site
- Chỉnh sửa tối đa **2 vòng** trong phạm vi HĐ

### Giai đoạn 6 — Nghiệm thu & Bàn giao (Cuối tháng 1)
- **AI (Claude):** Tạo báo cáo nghiệm thu: số URL đã tối ưu, schema triển khai, so sánh vs KPI cam kết
- AM gửi báo cáo kèm nhận xét → KH ký biên bản nghiệm thu
- Thu thập feedback qua form tự động (CSAT ≥ 4/5)

### Giai đoạn 7 — Chăm sóc & Gia hạn (Hàng tháng)
- **AI (Claude + crm_care.py):** Tự động báo cáo hàng tháng: số URL được SGE trích dẫn, thay đổi so tháng trước, gợi ý ưu tiên tháng tiếp
- AM review báo cáo AI → bổ sung nhận xét → gửi KH trước ngày 5 hàng tháng
- **AI:** Alert khi chỉ số tụt hơn 20% so tháng trước → AM xử lý trong 24h
- Nhắc gia hạn trước **30 ngày** hết HĐ, gợi ý upsell (SEO tổng thể, Content)

---

## 3. Phân công (RACI)

| Giai đoạn | AM | SP SEO | AI | QA | DIR |
|-----------|----|----|----|----|-----|
| Lead tiếp nhận | R | — | C | — | I |
| Tư vấn nhu cầu | R | C | C | — | I |
| Báo giá / Proposal | R | C | C | — | A |
| Ký hợp đồng | R | — | I | — | A |
| Onboarding / Kickoff | R | C | C | — | I |
| Triển khai AEO | I | R | C | A | I |
| Review & chỉnh sửa | C | R | C | A | I |
| Nghiệm thu | R | C | C | A | I |
| Báo cáo tháng | R | C | C | — | I |
| Gia hạn / Upsell | R | I | C | — | A |

*R=Responsible, A=Accountable, C=Consulted, I=Informed*

---

## 4. AI Integration

| Giai đoạn | AI làm gì | Tool |
|-----------|-----------|------|
| Lead | Chấm điểm, gán tag aeo, phân loại tự động | `crm_ai_qualify.py` |
| Tư vấn | Phân tích website KH, gợi ý 3 ưu tiên AEO | Claude API + `crm_lead_ai.py` |
| Proposal | Draft proposal theo template + số liệu thực | Claude API |
| Onboarding | Checklist AEO, đọc tài liệu KH, soạn agenda | Claude API |
| Triển khai | Tạo draft FAQ/schema, review cấu trúc, flagging | Claude API |
| Nghiệm thu | Báo cáo tự động, so sánh vs KPI | Claude API + `crm_daily_work_report.py` |
| Chăm sóc | Báo cáo tháng, alert KPI tụt, gợi ý upsell | Claude API + `crm_care.py` |

---

## 5. SLA & Timeline

| Mốc | Thời gian |
|-----|-----------|
| Phản hồi lead | ≤ 2h giờ hành chính |
| Gửi proposal | ≤ 2 ngày làm việc sau tư vấn |
| Phản hồi chỉnh sửa KH | ≤ 1 ngày làm việc |
| Vòng chỉnh sửa tối đa | 2 vòng |
| Kickoff → Bàn giao đầu tiên | **4 tuần** |
| Báo cáo định kỳ | Trước ngày 5 hàng tháng |
| Nhắc gia hạn | Trước 30 ngày hết HĐ |

---

## 6. KPI Nội bộ (Team)

| KPI | Người chịu trách nhiệm | Ngưỡng tốt |
|-----|----------------------|------------|
| Convert lead AEO → HĐ | AM | ≥ 30% |
| On-time delivery | SP + QA | ≥ 90% |
| Tỷ lệ cần > 2 vòng chỉnh sửa | SP + QA | ≤ 20% |
| CSAT sau nghiệm thu | AM | ≥ 4.2/5 |
| Tỷ lệ gia hạn | AM | ≥ 70% |
| AI usage rate trong quy trình | SP | ≥ 80% tasks |
| Thời gian phản hồi lead TB | AM | ≤ 1.5h |

---

## 7. KPI Cam kết với Khách hàng

| KPI | Ngưỡng cam kết | Đo bằng |
|-----|---------------|---------|
| Số URL được SGE/AI trích dẫn | Tăng theo từng mốc tháng | Kiểm tra thủ công + tool AEO |
| FAQ/Schema triển khai đúng hạn | 100% URL ưu tiên trong tháng 1 | Google Search Console |
| Cấu trúc câu hỏi–trả lời | ≥ 80% trang ưu tiên có FAQ rõ | Audit nội bộ |
| Không lỗi schema kỹ thuật | 0 lỗi critical sau deploy | Google Rich Results Test |
| Báo cáo đúng hạn | 100% tháng | Lịch gửi CRM |
