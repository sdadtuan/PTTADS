# Chi tiết hành động — Service Delivery (SVC)

> **UC gốc:** [`../02-AGENCY-SERVICE-DELIVERY.md`](../02-AGENCY-SERVICE-DELIVERY.md)  
> **Cross-system:** [`00-SYSTEM-ACTIONS.md`](00-SYSTEM-ACTIONS.md) · **Zalo:** [`08-ZALO-ACTIONS.md`](08-ZALO-ACTIONS.md)

---

## SVC-UC-001 — Workflow lifecycle 7 stage

**Mục tiêu khách hàng:** *"Theo dõi client từ ký HĐ → bàn giao → duy trì trên một kanban — không lạc stage."*

**Actors:** AM, Strategist, Finance, System

| # | Actor | Màn hình | Thao tác | Input | Phản hồi | Gate |
|---|-------|----------|----------|-------|----------|------|
| 1 | AM | `/crm/service-delivery` | Filter service slug / AM owner | filters | Kanban load | ✓ |
| 2 | AM | Kanban | Xem card **7 stages** | Prospect→…→Offboarding | Badge per client | ✓ |
| 3 | AM | `/crm/service-delivery/[id]` | Mở lifecycle detail | lifecycle id | Tabs load | ✓ |
| 4 | AM | Tab stage hiện tại | Xem gate items (checklist) | onboard/deliver/… | % complete | ✓ |
| 5 | AM | Workflow panel | **Advance stage** | confirm + reason | Stage update | ✓ gate pass |
| 6 | System | — | Log stage history immutable | timestamp, actor | Audit row | ✓ |
| 7 | AM | `/agency/clients/[id]` | Verify stage badge sync | — | Same stage | ✓ |
| 8 | Head | `/crm/hub` | Portfolio view by stage | filter | Health table | ○ |

**7 stages:** Prospect → **Onboard** → **Deliver** → Optimize → **Handover** → **Retain** → Offboarding

#### Nhánh E1 — Skip stage (pilot/admin)
Admin override + audit reason bắt buộc; không dùng production thường.

