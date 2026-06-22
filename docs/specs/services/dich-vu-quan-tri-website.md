# Spec Dịch vụ Quản trị Website

**Slug:** `dich-vu-quan-tri-website`
**Nhóm:** Tìm kiếm tự nhiên
**Mô tả:** Vận hành, cập nhật và bảo mật website ổn định — đảm bảo site luôn chạy tốt phục vụ marketing và tìm kiếm.

---

## 1. Tổng quan

**Đối tượng khách hàng:**
- Doanh nghiệp có website nhưng không có IT nội bộ
- KH sau khi bàn giao thiết kế cần người vận hành tiếp
- Doanh nghiệp muốn yên tâm về uptime và bảo mật

**Gói tham chiếu:** Retainer tháng theo số lượng trang / lượt cập nhật / yêu cầu.

**Cam kết cốt lõi:** Uptime ≥ 99.5%, cập nhật nội dung trong ≤ 1 ngày làm việc.

---

## 2. Vòng đời khách hàng

### Giai đoạn 1 — Lead & Tiếp nhận (Ngày 0)
- KH liên hệ: website bị lỗi, muốn có người duy trì, vừa bàn giao thiết kế
- **AI (crm_ai_qualify.py):** Chấm điểm, gán tag `quan-tri-website`, phát hiện urgency (site đang lỗi)
- AM phản hồi **≤ 2h** — nếu site đang lỗi thì phản hồi **≤ 30 phút**

### Giai đoạn 2 — Tư vấn & Phân tích nhu cầu (Ngày 1–2)
- AM meeting: nền tảng (WordPress / khác), hosting, tần suất cập nhật, nhu cầu đặc thù
- **AI (Claude):** Kiểm tra sơ bộ website: tốc độ, uptime, phiên bản CMS, lỗ hổng cơ bản
- Xác định gói phù hợp theo khối lượng công việc

### Giai đoạn 3 — Báo giá & Ký hợp đồng (Ngày 2–5)
- AM soạn proposal: danh sách dịch vụ theo tháng, SLA uptime, số lần cập nhật
- **AI (Claude):** Draft proposal, checklist bàn giao tiếp nhận site
- Ký HĐ

### Giai đoạn 4 — Onboarding & Kickoff (Ngày 1–3 sau ký)
- Thu thập: access hosting, FTP/SFTP, admin CMS, domain, Google Analytics
- **AI (Claude):** Tạo hồ sơ kỹ thuật site, checklist tiếp nhận, kế hoạch sao lưu, agenda kickoff
- Tiến hành kiểm tra toàn diện và sao lưu đầu tiên ngay sau onboarding

### Giai đoạn 5 — Triển khai (Hàng tháng, liên tục)
- **Hàng tuần:** Kiểm tra uptime, sao lưu, cập nhật plugin/core (môi trường staging trước)
- **Theo yêu cầu:** Cập nhật nội dung (banner, bài viết, sản phẩm) trong ≤ 1 ngày làm việc
- **AI (Claude):** Tạo nội dung cập nhật theo brief KH, kiểm tra SEO cơ bản trước khi publish, flagging lỗi bảo mật
- QA kiểm tra sau mỗi cập nhật lớn

### Giai đoạn 6 — Báo cáo tháng (Đầu tháng)
- **AI (Claude + crm_daily_work_report.py):** Tạo báo cáo tháng: uptime thực tế, số tác vụ hoàn thành, lỗi phát sinh và cách xử lý
- AM review → gửi KH trước ngày 5

### Giai đoạn 7 — Chăm sóc & Gia hạn (Hàng tháng)
- **AI (crm_care.py):** Alert khi uptime tụt dưới 99%, phát hiện lỗi bảo mật mới
- AM thông báo KH và xử lý trong SLA
- Nhắc gia hạn trước 30 ngày, gợi ý nâng gói nếu khối lượng tăng

---

## 3. Phân công (RACI)

| Giai đoạn | AM | SP Web | AI | QA | DIR |
|-----------|----|----|----|----|-----|
| Lead tiếp nhận | R | — | C | — | I |
| Tư vấn | R | C | C | — | I |
| Báo giá | R | C | C | — | A |
| Ký HĐ | R | — | I | — | A |
| Onboarding | R | R | C | — | I |
| Vận hành hàng tuần | I | R | C | A | I |
| Cập nhật nội dung | I | R | C | A | I |
| Báo cáo tháng | R | C | C | — | I |
| Xử lý sự cố | I | R | C | — | A |
| Gia hạn | R | I | C | — | A |

---

## 4. AI Integration

| Giai đoạn | AI làm gì | Tool |
|-----------|-----------|------|
| Lead | Chấm điểm, phát hiện urgency site lỗi | `crm_ai_qualify.py` |
| Tư vấn | Kiểm tra sơ bộ site, uptime, lỗ hổng | Claude API |
| Onboarding | Hồ sơ kỹ thuật site, checklist tiếp nhận | Claude API |
| Vận hành | Tạo nội dung cập nhật, flagging lỗi bảo mật | Claude API |
| Báo cáo | Báo cáo tháng tự động | Claude API + `crm_daily_work_report.py` |
| Chăm sóc | Alert uptime, bảo mật, nhắc gia hạn | `crm_care.py` |

---

## 5. SLA & Timeline

| Mốc | Thời gian |
|-----|-----------|
| Phản hồi lead (bình thường) | ≤ 2h giờ hành chính |
| Phản hồi lead (site đang lỗi) | ≤ 30 phút |
| Kickoff → Site tiếp nhận hoàn toàn | **3 ngày** |
| Cập nhật nội dung theo yêu cầu | ≤ 1 ngày làm việc |
| Xử lý sự cố kỹ thuật | ≤ 4h (critical) / ≤ 1 ngày (minor) |
| Báo cáo tháng | Trước ngày 5 |
| Nhắc gia hạn | Trước 30 ngày |

---

## 6. KPI Nội bộ (Team)

| KPI | Người chịu trách nhiệm | Ngưỡng tốt |
|-----|----------------------|------------|
| Convert lead → HĐ | AM | ≥ 40% |
| Uptime thực tế đạt cam kết | SP Web | ≥ 99.5% |
| On-time cập nhật nội dung | SP Web | ≥ 95% |
| CSAT tháng | AM | ≥ 4.3/5 |
| Tỷ lệ gia hạn | AM | ≥ 80% |
| Thời gian phản hồi sự cố TB | SP | ≤ 2h |

---

## 7. KPI Cam kết với Khách hàng

| KPI | Ngưỡng cam kết | Đo bằng |
|-----|---------------|---------|
| Uptime website | ≥ 99.5%/tháng | Uptime monitor |
| Cập nhật nội dung đúng hạn | ≤ 1 ngày làm việc | Lịch task CRM |
| Sao lưu định kỳ | Hàng tuần, lưu trữ ≥ 30 ngày | Log sao lưu |
| Xử lý sự cố critical | ≤ 4h | Ticket CRM |
| Báo cáo tháng đúng hạn | 100% | Lịch gửi |
| 0 lỗi bảo mật tồn đọng quá 48h | 0 | Audit log |
