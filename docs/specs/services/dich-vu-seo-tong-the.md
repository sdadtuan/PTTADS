# Spec Dịch vụ SEO Tổng thể

**Slug:** `dich-vu-seo-tong-the`
**Nhóm:** Tìm kiếm tự nhiên
**Mô tả:** Chiến lược SEO toàn diện từ kỹ thuật, nội dung đến liên kết — tăng thứ hạng và lưu lượng tìm kiếm tự nhiên bền vững.

---

## 1. Tổng quan

**Đối tượng khách hàng:**
- Doanh nghiệp muốn tăng traffic organic dài hạn
- Website đang có traffic nhưng chưa khai thác hết tiềm năng SEO
- KH muốn giảm phụ thuộc ngân sách quảng cáo

**Gói tham chiếu:** Gói tháng (retainer) hoặc theo dự án; tối thiểu 3 tháng để thấy kết quả.

**Cam kết cốt lõi:** Tăng organic traffic và thứ hạng từ khóa ưu tiên theo lộ trình đã cam kết.

---

## 2. Vòng đời khách hàng

### Giai đoạn 1 — Lead & Tiếp nhận (Ngày 0)
- KH liên hệ qua form / Zalo / giới thiệu
- **AI (crm_ai_qualify.py):** Chấm điểm, gán tag `seo-tong-the`, phân loại quy mô (SME / enterprise)
- AM phản hồi **≤ 2h**, tạo hồ sơ lead trong CRM

### Giai đoạn 2 — Tư vấn & Phân tích nhu cầu (Ngày 1–3)
- AM meeting khám phá: ngành, đối thủ, lịch sử SEO, mục tiêu traffic/lead
- **AI (Claude):** Crawl sơ bộ website, phân tích từ khóa cơ bản, so sánh với 2–3 đối thủ chính, đưa ra nhận xét nhanh
- SP SEO tham gia demo phân tích kỹ thuật nếu cần

### Giai đoạn 3 — Báo giá & Ký hợp đồng (Ngày 3–7)
- AM soạn proposal: phạm vi (on-page / technical / content / link), timeline 3–6 tháng, KPI theo từng mốc
- **AI (Claude):** Draft proposal, điền số liệu từ phân tích, tạo bảng milestone
- DIR duyệt → KH ký → tạo project trong CRM

### Giai đoạn 4 — Onboarding & Kickoff (Ngày 1–3 sau ký)
- Thu thập: GSC, GA4, Search Console, danh sách từ khóa ưu tiên, đối thủ cần bám
- **AI (Claude):** Tạo checklist onboarding SEO, đọc dữ liệu lịch sử KH, soạn agenda kickoff và tóm tắt tình trạng hiện tại
- Kickoff meeting: xác nhận từ khóa ưu tiên, cluster chủ đề, lịch content

### Giai đoạn 5 — Triển khai (Tháng 1–3 và tiếp theo)
- **Tháng 1 — Technical audit & fix:** SP rà crawl, index, redirect, sitemap, Core Web Vitals
- **AI (Claude):** Tạo danh sách lỗi ưu tiên, viết hướng dẫn fix chi tiết, kiểm tra sau fix
- **Tháng 2 — On-page & Content:** Tối ưu meta, heading, internal link, cluster content
- **AI (Claude):** Tạo content brief, draft bài chuẩn SEO, review trước QA
- **Tháng 3+ — Link building & mở rộng:** Hợp tác liên kết, theo dõi thứ hạng, điều chỉnh ưu tiên
- QA kiểm tra mỗi deliverable trước khi gửi KH

### Giai đoạn 6 — Nghiệm thu & Bàn giao (Theo milestone)
- **AI (Claude):** Báo cáo nghiệm thu theo mốc: thứ hạng từ khóa, traffic, Core Web Vitals so trước/sau
- AM gửi báo cáo → KH duyệt → ký biên bản từng milestone

