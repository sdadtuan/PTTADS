# Chi tiết hành động — CRM Core (CRM)

> **UC gốc:** [`../01-CRM-CORE.md`](../01-CRM-CORE.md)

---

## CRM-UC-001 — Đăng nhập & phân công lead tự động

**Mục tiêu khách hàng:** *"Lead từ ads/form vào CRM ngay, có người gọi trong 15 phút."*

| # | Actor | Màn hình | Thao tác | Input | Phản hồi | Gate |
|---|-------|----------|----------|-------|----------|------|
| 1 | System | Webhook | Meta/Zalo POST lead | payload signed | 200 + job id | ✓ |
| 2 | System | Worker | Dedup phone/email | — | new or merge | ✓ |
| 3 | System | Assignment engine | Gán owner round-robin | rules | owner_id | ✓ |
| 4 | CSKH | `/crm/leads` | Refresh / filter **Mới** | source, owner | Lead row | ✓ |
| 5 | CSKH | `/crm/leads/[id]` | Mở detail — xem source, UTM | — | Full lead card | ✓ |
| 6 | CSKH | `/crm/leads/review-queue` | (GDKD) Review nếu vào queue | assign owner | Owner set | ○ |

#### Nhánh E1 — Duplicate
System merge; CSKH thấy note "linked to existing" — mở lead gốc bước 5.

---

## CRM-UC-002 — Chăm sóc lead B2 (Liên hệ OK)

| # | Actor | Màn hình | Thao tác | Input | Gate |
|---|-------|----------|----------|-------|------|
| 1 | CSKH | `/crm/leads/[id]` | **+ Activity** → Call | duration, outcome | ✓ |
| 2 | CSKH | Same | Đổi status → **B2 Liên hệ OK** | — | ✓ |
| 3 | CSKH | Same | Ghi note nhu cầu | text | ✓ |
| 4 | CSKH | Same | (Optional) Schedule reminder | datetime | ○ |

---

## CRM-UC-003 — Review queue GDKD

| # | Actor | Màn hình | Thao tác | Input | Gate |
|---|-------|----------|----------|-------|------|
| 1 | GDKD | `/crm/leads/review-queue` | Mở queue | — | ✓ |
| 2 | GDKD | Row detail | Xem value, source | — | ✓ |
| 3 | GDKD | **Approve assign** | chọn owner + priority | staff id | ✓ |
| 4 | GDKD | **Reject** | comment bắt buộc | reason | ✓ |

---

## CRM-UC-004 — Add-on ngành trên lead

| # | Actor | Màn hình | Thao tác | Input | Gate |
|---|-------|----------|----------|-------|------|
| 1 | CSKH | `/crm/leads/[id]` | Tab add-ons → **+ Add-on** | industry từ catalog | ✓ |
| 2 | CSKH | Same | Gán specialist phụ | staff | ✓ |
| 3 | AM | Same | Track pipeline per add-on | status | ✓ |

---

## CRM-UC-005 — Pre-sales & KH MKT sơ bộ

| # | Actor | Màn hình | Thao tác | Input | Gate |
|---|-------|----------|----------|-------|------|
| 1 | Pre-sales | `/crm/intake` hoặc lead detail | Discovery notes | needs, budget | ✓ |
| 2 | Pre-sales | `/crm/marketing-plan` | **+ Tạo plan** draft | scope bullets | ✓ |
| 3 | Pre-sales | `/crm/marketing-plan/[id]` | **Save** KH MKT sơ bộ | fields | ✓ |
| 4 | Pre-sales | Link lead | Associate plan ↔ lead | — | ✓ |

---

## CRM-UC-006 — Chuyển lead → Proposal/HĐ

| # | Actor | Màn hình | Thao tác | Input | Gate |
|---|-------|----------|----------|-------|------|
| 1 | AM | `/crm/proposals` | **+ Tạo proposal** | template | ✓ |
| 2 | AM | Form proposal | Chọn SKU từ `/crm/catalog` | lines, pricing | ✓ |
| 3 | AM | Same | Export/send PDF client | email | ✓ client accept |
| 4 | AM | `/crm/hub` tab Contracts | Tạo HĐ draft | dates, value | ✓ |
| 5 | Finance | Same | Approve HĐ | — | ✓ signed |

---

## CRM-UC-007 — Convert → Customer + Case

