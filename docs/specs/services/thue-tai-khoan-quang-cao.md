# Spec Dịch vụ Cho thuê Tài khoản Quảng cáo

**Slug:** `thue-tai-khoan-quang-cao`
**Nhóm:** Quảng cáo kỹ thuật số
**Mô tả:** Hỗ trợ tài khoản quảng cáo ổn định, giảm rủi ro bị khóa, triển khai kèm quản trị minh bạch theo hợp đồng.

---

## 1. Tổng quan

**Đối tượng khách hàng:**
- KH bị khóa tài khoản Ads liên tục, không tự mở được
- Doanh nghiệp mới chưa có tài khoản Ads đủ uy tín
- Agency / freelancer cần tài khoản phụ để chạy cho client

**Gói tham chiếu:** Phí thuê tháng theo ngân sách chạy; cam kết minh bạch chi phí.

**Cam kết cốt lõi:** Tài khoản hoạt động ổn định, minh bạch 100% chi phí phát sinh.

---

## 2. Vòng đời khách hàng

### Giai đoạn 1 — Lead & Tiếp nhận (Ngày 0)
- KH liên hệ: tài khoản bị khóa, cần tài khoản chạy ngay
- **AI (crm_ai_qualify.py):** Chấm điểm, gán tag `thue-tai-khoan`, phát hiện urgency (bị khóa đang có campaign cần chạy)
- AM phản hồi **≤ 2h** — nếu urgency cao: **≤ 1h**

### Giai đoạn 2 — Tư vấn & Phân tích nhu cầu (Ngày 1)
- AM meeting nhanh: nền tảng cần (Meta / Google / TikTok), ngân sách tháng, lý do bị khóa (nếu có)
- **AI (Claude):** Đánh giá rủi ro từ lịch sử tài khoản KH mô tả, gợi ý loại tài khoản phù hợp, checklist điều kiện sử dụng
- Làm rõ điều khoản 2 bên trước khi tiến hành

### Giai đoạn 3 — Báo giá & Ký hợp đồng (Ngày 1–2)
- AM soạn proposal: phí thuê, % spend, điều khoản sử dụng, trách nhiệm 2 bên
- **AI (Claude):** Draft hợp đồng, checklist điều khoản rõ ràng
- DIR duyệt → ký HĐ → xác nhận ngay

### Giai đoạn 4 — Onboarding & Setup (Ngày 1–2 sau ký)
- Cấu hình tài khoản, thẻ thanh toán, Business Manager theo hướng dẫn nền tảng
- **AI (Claude):** Tạo checklist setup chuẩn theo từng nền tảng, hướng dẫn sử dụng an toàn để tránh vi phạm
- KH được hướng dẫn quy trình sử dụng và các điều cần tránh

### Giai đoạn 5 — Vận hành (Hàng tháng)
- KH / SP Ads chạy campaign qua tài khoản
- **AI (Claude + crm_care.py):** Monitor tình trạng tài khoản, phát hiện dấu hiệu vi phạm sớm
- Alert ngay khi có cảnh báo từ nền tảng → xử lý trong 2h

### Giai đoạn 6 — Báo cáo tháng
- **AI (Claude):** Báo cáo tháng: tổng spend, phí thuê, tình trạng tài khoản, sự cố (nếu có)
- AM gửi KH trước ngày 5, kèm hóa đơn minh bạch

### Giai đoạn 7 — Chăm sóc & Gia hạn
- **AI (crm_care.py):** Nhắc gia hạn trước 30 ngày, gợi ý chuyển sang gói Ads management toàn diện
- AM follow-up nếu KH không gia hạn: tìm hiểu lý do

---

## 3. Phân công (RACI)

| Giai đoạn | AM | SP Ads | AI | QA | DIR |
|-----------|----|----|----|----|-----|
| Lead tiếp nhận | R | — | C | — | I |
| Tư vấn điều khoản | R | C | C | — | A |
| Báo giá / HĐ | R | — | C | — | A |
| Setup tài khoản | R | R | C | — | I |
| Monitor vận hành | I | R | C | A | I |
| Báo cáo tháng | R | C | C | — | I |
| Xử lý vi phạm | R | R | C | — | A |
| Gia hạn | R | I | C | — | A |

---

## 4. AI Integration

| Giai đoạn | AI làm gì | Tool |
|-----------|-----------|------|
| Lead | Chấm điểm, phát hiện urgency | `crm_ai_qualify.py` |
| Tư vấn | Đánh giá rủi ro, checklist điều kiện | Claude API |
| HĐ | Draft hợp đồng, checklist điều khoản | Claude API |
| Onboarding | Checklist setup chuẩn, hướng dẫn tránh vi phạm | Claude API |
| Vận hành | Monitor tài khoản, phát hiện dấu hiệu vi phạm | `crm_care.py` |
| Báo cáo | Báo cáo spend + tình trạng tháng | Claude API |

---

## 5. SLA & Timeline

| Mốc | Thời gian |
|-----|-----------|
| Phản hồi lead (bình thường) | ≤ 2h |
| Phản hồi lead (urgency) | ≤ 1h |
| Gửi proposal | ≤ 1 ngày |
| Ký HĐ → Tài khoản sẵn sàng | **1–2 ngày** |
| Xử lý cảnh báo vi phạm | ≤ 2h |
| Báo cáo + hóa đơn tháng | Trước ngày 5 |
| Nhắc gia hạn | Trước 30 ngày |

---

## 6. KPI Nội bộ (Team)

| KPI | Người chịu trách nhiệm | Ngưỡng tốt |
|-----|----------------------|------------|
| Convert lead → HĐ | AM | ≥ 50% (nhu cầu rõ) |
| Tài khoản live đúng hạn | AM + SP | ≥ 95% |
| Uptime tài khoản | SP | ≥ 98% |
| Thời gian xử lý cảnh báo | SP | ≤ 2h |
| Tỷ lệ gia hạn | AM | ≥ 65% |
| Minh bạch hóa đơn đúng hạn | AM | 100% |

---

## 7. KPI Cam kết với Khách hàng

| KPI | Ngưỡng cam kết | Đo bằng |
|-----|---------------|---------|
| Tài khoản hoạt động ổn định | Uptime ≥ 98%/tháng | Monitor |
| Minh bạch chi phí | Hóa đơn rõ ràng 100% trước ngày 5 | Lịch gửi |
| Xử lý sự cố tài khoản | ≤ 2h từ khi phát hiện | Ticket log |
| 0 vi phạm do lỗi setup của PTT | 0 | Account log |
| Báo cáo đúng hạn | 100% tháng | Lịch CRM |
