# Chi tiết hành động — Platform (PLAT)

> **UC gốc:** [`../07-PLATFORM-AUTH-WEBHOOKS.md`](../07-PLATFORM-AUTH-WEBHOOKS.md)

> **Lưu ý:** Hầu hết PLAT UC là **System/DevOps** — bảng mô tả hành động vận hành + verify, không phải end-user business daily.

---

## PLAT-UC-001 — Staff JWT login & refresh

| # | Actor | Màn hình | Thao tác | Input | Gate |
|---|-------|----------|----------|-------|------|
| 1 | Staff | ops `/login` | Submit form | email, password | ✓ |
| 2 | System | `POST /auth/login` | Validate + issue JWT | access + refresh | ✓ |
| 3 | Staff | `/` | Dashboard load caps | sidebar visible | ✓ |
| 4 | Staff | (before expiry) | Silent refresh | refresh token | ✓ |

---

## PLAT-UC-002 — RBAC cap enforcement

| # | Actor | Màn hình | Thao tác | Gate |
|---|-------|----------|----------|------|
| 1 | Admin | Seed / DB | Assign caps to staff role | ✓ |
| 2 | Staff | ops any route | API without cap → 403 | ✓ |
| 3 | Staff | OpsNav | Menu hidden without cap | ✓ |
| 4 | QA | Test matrix | handover §5 roles | ✓ |

---

## PLAT-UC-003 — Portal JWT login

| # | Actor | Màn hình | Thao tác | Gate |
|---|-------|----------|----------|------|
| 1 | Client | portal `/login` | Credentials | ✓ |
| 2 | System | `POST /portal/auth/login` | JWT client_id + role | ✓ |
| 3 | QA | API fuzz | Other client_id blocked | ✓ |

---

## PLAT-UC-004 — Webhook Meta ingest

| # | Actor | Màn hình | Thao tác | Gate |
|---|-------|----------|----------|------|
| 1 | DevOps | Meta App Dashboard | Subscribe webhook URL | ✓ |
| 2 | DevOps | nginx + Nest | Route `POST /webhooks/meta` | ✓ |
| 3 | System | Verify signature | HMAC | ✓ |
| 4 | Tracking | `/agency/ingest` | Monitor success rate | ✓ |
| 5 | Tracking | Test lead | Meta test tool | ✓ CRM lead |

---

## PLAT-UC-005 — Webhook Zalo/Google ingest

| # | Actor | Màn hình | Thao tác | Gate |
|---|-------|----------|----------|------|
| 1 | DevOps | Channel config | Webhook URL + secret | ✓ |
| 2 | System | Normalize → CRM ingest | ✓ |
| 3 | CSKH | `/crm/leads` | Source filter zalo/google | ✓ |

---

## PLAT-UC-006 — Webhook Email ESP ingest

| # | Actor | Màn hình | Thao tác | Gate |
|---|-------|----------|----------|------|
| 1 | DevOps | ESP dashboard | Configure webhook events | ✓ |
| 2 | System | Parse bounce/open/click | update stats | ✓ |
| 3 | Strategist | `/email/campaigns/[id]` | Verify stats match ESP | ✓ |

---

## PLAT-UC-007 — Job queue worker process

| # | Actor | Màn hình | Thao tác | Gate |
|---|-------|----------|----------|------|
| 1 | DevOps | VPS | Worker + Redis up | ✓ |
| 2 | DevOps | `/agency/jobs` hoặc `/seo/automations` | Queue depth OK | ✓ |
| 3 | DevOps | Dead letter | Replay failed | ✓ |

---

## PLAT-UC-008 — Temporal approval workflow

| # | Actor | Màn hình | Thao tác | Gate |
|---|-------|----------|----------|------|
| 1 | DevOps | Temporal UI | Namespace running | ✓ |
| 2 | Staff | Submit approval item | workflow started | ✓ |
| 3 | Client | Portal approve signal | workflow continues | ✓ |
| 4 | System | Complete activity | side effect executed | ✓ |

---

## PLAT-UC-009 — Seed staff permissions

| # | Actor | Màn hình | Thao tác | Gate |
|---|-------|----------|----------|------|
| 1 | Admin | Seed script / `/crm/staff` | Create user | ✓ |
| 2 | Admin | Assign role template caps | ✓ |
| 3 | New hire | `/login` first time | access correct modules | ✓ |
| 4 | AM | credentials A4 form | vault handover | ✓ |

---

## PLAT-UC-010 — Health check & soak evidence

| # | Actor | Màn hình | Thao tác | Gate |
|---|-------|----------|----------|------|
| 1 | DevOps | `GET /health` | liveness/readiness | ✓ |
| 2 | QA | `./scripts/email_p1_gate.sh` | PASS output | ✓ |
| 3 | QA | Module gate-a pages | checklist tick | ✓ |
| 4 | PO | handover §6 | Attach evidence | ✓ sign-off |
