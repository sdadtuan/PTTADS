# Chi tiết hành động — CRM Core (CRM)

> **UC gốc:** [`../01-CRM-CORE.md`](../01-CRM-CORE.md)  
> **Cross-system:** [`00-SYSTEM-ACTIONS.md`](00-SYSTEM-ACTIONS.md) · **Zalo lead:** [`08-ZALO-ACTIONS.md`](08-ZALO-ACTIONS.md)

---

## CRM-UC-001 — Đăng nhập & phân công lead tự động

**Mục tiêu khách hàng:** *"Lead từ ads/form vào CRM ngay, có người gọi trong 15 phút."*

**Actors:** System, CSKH, GDKD (fallback queue)

| # | Actor | Màn hình | Thao tác | Input | Phản hồi | Gate |
|---|-------|----------|----------|-------|----------|------|
| 1 | System | `POST /webhooks/meta` hoặc `/zalo` | Nhận lead webhook | signed payload | 200 + job id | ✓ signature |
| 2 | System | worker | Dedup phone/email fingerprint | phone, email | new or merge | ✓ BR-CRM-01 |
| 3 | System | Assignment engine | Gán owner round-robin / territory | rules config | owner_id | ✓ |
| 4 | System | — | Set status **Mới**, source tag | meta/zalo/form | crm_leads row | ✓ |
| 5 | CSKH | `/login` | Đăng nhập ops-web | credentials | JWT + cap | ✓ |
| 6 | CSKH | `/crm/leads` | Filter **Mới** + owner=me | source filter | Lead row | ✓ |
| 7 | CSKH | `/crm/leads/[id]` | Mở detail — xem source, UTM, campaign | — | Full lead card | ✓ |
| 8 | CSKH | Same | **Log call** lần đầu (SLA 15 phút) | duration, note | Timeline | ✓ SLA |
| 9 | GDKD | `/crm/leads/review-queue` | Review nếu vào queue (no rule match) | assign owner | Owner set | ○ E2 |

#### Nhánh M — Lead Meta
Bước 1: source=meta; attribution campaign_id nếu mapped ([META-UC-004](03-META-ACTIONS.md)).

#### Nhánh Z — Lead Zalo
Bước 1: source=zalo; dedup [ZALO-UC-013](08-ZALO-ACTIONS.md); poll backup [ZALO-UC-012](08-ZALO-ACTIONS.md).

#### Nhánh E1 — Duplicate
System merge; CSKH thấy note "linked to existing" — mở lead gốc bước 7.