#### Nhánh E2 — Block Deliver
BR-SVC-01: Onboard checklist chưa 100% → advance Deliver disabled → [SVC-UC-002](#svc-uc-002--onboard-checklist-client).

#### Tiêu chí nghiệm thu
- [ ] Stage history không sửa được retroactive
- [ ] Không Deliver nếu onboard incomplete

---

## SVC-UC-002 — Onboard checklist client

**Mục tiêu khách hàng:** *"Onboard có checklist rõ — legal, billing, ads, portal — trước khi chạy campaign."*

**Actors:** AM, Tracking, SEO/Email Strategist

| # | Actor | Màn hình | Thao tác | Input | Phản hồi | Gate |
|---|-------|----------|----------|-------|----------|------|
| 1 | AM | `/crm/service-delivery/[id]` tab **Onboard** | Mở onboard panel | — | Checklist + orchestrator | ✓ |
| 2 | AM | `/agency/clients/[id]?tab=onboard` | Scroll **Onboarding widget** | — | Items list | ✓ |
| 3 | AM | Checklist items | Tick: legal, billing, brief | each item | progress % | ✓ |
| 4 | AM | Same | Paste evidence URL/file note | links | Audit | ○ |
| 5 | Tracking | `?tab=channels` | Meta/Google/**Zalo** channel + token | account ids | Channels green | ✓ [SVC-UC-008](#svc-uc-008--map-channel-account-metazalogoogle) |
| 6 | AM | Orchestrator panel | **Auto-sync** + deep-link steps | POST sync | Badges ✓ | ✓ [SYS-UC-001](00-SYSTEM-ACTIONS.md) |
| 7 | AM | `?tab=portal` | **+ Portal user** viewer/approver | email, role | User created | ✓ |
| 8 | AM | Onboard tab | Verify **100%** required items | — | Gate open Deliver | ✓ |
| 9 | AM | Same | **Activate client** status → active | confirm | Client active | ✓ |

#### Nhánh Z — Zalo trong HĐ
Orchestrator steps: `zalo_account`, `zalo_token`, `zalo_form`, `zalo_sync`, `zalo_first_lead` — [ZALO-UC-021](08-ZALO-ACTIONS.md).

#### Tiêu chí nghiệm thu
- [ ] Required checklist 100% trước Deliver
- [ ] Orchestrator deep-links không 404

---

## SVC-UC-003 — Deliver stage — TMMT chính thức

**Mục tiêu khách hàng:** *"Client chính thức vào giai đoạn delivery — TMMT published, campaign đầu tiên live."*

**Actors:** AM, Media Buyer, Tracking

| # | Actor | Màn hình | Thao tác | Input | Phản hồi | Gate |
|---|-------|----------|----------|-------|----------|------|
| 1 | AM | `/crm/service-delivery/[id]` | Xác nhận onboard 100% | — | Gate pass | ✓ [UC-002](#svc-uc-002--onboard-checklist-client) |
| 2 | AM | Same tab | **Advance stage** → **Deliver** | confirm | Stage Deliver | ✓ |
| 3 | AM | `/crm/marketing-plan/[id]` | **Publish TMMT** version chính thức | content | Version locked | ✓ |
| 4 | Buyer | `/crm/launch-qa` | Pass Launch QA run | checklist | status passed | ✓ [UC-005](#svc-uc-005--launch-qa-checklist) |
| 5 | Buyer | Channel launch (xem nhánh) | First campaign go-live | — | Spend T+1 | ✓ [SYS-UC-003](00-SYSTEM-ACTIONS.md) |
| 6 | AM | Lifecycle notes | Ghi **hypercare start date** | date | Note saved | ✓ [SYS-UC-012](00-SYSTEM-ACTIONS.md) |
| 7 | AM | `/agency/clients/[id]` | Client meeting kickoff Deliver | — | Comms log | ○ |
| 8 | Buyer | Hub tương ứng | Verify KPI T+1 | meta/zalo/google | CPL sane | ✓ |

#### Nhánh M — Meta first campaign
Buyer `/meta/ads-ops` Launch wizard → [SVC-UC-007](#svc-uc-007--campaign-write-queue-approval).

#### Nhánh Z — Zalo first campaign
Launch QA Zalo pass → manual Zalo UI go-live → map ID [ZALO-UC-009](08-ZALO-ACTIONS.md) nhánh E1.

#### Tiêu chí nghiệm thu
- [ ] TMMT version published
- [ ] Launch QA passed trước go-live
- [ ] Hypercare date documented

---

## SVC-UC-004 — Handover → Retain + finance gate

**Mục tiêu khách hàng:** *"Chuyển giai đoạn steady-state chỉ khi billing OK — không handover khi còn nợ."*

**Actors:** AM, Finance

| # | Actor | Màn hình | Thao tác | Input | Phản hồi | Gate |
|---|-------|----------|----------|-------|----------|------|
| 1 | AM | `/crm/service-delivery/[id]` | Xác nhận Deliver period complete | — | KPI stable | ✓ |
| 2 | AM | Same | Compile handover pack | reports, SOP, contacts | Doc bundle | ✓ |
| 3 | Finance | `/crm/financials` | ⚠ Verify **AR aging** current | client id | No overdue | ⚠ GAP-P1-01 |
| 4 | AM | `/crm/hub` tab Contracts | Cross-check HĐ active + billing | — | Aligned | ✓ [CRM-UC-011](01-CRM-ACTIONS.md) |
| 5 | AM | Lifecycle | **Advance** → **Handover** | confirm | Stage update | ✓ finance OK |
| 6 | AM | Meeting (offline) | Client sign-off pack | signature | Signed note | ✓ |
| 7 | AM | Lifecycle | **Advance** → **Retain** | confirm | Steady-state SLA | ✓ |
| 8 | AM | `/crm/sop` | Link retain SOP playbook | doc link | SOP active | ✓ |

#### Nhánh E1 — Outstanding invoice (GAP-P1-01 workaround)
| # | Actor | Màn hình | Thao tác | Gate |
|---|-------|----------|----------|------|
| F1 | Finance | `/crm/financials` | Flag overdue > 30d | ✓ block |
| F2 | AM | Lifecycle | **Không advance** Handover | ✓ blocked |
| F3 | AM | Email client | Payment reminder | ○ |
| F4 | Finance | Same | Mark paid → AM retry bước 5 | ✓ |

**Target product (GAP-P1-01):** UI cảnh báo trên lifecycle advance nếu AR overdue — auto-block Handover.

#### Tiêu chí nghiệm thu
- [ ] Handover không advance nếu finance chưa confirm (manual policy)
- [ ] Retain SOP linked

---

## SVC-UC-005 — Launch QA checklist

**Mục tiêu khách hàng:** *"Campaign không launch khi thiếu pixel, UTM, creative duyệt — checklist có sign-off."*

**Actors:** Media Buyer, Creative Lead

| # | Actor | Màn hình | Thao tác | Input | Phản hồi | Gate |
|---|-------|----------|----------|-------|----------|------|
| 1 | Buyer | `/crm/launch-qa` | Filter **in_progress** / client | client_id | Runs list | ✓ |
| 2 | Buyer | `/crm/service-delivery/[id]` | Panel **Launch QA** | — | Checklist load | ✓ |
| 3 | Buyer | Checklist Meta | Tick: UTM, pixel, LP, budget, audience | each item | Pass/Fail | ✓ critical |
| 4 | Buyer | Checklist Zalo (auto) | Verify `zalo_oauth_token`, `zalo_form_ids_configured` | auto-eval | Green badges | ✓ Z3-2 |
| 5 | Buyer | `/crm/creatives` | Confirm creative **approved** client | channel tag | Status approved | ✓ |
| 6 | Buyer | `/meta/tracking` | Preflight pixel test (Meta) | client_id | Health green | ✓ META-006 |
| 7 | Buyer | Same panel | Submit run → **passed** | — | status passed | ✓ |
| 8 | Buyer | Same | **Export** QA sign-off PDF | — | File | ○ |

#### Nhánh E1 — Critical item fail
Run **failed** → không launch ([SYS-UC-003](00-SYSTEM-ACTIONS.md)); Buyer fix → new run.

#### Nhánh Z — Zalo-only launch
Bước 3 skip Meta items; bước 4 Zalo auto-check bắt buộc pass.

#### Tiêu chí nghiệm thu
- [ ] Failed QA blocks campaign write submit (strict mode)
- [ ] Zalo auto-checklist pass trước go-live manual

---

## SVC-UC-006 — Creative Hub upload & review

**Mục tiêu khách hàng:** *"Creative có version control — duyệt nội bộ rồi khách duyệt trước ads."*

**Actors:** Creative, Creative Lead, Client Approver, Buyer

| # | Actor | Màn hình | Thao tác | Input | Phản hồi | Gate |
|---|-------|----------|----------|-------|----------|------|
| 1 | Creative | `/crm/creatives` | **Submit creative** | files, copy, client | status pending | ✓ |
| 2 | Creative | Same | Tag **channel**: meta / google / **zalo** | channel field | Filterable | ✓ Z3-1 |
| 3 | Creative | Same | Tag format (1:1, 9:16), campaign | metadata | Saved | ✓ |
| 4 | Creative Lead | Tab pending | Internal review → **approve internal** | comment | approved internal | ✓ |
| 5 | Creative | Same | **Submit client approval** | — | pending_client | ✓ |
| 6 | Client | portal `/creatives` | **Approve** / **Reject** | note if reject | approved / rejected | ✓ [PORTAL-UC-006](06-PORTAL-ACTIONS.md) |
| 7 | Buyer | `/meta/ads-ops` hoặc Zalo manual | Pick **approved only** creative | asset id | Wizard step | ✓ |
| 8 | System | notification_inbox | Milestone notify on approve | — | Staff inbox | ✓ Z3-8 |

#### Nhánh E1 — Client reject
Bước 6 reject → Creative revise bước 1 → resubmit bước 5.

#### Tiêu chí nghiệm thu
- [ ] Unapproved creative không chọn được launch wizard
- [ ] channel=zalo visible portal preview

---

## SVC-UC-007 — Campaign Write queue approval

**Mục tiêu khách hàng:** *"Thay đổi campaign Meta có governance — GDKD duyệt budget lớn."*

**Actors:** Media Buyer, GDKD, System

| # | Actor | Màn hình | Thao tác | Input | Phản hồi | Gate |
|---|-------|----------|----------|-------|----------|------|
| 1 | Buyer | `/crm/launch-qa` | Xác nhận QA **passed** | run id | Gate open | ✓ [UC-005](#svc-uc-005--launch-qa-checklist) |
| 2 | Buyer | `/meta/ads-ops` | **Launch wizard** step 1–4 | objective, budget, audience, creative | Preview | ✓ |
| 3 | Buyer | Same | **Submit** launch / edit | diff snapshot | Job queued | ✓ |
| 4 | Buyer | `/crm/campaign-writes` | View **pending** tab | — | Queue row | ✓ |
| 5 | GDKD | Same row | **Approve** / **Reject** | comment if reject | approved / rejected | ✓ threshold |
| 6 | System | Temporal worker | Meta API execute | — | campaign id | ✓ API 200 |
| 7 | Buyer | `/meta/facebook-ads` | Verify campaign **Active** | filter client | spend T+1 | ✓ |
| 8 | System | — | Audit: submitter, approvers, API ids | — | Immutable log | ✓ |

#### Nhánh E1 — Meta API error
Job status **failed** → Buyer fix payload → resubmit bước 3.

#### Nhánh Z — Zalo (GAP-Z4-01)
Zalo API write chưa có → manual go-live [ZALO-UC-009](08-ZALO-ACTIONS.md) nhánh E1; Campaign Write queue chỉ Meta.

#### Tiêu chí nghiệm thu
- [ ] Budget > threshold requires GDKD approve
- [ ] Audit log đủ submitter + approver + Meta id

---

## SVC-UC-008 — Map channel account (Meta/Google/Zalo)

**Mục tiêu khách hàng:** *"Mỗi client có ad account đúng kênh — token valid, sync chạy."*

**Actors:** AM, Tracking

| # | Actor | Màn hình | Thao tác | Input | Phản hồi | Gate |
|---|-------|----------|----------|-------|----------|------|
| 1 | AM | `/agency/clients/[id]?tab=channels` | Mở Channel accounts | — | List | ✓ |
| 2 | AM | Same | **+ Thêm channel** Meta | ad_account_id, label | Row meta | ✓ |
| 3 | Tracking | Same | **Connect token** Meta OAuth / manual | token | Token valid | ✓ |
| 4 | AM | Same | **+ Thêm channel** Google | customer_id | Row google | ✓ |
| 5 | Tracking | Same | Google OAuth connect | OAuth flow | Token valid | ✓ |
| 6 | AM | Same | **+ Thêm channel** Zalo + OA ID | external_id, oa_id | Row zalo | ✓ |
| 7 | Tracking | Same | **Connect Zalo** OAuth | redirect | Token vault | ✓ [ZALO-UC-001](08-ZALO-ACTIONS.md) |
| 8 | Tracking | Same | **Sync insights** button per channel | — | Jobs queued | ✓ |
| 9 | AM | Hub module | Confirm data T-1 green | meta/zalo/google | Sync badges | ✓ |

#### Tiêu chí nghiệm thu
- [ ] client_id ↔ ad_account_id mapping unique per channel
- [ ] Token expired → hub red + re-OAuth path documented

---

## SVC-UC-009 — Agency ingest monitor

**Mục tiêu khách hàng:** *"Tracking thấy webhook lỗi sớm — replay payload không mất lead."*

**Actors:** Tracking, DevOps

| # | Actor | Màn hình | Thao tác | Input | Phản hồi | Gate |
|---|-------|----------|----------|-------|----------|------|
| 1 | Tracking | `/agency/ingest` | View pipeline volume by channel | meta/zalo/email | Dashboard | ✓ |
| 2 | Tracking | Same | Check error rate / lag | — | Alerts | ✓ |
| 3 | Tracking | `/agency/jobs` | Filter **failed** jobs | channel | Failed list | ✓ |
| 4 | DevOps | Same | Drill job payload + stack | job id | Root cause | ✓ |
| 5 | DevOps | Retry/replay | Fix + replay payload | — | Job success | ✓ |
| 6 | Tracking | `/crm/leads` | Verify lead recovered | source filter | Row exists | ✓ |

#### Tiêu chí nghiệm thu
- [ ] Failed webhook replay không duplicate (dedup)
- [ ] P1 incident ack 30 min ([SYS-UC-008](00-SYSTEM-ACTIONS.md))

---

## SVC-UC-010 — KPI definitions agency-wide

**Mục tiêu khách hàng:** *"CPL, ROAS, rank delta định nghĩa thống nhất — hub widgets cùng công thức."*

**Actors:** Head, Admin

| # | Actor | Màn hình | Thao tác | Input | Phản hồi | Gate |
|---|-------|----------|----------|-------|----------|------|
| 1 | Head | `/agency/kpi-definitions` | **+ KPI** formula | name, expression | Row created | ✓ |
| 2 | Head | Same | Assign to roles (Buyer, AM) | role ids | Scoped | ✓ |
| 3 | Head | Row | Edit / delete definition | — | Updated | ✓ |
| 4 | AM | `/meta/facebook-ads`, `/zalo/zalo-ads` | Verify widgets use defs | — | CPL match formula | ✓ |
| 5 | Head | Export | Document KPI dictionary | — | PDF/CSV | ○ |

#### Tiêu chí nghiệm thu
- [ ] Hub CPL uses agency KPI definition
- [ ] Delete def không break hub (fallback)

---

## SVC-UC-011 — SOP & marketing plan

**Mục tiêu khách hàng:** *"Mỗi client có SOP và marketing plan the quarter — link lifecycle Optimize."*

**Actors:** Strategist, AM

| # | Actor | Màn hình | Thao tác | Input | Phản hồi | Gate |
|---|-------|----------|----------|-------|----------|------|
| 1 | Strategist | `/crm/sop` | **+ SOP run** / upload doc | client, template | SOP id | ✓ |
| 2 | AM | `/crm/marketing-plan` | Quarterly plan **+ Create** | quarter, goals | Plan draft | ✓ |
| 3 | AM | `/crm/marketing-plan/[id]` | Edit + link TMMT | content | Version | ✓ |
| 4 | AM | `/crm/service-delivery/[id]` | Stage **Optimize** reference plan | — | Cross-link | ○ |
| 5 | AM | Client meeting | Review plan with client | — | Notes | ○ |

#### Tiêu chí nghiệm thu
- [ ] SOP accessible from client workspace
- [ ] Marketing plan has quarter + KPI targets

---

## SVC-UC-012 — Offboarding SOP

**Mục tiêu khách hàng:** *"Kết thúc HĐ an toàn — thu hồi quyền, export data, archive."*

**Actors:** AM, Admin

| # | Actor | Màn hình | Thao tác | Input | Phản hồi | Gate |
|---|-------|----------|----------|-------|----------|------|
| 1 | AM | `/crm/service-delivery/[id]` | Advance → **Offboarding** | note | Stage update | ✓ |
| 2 | AM | Offboarding checklist | Revoke ad tokens, portal users | items tick | Progress | ✓ |
| 3 | AM | `/agency/clients/[id]` | **Offboard client** confirm | dialog | tokens_revoked | ✓ [SYS-UC-006](00-SYSTEM-ACTIONS.md) |
| 4 | Admin | — | Export data pack nếu HĐ yêu cầu | — | Archive zip | ○ |
| 5 | AM | — | Final report client | PDF | Delivered | ○ |
| 6 | Client | portal `/login` | Verify blocked | — | 403 / archived | ✓ |

#### Tiêu chí nghiệm thu
- [ ] Portal login blocked post-offboard
- [ ] Tokens revoked all channels

---

## Luồng SVC end-to-end (delivery)

| # | UC | Actor | Mục tiêu |
|---|-----|-------|----------|
| 1 | SVC-001 | AM | Lifecycle Onboard |
| 2 | SVC-002 | AM/Tracking | Checklist 100% |
| 3 | SVC-008 | Tracking | Channels + tokens |
| 4 | SVC-006 | Creative | Creative approved |
| 5 | SVC-005 | Buyer | Launch QA pass |
| 6 | SVC-007 / Zalo manual | Buyer | Go live |
| 7 | SVC-003 | AM | Deliver + TMMT |
| 8 | SVC-004 | AM/Finance | Handover → Retain |

**Finance gate:** [SVC-UC-004](#svc-uc-004--handover--retain--finance-gate) — GAP-P1-01 documented.
