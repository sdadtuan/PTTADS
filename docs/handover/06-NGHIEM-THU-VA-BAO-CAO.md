# 06 — Nghiệm thu bàn giao & catalog báo cáo

> **Phiên bản:** 1.0 · **Ngày:** 2026-07-25  
> **Biểu mẫu ký:** [`ban-giao-pttads-nghiem-thu-a4.html`](../forms/ban-giao-pttads-nghiem-thu-a4.html)

---

## 1. Mục đích nghiệm thu

Xác nhận PTT đã bàn giao hệ thống PTTADS theo phạm vi HĐ, khách hàng (PO) đã:

- Truy cập được staff console và/hoặc portal
- Hoàn thành UAT smoke test
- Nhận tài khoản, tài liệu và đào tạo cơ bản
- Đồng ý giới hạn in-scope mục 01 §3

---

## 2. Checklist nghiệm thu tổng thể

### 2.1. Tài liệu bàn giao

| # | Hạng mục | OK |
|---|----------|-----|
| D1 | Bộ tài liệu `docs/handover/` (01–06) | [ ] |
| D2 | Ops guide SEO / Email / Meta (link README) | [ ] |
| D3 | Checklist A4 in (SEO, Email, nghiệm thu) | [ ] |
| D4 | Slide đào tạo PPT | [ ] |
| D5 | Form bàn giao tài khoản (vault) | [ ] |

### 2.2. Hạ tầng & truy cập

| # | Hạng mục | OK |
|---|----------|-----|
| I1 | ops.pttads.vn HTTPS OK | [ ] |
| I2 | portal.pttads.vn HTTPS OK | [ ] |
| I3 | rs.pttads.vn redirect OK | [ ] |
| I4 | Health API `/health` OK | [ ] |
| I5 | Webhook endpoint reachable | [ ] |

### 2.3. UAT chức năng (tối thiểu)

| # | Hạng mục | OK |
|---|----------|-----|
| F1 | Staff login + CRM leads | [ ] |
| F2 | Portal login + dashboard | [ ] |
| F3 | Meta hub data T-1 | [ ] |
| F4 | SEO hub load | [ ] |
| F5 | Email hub load | [ ] |
| F6 | Lead webhook → CRM | [ ] |
| F7 | Portal approver test flow | [ ] |

### 2.4. Pilot client (điền)

| Field | Giá trị |
|-------|---------|
| Tên client pilot | |
| Client UUID / ID | |
| Meta ad account | |
| SEO customer_id | |
| Email client UUID | |
| Portal approver email | |

---

## 3. Catalog báo cáo & deliverables client

### 3.1. Meta (spec §23)

| ID | Deliverable | Tần suất | Audience | Trạng thái |
|----|-------------|----------|----------|------------|
| RPT-M1 | Portal live dashboard | T-1 | Client viewer | ✅ |
| RPT-M2 | CSV export self-serve | On demand | Client + AM | ✅ |
| RPT-M3 | Weekly Meta PDF white-label | Weekly Mon 08:00 | Client email | 🟡 HĐ enterprise |
| RPT-M4 | Monthly executive summary | Monthly | Approver | 🟡 |
| RPT-M5 | AM exception digest | Daily | Internal AM | ✅ |
| RPT-M6 | Owner weekly intelligence | Weekly | GDKD | ✅ |
| RPT-M7 | SLA / ops status | Daily | Ops | ✅ |

### 3.2. SEO/AEO

| Deliverable | Tần suất | Kênh |
|-------------|----------|------|
| Portal SEO dashboard | T-1 | portal.pttads.vn/seo |
| PDF executive report | Weekly/monthly (schedule) | Email / portal |
| GSC/GA4 sync | Daily ~06:xx | Internal hub |

### 3.3. Email Marketing

| Deliverable | Tần suất | Kênh |
|-------------|----------|------|
| Campaign performance | Post-send | portal + E-12 |
| Scheduled PDF executive | Weekly (per client schedule) | Email recipient |
| Deliverability scorecard | On demand | E-12 reports |
| Grafana dashboard | Real-time (ops) | E-12 embed |

### 3.4. CRM / Agency

| Deliverable | Tần suất | Audience |
|-------------|----------|----------|
| Lead pipeline export | On demand | Internal |
| Service delivery status | Per HĐ stage | AM + Client |
| Launch QA checklist | Per campaign | Internal + client sign-off |
| Owner weekly business | Weekly | Chủ DN (nội bộ PTT) |

---

## 4. KPI dictionary (client-facing)

| Label | Định nghĩa an toàn cho client |
|-------|-------------------------------|
| Chi tiêu Meta | Tiền thực tế Meta Ads Manager (VND) |
| Lead CRM | Lead hợp lệ hệ thống PTT (dedup/spam) |
| CPL | Chi tiêu ÷ Lead CRM |
| ROAS | Doanh thu chốt ÷ Chi tiêu (khi có sale data) |
| GSC Clicks | Click organic Google Search Console |
| Open rate email | Unique opens ÷ delivered |
| Complaint rate | Complaints ÷ delivered (< 0.1% target) |

---

## 5. Quy trình ký nghiệm thu

1. PTT gửi bộ tài liệu handover + lịch walkthrough
2. Khách thực hiện UAT §2.3 (1–2 ngày làm việc)
3. Ghi defect — PTT fix blocker trước ký
4. Ký form A4 in [`ban-giao-pttads-nghiem-thu-a4.html`](../forms/ban-giao-pttads-nghiem-thu-a4.html)
5. Lưu bản scan PDF — PO + PTT Tech Lead

**Defect severity cho nghiệm thu:**

| Loại | Block ký? |
|------|-----------|
| P1 — không login / mất data | ✅ Block |
| P2 — module lỗi có workaround | 🟡 Ký có điều kiện |
| P3 — cosmetic | ❌ Không block |

---

## 6. Bảo hành & giai đoạn tiếp theo

| Giai đoạn | Nội dung | Thời gian gợi ý |
|-----------|----------|-----------------|
| **Hypercare** | PTT on-call ưu tiên P1/P2 | 2–4 tuần post go-live |
| **Steady state** | SLA theo HĐ tier | Ongoing |
| **Enhancement** | Backlog P2 (identity merge, WYSIWYG…) | Roadmap riêng |

Roadmap module: [`EMAIL_MARKETING_COMPLETION_ROADMAP.md`](../EMAIL_MARKETING_COMPLETION_ROADMAP.md), [`SEO_AEO_COMPLETION_ROADMAP.md`](../SEO_AEO_COMPLETION_ROADMAP.md)

---

## 7. Sign-off

| Vai trò | Họ tên | Ngày | Chữ ký |
|---------|--------|------|--------|
| PO khách hàng | | | |
| PTT Tech Lead | | | |
| PTT AM | | | |

**Ghi chú / defect còn lại:**

```
_________________________________________________________________
_________________________________________________________________
```
