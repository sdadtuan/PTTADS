# Use Case — Client Portal

> **Prefix:** PORTAL · **Phiên bản:** 1.0 · **Ngày:** 2026-07-25  
> **Index:** [`README.md`](README.md) · **Spec:** [`handover/03-HUONG-DAN-PORTAL-KHACH-HANG.md`](../handover/03-HUONG-DAN-PORTAL-KHACH-HANG.md)

---

## PORTAL-UC-001 — Login portal scoped client

| Thuộc tính | Giá trị |
|------------|---------|
| **Actor chính** | Client Viewer, Client Approver |
| **Priority** | P0 |
| **Trigger** | User truy cập portal URL |

**Preconditions:** Portal user provisioned by AM ([SYS-UC-001](00-SYSTEM-OVERVIEW.md)); account active.

**Main flow:**

1. User mở portal-web login.
2. Email + password → [PLAT-UC-003](07-PLATFORM-AUTH-WEBHOOKS.md) JWT issued.
3. Token scoped single `client_id` + role (viewer/approver).
4. Redirect dashboard.

**Extensions:**

- **E1 — Wrong client:** 403; no data leak ([SYS-UC-011](00-SYSTEM-OVERVIEW.md)).

**Postconditions:** Session TTL per security policy; refresh supported.

**Traceability:** portal login; portal auth API

---

## PORTAL-UC-002 — Dashboard KPI multi-module

| Thuộc tính | Giá trị |
|------------|---------|
| **Actor chính** | Client Viewer |
| **Priority** | P0 |

**Main flow:**

1. Dashboard loads enabled modules (Meta, SEO, Email flags).
2. Cards: spend, leads, CPL, SEO traffic summary, email sends.
3. Date range selector; disclaimer attribution footer.

**Postconditions:** Read-only; no PII other staff contacts.

**Traceability:** portal dashboard; aggregated KPI API

---

## PORTAL-UC-003 — Meta performance view + CSV

| Thuộc tính | Giá trị |
|------------|---------|
| **Actor chính** | Client Viewer |
| **Priority** | P0 |

**Main flow:** Meta tab → campaign table → drill metrics → export CSV period.

**Traceability:** portal `/meta`; [META-UC-003](03-META-ENTERPRISE.md) data subset

---

## PORTAL-UC-004 — SEO summary view

| Thuộc tính | Giá trị |
|------------|---------|
| **Actor chính** | Client Viewer |
| **Priority** | P1 |

**Main flow:** SEO tab → traffic trend, top pages, content delivered count; link PDF if published.

**Traceability:** portal `/seo`; [SEO-UC-013](04-SEO-AEO.md)

---

## PORTAL-UC-005 — Email campaign stats

| Thuộc tính | Giá trị |
|------------|---------|
| **Actor chính** | Client Viewer |
| **Priority** | P1 |

**Main flow:** Email tab → sent campaigns list → open/click rates (aggregate only).

**Traceability:** portal `/email`; EM campaign stats API

---

## PORTAL-UC-006 — Approval inbox Meta creative

| Thuộc tính | Giá trị |
|------------|---------|
| **Actor chính** | Client Approver |
| **Priority** | P0 |
| **Trigger** | Staff submit creative for approval |

**Main flow:**

1. Notification → Approvals inbox.
2. Preview creative assets + copy.
3. Approve → notify staff; creative unlocked for launch.
4. Reject → [PORTAL-UC-009](#portal-uc-009--reject-with-comment).

**Postconditions:** Decision synced to ops-web + Temporal ([SYS-UC-004](00-SYSTEM-OVERVIEW.md)).

**Traceability:** portal `/approvals`; [SVC-UC-006](02-AGENCY-SERVICE-DELIVERY.md)

---

## PORTAL-UC-007 — Approval SEO content

| Thuộc tính | Giá trị |
|------------|---------|
| **Actor chính** | Client Approver |
| **Priority** | P1 |

**Main flow:** Preview content draft (HTML/markdown); approve/reject; comment on sections.

**Postconditions:** Content pipeline advances ([SEO-UC-005](04-SEO-AEO.md)).

**Traceability:** portal SEO approval item

---

## PORTAL-UC-008 — Approval email campaign

| Thuộc tính | Giá trị |
|------------|---------|
| **Actor chính** | Client Approver |
| **Priority** | P1 |

**Main flow:** Preview email template + subject + segment size summary; approve unlocks send ([EM-UC-007](05-EMAIL-MARKETING.md)).

**Traceability:** portal email approval; EM campaign submit

---

## PORTAL-UC-009 — Reject with comment

| Thuộc tính | Giá trị |
|------------|---------|
| **Actor chính** | Client Approver |
| **Priority** | P0 |

**Main flow:**

1. Select Reject → comment required (min length).
2. Status → rejected; staff notified.
3. Item returns to draft in ops-web.

**Postconditions:** Rejection reason in audit; no auto-resubmit.

**Business rules:** BR-PORTAL-01 — Reject without comment blocked.

**Traceability:** approval reject API; all approval UCs

---

## PORTAL-UC-010 — Export & download artifact

| Thuộc tính | Giá trị |
|------------|---------|
| **Actor chính** | Client Viewer |
| **Priority** | P0 |

**Main flow:** Download weekly PDF reports, signed URLs for Meta CSV, SEO PDF; expiry on links.

**Postconditions:** Download logged for compliance.

**Traceability:** portal downloads; [SYS-UC-005](00-SYSTEM-OVERVIEW.md)
