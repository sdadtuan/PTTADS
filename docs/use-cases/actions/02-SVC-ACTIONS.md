# Chi tiết hành động — Service Delivery (SVC)

> **UC gốc:** [`../02-AGENCY-SERVICE-DELIVERY.md`](../02-AGENCY-SERVICE-DELIVERY.md)

---

## SVC-UC-001 — Workflow lifecycle 7 stage

**Mục tiêu:** *"Theo dõi client từ ký HĐ → bàn giao → duy trì trên một kanban."*

| # | Actor | Màn hình | Thao tác | Input | Gate |
|---|-------|----------|----------|------|
| 1 | AM | `/crm/service-delivery` | Filter service slug / AM | — | ✓ |
| 2 | AM | Kanban | Xem card stage hiện tại | 7 stages | ✓ |
| 3 | AM | `/crm/service-delivery/[id]` | Tab stage tương ứng | onboard/deliver/… | ✓ |
| 4 | AM | Workflow panel | **Advance stage** | confirm + gate | ✓ gate pass |
| 5 | System | — | Log stage history | timestamp | ✓ immutable |

---

## SVC-UC-002 — Onboard checklist client

| # | Actor | Màn hình | Thao tác | Input | Gate |
|---|-------|----------|----------|------|
| 1 | AM | `/agency/clients/[id]` | Scroll **Onboarding widget** | — | ✓ |
| 2 | AM | Checklist items | Tick từng item | legal, billing, access… | ✓ |
| 3 | AM | Link evidence | Paste URL/file note | — | ○ |
| 4 | AM | `/crm/service-delivery/[id]` Onboard tab | Xem **LifecycleOnboardingPanel** % | — | ✓ 100% |
| 5 | AM | **Activate client** nếu prospect | status → active | — | ✓ |

---

## SVC-UC-003 — Deliver stage — TMMT chính thức

| # | Actor | Màn hình | Thao tác | Gate |
|---|-------|----------|----------|------|
| 1 | AM | Lifecycle detail tab Deliver | Advance → Deliver | ✓ onboard done |
| 2 | AM | `/crm/marketing-plan/[id]` | Publish TMMT version | ✓ |
| 3 | Buyer | `/crm/launch-qa` + `/meta/ads-ops` | First campaign live | ✓ |
| 4 | AM | Notes panel | Ghi hypercare start date | ✓ |

---

## SVC-UC-004 — Handover → Retain + finance gate

| # | Actor | Màn hình | Thao tác | Gate |
|---|-------|----------|----------|------|
| 1 | AM | `/crm/financials` | ⚠ Check AR aging | ⚠ GAP-P1-01 manual |
| 2 | AM | Lifecycle | Advance → **Handover** | ✓ finance OK |
| 3 | AM | Meeting | Client sign-off pack | ✓ |
| 4 | AM | Lifecycle | Advance → **Retain** | ✓ |
| 5 | AM | `/crm/sop` | Link retain SOP | ✓ |

---

## SVC-UC-005 — Launch QA checklist

| # | Actor | Màn hình | Thao tác | Input | Gate |
|---|-------|----------|----------|-------|------|
| 1 | Buyer | `/crm/launch-qa` | Filter **in_progress** | client | ✓ |
| 2 | Buyer | `/crm/service-delivery/[id]` | Panel **Launch QA** | — | ✓ |
| 3 | Buyer | Checklist | Tick: UTM, pixel, LP, budget, audience | each item | ✓ critical |
| 4 | Buyer | Submit | Mark run **passed** | — | ✓ |
| 5 | Buyer | Export | QA sign-off PDF | ○ |

---

## SVC-UC-006 — Creative Hub upload & review

| # | Actor | Màn hình | Thao tác | Input | Gate |
|---|-------|----------|----------|-------|------|
| 1 | Creative | `/crm/creatives` | **Submit creative** | files, copy, client, format | ✓ |
| 2 | Lead | Tab pending | Internal review approve | — | ✓ |
| 3 | Creative | **Submit client approval** | — | pending_client | ✓ |
| 4 | Client | portal `/creatives` | Approve/Reject | note if reject | ✓ |
| 5 | Buyer | `/meta/ads-ops` | Pick creative in wizard | approved only | ✓ |

---

## SVC-UC-007 — Campaign Write queue approval

| # | Actor | Màn hình | Thao tác | Input | Gate |
|---|-------|----------|----------|-------|------|
| 1 | Buyer | `/meta/ads-ops` | Submit launch/edit | diff snapshot | ✓ |
| 2 | Buyer | `/crm/campaign-writes` | View **pending** tab | — | ✓ |
| 3 | GDKD | Same row | **Approve** / **Reject** | comment if reject | ✓ |
| 4 | System | Worker | Meta API execute | — | ✓ job completed |
| 5 | Buyer | `/meta/facebook-ads` | Verify campaign state | — | ✓ |

---

## SVC-UC-008 — Map channel account (Meta/Google)

| # | Actor | Màn hình | Thao tác | Input | Gate |
|---|-------|----------|----------|-------|------|
| 1 | AM | `/agency/clients/[id]` | **+ Channel account** | meta/google, account_id | ✓ |
| 2 | Tracking | Same | **Connect token** / OAuth | token or OAuth flow | ✓ |
| 3 | Tracking | Same | **Sync insights** button | — | job queued | ✓ |
| 4 | AM | Hub module | Confirm data T-1 | — | ✓ |

---

## SVC-UC-009 — Agency ingest monitor

| # | Actor | Màn hình | Thao tác | Gate |
|---|-------|----------|----------|------|
| 1 | Tracking | `/agency/ingest` | View pipeline volume | ✓ |
| 2 | Tracking | `/agency/jobs` | Filter failed jobs | ✓ |
| 3 | DevOps | Retry/replay | fix payload | ✓ |

---

## SVC-UC-010 — KPI definitions agency-wide

| # | Actor | Màn hình | Thao tác | Gate |
|---|-------|----------|----------|------|
| 1 | Head | `/agency/kpi-definitions` | **+ KPI** formula | ✓ |
| 2 | Head | Delete/edit | — | ✓ |
| 3 | AM | Hubs | Widgets consume defs | ✓ |

---

## SVC-UC-011 — SOP & marketing plan

| # | Actor | Màn hình | Thao tác | Gate |
|---|-------|----------|----------|------|
| 1 | Strategist | `/crm/sop` | **+ SOP run** | ✓ |
| 2 | AM | `/crm/marketing-plan` | Quarterly plan CRUD | ✓ |

---

## SVC-UC-012 — Offboarding SOP

| # | Actor | Màn hình | Thao tác | Gate |
|---|-------|----------|----------|------|
| 1 | AM | Lifecycle | Stage Offboarding | ✓ |
| 2 | AM | `/agency/clients/[id]` | **Offboard client** | ✓ |
| 3 | AM | handover export | Data pack | ○ |
