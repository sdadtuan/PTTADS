# Use Case — CRM Core

> **Prefix:** CRM · **Phiên bản:** 1.0 · **Ngày:** 2026-07-25  
> **Index:** [`README.md`](README.md) · **Spec:** [`product-model-v1.md`](../product-model-v1.md), [`SPEC_AGENCY_OPERATING_PLATFORM.md`](../SPEC_AGENCY_OPERATING_PLATFORM.md)

---

## CRM-UC-001 — Đăng nhập & phân công lead tự động

| Thuộc tính | Giá trị |
|------------|---------|
| **Actor chính** | CSKH / Sales |
| **Actor phụ** | System (webhook ingest, assignment engine) |
| **Priority** | P0 |
| **Trigger** | Lead mới từ Meta/Zalo/form hoặc import |

**Preconditions:** Staff đăng nhập ops-web; assignment rules configured; lead source mapped.

**Main flow:**

1. Webhook hoặc form submit tạo lead record ([PLAT-UC-004](07-PLATFORM-AUTH-WEBHOOKS.md), [PLAT-UC-005](07-PLATFORM-AUTH-WEBHOOKS.md)).
2. Engine dedup theo phone/email ([META-UC-004](03-META-ENTERPRISE.md)).
3. Gán owner theo rule: round-robin / territory / product line.
4. Lead xuất hiện trên `/crm/leads` với status **Mới**.
5. CSKH nhận notification (in-app / optional Slack).

**Extensions:**

