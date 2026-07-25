# Use Case — Platform (Auth, Webhooks, Admin)

> **Prefix:** PLAT · **Phiên bản:** 1.0 · **Ngày:** 2026-07-25  
> **Index:** [`README.md`](README.md) · **Spec:** [`SPEC_AGENCY_OPERATING_PLATFORM.md`](../SPEC_AGENCY_OPERATING_PLATFORM.md), [`handover/04-KIEN-TRUC-TRIEN-KHAI-BAN-GIAO.md`](../handover/04-KIEN-TRUC-TRIEN-KHAI-BAN-GIAO.md)

---

## PLAT-UC-001 — Staff JWT login & refresh

| Thuộc tính | Giá trị |
|------------|---------|
| **Actor chính** | All staff roles |
| **Priority** | P0 |
| **Trigger** | Login ops-web |

**Preconditions:** Staff account seeded ([PLAT-UC-009](#plat-uc-009--seed-staff-permissions)).

**Main flow:**

1. POST `/auth/login` email + password.
2. Validate bcrypt hash; issue access JWT + refresh token.
3. ops-web stores token; attaches Authorization header.
4. Refresh before expiry via `/auth/refresh`.

**Extensions:**

- **E1 — Invalid credentials:** 401; rate limit lockout.

**Postconditions:** Session scoped staff id + caps array.

**Traceability:** Nest auth module; ops-web auth middleware

---

## PLAT-UC-002 — RBAC cap enforcement

| Thuộc tính | Giá trị |
|------------|---------|
| **Actor chính** | System |
| **Priority** | P0 |

**Main flow:**

1. Every API route declares required cap (e.g. `crm.leads.read`, `meta.write`).
2. Guard checks JWT caps vs route.
3. UI hides nav items without cap.
4. 403 on unauthorized API.

**Postconditions:** Least privilege enforced server-side (not UI-only).

**Business rules:** BR-PLAT-01 — Deny by default.

**Traceability:** [`handover/05-PHAN-QUYEN-BAO-MAT-SLA.md`](../handover/05-PHAN-QUYEN-BAO-MAT-SLA.md); cap matrix

---

## PLAT-UC-003 — Portal JWT login

| Thuộc tính | Giá trị |
|------------|---------|
| **Actor chính** | Portal users |
| **Priority** | P0 |

**Main flow:** Separate issuer/audience for portal; JWT contains `client_id`, `portal_role`; all portal APIs filter by client.

**Postconditions:** No cross-tenant access ([SYS-UC-011](00-SYSTEM-OVERVIEW.md)).

**Traceability:** portal auth; [PORTAL-UC-001](06-CLIENT-PORTAL.md)

---

## PLAT-UC-004 — Webhook Meta ingest

| Thuộc tính | Giá trị |
|------------|---------|
| **Actor chính** | System (Meta) |
| **Priority** | P0 |
| **Trigger** | Meta POST leadgen / verification |

**Main flow:**

1. Verify `X-Hub-Signature-256`.
2. Handle challenge GET for subscription.
3. Queue lead payload → worker → CRM ([META-UC-004](03-META-ENTERPRISE.md)).
4. Return 200 within timeout.

**Extensions:**

- **E1 — Down:** [SYS-UC-008](00-SYSTEM-OVERVIEW.md) incident.

**Postconditions:** Idempotent processing via event id.

**Traceability:** `POST /webhooks/meta`; nginx route

---

## PLAT-UC-005 — Webhook Zalo/Google ingest

| Thuộc tính | Giá trị |
|------------|---------|
| **Actor chính** | System |
| **Priority** | P0 |

**Main flow:** Channel-specific signature verify → normalize lead → CRM ingest ([CRM-UC-001](01-CRM-CORE.md)).

**Traceability:** Zalo OA webhook; Google Ads lead form webhook

---

## PLAT-UC-006 — Webhook Email ESP ingest

| Thuộc tính | Giá trị |
|------------|---------|
| **Actor chính** | System (ESP) |
| **Priority** | P0 |

**Main flow:** Parse delivered/bounce/open/click/spam complaint → update contact + campaign stats ([EM-UC-008](05-EMAIL-MARKETING.md)).

**Postconditions:** Bounce triggers suppression ([EM-UC-009](05-EMAIL-MARKETING.md)).

**Traceability:** ESP webhook endpoints; email event worker

---

## PLAT-UC-007 — Job queue worker process

| Thuộc tính | Giá trị |
|------------|---------|
| **Actor chính** | System (worker) |
| **Priority** | P0 |

**Main flow:**

1. BullMQ/Redis queue: sync, send, report, segment compute.
2. Worker consume with retry + dead letter.
3. Metrics: queue depth, failure rate.

**Postconditions:** At-least-once processing; idempotent handlers.

**Traceability:** worker service; Redis; job dashboards

---

## PLAT-UC-008 — Temporal approval workflow

| Thuộc tính | Giá trị |
|------------|---------|
| **Actor chính** | System |
| **Priority** | P1 |

**Main flow:**

1. Start workflow on campaign write / email send / cross-module approval.
2. Wait human signals (staff, client).
3. Timeout → escalate notification.
4. Complete → execute side effect (Meta API, ESP send).

**Postconditions:** Durable workflow history.

**Traceability:** Temporal namespace; [SVC-UC-007](02-AGENCY-SERVICE-DELIVERY.md), [EM-UC-007](05-EMAIL-MARKETING.md)

---

## PLAT-UC-009 — Seed staff permissions

| Thuộc tính | Giá trị |
|------------|---------|
| **Actor chính** | Super Admin, DevOps |
| **Priority** | P0 |
| **Trigger** | Fresh deploy / new hire |

**Main flow:**

1. Run seed script or admin UI create user.
2. Assign role template caps.
3. User first login → force password change (optional policy).

**Postconditions:** Staff can access permitted modules only.

**Traceability:** seed scripts; admin user API; credentials handover form

---

## PLAT-UC-010 — Health check & soak evidence

| Thuộc tính | Giá trị |
|------------|---------|
| **Actor chính** | DevOps, QA |
| **Priority** | P1 |

**Main flow:**

1. `GET /health` liveness/readiness (DB, Redis, Temporal).
2. Run soak scripts (`email_p1_gate.sh`, module gates).
3. Collect evidence for nghiệm thu ([handover/06](../handover/06-NGHIEM-THU-VA-BAO-CAO.md)).

**Postconditions:** Gate PASS artifacts stored in CI or ops folder.

**Traceability:** health endpoints; gate scripts; [SYS-UC-009](00-SYSTEM-OVERVIEW.md)
