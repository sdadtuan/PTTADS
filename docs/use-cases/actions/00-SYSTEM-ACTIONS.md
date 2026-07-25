# Chi tiết hành động — System Overview (SYS)

> **UC gốc:** [`../00-SYSTEM-OVERVIEW.md`](../00-SYSTEM-OVERVIEW.md)

---

## SYS-UC-001 — Onboard client mới end-to-end

**Mục tiêu khách hàng:** *"Ký HĐ xong, trong 2 tuần client có ads chạy, portal xem được, lead vào CRM."*

**Actors:** AM (dẫn dắt), Tracking/Tech, SEO/Email Strategist, Admin

| # | Actor | Màn hình | Thao tác | Input | Phản hồi | Gate |
|---|-------|----------|----------|-------|----------|------|
| 1 | AM | `/login` | Đăng nhập ops-web | email, password | JWT + sidebar theo cap | ✓ cap `crm_agency` |
| 2 | AM | `/crm/customers` | Tìm hoặc xác nhận customer sau convert | search name/phone | Danh sách customer | ✓ customer tồn tại |
| 3 | AM | `/agency/clients/new` hoặc `/agency` | **+ Client** nếu chưa có agency client | name, industry, owner_am | Client UUID tạo | ✓ link customer_id |
| 4 | AM | `/crm/service-delivery` | Tạo / mở lifecycle → stage **Onboard** | service slug, AM assign | Kanban card Onboard | ✓ lifecycle id |
| 5 | AM | `/crm/service-delivery/[id]` tab **Onboard** | Xem **Onboard orchestrator** (cross-module steps + deep-links) | — | % required steps, auto-detect badges | ✓ panel load |
| 6 | AM | `/agency/clients/[id]` | Tick **onboarding checklist** items | legal, billing, brief… | progress % tăng | ✓ ≥100% nếu strict |
| 7 | Tracking | `/agency/clients/[id]` | **+ Channel account** Meta | ad_account_id, label | Account row | ✓ |
| 8 | Tracking | `/agency/clients/[id]` | **Lưu token** Meta / OAuth Google | access_token hoặc OAuth | "sync job queued" | ✓ token valid |
| 9 | Tracking | `/meta/tracking` | Client filter → **Preflight** + pixel test | client_id | Health green | ✓ CAPI OK |
| 10 | SEO Strategist | `/seo/clients/[id]` | Tạo workspace → **OAuth GSC/GA4** | domain, property | Sync status | ✓ nếu HĐ SEO |
| 11 | Email Strategist | `/email/clients/[id]` | Mở workspace | client | Workspace active | ✓ nếu HĐ Email |
| 12 | Email Strategist | `/email/deliverability` | **+ Thêm domain** → wizard E-11 DNS | domain, SPF/DKIM records | Verify pass | ✓ domain authenticated |
| 13 | AM | `/agency/clients/[id]` tab **Portal users** | **+ Tạo user** viewer/approver | email, role, password optional | temporary_password once | ✓ |
| 14 | AM | `/crm/service-delivery/[id]` | **Advance stage** → Deliver | confirm | Stage Deliver | ✓ checklist pass |
| 15 | AM | Handover form A4 | Giao credential portal cho khách | credentials vault | Signed handover | ✓ |

#### Nhánh E1 — Chưa có Meta trong HĐ
Bước 7–9: AM tick checklist item **"Meta deferred"** + ghi note; bỏ qua Meta.

#### Nhánh Z1 — Zalo Ads trong HĐ (song song Meta bước 7–9)

| # | Actor | Màn hình | Thao tác | Input | Phản hồi | Gate |
|---|-------|----------|----------|-------|----------|------|
| Z1 | Tracking | `/agency/clients/[id]?tab=channels` | **+ Channel Zalo** + OA ID | external_account_id, oa_id | Row channel `zalo` | ✓ |
| Z2 | Tracking | Same | **Connect Zalo** OAuth | redirect Zalo | Token vault | ✓ token valid |
| Z3 | Tracking | `/zalo/leads` tab **Form sync** | Cấu hình **form IDs** + poll smoke | form_id list | Cursor + job queued | ✓ form configured |
| Z4 | Buyer | `/zalo/zalo-ads` | **Sync Zalo insights** + verify CPL | T-7 | Hub KPI green | ✓ daily_performance |
| Z5 | CSKH | `/crm/leads/[id]` | Qualify → **Won** + deal value | status, deal_value_vnd | Hub CPA refresh | ✓ ZALO-UC-015 |