- **E1 — Duplicate:** Merge hoặc link existing lead; không tạo bản ghi trùng.
- **E2 — Không match rule:** Fallback queue GDKD review ([CRM-UC-003](#crm-uc-003--review-queue-gdkd)).

**Postconditions:** Lead có owner; audit source + timestamp.

**Business rules:** BR-CRM-01 — Một lead active chỉ một owner primary.

**Traceability:** `/crm/leads`, `POST /crm/leads`, product-model §Lead lifecycle

---

## CRM-UC-002 — Chăm sóc lead B2 (Liên hệ OK)

| Thuộc tính | Giá trị |
|------------|---------|
| **Actor chính** | CSKH |
| **Priority** | P0 |
| **Trigger** | CSKH liên hệ thành công lead Mới |

**Preconditions:** Lead status Mới/B1; staff là owner.

**Main flow:**

1. CSKH mở lead detail → log call/note.
2. Cập nhật status → **B2 — Liên hệ OK**.
3. Hệ thống ghi activity timeline.
4. Nếu qualify → chuyển Pre-sales ([CRM-UC-005](#crm-uc-005--pre-sales--kh-mkt-sơ-bộ)).

**Extensions:**

- **E1 — Không liên lạc được:** Chuyển B1 retry hoặc Lost với reason.

**Postconditions:** SLA contact time tracked; KPI CSKH cập nhật.

**Traceability:** `/crm/leads/:id`, activity API

---

## CRM-UC-003 — Review queue GDKD

| Thuộc tính | Giá trị |
|------------|---------|
| **Actor chính** | GDKD / Head Sales |
| **Priority** | P0 |
| **Trigger** | Lead vào queue review (high value / no owner / policy) |

**Main flow:**

1. GDKD mở review queue trên hub CRM.
2. Xem lead summary, source, estimated value.
3. **Approve assign** → chọn owner + priority.
4. **Reject / reassign** → comment bắt buộc.

**Postconditions:** Lead có owner hợp lệ hoặc archived với reason.

**Business rules:** BR-CRM-02 — Deal > threshold bắt buộc GDKD approve trước proposal.

**Traceability:** `/crm/hub`, review queue widget

---

## CRM-UC-004 — Add-on ngành trên lead

| Thuộc tính | Giá trị |
|------------|---------|
| **Actor chính** | CSKH, AM |
| **Priority** | P1 |
| **Trigger** | Lead có nhu cầu đa ngành (BĐS + MKT + …) |

**Main flow:**

1. Mở lead → tab Add-ons.
2. Chọn ngành từ catalog ([CRM-UC-012](#crm-uc-012--catalog-dịch-vungành)).
3. Gán specialist phụ theo ngành.
4. Pipeline tracking per add-on line.

**Postconditions:** Lead có 1+ add-on; routing rules áp dụng.

**Traceability:** catalog API; product-model add-on

---

## CRM-UC-005 — Pre-sales & KH MKT sơ bộ

| Thuộc tính | Giá trị |
|------------|---------|
| **Actor chính** | Pre-sales / AM |
| **Priority** | P0 |
| **Trigger** | Lead B2 qualify |

**Main flow:**

1. Pre-sales discovery call → ghi needs, budget, timeline.
2. Tạo **KH MKT sơ bộ** (draft scope).
3. Attach competitor / brief docs.
4. Chuyển stage → **Proposal prep** ([CRM-UC-006](#crm-uc-006--chuyển-lead--proposalhđ)).

**Postconditions:** KH MKT draft linked to lead.

**Traceability:** `/crm/pre-sales`, KH MKT entity

---

## CRM-UC-006 — Chuyển lead → Proposal/HĐ

| Thuộc tính | Giá trị |
|------------|---------|
| **Actor chính** | AM |
| **Priority** | P0 |
| **Trigger** | Client đồng ý scope sơ bộ |

**Main flow:**

1. AM tạo Proposal từ template.
2. Chọn dịch vụ từ catalog → pricing lines.
3. Gửi client (email/PDF).
4. Client accept → tạo HĐ draft.
5. Legal/finance sign-off → HĐ active.

**Extensions:**

- **E1 — Revision:** Version proposal; giữ history.

**Postconditions:** Lead stage Proposal/Won path; HĐ record nếu ký.

**Traceability:** `/crm/contracts`, proposal API

---

## CRM-UC-007 — Convert → Customer + Case

| Thuộc tính | Giá trị |
|------------|---------|
| **Actor chính** | AM |
| **Actor phụ** | System |
| **Priority** | P0 |
| **Trigger** | HĐ ký / Won deal |

**Main flow:**

1. AM action **Convert to Customer** trên lead/deal.
2. System tạo Customer master + link HĐ.
3. Tạo **Case** delivery initial (optional RE project).
4. Trigger service lifecycle Onboard ([SVC-UC-001](02-AGENCY-SERVICE-DELIVERY.md)).
5. Revenue fields feed closed-loop ([SYS-UC-002](00-SYSTEM-OVERVIEW.md)).

**Postconditions:** Customer active; duplicate lead merged.

**Business rules:** BR-CRM-03 — Customer code unique; một legal entity một master.

**Traceability:** `/crm/customers`, convert API, [SYS-UC-001](00-SYSTEM-OVERVIEW.md)

---

## CRM-UC-008 — Quản lý bảng CSKH

| Thuộc tính | Giá trị |
|------------|---------|
| **Actor chính** | CSKH Lead |
| **Priority** | P0 |
| **Trigger** | Daily ops CSKH |

**Main flow:**

1. Mở bảng CSKH `/crm/cskh-board`.
2. Filter theo owner, SLA, status.
3. Bulk assign / reschedule follow-up.
4. Export snapshot cho standup.

**Postconditions:** SLA breaches visible; assignments updated.

**Traceability:** CSKH board UI; KPI widgets

---

## CRM-UC-009 — Pipeline sales & đề xuất

| Thuộc tính | Giá trị |
|------------|---------|
| **Actor chính** | Sales, AM |
| **Priority** | P1 |

**Main flow:** Kanban pipeline stages (Qualify → Proposal → Negotiation → Won/Lost); drag stage; forecast weight; lost reason taxonomy.

**Postconditions:** Pipeline report accurate; Won triggers CRM-UC-007.

**Traceability:** `/crm/pipeline`, forecast API

---

## CRM-UC-010 — Dự án BĐS (RE Projects)

| Thuộc tính | Giá trị |
|------------|---------|
| **Actor chính** | AM BĐS |
| **Priority** | P1 |

**Main flow:** Tạo RE project gắn customer; units inventory; campaign mapping per dự án; báo cáo theo project.

**Traceability:** RE module routes; product-model RE

---

## CRM-UC-011 — Hub hợp đồng & lifecycle

| Thuộc tính | Giá trị |
|------------|---------|
| **Actor chính** | AM, Finance |
| **Priority** | P0 |

**Main flow:**

1. Hub `/crm/hub` — contracts expiring, lifecycle stage per client.
2. Drill client → HĐ detail → linked services.
3. Alert renewal 30/60/90 days.

**Postconditions:** AM có single pane contract health.

**Traceability:** `/crm/hub`, contract lifecycle API

---

## CRM-UC-012 — Catalog dịch vụ/ngành

| Thuộc tính | Giá trị |
|------------|---------|
| **Actor chính** | Admin, AM |
| **Priority** | P1 |

**Main flow:** CRUD service SKUs, industry verticals, pricing tiers; enable/disable for proposals.

**Traceability:** `/crm/catalog`, admin catalog API

---

## CRM-UC-013 — KPI nhân sự & chấm công

| Thuộc tính | Giá trị |
|------------|---------|
| **Actor chính** | HR, Team Lead |
| **Priority** | P1 |

**Main flow:** Attendance log; KPI targets per role (leads handled, conversion); monthly scorecard.

**Traceability:** `/crm/kpi-staff`, attendance module

---

## CRM-UC-014 — Dashboard kinh doanh chủ DN

| Thuộc tính | Giá trị |
|------------|---------|
| **Actor chính** | Chủ DN / GDKD |
| **Priority** | P1 |

**Main flow:** Executive CRM dashboard — revenue YTD, pipeline, win rate, top AM; export PDF.

**Traceability:** `/crm/executive`, dashboard aggregates

---

## CRM-UC-015 — Import/export lead

| Thuộc tính | Giá trị |
|------------|---------|
| **Actor chính** | CSKH Lead, Admin |
| **Priority** | P1 |

**Main flow:**

1. Download CSV template.
2. Upload → validate columns, dedup preview.
3. Confirm import → batch create/update.
4. Export filter results CSV.

**Extensions:**

- **E1 — Validation fail:** Row-level error report; partial import optional.

**Postconditions:** Import job log; source tagged `import`.

**Traceability:** `/crm/leads/import`, bulk API
