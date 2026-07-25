# Chi tiết hành động — Meta Enterprise (META)

> **UC gốc:** [`../03-META-ENTERPRISE.md`](../03-META-ENTERPRISE.md)  
> **Cross-system:** [`00-SYSTEM-ACTIONS.md`](00-SYSTEM-ACTIONS.md) · [`02-SVC-ACTIONS.md`](02-SVC-ACTIONS.md) · [`01-CRM-ACTIONS.md`](01-CRM-ACTIONS.md)

---

## META-UC-001 — Kết nối ad account & sync insights

**Mục tiêu khách hàng:** *"Meta ad account kết nối an toàn — số liệu T-1 sync lên hub."*

**Actors:** Tracking, Buyer

| # | Actor | Màn hình | Thao tác | Input | Phản hồi | Gate |
|---|-------|----------|----------|-------|----------|------|
| 1 | Tracking | `/login` | Đăng nhập ops-web | credentials | JWT | ✓ |
| 2 | Tracking | `/agency/clients/[id]?tab=channels` | **+ Thêm channel** Meta | ad_account_id, label | Row created | ✓ |
| 3 | Tracking | Same | **Lưu token** / OAuth Meta | access_token | Token vault valid | ✓ |
| 4 | Tracking | Same | **Sync insights** smoke | — | Job enqueued | ✓ |
| 5 | Buyer | `/meta/facebook-ads` | Filter client → tab Clients | client_id | last_sync 🟢 | ✓ |
| 6 | Buyer | Same | Chọn **T-7 / T-30** | date range | KPI populate | ✓ |
| 7 | Buyer | `/meta/ads-combined` | Tab Meta cross-check | T-7 | Combined row | ✓ |
| 8 | AM | Onboard orchestrator | Step Meta sync auto ✓ | — | [SVC-UC-008](02-SVC-ACTIONS.md) | ✓ |

#### Nhánh E1 — Token expired
Hub 🔴 → Tracking re-OAuth bước 3.

#### Tiêu chí nghiệm thu
- [ ] daily_performance T-1 có row Meta
- [ ] Hub sync badge green trong 24h

---

## META-UC-002 — Hub map campaign ↔ CRM

**Mục tiêu khách hàng:** *"Mọi chi tiêu Meta gắn đúng client — CPL không bị phân bổ sai."*

| # | Actor | Màn hình | Thao tác | Input | Phản hồi | Gate |
|---|-------|----------|----------|-------|----------|------|
| 1 | Buyer | `/meta/facebook-ads` tab **Campaigns** | Sort/filter **unmapped** | — | Yellow rows | ✓ |
| 2 | Buyer | Row action | **Map to client** | client_id, project | Row green | ✓ |
| 3 | Buyer | Same | Accept AI **suggest** (nếu có) | confirm | Mapped | ○ GAP-P1-04 |
| 4 | Buyer | `/crm/hub` tab Campaigns | Verify map | — | Match hub | ✓ |
| 5 | Buyer | `/meta/facebook-ads` | unmapped count = 0 | — | All green | ✓ |
| 6 | AM | Same | Export map snapshot CSV | — | File | ○ |
| 7 | Buyer | `/meta/ads-combined` | Verify client spend | T-7 | CPL sane | ✓ |

#### Tiêu chí nghiệm thu
- [ ] Unmapped = 0 trước báo cáo client
- [ ] Map unique per external_campaign_id

---

## META-UC-003 — Xem CPL/ROAS trên hub

**Mục tiêu khách hàng:** *"Buyer và AM biết CPL, ROAS, spend theo client/campaign — export được."*

| # | Actor | Màn hình | Thao tác | Input | Phản hồi | Gate |
|---|-------|----------|----------|-------|----------|------|
| 1 | Buyer | `/meta/facebook-ads` | Mở hub | — | KPI grid load | ✓ |
| 2 | Buyer | Same | Select **client** + **T-7/T-30** | filters | Scoped | ✓ |
| 3 | Buyer | KPI grid | Read Spend, Leads, CPL, ROAS | — | Calculated | ✓ |
| 4 | Buyer | Campaign row | Drill underperforming | click | Detail panel | ✓ |
| 5 | Buyer | Same | Compare vs target CPL | target_vnd | Red/green | ○ |
| 6 | AM | **Export CSV** | period | File download | ✓ |
| 7 | Client | portal `/meta` | Read-only same KPI | T-7 | Match hub | ✓ [PORTAL-UC-003](06-PORTAL-ACTIONS.md) |
| 8 | Buyer | `/meta/ads-combined` | Tab All — Meta slice | — | Cross-channel | ✓ |

