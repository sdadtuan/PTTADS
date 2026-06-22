# Spec Dịch vụ Tiếp thị Nội dung

**Slug:** `tiep-thi-noi-dung`
**Nhóm:** Tiếp thị nội dung
**Mô tả:** Kế hoạch và sản xuất nội dung theo từng kênh (web, social, tài liệu) hướng tới tăng lưu lượng và lòng tin thương hiệu.

---

## 1. Tổng quan

**Đối tượng khách hàng:**
- Doanh nghiệp cần nội dung đều đặn cho website / blog / mạng xã hội
- KH muốn giảm phụ thuộc Ads bằng nội dung organic dài hạn
- Thương hiệu cần xây uy tín chuyên môn trong ngành (thought leadership)

**Gói tham chiếu:** Retainer tháng theo số lượng bài / kênh / định dạng.

**Cam kết cốt lõi:** Đủ số bài theo lịch, organic traffic từ content tăng X% sau 3 tháng.

---

## 2. Vòng đời khách hàng

### Giai đoạn 1 — Lead & Tiếp nhận (Ngày 0)
- KH liên hệ: cần nội dung, không có người viết nội bộ, muốn tăng traffic organic
- **AI (crm_ai_qualify.py):** Chấm điểm, gán tag `tiep-thi-noi-dung`, phân loại kênh chính (blog / social / cả hai)
- AM phản hồi **≤ 2h**

### Giai đoạn 2 — Tư vấn & Phân tích nhu cầu (Ngày 1–3)
- AM meeting: ngành, đối tượng độc giả, kênh, tần suất, tone of voice, nội dung đang có
- **AI (Claude):** Phân tích nội dung hiện có của KH, so sánh với đối thủ trong ngành, gợi ý cluster chủ đề và content calendar sơ bộ
- SP Content tham gia nếu cần tư vấn chiến lược sâu

### Giai đoạn 3 — Báo giá & Ký hợp đồng (Ngày 3–7)
- AM soạn proposal: số lượng bài/tháng theo định dạng, lịch content, quy trình duyệt
- **AI (Claude):** Draft proposal, tạo content calendar tháng 1 minh họa, danh sách chủ đề gợi ý
- DIR duyệt → ký HĐ

### Giai đoạn 4 — Onboarding & Kickoff (Ngày 1–3 sau ký)
- Thu thập: brand guideline, tone of voice, từ khóa ưu tiên, style guide, nội dung cấm
- **AI (Claude):** Tạo content strategy brief, persona người đọc, brand voice guide cho team writer
- Kickoff: xác nhận content calendar tháng 1, quy trình duyệt (bao nhiêu ngày, ai duyệt)

### Giai đoạn 5 — Triển khai (Hàng tháng)
- **Tuần 1 — Lập kế hoạch tháng:** AI + SP tạo content calendar chi tiết theo cluster chủ đề
- **AI (Claude):** Research từ khóa cho từng bài, outline tự động, data/số liệu hỗ trợ, SEO brief
- **Tuần 2–3 — Sản xuất:** SP Writer viết theo brief AI đã tạo
- **AI (Claude):** Review bài: kiểm tra SEO on-page, fact-checking cơ bản, tone consistency, gợi ý cải thiện
- **Tuần 4 — Duyệt & publish:** KH duyệt → SP sửa theo feedback → publish đúng lịch
- QA: kiểm tra link, ảnh, formatting trước khi gửi KH duyệt

### Giai đoạn 6 — Báo cáo tháng (Đầu tháng tiếp)
- **AI (Claude + crm_daily_work_report.py):** Báo cáo: số bài đã publish, traffic từ content, từ khóa ranking, engagement
- AM review → bổ sung nhận xét chiến lược → gửi KH trước ngày 5

### Giai đoạn 7 — Chăm sóc & Gia hạn (Hàng tháng)
- **AI (crm_care.py):** Alert khi traffic content tụt hơn 20% → phân tích nguyên nhân
- AI gợi ý điều chỉnh strategy theo dữ liệu thực (cluster nào đang tốt, cluster nào cần pivot)
- Nhắc gia hạn trước 30 ngày, gợi ý upsell thêm kênh / định dạng (video script, infographic)

---

## 3. Phân công (RACI)

| Giai đoạn | AM | SP Content | AI | QA | DIR |
|-----------|----|----|----|----|-----|
| Lead tiếp nhận | R | — | C | — | I |
| Tư vấn | R | C | C | — | I |
| Báo giá | R | C | C | — | A |
| Ký HĐ | R | — | I | — | A |
| Onboarding / Strategy | R | C | C | — | I |
| Content calendar | I | R | C | A | I |
| Sản xuất bài | I | R | C | A | I |
| Review & duyệt | C | R | C | A | I |
| Publish | I | R | C | A | I |
| Báo cáo tháng | R | C | C | — | I |
| Gia hạn / Upsell | R | I | C | — | A |

---

## 4. AI Integration

| Giai đoạn | AI làm gì | Tool |
|-----------|-----------|------|
| Lead | Chấm điểm, phân loại kênh | `crm_ai_qualify.py` |
| Tư vấn | Phân tích nội dung KH, cluster topic, calendar sơ bộ | Claude API |
| Proposal | Draft proposal, calendar tháng 1 mẫu, chủ đề gợi ý | Claude API |
| Onboarding | Strategy brief, persona, brand voice guide | Claude API |
| Lập kế hoạch | Keyword research, outline, SEO brief từng bài | Claude API |
| Sản xuất | Review SEO, fact-check cơ bản, tone consistency | Claude API |
| Báo cáo | Báo cáo traffic / ranking / engagement tự động | Claude API + `crm_daily_work_report.py` |
| Chăm sóc | Alert traffic tụt, gợi ý pivot strategy | `crm_care.py` |

---

## 5. SLA & Timeline

| Mốc | Thời gian |
|-----|-----------|
| Phản hồi lead | ≤ 2h giờ hành chính |
| Gửi proposal | ≤ 2 ngày |
| Kickoff → Bài đầu tiên gửi duyệt | **1 tuần** |
| Gửi bài để KH duyệt | Trước ngày publish 5 ngày |
| KH duyệt → Publish | 2 ngày làm việc sau khi KH OK |
| Báo cáo tháng | Trước ngày 5 |
| Nhắc gia hạn | Trước 30 ngày |

---

## 6. KPI Nội bộ (Team)

| KPI | Người chịu trách nhiệm | Ngưỡng tốt |
|-----|----------------------|------------|
| Convert lead → HĐ | AM | ≥ 30% |
| Publish đúng lịch | SP Content | ≥ 95% |
| Tỷ lệ bài cần > 2 vòng sửa | SP Content | ≤ 25% |
| CSAT tháng | AM | ≥ 4.2/5 |
| Tỷ lệ gia hạn | AM | ≥ 70% |
| AI usage rate (brief + review) | SP | 100% bài |

---

## 7. KPI Cam kết với Khách hàng

| KPI | Ngưỡng cam kết | Đo bằng |
|-----|---------------|---------|
| Số bài publish đúng lịch | 100% theo HĐ | Lịch content |
| Organic traffic từ content | Tăng ≥ 20% sau 3 tháng | GA4 |
| Từ khóa bài viết vào top 20 | ≥ 50% từ khóa ưu tiên sau 3 tháng | GSC |
| Bài đạt chuẩn SEO on-page | 100% bài | Audit checklist |
| Báo cáo đúng hạn | 100% tháng | Lịch gửi |
