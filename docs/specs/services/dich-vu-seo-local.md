# Spec Dịch vụ SEO Local

**Slug:** `dich-vu-seo-local`
**Nhóm:** Tìm kiếm tự nhiên
**Mô tả:** Tăng mức độ hiển thị cho doanh nghiệp có địa điểm trên Google Maps, Google Business Profile và tìm kiếm theo khu vực.

---

## 1. Tổng quan

**Đối tượng khách hàng:**
- Doanh nghiệp có cửa hàng / văn phòng / chi nhánh cụ thể
- Ngành: nhà hàng, spa, phòng khám, bất động sản, giáo dục, bán lẻ
- KH muốn xuất hiện khi khách tìm kiếm "gần tôi" hoặc theo quận/tỉnh

**Gói tham chiếu:** Setup 1 lần + retainer tháng theo số chi nhánh.

**Cam kết cốt lõi:** Xuất hiện trong Local Pack (top 3 bản đồ) cho từ khóa địa phương ưu tiên.

---

## 2. Vòng đời khách hàng

### Giai đoạn 1 — Lead & Tiếp nhận (Ngày 0)
- KH liên hệ hỏi về Google Maps, "tìm kiếm gần đây", đánh giá Google
- **AI (crm_ai_qualify.py):** Chấm điểm, gán tag `seo-local`, phát hiện số chi nhánh từ mô tả
- AM phản hồi **≤ 2h**, tạo hồ sơ lead

### Giai đoạn 2 — Tư vấn & Phân tích nhu cầu (Ngày 1–3)
- AM meeting: số chi nhánh, khu vực mục tiêu, ngành, mục tiêu (gọi / chỉ đường / form)
- **AI (Claude):** Kiểm tra tình trạng GBP hiện tại, so sánh với đối thủ local trong khu vực, gợi ý 3 hành động ưu tiên
- SP SEO tham gia nếu cần audit kỹ thuật

### Giai đoạn 3 — Báo giá & Ký hợp đồng (Ngày 3–7)
- AM soạn proposal: setup GBP, tối ưu NAP, content local, kế hoạch đánh giá
- **AI (Claude):** Draft proposal theo template, điền phân tích đối thủ local
- DIR duyệt → ký HĐ

### Giai đoạn 4 — Onboarding & Kickoff (Ngày 1–3 sau ký)
- Thu thập: access Google Business Profile, brand guideline, danh sách chi nhánh, ảnh
- **AI (Claude):** Checklist onboarding local, tóm tắt trạng thái GBP hiện có, soạn agenda kickoff
- Xác nhận từ khóa địa phương ưu tiên theo từng chi nhánh

### Giai đoạn 5 — Triển khai (Tuần 1–2 setup, hàng tháng tối ưu)
- **Tuần 1:** Tối ưu GBP (tên, địa chỉ, số điện thoại, giờ mở cửa, danh mục, ảnh)
- **Tuần 2:** Đồng bộ NAP trên các directory, tạo content local cho trang website
- **AI (Claude):** Tạo mô tả GBP chuẩn, viết post GBP hàng tuần, tạo nội dung trang địa điểm
- **Hàng tháng:** Theo dõi đánh giá, tạo post GBP, cập nhật thông tin theo mùa vụ
- QA kiểm tra NAP consistency trước khi hoàn thành setup

### Giai đoạn 6 — Nghiệm thu & Bàn giao (Cuối tuần 2)
- **AI (Claude):** Báo cáo setup: trạng thái GBP, NAP score, từ khóa xuất hiện trên map
- AM gửi báo cáo → KH ký nghiệm thu setup

### Giai đoạn 7 — Chăm sóc & Gia hạn (Hàng tháng)
- **AI (Claude + crm_care.py):** Báo cáo tháng: lượt xem GBP, cuộc gọi, chỉ đường, đánh giá mới
- AM review → gợi ý xử lý đánh giá tiêu cực → gửi KH
- Alert khi có đánh giá 1–2 sao → AM thông báo KH trong 4h
- Nhắc gia hạn trước 30 ngày

---

## 3. Phân công (RACI)

| Giai đoạn | AM | SP SEO | AI | QA | DIR |
|-----------|----|----|----|----|-----|
| Lead tiếp nhận | R | — | C | — | I |
| Tư vấn | R | C | C | — | I |
| Báo giá | R | C | C | — | A |
| Ký HĐ | R | — | I | — | A |
| Onboarding | R | C | C | — | I |
| Setup GBP & NAP | I | R | C | A | I |
| Content local | I | R | C | A | I |
| Nghiệm thu | R | C | C | A | I |
| Báo cáo tháng | R | C | C | — | I |
| Xử lý đánh giá | R | C | C | — | I |
| Gia hạn | R | I | C | — | A |

---

## 4. AI Integration

| Giai đoạn | AI làm gì | Tool |
|-----------|-----------|------|
| Lead | Chấm điểm, phát hiện số chi nhánh | `crm_ai_qualify.py` |
| Tư vấn | Kiểm tra GBP, so sánh đối thủ local | Claude API |
| Proposal | Draft proposal, phân tích đối thủ local | Claude API |
| Onboarding | Checklist local, tóm tắt GBP hiện có | Claude API |
| Setup | Mô tả GBP chuẩn, post GBP, trang địa điểm | Claude API |
| Chăm sóc | Báo cáo tháng, alert đánh giá tiêu cực | Claude API + `crm_care.py` |

---

## 5. SLA & Timeline

| Mốc | Thời gian |
|-----|-----------|
| Phản hồi lead | ≤ 2h giờ hành chính |
| Gửi proposal | ≤ 2 ngày |
| Kickoff → Setup hoàn thành | **2 tuần** |
| Báo cáo tháng | Trước ngày 5 |
| Alert đánh giá tiêu cực | ≤ 4h |
| Nhắc gia hạn | Trước 30 ngày |

---

## 6. KPI Nội bộ (Team)

| KPI | Người chịu trách nhiệm | Ngưỡng tốt |
|-----|----------------------|------------|
| Convert lead → HĐ | AM | ≥ 30% |
| Setup đúng hạn 2 tuần | SP + QA | ≥ 95% |
| NAP consistency sau setup | SP | 100% trên directory ưu tiên |
| CSAT sau nghiệm thu | AM | ≥ 4.2/5 |
| Tỷ lệ gia hạn | AM | ≥ 70% |
| Thời gian xử lý alert đánh giá | AM | ≤ 4h |

---

## 7. KPI Cam kết với Khách hàng

| KPI | Ngưỡng cam kết | Đo bằng |
|-----|---------------|---------|
| Lượt xem GBP | Tăng ≥ 30% sau 2 tháng | GBP Insights |
| Lượt gọi / chỉ đường từ GBP | Tăng ≥ 20% sau 2 tháng | GBP Insights |
| Xuất hiện Local Pack | Top 3 cho ≥ 50% từ khóa ưu tiên sau 2 tháng | Rank tracker local |
| NAP consistency | 100% đồng nhất trên các directory | Audit định kỳ |
| Đánh giá mới | ≥ 2 đánh giá mới/tháng (tư vấn chiến lược) | GBP |
| Báo cáo đúng hạn | 100% tháng | Lịch CRM |