#### Tiêu chí nghiệm thu
- [ ] CPL = spend/leads ± rounding
- [ ] Portal KPI khớp hub staff

---

## META-UC-004 — Webhook lead Meta → CRM

**Mục tiêu khách hàng:** *"Lead Meta vào CRM < 1 phút — CSKH gọi ngay."*

| # | Actor | Màn hình | Thao tác | Input | Phản hồi | Gate |
|---|-------|----------|----------|-------|----------|------|
| 1 | DevOps | Meta App Dashboard | Subscribe webhook leadgen | URL | Verified | ✓ [PLAT-UC-004](07-PLAT-ACTIONS.md) |
| 2 | System | `POST /webhooks/meta` | Verify HMAC + parse | payload | 200 OK | ✓ |
| 3 | System | worker | Dedup + assign owner | phone | crm_leads row | ✓ |
| 4 | Tracking | `/agency/ingest` | Monitor job success rate | — | <1% error | ✓ |
| 5 | CSKH | `/crm/leads` | Filter source=**meta** | — | Lead ≤60s | ✓ [CRM-UC-001](01-CRM-ACTIONS.md) |
| 6 | CSKH | `/crm/leads/[id]` | Log first call SLA 15m | note | Timeline | ✓ |
| 7 | Tracking | `/meta/tracking` | Verify dedup rate | — | Acceptable | ✓ |

#### Nhánh E1 — Invalid signature
401 + alert; không insert lead.

#### Tiêu chí nghiệm thu
- [ ] Lead visible ≤ 60s
- [ ] Dedup không duplicate 24h

---

## META-UC-005 — CAPI event gửi & dedup

**Mục tiêu khách hàng:** *"Won deal gửi CAPI — Meta optimize đúng conversion, không double count."*

| # | Actor | Màn hình | Thao tác | Input | Phản hồi | Gate |
|---|-------|----------|----------|-------|----------|------|
| 1 | Sales | `/crm/leads/[id]` | Status → **Won** + deal_value | revenue VND | CRM saved | ✓ |
| 2 | System | CAPI worker | Hash PII + event_id dedup | phone/email hash | Queued | ✓ |
| 3 | System | Meta Graph API | Send Purchase/Lead event | payload | 200 ack | ✓ |
| 4 | Tracking | `/meta/tracking` tab **CAPI events** | Verify event row | event_id | ack status | ✓ |
| 5 | Tracking | Meta Events Manager | Test event match | — | Match | ✓ |
| 6 | Buyer | `/meta/facebook-ads` | ROAS reflects conversion lag | T+1 | Sane | ○ |

#### Tiêu chí nghiệm thu
- [ ] Won → CAPI trong 15 phút
- [ ] Same event_id không gửi 2 lần

---

## META-UC-006 — Tracking health & pixel test

**Mục tiêu khách hàng:** *"Pixel và CAPI healthy trước launch — preflight green."*

| # | Actor | Màn hình | Thao tác | Input | Phản hồi | Gate |
|---|-------|----------|----------|-------|----------|------|
| 1 | Tracking | `/meta/tracking` | Select **client** | client_id | Panel load | ✓ |
| 2 | Tracking | **Preflight checklist** | Tick: pixel, CAPI, domain verify | each item | Pass/Fail | ✓ |
| 3 | Tracking | Same | **Send test event** | event type | Green ack | ✓ |
| 4 | Tracking | Conversion rules tab | Configure rules | rules JSON | Saved | ✓ |
| 5 | Tracking | Same | Re-run preflight | — | All green | ✓ |
| 6 | Buyer | `/crm/launch-qa` | Launch QA pixel item pass | checklist | QA green | ✓ [SVC-UC-005](02-SVC-ACTIONS.md) |
| 7 | Tracking | Meta Events Manager | Cross-verify test | — | Match ops | ✓ |

#### Tiêu chí nghiệm thu
- [ ] Preflight all critical green trước META-UC-007
- [ ] Test event visible Events Manager ≤ 5 min

---

## META-UC-007 — Launch Ads wizard

**Mục tiêu khách hàng:** *"Launch Meta có governance — QA pass, creative approved, budget gate."*

