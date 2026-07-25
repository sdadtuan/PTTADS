# Phân tích Gap — Use Case vs Hành động người dùng thực tế

> **Phiên bản:** 1.1 · **Ngày:** 2026-07-25  
> **Cập nhật:** Phase A — Zalo actions 21/21, SYS-002/003/004/005 multi-channel, Portal Zalo  
> **Mục đích:** Đối chiếu ~122 UC với ops-web / portal-web thực tế; xác định bước nghiệp vụ khách hàng chưa được hệ thống dẫn đủ.

---

## 1. Kết luận tổng quan

| Mức | Số UC ước lượng | Ý nghĩa |
|-----|-----------------|---------|
| **Đủ bước UI** | ~88 UC | Toàn bộ hành động chính có màn hình + API |
| **Thiếu bước / workaround thủ công** | ~24 UC | Nghiệp vụ đúng spec nhưng thiếu UI hoặc liên kết giữa module |
| **Chưa có / stub only** | ~10 UC | Cần phát triển trước khi khách tự phục vụ (chủ yếu Z4 API write, P2 BI) |

**Thay đổi post Phase A (doc):**

| Module | Trước Phase A | Sau Phase A |
|--------|---------------|-------------|
| ZALO actions | 9/21 UC | **21/21 UC** ✅ |
| SYS cross-channel | Meta-only SYS-002/003 | **Meta + Zalo + Google** nhánh |
| PORTAL Zalo | Không có | **PORTAL-UC-013/014** ✅ |
| Gap doc Zalo | Stale (nhiều ❌ đã ship Z1–Z3) | **Refreshed** |

**Nguyên nhân hệ thống "chưa ổn" khi đọc UC cũ:** UC mô tả luồng logic (Main flow 5–7 bước) nhưng **không liệt kê từng click, form field, điều kiện chuyển màn** — AM/CSKH không biết "làm gì tiếp theo" khi onboard đa module.

**Giải pháp tài liệu:** Bộ [`actions/`](actions/README.md) — mỗi UC có bảng hành động `# | Actor | Màn hình | Thao tác | Input | Output | Gate`.

---

## 2. Ma trận mong muốn khách hàng → UC → Trạng thái

| Mong muốn khách hàng / agency | UC liên quan | Trạng thái đáp ứng |
|------------------------------|--------------|-------------------|
| Ký HĐ xong → client chạy ads trong 2 tuần | SYS-001, SVC-001/002, META-001, **ZALO-001/021** | ⚠️ Orchestrator ✅; AM vẫn deep-link nhiều URL — **doc Phase A** đã map đủ bước |
| Lead Meta vào CRM < 1 phút, CSKH gọi ngay | META-004, CRM-001, PLAT-004 | ✅ Webhook + lead list + review queue |
| **Lead Zalo vào CRM (webhook + poll)** | **ZALO-011/012/013/014** | ✅ Shipped Z0–Z2; **actions doc Phase A** |
| Biết CPL/ROAS đúng theo client | SYS-002, META-002/003, **ZALO-004/015** | ✅ Hub + map; Zalo CPA refresh Z2-B7 |
| **So sánh Meta/Google/Zalo một màn** | **SYS-002, ZALO-018** | ✅ `/meta/ads-combined` Z3-7 |
| Launch ads chỉ khi QA + client duyệt | SYS-003, SVC-005/006/007, PORTAL-006, **ZALO-008/019** | ✅ Launch QA Zalo checklist Z3-2; go-live manual v1 |
| Khách tự xem báo cáo T-1 | SYS-005, PORTAL-002/003, **PORTAL-UC-013** | ✅ Dashboard + export CSV/PDF; **Zalo PDF Z3-6** |
| Khách duyệt email trước gửi | EM-007, PORTAL-008 | ✅ Portal approvals |
| **Khách duyệt creative Zalo** | **ZALO-019, PORTAL-014** | ✅ Shared `/creatives` + channel=zalo tag |
| SEO content duyệt trước publish | SEO-005/006, PORTAL-007 | ✅ Content pipeline + portal review |
| Tạo tài khoản portal cho khách | PORTAL-001, SYS-001 bước 13 | ✅ Tab **Portal users** |
| Reset mật khẩu portal | PORTAL-001 | ✅ `/forgot-password`, `/reset-password` |
| Offboard → thu hồi hết quyền | SYS-006, SVC-012 | ✅ Nút Offboard |
| Finance chặn handover khi nợ | SVC-004 | ⚠️ **GAP-P1-01** — Gate logic spec; UI cảnh báo hạn chế |
| **Cảnh báo Zalo CPL/zero leads** | **ZALO-017** | ✅ Alerts Z3 + Slack + hub banner |
| **Thông báo tiến độ campaign Zalo** | **ZALO-020** | ⚠️ Staff inbox ✅; portal client ⚠ GAP-P1-02 |
| Onboard email domain tự phục vụ | EM-001 | ✅ Wizard E-11 |
| Journey email tự động | EM-011 | ⚠️ **GAP-P1-02** — Flag `PTT_EMAIL_JOURNEYS=1` |
| Báo cáo BI Grafana khách xem | EM-013, SEO-014 | ⚠️ **GAP-P1-03** — Staff embed OK; portal chưa embed |
| Subscriber preference center | EM-014 | ✅ Public routes tokenized |
| Multi-client isolation | SYS-011, PLAT-002/003 | ✅ JWT scope + e2e pen test |
| **Deploy campaign Zalo qua API** | **ZALO-009/010** | ❌ **GAP-Z4-01** — v1 manual go-live + map |

