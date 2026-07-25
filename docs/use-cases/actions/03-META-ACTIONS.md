# Chi tiết hành động — Meta Enterprise (META)

> **UC gốc:** [`../03-META-ENTERPRISE.md`](../03-META-ENTERPRISE.md)

---

## META-UC-001 — Kết nối ad account & sync insights

| # | Actor | Màn hình | Thao tác | Input | Gate |
|---|-------|----------|----------|-------|------|
| 1 | Tracking | `/agency/clients/[id]` | Add Meta channel account | ad_account_id | ✓ |
| 2 | Tracking | Same | Paste **access token** → Lưu | token | ✓ vault saved |
| 3 | Tracking | Same | Click **Sync insights** | — | job enqueued | ✓ |
| 4 | Buyer | `/meta/facebook-ads` | Client filter → tab Clients | — | last_sync time | ✓ green |
| 5 | Buyer | Same | **Refresh** | date range | KPI populate | ✓ |

---

## META-UC-002 — Hub map campaign ↔ CRM

| # | Actor | Màn hình | Thao tác | Input | Gate |
|---|-------|----------|----------|-------|------|
| 1 | Buyer | `/meta/facebook-ads` tab Campaigns | Sort **unmapped** | — | ✓ yellow rows |
| 2 | Buyer | Row action | **Map to client** / suggest accept | client, project | ✓ |
| 3 | Buyer | `/crm/hub` tab Campaigns | Verify map | — | ✓ |
| 4 | AM | Same | Bulk map CSV | ○ import |

---

## META-UC-003 — Xem CPL/ROAS trên hub

| # | Actor | Màn hình | Thao tác | Gate |
|---|-------|----------|----------|------|
| 1 | Buyer | `/meta/facebook-ads` | Select client + T-7/T-30 | ✓ |
| 2 | Buyer | KPI grid | Read Spend, Leads, CPL, ROAS | ✓ |
| 3 | Buyer | Drill campaign row | Underperforming list | ✓ |
| 4 | AM | Export | CSV for client report | ✓ |

---

## META-UC-004 — Webhook lead Meta → CRM

| # | Actor | Màn hình | Thao tác | Gate |
|---|-------|----------|----------|------|
| 1 | System | Meta webhook | POST leadgen | ✓ 200 |
| 2 | Tracking | `/agency/ingest` | Monitor job | ✓ |
| 3 | CSKH | `/crm/leads` | New lead visible | ✓ ≤60s |
| 4 | Tracking | `/meta/tracking` | Verify dedup rate | ✓ |

---

## META-UC-005 — CAPI event gửi & dedup

| # | Actor | Màn hình | Thao tác | Gate |
|---|-------|----------|----------|------|
| 1 | Sales | `/crm/leads/[id]` | Mark Won | ✓ |
| 2 | System | CAPI worker | Send event hashed PII | ✓ |
| 3 | Tracking | `/meta/tracking` | Tab CAPI events | ✓ ack |
| 4 | Tracking | Meta Events Manager | Verify test event | ✓ |

---

## META-UC-006 — Tracking health & pixel test

| # | Actor | Màn hình | Thao tác | Gate |
|---|-------|----------|----------|------|
| 1 | Tracking | `/meta/tracking` | Select client | ✓ |
| 2 | Tracking | **Preflight checklist** | Tick items | ✓ |
| 3 | Tracking | **Send test event** | — | ✓ green |
| 4 | Tracking | Conversion rules | Configure rules | ✓ |

---

## META-UC-007 — Launch Ads wizard

| # | Actor | Màn hình | Thao tác | Input | Gate |
|---|-------|----------|----------|-------|------|
| 1 | Buyer | `/meta/ads-ops` | Launch tab | — | ✓ |
| 2 | Buyer | Step 1 | Chọn client, objective | client_id | ✓ |
| 3 | Buyer | Step 2 | Budget, schedule | VND/day | ✓ |
| 4 | Buyer | Step 3 | Audience + placement | targeting | ✓ |
| 5 | Buyer | Step 4 | Creative from hub | approved asset | ✓ |
| 6 | Buyer | Preflight panel | Fix warnings | — | ✓ |
| 7 | Buyer | **Submit launch** | — | write queue id | ✓ Launch QA passed |

---

## META-UC-008 — Edit campaign có governance

| # | Actor | Màn hình | Thao tác | Gate |
|---|-------|----------|----------|------|
| 1 | Buyer | `/meta/ads-ops` Edit tab | Select campaign snapshot | ✓ |
| 2 | Buyer | Diff view | Change budget/status | ✓ |
| 3 | Buyer | Submit edit | → campaign-writes | ✓ threshold approval |
| 4 | GDKD | `/crm/campaign-writes` | Approve | ✓ |

---

## META-UC-009 — Anomaly detection & alert

| # | Actor | Màn hình | Thao tác | Gate |
|---|-------|----------|----------|------|
| 1 | System | — | Detect CPL/spend anomaly | ✓ |
| 2 | Buyer | `/meta/facebook-ads` tab Alerts | View banner | ✓ |
| 3 | Buyer | **Acknowledge alert** | — | ✓ |
| 4 | Buyer | `/meta/intelligence` | Drill anomaly detail | ✓ |

---

## META-UC-010 — Intelligence forecast

| # | Actor | Màn hình | Thao tác | Gate |
|---|-------|----------|----------|------|
| 1 | AM | `/meta/intelligence` | Client + days filter | ✓ |
| 2 | AM | ROAS chart | Read forecast | ✓ |
| 3 | Buyer | Budget slider | Scenario what-if | ✓ |

---

## META-UC-011 — Breakdown insights

| # | Actor | Màn hình | Thao tác | Gate |
|---|-------|----------|----------|------|
| 1 | Buyer | `/meta/facebook-ads` | Campaign drill → breakdown | ✓ |
| 2 | Buyer | Export CSV | platform/placement | ✓ |

---

## META-UC-012 — Pause domain/client spend emergency

| # | Actor | Màn hình | Thao tác | Gate |
|---|-------|----------|----------|------|
| 1 | Head | `/agency/clients/[id]` hoặc hub | Emergency pause toggle | ✓ confirm |
| 2 | System | Queue pause all campaigns | — | ✓ Meta PAUSED |
| 3 | AM | Notify client | email/call | ✓ |

---

## META-UC-013 — Weekly client PDF report

| # | Actor | Màn hình | Thao tác | Gate |
|---|-------|----------|----------|------|
| 1 | System | Scheduler RPT-M3 | Generate PDF | ✓ |
| 2 | Client | portal `/meta` | **Export PDF** | ✓ |
| 3 | AM | Confirm delivery | — | ○ |

---

## META-UC-014 — Horizon migration signoff

| # | Actor | Màn hình | Thao tác | Gate |
|---|-------|----------|----------|------|
| 1 | Tech | `/meta/migration` | Readiness status | ✓ |
| 2 | Tech | UAT fields | Manual sign-off | ✓ |
| 3 | Tech | Deploy API version bump | env | ✓ |