| # | Actor | Màn hình | Thao tác | Input | Phản hồi | Gate |
|---|-------|----------|----------|-------|----------|------|
| 1 | Buyer | `/crm/launch-qa` | Xác nhận QA **passed** | run id | Gate open | ✓ |
| 2 | Buyer | `/meta/ads-ops` tab **Launch** | Mở wizard | — | Step 1 | ✓ |
| 3 | Buyer | Step 1 | Chọn client, **objective** | client_id | Valid | ✓ |
| 4 | Buyer | Step 2 | Budget, schedule | VND/day, dates | Valid | ✓ |
| 5 | Buyer | Step 3 | Audience + placement | targeting | Valid | ✓ |
| 6 | Buyer | Step 4 | Creative từ hub **approved** | asset id | Preview | ✓ [SVC-UC-006](02-SVC-ACTIONS.md) |
| 7 | Buyer | Preflight panel | Fix warnings | — | No blockers | ✓ |
| 8 | Buyer | **Submit launch** | — | write queue id | Queued | ✓ [SVC-UC-007](02-SVC-ACTIONS.md) |

#### Nhánh E1 — Launch QA failed
Block submit; fix checklist → new QA run.

#### Tiêu chí nghiệm thu
- [ ] Unapproved creative không chọn được
- [ ] Submit tạo campaign-writes row

---

## META-UC-008 — Edit campaign có governance

**Mục tiêu khách hàng:** *"Sửa budget/status Meta có diff + GDKD duyệt nếu vượt ngưỡng."*

| # | Actor | Màn hình | Thao tác | Input | Phản hồi | Gate |
|---|-------|----------|----------|-------|----------|------|
| 1 | Buyer | `/meta/ads-ops` tab **Edit** | Select campaign snapshot | campaign id | Diff view | ✓ |
| 2 | Buyer | Diff view | Change budget / status / audience | fields | Preview diff | ✓ |
| 3 | Buyer | Same | Review impact warning | — | Acknowledged | ✓ |
| 4 | Buyer | **Submit edit** | — | → campaign-writes | Queued | ✓ |
| 5 | GDKD | `/crm/campaign-writes` | **Approve** / **Reject** | comment if reject | Decision | ✓ threshold |
| 6 | System | Worker | Meta API execute edit | — | API 200 | ✓ |
| 7 | Buyer | `/meta/facebook-ads` | Verify campaign state | filter | Matches diff | ✓ |
| 8 | System | — | Audit log submitter + approver | — | Immutable | ✓ |

#### Tiêu chí nghiệm thu
- [ ] Budget > threshold requires GDKD
- [ ] Reject có comment bắt buộc

---

## META-UC-009 — Anomaly detection & alert

**Mục tiêu khách hàng:** *"Buyer biết ngay CPL/spend bất thường — acknowledge và xử lý."*

