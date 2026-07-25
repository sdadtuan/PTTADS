# Phân tích Gap — Use Case vs Hành động người dùng thực tế

> **Phiên bản:** 1.0 · **Ngày:** 2026-07-25  
> **Mục đích:** Đối chiếu 101 UC với ops-web / portal-web thực tế; xác định bước nghiệp vụ khách hàng chưa được hệ thống dẫn đủ.

---

## 1. Kết luận tổng quan

| Mức | Số UC ước lượng | Ý nghĩa |
|-----|-----------------|---------|
| **Đủ bước UI** | ~72 UC | Toàn bộ hành động chính có màn hình + API |
| **Thiếu bước / workaround thủ công** | ~22 UC | Nghiệp vụ đúng spec nhưng thiếu UI hoặc liên kết giữa module |
| **Chưa có / stub only** | ~7 UC | Cần phát triển trước khi khách tự phục vụ |

**Nguyên nhân hệ thống "chưa ổn" khi đọc UC cũ:** UC mô tả luồng logic (Main flow 5–7 bước) nhưng **không liệt kê từng click, form field, điều kiện chuyển màn** — AM/CSKH không biết "làm gì tiếp theo" khi onboard đa module.

**Giải pháp tài liệu:** Bộ [`actions/`](actions/README.md) — mỗi UC có bảng hành động `# | Actor | Màn hình | Thao tác | Input | Output | Gate`.

---

## 2. Ma trận mong muốn khách hàng → UC → Trạng thái

| Mong muốn khách hàng / agency | UC liên quan | Trạng thái đáp ứng |
|------------------------------|--------------|-------------------|
| Ký HĐ xong → client chạy ads trong 2 tuần | SYS-001, SVC-001/002, META-001/006/007 | ⚠️ Thiếu wizard end-to-end; AM phải nhớ 6+ URL |
| Lead Meta vào CRM < 1 phút, CSKH gọi ngay | META-004, CRM-001, PLAT-004 | ✅ Webhook + lead list + review queue |
| Biết CPL/ROAS đúng theo client | SYS-002, META-002/003 | ⚠️ Phụ thuộc map campaign thủ công |
| Launch ads chỉ khi QA + client duyệt | SYS-003, SVC-005/006/007, PORTAL-006 | ✅ Có Launch QA, Creative, Campaign Write, Portal |
| Khách tự xem báo cáo T-1 | SYS-005, PORTAL-002/003 | ✅ Dashboard + export CSV/PDF |
| Khách duyệt email trước gửi | EM-007, PORTAL-008 | ✅ Portal approvals |
| SEO content duyệt trước publish | SEO-005/006, PORTAL-007 | ✅ Content pipeline + portal review |
| Tạo tài khoản portal cho khách | PORTAL-001, SYS-001 bước 6 | ✅ Tab **Portal users** trên `/agency/clients/[id]` |
| Reset mật khẩu portal | PORTAL-001 | ✅ `/forgot-password`, `/reset-password`, `/settings` |
| Offboard → thu hồi hết quyền | SYS-006, SVC-012 | ✅ Nút Offboard trên `/agency/clients/[id]` |
| Finance chặn handover khi nợ | SVC-004 | ⚠️ **GAP-P1-01** — Gate logic spec; UI cảnh báo hạn chế |
| Onboard email domain tự phục vụ | EM-001 | ✅ Wizard E-11 `/email/deliverability` |
| Journey email tự động | EM-011 | ⚠️ **GAP-P1-02** — Cần flag `PTT_EMAIL_JOURNEYS=1` + canvas có nhưng chưa Gate A prod |
| Báo cáo BI Grafana khách xem | EM-013, SEO-014 | ⚠️ **GAP-P1-03** — Staff embed OK; portal chưa embed Grafana |
| Subscriber preference center | EM-014 | ✅ Public routes tokenized |
| Multi-client isolation | SYS-011, PLAT-002/003 | ✅ JWT scope + e2e pen test checklist |

---

## 3. Danh sách Gap chi tiết (ưu tiên sửa)