#### Nhánh E2 — Không match assignment rule
Lead vào GDKD review queue → [CRM-UC-003](#crm-uc-003--review-queue-gdkd).

#### Tiêu chí nghiệm thu
- [ ] Lead visible ≤ 1 phút từ webhook
- [ ] Một lead active chỉ một owner primary (BR-CRM-01)
- [ ] CSKH log call trong 15 phút (SLA)

---

## CRM-UC-002 — Chăm sóc lead B2 (Liên hệ OK)

**Mục tiêu khách hàng:** *"Biết lead nào đã liên hệ được, ai đang follow — không bỏ sót."*

**Actors:** CSKH, Sales

| # | Actor | Màn hình | Thao tác | Input | Phản hồi | Gate |
|---|-------|----------|----------|-------|----------|------|
| 1 | CSKH | `/crm/leads` | Filter owner=me, status **Mới/B1** | — | List | ✓ |
| 2 | CSKH | `/crm/leads/[id]` | **+ Activity** → Call | duration, outcome | Timeline row | ✓ |
| 3 | CSKH | Same | Đổi status → **B2 — Liên hệ OK** | — | Status update | ✓ |
| 4 | CSKH | Same | Ghi note nhu cầu khách | text | Saved | ✓ |
| 5 | CSKH | Same | Tag qualify level (hot/warm/cold) | tag | Filterable | ○ |
| 6 | CSKH | Same | (Optional) Schedule reminder follow-up | datetime | Reminder | ○ |
| 7 | CSKH | Same | Chuyển Pre-sales nếu qualify | — | → [CRM-UC-005](#crm-uc-005--pre-sales--kh-mkt-sơ-bộ) | ✓ hot/warm |
| 8 | CSKH Lead | `/crm/cskh-board` | Monitor SLA breach trên board | filter | Red rows | ✓ [UC-008](#crm-uc-008--quản-lý-bảng-cskh) |

#### Nhánh E1 — Không liên lạc được
Bước 2 outcome=No answer → status **B1 retry** hoặc **Lost** + lost_reason.

#### Nhánh E2 — Won trực tiếp (lead ads agency)
| # | Actor | Màn hình | Thao tác | Gate |
|---|-------|----------|----------|------|
| W1 | Sales | `/crm/leads/[id]` hoặc `/crm/pipeline` | Status → **Won** + deal_value_vnd | ✓ |
| W2 | System | — | Hub CPA refresh (Meta/Zalo) | ✓ [SYS-UC-002](00-SYSTEM-ACTIONS.md), [ZALO-UC-015](08-ZALO-ACTIONS.md) |
| W3 | Buyer | `/zalo/zalo-ads` hoặc `/meta/facebook-ads` | Verify conversion column | ✓ |

#### Tiêu chí nghiệm thu
- [ ] Activity timeline có call log trước B2
- [ ] SLA contact time tracked trên KPI CSKH

---

## CRM-UC-003 — Review queue GDKD

**Mục tiêu khách hàng:** *"Deal lớn hoặc lead khó gán được GDKD quyết định — không rơi vào void."*

**Actors:** GDKD, Head Sales

| # | Actor | Màn hình | Thao tác | Input | Phản hồi | Gate |
|---|-------|----------|----------|-------|----------|------|
| 1 | GDKD | `/login` | Đăng nhập cap GDKD | credentials | JWT | ✓ |
| 2 | GDKD | `/crm/leads/review-queue` hoặc `/crm/hub` widget | Mở review queue | — | Pending list | ✓ |
| 3 | GDKD | Row | Xem summary: source, value, client | — | Detail panel | ✓ |
| 4 | GDKD | Same | Kiểm tra estimated deal value vs threshold | value VND | Flag high-value | ✓ BR-CRM-02 |
| 5 | GDKD | Same | **Approve assign** → chọn owner | staff id, priority | Owner set | ✓ |
| 6 | GDKD | Same | Hoặc **Reject** | comment bắt buộc | Archived + reason | ✓ |
| 7 | CSKH | `/crm/leads/[id]` | Owner mới nhận lead | notification | Row assigned | ✓ |
| 8 | GDKD | `/crm/hub` | Verify queue empty EOD | — | Zero pending | ○ |

#### Nhánh E1 — Deal > threshold trước proposal
GDKD must approve assign trước khi AM tạo proposal ([CRM-UC-006](#crm-uc-006--chuyển-lead--proposalhđ)).

#### Tiêu chí nghiệm thu
- [ ] Reject bắt buộc có comment
- [ ] High-value lead không vào proposal without GDKD assign

---

## CRM-UC-004 — Add-on ngành trên lead

**Mục tiêu khách hàng:** *"Lead cần đa dịch vụ (BĐS + MKT) được route đúng specialist."*

**Actors:** CSKH, AM

| # | Actor | Màn hình | Thao tác | Input | Phản hồi | Gate |
|---|-------|----------|----------|-------|----------|------|
| 1 | CSKH | `/crm/leads/[id]` | Tab **Add-ons** | — | List empty/new | ✓ |
| 2 | CSKH | Same | **+ Add-on** | industry từ catalog | Row created | ✓ [UC-012](#crm-uc-012--catalog-dịch-vụngành) |
| 3 | CSKH | Same | Gán specialist phụ | staff id | Owner secondary | ✓ |
| 4 | AM | Same | Track pipeline per add-on line | status per line | Multi-track | ✓ |
| 5 | Specialist | `/crm/leads/[id]` | Nhận notification add-on assigned | — | Activity | ✓ |
| 6 | AM | `/crm/proposals` | Include add-on SKUs khi proposal | catalog lines | Pricing | ○ |

#### Tiêu chí nghiệm thu
- [ ] Lead có ≥1 add-on với specialist
- [ ] Routing rules áp dụng per ngành

---

## CRM-UC-005 — Pre-sales & KH MKT sơ bộ

**Mục tiêu khách hàng:** *"Trước khi báo giá, hiểu rõ nhu cầu khách và có scope marketing sơ bộ."*

**Actors:** Pre-sales, AM

| # | Actor | Màn hình | Thao tác | Input | Phản hồi | Gate |
|---|-------|----------|----------|-------|----------|------|
| 1 | Pre-sales | `/crm/leads/[id]` | Xác nhận lead **B2 qualify** | — | Status OK | ✓ |
| 2 | Pre-sales | `/crm/intake` hoặc lead detail tab Discovery | Discovery call notes | needs, pain points | Saved | ✓ |
| 3 | Pre-sales | Same | Ghi budget range + timeline | VND, dates | Saved | ✓ |
| 4 | Pre-sales | Same | Upload competitor / brief docs | files | Attachments | ○ |
| 5 | Pre-sales | `/crm/marketing-plan` | **+ Tạo plan** draft KH MKT sơ bộ | scope bullets | plan id | ✓ |
| 6 | Pre-sales | `/crm/marketing-plan/[id]` | **Save** fields: channels, KPI target | meta/zalo/seo | Draft saved | ✓ |
| 7 | Pre-sales | Lead detail | Associate plan ↔ lead | link | Cross-ref | ✓ |
| 8 | Pre-sales | Lead / pipeline | Advance stage → **Proposal prep** | — | Ready for UC-006 | ✓ |

#### Nhánh E1 — Khách chưa sẵn sàng budget
Ghi note "nurture" → reminder 30 ngày; không advance proposal.

#### Tiêu chí nghiệm thu
- [ ] KH MKT draft linked to lead
- [ ] Discovery có needs + budget + timeline

---

## CRM-UC-006 — Chuyển lead → Proposal/HĐ

**Mục tiêu khách hàng:** *"Từ scope đã thống nhất → proposal chuyên nghiệp → HĐ ký — có version control."*

**Actors:** AM, Finance, Legal (optional)

| # | Actor | Màn hình | Thao tác | Input | Phản hồi | Gate |
|---|-------|----------|----------|-------|----------|------|
| 1 | AM | `/crm/proposals` | **+ Tạo proposal** | template | Draft id | ✓ |
| 2 | AM | Form proposal | Chọn SKU từ `/crm/catalog` | lines, pricing | Totals calc | ✓ |
| 3 | AM | Same | Link KH MKT từ [UC-005](#crm-uc-005--pre-sales--kh-mkt-sơ-bộ) | plan id | Scope attached | ✓ |
| 4 | AM | Same | Preview PDF | — | Render OK | ✓ |
| 5 | AM | Same | Export/send PDF client | email | Sent log | ✓ client review |
| 6 | Client | Email/offline | Accept scope (external) | signed/email | AM confirms | ✓ |
| 7 | AM | `/crm/hub` tab **Contracts** | **+ Tạo HĐ** draft | dates, value, terms | Contract id | ✓ |
| 8 | Finance | Same | Approve HĐ + billing terms | — | Status active | ✓ signed |

#### Nhánh E1 — Revision
AM tạo proposal v2; v1 archived; history retained.

#### Nhánh E2 — GDKD gate (deal > threshold)
[CRM-UC-003](#crm-uc-003--review-queue-gdkd) assign phải pass trước bước 1.

#### Tiêu chí nghiệm thu
- [ ] Proposal có catalog SKU + pricing
- [ ] HĐ active trước convert customer

---

## CRM-UC-007 — Convert → Customer + Case

**Mục tiêu khách hàng:** *"Ký HĐ xong → customer master + lifecycle delivery tự khởi tạo."*

**Actors:** AM, System

| # | Actor | Màn hình | Thao tác | Input | Phản hồi | Gate |
|---|-------|----------|----------|-------|----------|------|
| 1 | AM | `/crm/leads/[id]` hoặc `/crm/pipeline` | Xác nhận **Won** / HĐ signed | — | Precondition | ✓ |
| 2 | AM | Same | **Convert to Customer** | confirm dialog | Job started | ✓ |
| 3 | System | — | Tạo Customer master + link HĐ | legal entity | customer_id | ✓ BR-CRM-03 |
| 4 | System | — | Merge duplicate lead records | — | Single customer | ✓ |
| 5 | AM | `/crm/customers/[id]` | Verify profile | legal name, tax, contacts | Profile complete | ✓ |
| 6 | AM | `/crm/service-delivery` | Lifecycle auto **Onboard** | service slug from HĐ | Kanban card | ✓ [SVC-UC-001](02-SVC-ACTIONS.md) |
| 7 | AM | `/agency/clients/new` | **+ Client** link customer_id | name, industry, AM | agency client UUID | ✓ |
| 8 | AM | [`00-SYSTEM-ACTIONS.md`](00-SYSTEM-ACTIONS.md#sys-uc-001--onboard-client-mới-end-to-end) | Bắt đầu onboard E2E | — | Orchestrator | ✓ SYS-001 |

#### Tiêu chí nghiệm thu
- [ ] Customer code unique (BR-CRM-03)
- [ ] Lifecycle Onboard card tồn tại
- [ ] Agency client linked customer_id

---

## CRM-UC-008 — Quản lý bảng CSKH

**Mục tiêu khách hàng:** *"Lead team thấy SLA breach, reassign nhanh — standup có số liệu."*

**Actors:** CSKH Lead, CSKH

| # | Actor | Màn hình | Thao tác | Input | Phản hồi | Gate |
|---|-------|----------|----------|-------|----------|------|
| 1 | CSKH Lead | `/login` | Đăng nhập cap lead | credentials | JWT | ✓ |
| 2 | CSKH Lead | `/crm/cskh-board` hoặc `/crm/leads` | Mở bảng CSKH | — | Board load | ✓ |
| 3 | CSKH Lead | Same | Filter **SLA breach** / status / owner | filters | Red/yellow rows | ✓ |
| 4 | CSKH Lead | Same | Bulk select leads overdue | checkbox | Selection | ✓ |
| 5 | CSKH Lead | Same | **Reassign owner** | staff ids | Owners updated | ✓ |
| 6 | CSKH Lead | Same | Reschedule follow-up batch | datetime | Reminders set | ○ |
| 7 | CSKH Lead | Same | **Export** CSV snapshot | filters | File download | ✓ standup |
| 8 | CSKH Lead | `/crm/staff-kpi` | Review contact SLA KPI | month | vs target | ○ |

#### Tiêu chí nghiệm thu
- [ ] SLA breaches visible trên board
- [ ] Bulk reassign không mất activity history

---

## CRM-UC-009 — Pipeline sales & đề xuất

**Mục tiêu khách hàng:** *"Sales thấy funnel rõ — forecast và lost reason có taxonomy."*

**Actors:** Sales, AM

| # | Actor | Màn hình | Thao tác | Input | Phản hồi | Gate |
|---|-------|----------|----------|-------|----------|------|
| 1 | Sales | `/crm/sales` tab **Funnel** | Xem kanban stages | — | Cards load | ✓ |
| 2 | Sales | Same | Drag card → stage mới | Proposal/Negotiation | Stage update | ✓ |
| 3 | Sales | Card detail | Update deal value + close date | VND, date | Forecast weight | ✓ |
| 4 | Sales | Same | **Lost** → chọn **lost reason** | taxonomy | Lost recorded | ✓ |
| 5 | Sales | Same | **Won** → deal_value_vnd | revenue | Won + hub refresh | ✓ SYS-002 |
| 6 | AM | Same | Forecast weight view | — | Pipeline value | ○ |
| 7 | AM | `/crm/business-dashboard` | Cross-check win rate | YTD | Widget | ○ |

#### Tiêu chí nghiệm thu
- [ ] Lost bắt buộc có reason
- [ ] Won có deal_value_vnd

---

## CRM-UC-010 — Dự án BĐS (RE Projects)

**Mục tiêu khách hàng:** *"Campaign ads map đúng dự án BĐS — báo cáo accounting the lead theo unit."*

**Actors:** AM BĐS, Buyer

| # | Actor | Màn hình | Thao tác | Input | Phản hồi | Gate |
|---|-------|----------|----------|-------|----------|------|
| 1 | AM BĐS | `/crm/re-projects` | **+ Project** | name, location | Project id | ✓ |
| 2 | AM | `/crm/re-projects/[id]` | Config lead routing rules | units, staff | Rules saved | ✓ |
| 3 | AM | Same | Link campaigns / forms | campaign ids | Mapping | ✓ |
| 4 | Buyer | `/meta/facebook-ads` hoặc `/zalo/zalo-ads` | Map campaign → RE project | campaign id | Hub green | ✓ |
| 5 | CSKH | `/crm/leads` | Filter by RE project | project id | Scoped leads | ✓ |
| 6 | AM | `/crm/re-projects/[id]` | **Export** accounting report | period | CSV/PDF | ✓ |

#### Tiêu chí nghiệm thu
- [ ] Lead attribution có RE project id
- [ ] Export report khớp lead count hub

---

## CRM-UC-011 — Hub hợp đồng & lifecycle

**Mục tiêu khách hàng:** *"AM biết HĐ nào sắp hết hạn — renewal có action plan."*

**Actors:** AM, Finance

| # | Actor | Màn hình | Thao tác | Input | Phản hồi | Gate |
|---|-------|----------|----------|-------|----------|------|
| 1 | AM | `/crm/hub` | Mở CRM hub | — | Dashboard load | ✓ |
| 2 | AM | Tab **Contracts** | Filter client / status | active/expiring | List | ✓ |
| 3 | AM | Row | Drill contract detail | — | Terms, value, dates | ✓ |
| 4 | AM | Alert widget | Renewal **30/60/90d** | — | Action items | ✓ |
| 5 | AM | Same | Ghi action plan renewal | note, owner | Saved | ✓ |
| 6 | Finance | `/crm/financials` | Cross-check AR vs contract | — | Billing current | ✓ [SVC-UC-004](02-SVC-ACTIONS.md) |
| 7 | AM | `/crm/service-delivery` | Link lifecycle stage | lifecycle id | Badge sync | ✓ |

#### Tiêu chí nghiệm thu
- [ ] Expiring contracts visible 90d ahead
- [ ] Drill contract → customer → lifecycle trong 3 click

---

## CRM-UC-012 — Catalog dịch vụ/ngành

**Mục tiêu khách hàng:** *"Proposal và add-on dùng SKU chuẩn — giá nhất quán."*

**Actors:** Admin, AM

| # | Actor | Màn hình | Thao tác | Input | Phản hồi | Gate |
|---|-------|----------|----------|-------|----------|------|
| 1 | Admin | `/crm/catalog` | **+ Scope/Product** | name, slug, price VND | Row created | ✓ |
| 2 | Admin | Row | Edit description / bundle | text | Saved | ✓ |
| 3 | Admin | Same | Disable SKU (không xóa) | active=false | Hidden proposal | ✓ |
| 4 | AM | `/crm/proposals` | Pick from catalog | SKU search | Line added | ✓ |
| 5 | AM | `/crm/leads/[id]` tab Add-ons | Pick industry scope | catalog slug | Add-on row | ✓ [UC-004](#crm-uc-004--add-on-ngành-trên-lead) |

#### Tiêu chí nghiệm thu
- [ ] Disabled SKU không pick được proposal mới
- [ ] Slug unique per product

---

## CRM-UC-013 — KPI nhân sự & chấm công

**Mục tiêu khách hàng:** *"Lead/HR đánh giá CSKH và AM theo KPI thực — có số chấm công."*

**Actors:** HR, Team Lead

| # | Actor | Màn hình | Thao tác | Input | Phản hồi | Gate |
|---|-------|----------|----------|-------|----------|------|
| 1 | HR | `/crm/payroll` | View attendance tháng | month picker | Grid | ✓ |
| 2 | Lead | `/crm/staff-kpi` | Compare staff vs target | AM/CSKH role | Scorecards | ✓ |
| 3 | Lead | Same | Drill KPI: contact SLA, win rate | staff id | Detail | ✓ |
| 4 | HR | `/crm/kpi` | **Export** scorecard | period | CSV | ✓ |
| 5 | Lead | `/crm/cskh-board` | Cross-check SLA vs KPI | — | Consistent | ○ |

#### Tiêu chí nghiệm thu
- [ ] KPI export reproducible cùng kỳ
- [ ] Attendance month locked sau payroll

---

## CRM-UC-014 — Dashboard kinh doanh chủ DN

**Mục tiêu khách hàng:** *"Chủ DN xem revenue, pipeline, win rate YTD — không cần Excel."*

**Actors:** Chủ DN, AM

| # | Actor | Màn hình | Thao tác | Input | Phản hồi | Gate |
|---|-------|----------|----------|-------|----------|------|
| 1 | Chủ DN | `/login` | Đăng nhập cap owner | credentials | JWT | ✓ |
| 2 | Chủ DN | `/crm/business-dashboard` | Open dashboard | YTD default | Widgets load | ✓ |
| 3 | Chủ DN | Widgets | Revenue, pipeline value, win rate | — | Numbers | ✓ |
| 4 | Chủ DN | Same | Filter AM / service line | filters | Scoped | ✓ |
| 5 | Chủ DN | `/crm/owner-weekly` | **Export** weekly report | config | PDF/CSV | ✓ |
| 6 | Chủ DN | `/crm/hub` | Drill expiring contracts | click | Contract list | ○ |

#### Tiêu chí nghiệm thu
- [ ] YTD revenue khớp finance export ± rounding
- [ ] Owner không thấy staff payroll detail

---

## CRM-UC-015 — Import/export lead

**Mục tiêu khách hàng:** *"Import lead sự kiện/offline an toàn — export phục vụ báo cáo."*

**Actors:** CSKH, Admin

| # | Actor | Màn hình | Thao tác | Input | Phản hồi | Gate |
|---|-------|----------|----------|-------|----------|------|
| 1 | CSKH | `/crm/leads` | Click **Import** → download template | — | CSV template | ✓ |
| 2 | CSKH | Import UI | Upload CSV | file | Parse preview | ✓ |
| 3 | CSKH | Preview | Fix validation errors / confirm partial | row fixes | Error count | ✓ |
| 4 | CSKH | Same | **Confirm import** | — | N rows created | ✓ dedup |
| 5 | System | — | Assignment engine on import rows | — | Owners set | ✓ |
| 6 | CSKH | `/crm/leads` | Verify imported leads | filter source=import | Rows | ✓ |
| 7 | CSKH | Same | **Export** filtered CSV | filters | File download | ✓ |

#### Nhánh E1 — Duplicate on import
Preview flag dup → skip or merge per policy.

#### Tiêu chí nghiệm thu
- [ ] Invalid phone rows blocked at preview
- [ ] Import dedup không tạo trùng 24h

---

## Luồng CRM end-to-end (sales → delivery)

| # | UC | Actor | Mục tiêu |
|---|-----|-------|----------|
| 1 | CRM-001 | System/CSKH | Lead ingest + assign |
| 2 | CRM-002 | CSKH | B2 contact OK |
| 3 | CRM-005 | Pre-sales | KH MKT sơ bộ |
| 4 | CRM-006 | AM | Proposal → HĐ |
| 5 | CRM-007 | AM | Convert → Customer |
| 6 | SVC-001 | AM | Lifecycle Onboard |
| 7 | SYS-001 | AM/Tracking | Onboard E2E |

**Closed-loop ads:** CRM-002 nhánh E2 Won → [SYS-UC-002](00-SYSTEM-ACTIONS.md) + [ZALO-UC-015](08-ZALO-ACTIONS.md).