| # | Actor | Màn hình | Thao tác | Input | Phản hồi | Gate |
|---|-------|----------|----------|-------|----------|------|
| 1 | System | — | Detect CPL/spend anomaly | rules | alert row | ✓ |
| 2 | Buyer | `/meta/facebook-ads` tab **Alerts** | View banner | — | Alert detail | ✓ |
| 3 | Buyer | Same | **Acknowledge alert** | — | Ack saved | ✓ |
| 4 | Buyer | `/meta/intelligence` | Drill anomaly detail | client | Root cause | ✓ |
| 5 | Buyer | Action | Pause campaign nếu emergency | — | [META-UC-012](#meta-uc-012--pause-domainclient-spend-emergency) | ○ |

#### Tiêu chí nghiệm thu
- [ ] Alert visible within 1 sync cycle
- [ ] Ack logged with actor + timestamp

---

## META-UC-010 — Intelligence forecast

**Mục tiêu khách hàng:** *"AM forecast ROAS — what-if budget trước quyết định scale."*

| # | Actor | Màn hình | Thao tác | Input | Phản hồi | Gate |
|---|-------|----------|----------|-------|----------|------|
| 1 | AM | `/meta/intelligence` | Select client + forecast days | filters | Chart load | ✓ |
| 2 | AM | ROAS chart | Read forecast band | — | Numbers | ✓ |
| 3 | Buyer | Budget slider | Scenario what-if | budget VND | Projected ROAS | ✓ |
| 4 | AM | Export | Snapshot for client meeting | — | CSV/PDF | ○ |

#### Tiêu chí nghiệm thu
- [ ] Forecast uses T-30 historical minimum

---

## META-UC-011 — Breakdown insights

**Mục tiêu khách hàng:** *"Biết placement/platform nào hiệu quả — optimize creative/placement."*

| # | Actor | Màn hình | Thao tác | Input | Phản hồi | Gate |
|---|-------|----------|----------|-------|----------|------|
| 1 | Buyer | `/meta/facebook-ads` | Select client + campaign | filters | Table | ✓ |
| 2 | Buyer | Campaign drill | Open **breakdown** | platform/placement | Sub-rows | ✓ |
| 3 | Buyer | Same | Identify low CTR placement | — | Action list | ✓ |
| 4 | Buyer | **Export CSV** | breakdown dimensions | File | ✓ |
| 5 | Buyer | `/meta/ads-ops` Edit | Adjust placement nếu cần | diff | Queued | ○ |

#### Tiêu chí nghiệm thu
- [ ] Breakdown sums to campaign total ± rounding

---

## META-UC-012 — Pause domain/client spend emergency

**Mục tiêu khách hàng:** *"Head/Buyer dừng chi tiêu khẩn cấp — bảo vệ budget client."*

| # | Actor | Màn hình | Thao tác | Input | Phản hồi | Gate |
|---|-------|----------|----------|-------|----------|------|
| 1 | Head/Buyer | `/agency/clients/[id]` hoặc hub | Identify emergency client | — | Context | ✓ |
| 2 | Head | Same hoặc hub toggle | **Emergency pause** | confirm dialog | Toggle ON | ✓ |
| 3 | System | campaign-writes queue | Pause all active campaigns | client_id | Jobs queued | ✓ |
| 4 | System | Meta API | Execute PAUSED status | — | API 200 | ✓ |
| 5 | Buyer | `/meta/facebook-ads` | Verify spend flat T+1 | — | Spend stop | ✓ |
| 6 | AM | Email/call | Notify client + reason | — | Comms log | ✓ |
| 7 | Head | Same toggle | **Resume** khi resolved | confirm | Toggle OFF | ○ |
| 8 | System | — | Audit emergency action | actor, reason | Log | ✓ |

#### Tiêu chí nghiệm thu
- [ ] Pause reflected Meta within 15 min
- [ ] Client notified same business day

---

## META-UC-013 — Weekly client PDF report

**Mục tiêu khách hàng:** *"Khách nhận báo cáo Meta weekly — PDF đẹp, số T-1."*

| # | Actor | Màn hình | Thao tác | Input | Phản hồi | Gate |
|---|-------|----------|----------|-------|----------|------|
| 1 | System | Scheduler RPT-M3 | Generate weekly PDF | client list | Blob stored | ✓ |
| 2 | AM | `/meta/facebook-ads` | Verify unmapped=0 trước gửi | T-7 | Hub sane | ✓ |
| 3 | AM | Same | Manual export PDF nếu cần | period | File | ✓ |
| 4 | Client | portal `/meta` | **Export PDF** self-serve | T-7 | Download | ✓ |
| 5 | AM | Email | Confirm client received | — | Hypercare note | ○ |

#### Tiêu chí nghiệm thu
- [ ] PDF KPI khớp hub ± rounding

---

## META-UC-014 — Horizon migration signoff

**Mục tiêu khách hàng:** *"Migration Meta API version an toàn — UAT pass trước prod."*

| # | Actor | Màn hình | Thao tác | Input | Phản hồi | Gate |
|---|-------|----------|----------|-------|----------|------|
| 1 | Tech | `/meta/migration` | Read readiness status | — | Checklist | ✓ |
| 2 | Tech | UAT fields | Run test campaigns | — | Pass/Fail | ✓ |
| 3 | Tech | Same | Manual sign-off fields | name, date | Signed | ✓ |
| 4 | DevOps | Env / deploy | API version bump | env var | Deployed | ✓ |
| 5 | Buyer | `/meta/facebook-ads` | Smoke hub post-migration | T-1 | Green | ✓ |

#### Tiêu chí nghiệm thu
- [ ] UAT sign-off documented before prod cutover

---

## Luồng Meta end-to-end

| # | UC | Mục tiêu |
|---|-----|----------|
| 1 | META-001 | Connect + sync |
| 2 | META-006 | Preflight green |
| 3 | META-002 | Map campaigns |
| 4 | SVC-006/007 | Creative + Launch |
| 5 | META-004/005 | Lead + CAPI closed-loop |
| 6 | META-003 | Hub CPL/ROAS |

**Liên kết SYS:** [SYS-UC-002](00-SYSTEM-ACTIONS.md) nhánh M.
