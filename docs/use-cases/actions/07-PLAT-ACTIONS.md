# Chi tiết hành động — Platform (PLAT)

> **UC gốc:** [`../07-PLATFORM-AUTH-WEBHOOKS.md`](../07-PLATFORM-AUTH-WEBHOOKS.md)  
> **Cross-module:** [`01-CRM-ACTIONS.md`](01-CRM-ACTIONS.md) · [`03-META-ACTIONS.md`](03-META-ACTIONS.md) · [`08-ZALO-ACTIONS.md`](08-ZALO-ACTIONS.md)

> **Lưu ý:** Hầu hết PLAT UC là **System/DevOps** — bảng mô tả hành động vận hành + verify UAT, không phải end-user business daily.

---

## PLAT-UC-001 — Staff JWT login & refresh

**Mục tiêu khách hàng:** *"Staff đăng nhập an toàn — session refresh, sidebar theo cap."*

**Actors:** Staff, System

| # | Actor | Màn hình | Thao tác | Input | Phản hồi | Gate |
|---|-------|----------|----------|-------|----------|------|
| 1 | Staff | ops `/login` | Nhập email + password | credentials | Form submit | ✓ |
| 2 | System | `POST /auth/login` | Validate hash + issue JWT | — | access + refresh tokens | ✓ |
| 3 | Staff | `/` (dashboard) | Redirect after login | — | Sidebar caps visible | ✓ [UC-002](#plat-uc-002--rbac-cap-enforcement) |
| 4 | Staff | Any ops route | API calls with Bearer token | — | 200 scoped | ✓ |
| 5 | System | (before expiry) | **Silent refresh** | refresh token | New access JWT | ✓ |
| 6 | Staff | Logout / expiry | Re-login required | — | Redirect login | ✓ |
| 7 | QA | Invalid creds | Login attempt | wrong password | 401 generic | ✓ |

#### Tiêu chí nghiệm thu
- [ ] Refresh works without re-enter password
- [ ] Expired token → 401 on API

---

## PLAT-UC-002 — RBAC cap enforcement

**Mục tiêu khách hàng:** *"Mỗi role chỉ thấy module được phép — API enforce 403."*

**Actors:** Admin, Staff, QA

| # | Actor | Màn hình | Thao tác | Input | Phản hồi | Gate |
|---|-------|----------|----------|-------|----------|------|
| 1 | Admin | Seed script / `/crm/staff` | Assign **caps** to role template | role, cap list | Saved | ✓ |
| 2 | Admin | Same | Assign staff to role | staff id | Updated | ✓ |
| 3 | Staff | ops any route | Access allowed module | e.g. `/crm/leads` | 200 | ✓ |
| 4 | Staff | ops denied route | Access without cap | e.g. `/email/governance` | **403** | ✓ |
| 5 | Staff | OpsNav sidebar | Menu hidden without cap | — | Not visible | ✓ |
| 6 | QA | Test matrix | handover §5 roles | each role | Documented | ✓ |
| 7 | QA | API direct | `curl` without cap header scope | — | 403 | ✓ |
| 8 | Admin | Cap change | Revoke cap → staff refresh | — | Access removed | ✓ |

#### Tiêu chí nghiệm thu
- [ ] UI hide + API 403 consistent
- [ ] Pen test matrix PASS handover §5

---

## PLAT-UC-003 — Portal JWT login

**Mục tiêu khách hàng:** *"Client login scoped — chỉ data công ty mình, role viewer/approver."*

| # | Actor | Màn hình | Thao tác | Input | Phản hồi | Gate |
|---|-------|----------|----------|-------|----------|------|
| 1 | Client | portal `/login` | Nhập credentials | email, password | Submit | ✓ |
| 2 | System | `POST /portal/auth/login` | Issue JWT `client_id` + role | — | Token scoped | ✓ |
| 3 | Client | `/dashboard` | Widgets load scoped | — | No other client | ✓ |
| 4 | QA | API fuzz | Request `client_id=B` with token A | — | **403/empty** | ✓ [SYS-UC-011](00-SYSTEM-ACTIONS.md) |
| 5 | Client | Archived client | Login attempt | — | Redirect `/archived` | ✓ |
| 6 | Client | `/settings` | Change password | — | [PORTAL-UC-012](06-PORTAL-ACTIONS.md) | ✓ |

#### Tiêu chí nghiệm thu
- [ ] JWT cannot access other client_id
- [ ] Approver vs viewer cap enforced

---

## PLAT-UC-004 — Webhook Meta ingest

**Mục tiêu khách hàng:** *"Meta leadgen webhook reliable — signature verify, CRM ingest."*

**Actors:** DevOps, Tracking, System

| # | Actor | Màn hình | Thao tác | Input | Phản hồi | Gate |
|---|-------|----------|----------|-------|----------|------|
| 1 | DevOps | Meta App Dashboard | Subscribe **leadgen** webhook | callback URL | Verified | ✓ |
| 2 | DevOps | nginx + Nest deploy | Route `POST /webhooks/meta` | — | 200 reachable | ✓ |
| 3 | DevOps | Env | Set `META_APP_SECRET` | secret | Configured | ✓ |
| 4 | System | Ingest handler | **Verify HMAC** signature | header | pass/fail | ✓ |
| 5 | System | worker | Normalize → CRM queue | payload | job id | ✓ |
| 6 | Tracking | `/agency/ingest` | Monitor success rate | — | <1% error | ✓ |
| 7 | Tracking | Meta test tool | Send **test lead** | — | CRM lead row | ✓ [META-UC-004](03-META-ACTIONS.md) |
| 8 | DevOps | Incident | [SYS-UC-008](00-SYSTEM-ACTIONS.md) playbook | — | Recovery | ○ |

#### Nhánh E1 — Invalid signature
401 response; no CRM insert; alert DevOps.

#### Tiêu chí nghiệm thu
- [ ] Test lead → CRM ≤ 60s
- [ ] Invalid signature rejected 100%

---

## PLAT-UC-005 — Webhook Zalo/Google ingest

**Mục tiêu khách hàng:** *"Zalo/Google lead webhook + normalize — CRM source tag đúng."*

| # | Actor | Màn hình | Thao tác | Input | Phản hồi | Gate |
|---|-------|----------|----------|-------|----------|------|
| 1 | DevOps | Zalo Developer / Google | Configure webhook URL + secret | URLs | Verified | ✓ |
| 2 | System | `POST /webhooks/zalo` | Verify signature + parse | payload | 200 OK | ✓ |
| 3 | System | — | Normalize → CRM ingest queue | phone, form | job | ✓ |
| 4 | System | Google (if configured) | Lead form webhook | payload | 200 | ○ |
| 5 | Tracking | `/agency/ingest` | Monitor zalo channel volume | — | Dashboard | ✓ |
| 6 | CSKH | `/crm/leads` | Filter **source=zalo** / google | — | Rows | ✓ [CRM-UC-001](01-CRM-ACTIONS.md) |
| 7 | Tracking | Test payload | Replay sample | — | Deduped lead | ✓ [ZALO-UC-011](08-ZALO-ACTIONS.md) |

#### Tiêu chí nghiệm thu
- [ ] Zalo HMAC verify pass
- [ ] source=zalo on CRM lead

---

## PLAT-UC-006 — Webhook Email ESP ingest

**Mục tiêu khách hàng:** *"ESP events (bounce/open/click) cập nhật stats realtime."*

| # | Actor | Màn hình | Thao tác | Input | Phản hồi | Gate |
|---|-------|----------|----------|-------|----------|------|
| 1 | DevOps | ESP dashboard (SendGrid/etc) | Configure webhook events | URL + events | Active | ✓ |
| 2 | System | Ingest handler | Parse bounce/open/click | JSON | Parsed | ✓ |
| 3 | System | — | Update campaign stats + suppression | email | Rows updated | ✓ |
| 4 | Strategist | `/email/campaigns/[id]` | Stats tab matches ESP | — | ± lag 5m | ✓ [EM-UC-008](05-EM-ACTIONS.md) |
| 5 | Strategist | `/email/suppression` | Hard bounce auto-added | email | Row | ✓ |
| 6 | DevOps | `/agency/ingest` | Monitor email channel errors | — | <1% | ✓ |

#### Tiêu chí nghiệm thu
- [ ] Hard bounce → suppression ≤ 5 min
- [ ] Stats reconcile with ESP dashboard

---

## PLAT-UC-007 — Job queue worker process

**Mục tiêu khách hàng:** *"Background jobs (sync, send, poll) chạy ổn — dead letter replay được."*

**Actors:** DevOps, Tracking

| # | Actor | Màn hình | Thao tác | Input | Phản hồi | Gate |
|---|-------|----------|----------|-------|----------|------|
| 1 | DevOps | VPS / docker | Worker + **Redis** up | — | Health OK | ✓ |
| 2 | DevOps | Env flags | Enable module jobs e.g. `PTT_ZALO_FORM_POLL=1` | — | Workers register | ✓ |
| 3 | DevOps | `/agency/jobs` hoặc `/seo/automations` | Check **queue depth** | — | < threshold | ✓ |
| 4 | Tracking | Same | Filter **failed** jobs | channel | List | ✓ |
| 5 | DevOps | Dead letter | **Replay** failed job | job id | Success | ✓ |
| 6 | DevOps | Monitoring | Alert queue lag > N min | — | P1 if critical | ○ |
| 7 | QA | Smoke | Trigger sync job manually | — | Completes | ✓ |

#### Tiêu chí nghiệm thu
- [ ] Queue depth recovers after spike
- [ ] Failed job replay idempotent

---

## PLAT-UC-008 — Temporal approval workflow

**Mục tiêu khách hàng:** *"Approval workflow durable — client signal → side effect execute."*

| # | Actor | Màn hình | Thao tác | Input | Phản hồi | Gate |
|---|-------|----------|----------|-------|----------|------|
| 1 | DevOps | Temporal UI / CLI | Namespace **running** | — | Green | ✓ |
| 2 | Staff | ops module | Submit approval item | creative/campaign | workflow id | ✓ |
| 3 | System | Temporal | Wait client approval signal | — | Pending | ✓ |
| 4 | Client | Portal approve | Signal workflow | approve | Continues | ✓ |
| 5 | System | Activity worker | Execute side effect (send/create) | — | Complete | ✓ |
| 6 | DevOps | Temporal UI | Verify workflow history | — | Audit trail | ✓ |

#### Tiêu chí nghiệm thu
- [ ] Workflow survives worker restart
- [ ] Reject signal terminates cleanly

---

## PLAT-UC-009 — Seed staff permissions

**Mục tiêu khách hàng:** *"New hire có account + caps đúng role ngày đầu — A4 handover."*

| # | Actor | Màn hình | Thao tác | Input | Phản hồi | Gate |
|---|-------|----------|----------|-------|----------|------|
| 1 | Admin | Seed script / `/crm/staff` | **Create user** | email, name | staff id | ✓ |
| 2 | Admin | Same | Assign **role template** caps | AM/Buyer/CSKH | Caps set | ✓ |
| 3 | Admin | Same | Set temporary password / invite | — | Once display | ✓ |
| 4 | New hire | `/login` | First login + change password | — | Success | ✓ |
| 5 | New hire | ops modules | Verify access correct | sidebar | Expected caps | ✓ |
| 6 | AM | credentials **A4 form** | Vault handover | — | Signed | ✓ |
| 7 | Admin | Offboard path | Deactivate staff | — | Login blocked | ○ |

#### Tiêu chí nghiệm thu
- [ ] Role template matches job function
- [ ] Deactivated staff cannot login

---

## PLAT-UC-010 — Health check & soak evidence

**Mục tiêu khách hàng:** *"Prod healthy — gate scripts PASS trước nghiệm thu module."*

| # | Actor | Màn hình | Thao tác | Input | Phản hồi | Gate |
|---|-------|----------|----------|-------|----------|------|
| 1 | DevOps | `GET /health` | Liveness + readiness | — | 200 OK | ✓ |
| 2 | QA | `./scripts/email_p1_gate.sh` | Run gate script | — | PASS output | ✓ |
| 3 | QA | `./scripts/staging_zalo_wave_z2_gate.sh` | Zalo gate (if applicable) | — | PASS | ✓ |
| 4 | QA | `/email/gate-a` hoặc `/seo/gate-a` | Module checklist UI | ticks | Complete | ✓ |
| 5 | DevOps | Soak 3–7 days | Monitor error rates | — | Stable | ✓ [SYS-UC-009](00-SYSTEM-ACTIONS.md) |
| 6 | PO | handover §6 | Attach evidence bundle | logs, screenshots | Sign-off | ✓ |

#### Tiêu chí nghiệm thu
- [ ] All gate scripts PASS on staging
- [ ] Soak no P1 incidents

---

## Ma trận webhook → CRM (tóm tắt)

| Channel | Endpoint | UC downstream | Verify màn hình |
|---------|----------|---------------|-----------------|
| Meta | `POST /webhooks/meta` | [META-UC-004](03-META-ACTIONS.md), [CRM-UC-001](01-CRM-ACTIONS.md) | `/agency/ingest` |
| Zalo | `POST /webhooks/zalo` | [ZALO-UC-011](08-ZALO-ACTIONS.md), [CRM-UC-001](01-CRM-ACTIONS.md) | `/crm/leads?source=zalo` |
| Email ESP | ESP webhook | [EM-UC-008](05-EM-ACTIONS.md) | `/email/campaigns/[id]` |

**Liên kết SYS:** [SYS-UC-008](00-SYSTEM-ACTIONS.md) incident P1 webhook down.