| # | Actor | Màn hình | Thao tác | Input | Gate |
|---|-------|----------|----------|-------|------|
| 1 | AM | `/crm/leads/[id]` hoặc pipeline | **Convert to Customer** | confirm | ✓ Won |
| 2 | System | — | Tạo customer + link HĐ | — | customer_id | ✓ |
| 3 | AM | `/crm/customers/[id]` | Verify profile | legal name, tax | ✓ |
| 4 | AM | `/crm/service-delivery` | Lifecycle auto **Onboard** | service | ✓ |
| 5 | AM | `/agency/clients/new` | Link agency client | customer_id | ✓ |

---

## CRM-UC-008 — Quản lý bảng CSKH

| # | Actor | Màn hình | Thao tác | Input | Gate |
|---|-------|----------|----------|-------|------|
| 1 | CSKH Lead | `/crm` board hoặc leads list | Filter SLA breach | status, owner | ✓ |
| 2 | CSKH Lead | Bulk select | Reassign owner | staff ids | ✓ |
| 3 | CSKH Lead | Export | CSV snapshot standup | — | ✓ |

---

## CRM-UC-009 — Pipeline sales & đề xuất

| # | Actor | Màn hình | Thao tác | Input | Gate |
|---|-------|----------|----------|-------|------|
| 1 | Sales | `/crm/sales` tab Funnel | Xem kanban | — | ✓ |
| 2 | Sales | Drag card | Đổi stage | Proposal/Negotiation | ✓ |
| 3 | Sales | Lost | Chọn **lost reason** | taxonomy | ✓ |
| 4 | AM | Same | Forecast weight view | — | ○ |

---

## CRM-UC-010 — Dự án BĐS (RE Projects)

| # | Actor | Màn hình | Thao tác | Input | Gate |
|---|-------|----------|----------|-------|------|
| 1 | AM BĐS | `/crm/re-projects` | **+ Project** | name, location | ✓ |
| 2 | AM | `/crm/re-projects/[id]` | Config lead routing | units | ✓ |
| 3 | AM | Same | **Export** accounting report | period | ✓ |
| 4 | Buyer | `/meta/facebook-ads` | Map campaign → RE project | campaign id | ✓ |

---

## CRM-UC-011 — Hub hợp đồng & lifecycle

| # | Actor | Màn hình | Thao tác | Input | Gate |
|---|-------|----------|----------|-------|------|
| 1 | AM | `/crm/hub` | Tab **Contracts** | filter client | ✓ |
| 2 | AM | Row | Drill contract detail | — | ✓ |
| 3 | AM | Alert widget | Renewal 30/60/90d | — | ✓ action plan |

---

## CRM-UC-012 — Catalog dịch vụ/ngành

| # | Actor | Màn hình | Thao tác | Input | Gate |
|---|-------|----------|----------|-------|------|
| 1 | Admin | `/crm/catalog` | **+ Scope/Product** | name, slug, price | ✓ |
| 2 | Admin | Row | Edit / disable | active flag | ✓ |
| 3 | AM | `/crm/proposals` | Pick from catalog | SKU | ✓ |

---

## CRM-UC-013 — KPI nhân sự & chấm công

| # | Actor | Màn hình | Thao tác | Input | Gate |
|---|-------|----------|----------|-------|------|
| 1 | HR | `/crm/payroll` | View attendance | month | ✓ |
| 2 | Lead | `/crm/staff-kpi` | Compare vs target | AM/SP | ✓ |
| 3 | HR | `/crm/kpi` | **Export** scorecard | — | ✓ |

---

## CRM-UC-014 — Dashboard kinh doanh chủ DN

| # | Actor | Màn hình | Thao tác | Input | Gate |
|---|-------|----------|----------|-------|------|
| 1 | Chủ DN | `/crm/business-dashboard` | Open dashboard | YTD | ✓ |
| 2 | Chủ DN | Widgets | Revenue, pipeline, win rate | — | ✓ |
| 3 | Chủ DN | `/crm/owner-weekly` | **Export** weekly | config | ✓ |

---

## CRM-UC-015 — Import/export lead

| # | Actor | Màn hình | Thao tác | Input | Gate |
|---|-------|----------|----------|-------|------|
| 1 | CSKH | `/crm/leads` | **Import** → download template | — | ✓ |
| 2 | CSKH | Import UI | Upload CSV | file | ✓ validation |
| 3 | CSKH | Preview | Fix errors / confirm partial | — | ✓ |
| 4 | CSKH | Same | **Export** filtered CSV | filters | ✓ |