### Giai đoạn 7 — Chăm sóc & Gia hạn (Hàng tháng)
- **AI (Claude + crm_care.py):** Báo cáo tháng tự động: thứ hạng, traffic, backlink mới, đề xuất tháng tiếp
- AM review → bổ sung nhận xét → gửi trước ngày 5
- Alert khi từ khóa ưu tiên tụt hơn 5 vị trí → xử lý trong 48h
- Nhắc gia hạn trước 30 ngày

---

## 3. Phân công (RACI)

| Giai đoạn | AM | SP SEO | AI | QA | DIR |
|-----------|----|----|----|----|-----|
| Lead tiếp nhận | R | — | C | — | I |
| Tư vấn nhu cầu | R | C | C | — | I |
| Báo giá / Proposal | R | C | C | — | A |
| Ký hợp đồng | R | — | I | — | A |
| Onboarding / Kickoff | R | C | C | — | I |
| Technical audit & fix | I | R | C | A | I |
| On-page & Content | I | R | C | A | I |
| Link building | I | R | C | A | I |
| Nghiệm thu milestone | R | C | C | A | I |
| Báo cáo tháng | R | C | C | — | I |
| Gia hạn / Upsell | R | I | C | — | A |

---

## 4. AI Integration

| Giai đoạn | AI làm gì | Tool |
|-----------|-----------|------|
| Lead | Chấm điểm, gán tag, phân loại quy mô | `crm_ai_qualify.py` |
| Tư vấn | Crawl sơ bộ, phân tích từ khóa, so sánh đối thủ | Claude API + `crm_lead_ai.py` |
| Proposal | Draft proposal, bảng milestone, KPI theo tháng | Claude API |
| Onboarding | Checklist SEO, tóm tắt tình trạng hiện tại | Claude API |
| Technical | Danh sách lỗi ưu tiên, hướng dẫn fix, kiểm tra sau | Claude API |
| Content | Brief bài, draft chuẩn SEO, review cluster | Claude API |
| Nghiệm thu | Báo cáo milestone tự động | Claude API + `crm_daily_work_report.py` |
| Chăm sóc | Báo cáo tháng, alert thứ hạng tụt, upsell | Claude API + `crm_care.py` |

---

## 5. SLA & Timeline

| Mốc | Thời gian |
|-----|-----------|
| Phản hồi lead | ≤ 2h giờ hành chính |
| Gửi proposal | ≤ 2 ngày làm việc |
| Kickoff → Bàn giao audit đầu tiên | **6 tuần** |
| Báo cáo tháng | Trước ngày 5 hàng tháng |
| Xử lý alert thứ hạng tụt | ≤ 48h |
| Nhắc gia hạn | Trước 30 ngày hết HĐ |

---

## 6. KPI Nội bộ (Team)

| KPI | Người chịu trách nhiệm | Ngưỡng tốt |
|-----|----------------------|------------|
| Convert lead → HĐ | AM | ≥ 30% |
| On-time delivery milestone | SP + QA | ≥ 90% |
| Tỷ lệ > 2 vòng chỉnh sửa | SP + QA | ≤ 20% |
| CSAT sau 3 tháng | AM | ≥ 4.2/5 |
| Tỷ lệ gia hạn sau 3 tháng | AM | ≥ 70% |
| AI usage rate | SP | ≥ 80% tasks |

---

## 7. KPI Cam kết với Khách hàng

| KPI | Ngưỡng cam kết | Đo bằng |
|-----|---------------|---------|
| Tăng organic traffic | ≥ 20% sau 3 tháng; ≥ 40% sau 6 tháng | GA4 |
| Từ khóa ưu tiên vào top 10 | ≥ 50% từ khóa đã cam kết sau 3 tháng | GSC + rank tracker |
| Core Web Vitals | LCP ≤ 2.5s, CLS ≤ 0.1, INP ≤ 200ms | PageSpeed Insights |
| 0 lỗi critical kỹ thuật tồn đọng | Sau tháng 1 | Screaming Frog / GSC |
| Báo cáo đúng hạn | 100% tháng | Lịch CRM |