**Orchestrator steps (auto-detect trên tab Onboard):** `zalo_account`, `zalo_token`, `zalo_form`, `zalo_sync`, `zalo_first_lead` — chi tiết [`08-ZALO-ACTIONS.md`](08-ZALO-ACTIONS.md#zalo-uc-021--onboard-zalo-orchestrator).

#### Nhánh E2 — Khách không dùng portal
Bước 13: Skip; AM cấu hình báo cáo PDF email manual ([SYS-UC-005](#sys-uc-005--báo-cáo-định-kỳ-cho-khách-hàng)).

#### Tiêu chí nghiệm thu
- [ ] Client status **active** trên `/agency/clients/[id]`
- [ ] Lifecycle stage **Deliver**
- [ ] Module tương ứng sync green trên hub
- [ ] Portal login thành công (nếu có portal user)

---

## SYS-UC-002 — Closed-loop Spend → Lead → Revenue

**Mục tiêu khách hàng:** *"Biết chính xác bao nhiêu tiền ads → bao nhiêu lead → bao nhiêu doanh thu."*

| # | Actor | Màn hình | Thao tác | Input | Phản hồi | Gate |
|---|-------|----------|----------|-------|----------|------|
| 1 | System | — | Worker **meta_insights_sync** T-1 | ad_account mapped | Insights rows | ✓ job success |
| 2 | System | `POST /webhooks/meta` | Leadgen webhook → queue | Meta payload | 200 OK | ✓ signature |
| 3 | CSKH | `/crm/leads` | Lead mới xuất hiện | filter source=meta | Row + owner | ✓ deduped |
| 4 | CSKH | `/crm/leads/[id]` | Log call, đổi status → Qualified | note, status | Timeline update | ✓ |
| 5 | Sales | `/crm/pipeline` hoặc lead detail | Kéo stage → **Won** + revenue | deal value VND | Won record | ✓ revenue field |
| 6 | System | CAPI worker | Gửi Purchase/Lead event | event_id hash | Meta EM ack | ✓ |
| 7 | Buyer | `/meta/facebook-ads` | Chọn client, tab **Campaigns** | date T-7/T-30 | CPL, ROAS cards | ✓ mapped campaigns |
| 8 | Buyer | `/meta/facebook-ads` | **Map campaign** chưa map | campaign → client | Yellow → green | ✓ unmapped = 0 |
| 9 | AM | `/meta/facebook-ads` | **Export** hoặc brief client | CSV | File download | ✓ |
| 10 | Client | portal `/meta` | Xem CPL read-only | T-7/T-30 | KPI cards | ✓ portal flag |

#### Nhánh E1 — Unmapped spend
Bước 8 bắt buộc trước khi AM gửi báo cáo client (disclaimer nếu còn vàng).

#### Tiêu chí nghiệm thu
- [ ] CPL = spend/leads cùng kỳ khớp hub vs portal ± rounding
- [ ] Won deal trigger CAPI trong 15 phút

---

## SYS-UC-003 — Launch campaign đa kênh có governance

**Mục tiêu khách hàng:** *"Campaign go-live an toàn — QA nội bộ + khách duyệt trước khi tiêu tiền."*

| # | Actor | Màn hình | Thao tác | Input | Phản hồi | Gate |
|---|-------|----------|----------|-------|----------|------|
| 1 | Creative | `/crm/creatives` | **Submit creative** | files, copy, client | status pending | ✓ |
| 2 | Creative Lead | `/crm/creatives` | Internal review → approve internal | comment | approved internal | ✓ |
| 3 | Creative | `/crm/creatives` | **Submit client approval** | — | pending_client | ✓ |
| 4 | Client Approver | portal `/creatives` | **Approve** creative | optional note | approved | ✓ |
| 5 | Buyer | `/crm/launch-qa` | Tạo / pass **Launch QA run** | checklist items tick | status passed | ✓ critical items |
| 6 | Buyer | `/meta/ads-ops` | **Launch wizard** step 1–4 | objective, budget, audience, creative | preview | ✓ |
| 7 | Buyer | `/meta/ads-ops` | **Submit** launch | — | job → campaign-writes queue | ✓ |
| 8 | GDKD | `/crm/campaign-writes` | **Approve** nếu budget > threshold | approve/reject | approved | ✓ |
| 9 | System | Temporal | Execute Meta create API | — | campaign id | ✓ API 200 |
| 10 | Buyer | `/meta/facebook-ads` | Verify campaign **Active** | filter client | spend > 0 next day | ✓ |

#### Nhánh E1 — Client reject creative
Bước 4 → Reject + comment → quay bước 1 Creative sửa → resubmit bước 3.

#### Tiêu chí nghiệm thu
- [ ] Không launch được khi Launch QA failed (nếu strict mode)
- [ ] Audit log đủ: creative approval + write queue + Meta id

---

## SYS-UC-004 — Client approval cross-module

**Mục tiêu khách hàng:** *"Mọi thứ gửi khách phải qua inbox duyệt thống nhất."*

| # | Actor | Màn hình | Thao tác | Input | Phản hồi | Gate |
|---|-------|----------|----------|-------|----------|------|
| 1 | Staff | Module tương ứng | Submit for client approval | item id | status pending_client | ✓ |
| 2 | Client | portal login | Đăng nhập | credentials | JWT scoped client | ✓ approver role |
| 3 | Client | `/creatives` hoặc `/seo/content` hoặc `/email/approvals` | Mở item pending | — | Preview full | ✓ |
| 4 | Client | Same | **Approve** hoặc **Reject** | reject: comment ≥ N chars | decision saved | ✓ |
| 5 | Staff | ops module | Refresh → status updated | — | can launch/send | ✓ approved |

#### Tiêu chí nghiệm thu
- [ ] Reject không comment → UI block
- [ ] Approver không thấy client khác

---

## SYS-UC-005 — Báo cáo định kỳ cho khách hàng

| # | Actor | Màn hình | Thao tác | Input | Phản hồi | Gate |
|---|-------|----------|----------|-------|----------|------|
| 1 | System | Scheduler | Trigger weekly/monthly job | client list | PDF/blob | ✓ sync OK |
| 2 | AM | `/meta/facebook-ads` hoặc `/seo/reports` hoặc `/email/reports` | Verify data T-1 trước gửi | period | KPI sane | ✓ |
| 3 | System | Email/webhook | Deliver PDF link | recipient | delivery log | ✓ |
| 4 | Client | portal `/meta` `/seo/reports` | Self-serve download | Export CSV/PDF | file | ✓ |
| 5 | AM | Email/ call | Confirm client received | — | hypercare note | ○ |

---

## SYS-UC-006 — Offboard client & thu hồi quyền

| # | Actor | Màn hình | Thao tác | Input | Phản hồi | Gate |
|---|-------|----------|----------|-------|----------|------|
| 1 | AM | `/crm/service-delivery/[id]` | Advance → **Offboarding** | note | stage update | ✓ |
| 2 | AM | `/agency/clients/[id]` | **Offboard client** confirm dialog | confirm | tokens_revoked, portal_users_deactivated | ✓ |
| 3 | Admin | — | Export data nếu HĐ yêu cầu | — | archive zip | ○ |
| 4 | Client | portal `/login` | Thử login | — | 403 / archived redirect | ✓ blocked |

---

## SYS-UC-007 — Executive drill-down ≤3 clicks

| # | Actor | Màn hình | Thao tác | Phản hồi | Gate |
|---|-------|----------|----------|----------|------|
| 1 | Head | `/seo/hub` hoặc `/email/hub` hoặc `/meta/facebook-ads` | Mở hub | Client health table | ✓ |
| 2 | Head | Same | **Click 1** client row | Client workspace / detail | ✓ |
| 3 | Head | Client detail | **Click 2** tab issue/campaign/contacts | Module detail | ✓ |
| 4 | Head | Detail | **Click 3** drill item | Actionable record | ✓ ≤3 clicks |

---

## SYS-UC-008 — Incident P1 webhook down

| # | Actor | Màn hình | Thao tác | Gate |
|---|-------|----------|----------|------|
| 1 | System | Monitoring | Alert error rate >1% | ✓ P1 |
| 2 | DevOps | VPS / `/agency/ingest` | Check nginx, Nest logs, Meta app secret | ✓ root cause |
| 3 | DevOps | Env / deploy | Fix + redeploy | ✓ health green |
| 4 | Tracking | `/crm/leads` | Verify lead mới ingest | ✓ test lead |
| 5 | AM | Email client | Comms nếu mất lead | ○ |

---

## SYS-UC-009 — Staged prod cutover module flag

| # | Actor | Màn hình | Thao tác | Gate |
|---|-------|----------|----------|------|
| 1 | DevOps | VPS env | B1: `PTT_EMAIL_ENABLED=1`, send off | ✓ |
| 2 | QA | `/email/gate-a` hoặc `/seo/gate-a` | Run checklist + `./scripts/*_gate.sh` | ✓ PASS |
| 3 | DevOps | Soak 3–7 ngày | Monitor hub alerts | ✓ |
| 4 | DevOps | B2/B3/B4 flags | Enable send, portal, journeys | ✓ |
| 5 | PO | handover §6 | Sign-off nghiệm thu | ✓ |

---

## SYS-UC-010 — Audit trail tra cứu cross-module

| # | Actor | Màn hình | Thao tác | Gate |
|---|-------|----------|----------|------|
| 1 | Compliance | `/email/governance` | Tab audit log | filter date/client | ✓ |
| 2 | Compliance | `/seo/governance` | Evaluation history | ✓ |
| 3 | Compliance | `/crm/leads/[id]` | Activity timeline | ✓ |
| 4 | Compliance | portal (staff view) | Approval decisions export | ○ manual |

---

## SYS-UC-011 — Multi-client isolation verify

| # | Actor | Màn hình | Thao tác | Gate |
|---|-------|----------|----------|------|
| 1 | QA | portal client A login | Gọi API `/portal/*` | ✓ no client B data |
| 2 | QA | ops staff | Meta/SEO/Email API với client_id A | ✓ filter enforced |
| 3 | QA | Pen test checklist | Document evidence | ✓ handover §5 |

---

## SYS-UC-012 — Hypercare post go-live

| # | Actor | Màn hình | Thao tác | Gate |
|---|-------|----------|----------|------|
| 1 | AM | Daily standup | Review hub alerts all modules | ✓ |
| 2 | Tech | Gate scripts | `./scripts/email_p1_gate.sh` etc. | ✓ PASS |
| 3 | AM | Defect log | Triage P1 ack 30min | ✓ |
| 4 | PO | handover form | Hypercare exit sign-off | ✓ steady state |