---

## 3. Danh sách Gap chi tiết (ưu tiên sửa)

### GAP-P0 — Chặn nghiệp vụ khách hàng

| ID | Mô tả | UC | Workaround hiện tại | Đề xuất |
|----|-------|-----|---------------------|---------|
| **GAP-P0-01** | ~~Không có UI CRUD portal users trên ops-web~~ | PORTAL-001, SYS-001 | — | ✅ **Đã implement** |
| **GAP-P0-02** | ~~Portal forgot password~~ | PORTAL-001 | — | ✅ **Đã implement** |
| **GAP-P0-03** | ~~Onboard đa module không có checklist thống nhất~~ | SYS-001, SVC-002 | — | ✅ **Onboard orchestrator** Z2 + doc nhánh Zalo SYS-001 |

### GAP-P1 — Enterprise depth / workaround được

| ID | Mô tả | UC | Workaround |
|----|-------|-----|------------|
| **GAP-P1-01** | Finance gate handover | SVC-004 | AM check `/crm/financials` thủ công trước advance stage |
| **GAP-P1-02** | Notification client khi có approval pending / milestone | PORTAL-006/008, **ZALO-020** | Email manual từ AM; staff inbox có; portal widget partial |
| **GAP-P1-03** | Grafana BI trên portal khách | EM-013, SEO-014 | Khách xem PDF export; staff xem Grafana |
| **GAP-P1-04** | Campaign map bulk AI suggest | META-002 | Hub có suggest; buyer confirm từng dòng |
| **GAP-P1-05** | Double opt-in email public confirm | EM-002 | Route có; thiếu UI embed builder trong ops |
| **GAP-P1-06** | Zalo lead ops visibility | PLAT-005, **ZALO-011** | ✅ Filter `source=zalo` trên `/crm/leads`; `/agency/ingest` xem job |

### GAP-P2 — Pilot / optional

| ID | Mô tả | UC |
|----|-------|-----|
| **GAP-P2-01** | ClickHouse / DWH export self-serve portal | SEO-014, **ZALO-018** |
| **GAP-P2-02** | Meta Horizon migration UAT client-facing | META-014 |
| **GAP-P2-03** | Portal branding full white-label | PORTAL settings partial |

### GAP-Z4 — Zalo API write (Wave Z4)

| ID | Mô tả | UC | Workaround v1 |
|----|-------|-----|---------------|
| **GAP-Z4-01** | Campaign create/pause/update qua Zalo API | ZALO-009, ZALO-010 | Manual trên Zalo Ads UI + hub map ([08-ZALO-ACTIONS.md](actions/08-ZALO-ACTIONS.md) nhánh E1/M1) |

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

**Coverage sau Phase A:**

| Module | UC catalog | Action file | Đạt checklist §4 |
|--------|------------|-------------|------------------|
| ZALO | 21 | 21 ✅ | **21/21** (Phase A) |
| SYS | 12 | 12 | **5/12** (001–005 expanded) |
| PORTAL | 10 + extras | 14 | **+2 Zalo** (013/014) |
| CRM/SVC/META/SEO/EM/PLAT | ~79 | ~79 | **~4/79** full standard — **Phase B target** |

---

## 5. Lộ trình khuyến nghị (product + doc)

| Phase | Hạng mục | Trạng thái |
|-------|----------|------------|
| **A** | Zalo 21 UC actions; SYS-002/003/004/005 multi-channel; Portal Zalo; refresh gap doc | ✅ **Done** (2026-07-25) |
| **B** (1–2 sprint doc) | CRM + SVC P0 actions expand; GAP-P1-01 finance gate UI | Pending |
| **C** (1 sprint doc) | META/SEO/EM P0 actions expand | Pending |
| **D** (product) | GAP-P1-02 portal notify; GAP-Z4-01 Zalo API write | Pending |
| **E** (product) | GAP-P1-03 Grafana portal | Pending |

---

## 6. Liên kết tài liệu

| Tài liệu | Nội dung |
|----------|----------|
| [`actions/README.md`](actions/README.md) | Quy ước bảng hành động |
| [`actions/00-SYSTEM-ACTIONS.md`](actions/00-SYSTEM-ACTIONS.md) | 12 SYS UC — SYS-002/003/004/005 multi-channel |
| [`actions/08-ZALO-ACTIONS.md`](actions/08-ZALO-ACTIONS.md) | **21/21 ZALO UC** chi tiết |
| [`actions/06-PORTAL-ACTIONS.md`](actions/06-PORTAL-ACTIONS.md) | PORTAL + UC-013/014 Zalo |
| [`huong-dan-zalo-ads-ops.md`](../huong-dan-zalo-ads-ops.md) | Ops handover Z1–Z3 |