### GAP-P0 — Chặn nghiệp vụ khách hàng

| ID | Mô tả | UC | Workaround hiện tại | Đề xuất |
|----|-------|-----|---------------------|---------|
| **GAP-P0-01** | ~~Không có UI CRUD portal users trên ops-web~~ | PORTAL-001, SYS-001 | — | ✅ **Đã implement** — tab Portal users + API CRUD |
| **GAP-P0-02** | ~~Portal forgot password~~ | PORTAL-001 | Self-serve `/forgot-password` + `/reset-password`; AM reset ops | ✅ **Đã implement** |
| **GAP-P0-03** | Onboard đa module không có checklist thống nhất 1 màn | SYS-001, SVC-002 | AM nhảy giữa Agency, Meta, SEO, Email | **Onboard orchestrator** trên lifecycle tab: deep-link từng bước + auto tick khi detect done |

### GAP-P1 — Enterprise depth / workaround được

| ID | Mô tả | UC | Workaround |
|----|-------|-----|------------|
| **GAP-P1-01** | Finance gate handover | SVC-004 | AM check `/crm/financials` thủ công trước advance stage |
| **GAP-P1-02** | Notification client khi có approval pending | PORTAL-006/008 | Email manual từ AM; không push in-app portal |
| **GAP-P1-03** | Grafana BI trên portal khách | EM-013, SEO-014 | Khách xem PDF export; staff xem Grafana |
| **GAP-P1-04** | Campaign map bulk AI suggest | META-002 | Hub có suggest; buyer confirm từng dòng |
| **GAP-P1-05** | Double opt-in email public confirm | EM-002 | Route `/email/public/confirm/[token]` có; thiếu UI embed builder trong ops |
| **GAP-P1-06** | Zalo lead webhook ops visibility | PLAT-005 | `/agency/ingest` xem job; không có lead source filter riêng Zalo trên CRM |

### GAP-P2 — Pilot / optional

| ID | Mô tả | UC |
|----|-------|-----|
| **GAP-P2-01** | ClickHouse export self-serve portal | SEO-014 |
| **GAP-P2-02** | Meta Horizon migration UAT client-facing | META-014 |
| **GAP-P2-03** | Portal branding full white-label | PORTAL settings partial |

---

## 4. Checklist nghiệm thu hành động (per UC)

Một UC được coi **"đủ bước nghiệp vụ"** khi file actions tương ứng có:

- [ ] **Mục tiêu khách hàng** — câu nói đúng ngôn ngữ PO/AM
- [ ] **Bảng hành động** ≥ 8 bước cho P0 UC (≥ 5 cho P1)
- [ ] **Mỗi bước** có URL ops-web hoặc portal-web cụ thể
- [ ] **Input/Output** — field form, nút bấm, message hệ thống
- [ ] **Gate** — điều kiện pass/fail trước bước tiếp
- [ ] **Nhánh E*** — hành động khi lỗi / từ chối / timeout
- [ ] **Gap tag** — nếu bước thiếu UI

---

## 5. Lộ trình khuyến nghị (product)

| Phase | Hạng mục | UC được unblock |
|-------|----------|-----------------|
| **A** (2 sprint) | ~~GAP-P0-01~~, ~~GAP-P0-02~~, GAP-P0-03 | PORTAL-001 self-serve ✅ |
| **B** (1 sprint) | GAP-P1-01 finance gate UI, GAP-P1-02 portal notification | SVC-004, PORTAL-006/008 |
| **C** | GAP-P1-03 Grafana portal read-only | EM-013, SEO-014 client-facing |

---

## 6. Liên kết tài liệu

| Tài liệu | Nội dung |
|----------|----------|
| [`actions/README.md`](actions/README.md) | Quy ước bảng hành động |
| [`actions/00-SYSTEM-ACTIONS.md`](actions/00-SYSTEM-ACTIONS.md) | 12 SYS UC chi tiết |
| [`actions/01-CRM-ACTIONS.md`](actions/01-CRM-ACTIONS.md) | 15 CRM UC |
| … | 02–07 tương tự |
