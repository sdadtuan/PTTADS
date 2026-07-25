# Chi tiết hành động — Client Portal (PORTAL)

> **UC gốc:** [`../06-CLIENT-PORTAL.md`](../06-CLIENT-PORTAL.md)

---

## PORTAL-UC-001 — Login portal scoped client

**Mục tiêu khách hàng:** *"Đăng nhập an toàn, chỉ thấy data công ty mình."*

| # | Actor | Màn hình | Thao tác | Input | Gate |
|---|-------|----------|----------|-------|------|
| 1 | PTT Admin | `/agency/clients/[id]` tab Portal users | **+ Tạo user** | email, role, password | temporary_password | ✓ |
| 2 | AM | Handover A4 credentials | Giao email/password vault | — | ✓ |
| 3 | Client | portal `/login` | Nhập email + password | credentials | ✓ |
| 4 | System | Auth API | Issue JWT scoped `client_id` | — | ✓ |
| 5 | Client | `/dashboard` | Redirect after login | — | ✓ widgets load |
| 6 | Client | (Policy) | Đổi mật khẩu lần đầu | ⚠ GAP-P0-02 no self-serve | ⚠ AM reset |

#### Nhánh archived client
Login → redirect `/archived` — không xem KPI.

---

## PORTAL-UC-002 — Dashboard KPI multi-module

| # | Actor | Màn hình | Thao tác | Gate |
|---|-------|----------|----------|------|
| 1 | Viewer | `/dashboard` | View Meta/SEO/Email widgets | ✓ flags |
| 2 | Viewer | Date picker | T-7 / T-30 | ✓ |
| 3 | Viewer | Pending approvals widget | Click → inbox | ✓ if approver |
| 4 | Viewer | Footer | Read attribution disclaimer | ✓ |

---

## PORTAL-UC-003 — Meta performance view + CSV

| # | Actor | Màn hình | Thao tác | Gate |
|---|-------|----------|----------|------|
| 1 | Viewer | `/meta` hoặc `/dashboard` | Open Meta panel | ✓ |
| 2 | Viewer | Group by day/campaign | select | ✓ |
| 3 | Viewer | **Export CSV** / **PDF** | download | ✓ |
| 4 | Viewer | Read CPL disclaimer if unmapped | yellow note | ✓ |

---

## PORTAL-UC-004 — SEO summary view

| # | Actor | Màn hình | Thao tác | Gate |
|---|-------|----------|----------|------|
| 1 | Viewer | `/seo` | Requires `seo_enabled` | ✓ |
| 2 | Viewer | Widgets | GSC clicks, content count | ✓ |
| 3 | Viewer | `/seo/reports` | Open reports | ✓ |

---

## PORTAL-UC-005 — Email campaign stats

| # | Actor | Màn hình | Thao tác | Gate |
|---|-------|----------|----------|------|
| 1 | Viewer | `/email` | Requires `email_enabled` | ✓ |
| 2 | Viewer | Campaign list stats | open/click aggregate | ✓ |
| 3 | Viewer | `/email/campaigns/[id]` | Drill metrics | ✓ |

---

## PORTAL-UC-006 — Approval inbox Meta creative

| # | Actor | Màn hình | Thao tác | Input | Gate |
|---|-------|----------|----------|-------|------|
| 1 | Approver | `/creatives` | List pending | — | ✓ role |
| 2 | Approver | Row | Preview image/video/copy | — | ✓ |
| 3 | Approver | **Approve** | optional note | ✓ staff notified |
| 4 | Approver | **Reject** | comment required | → [PORTAL-UC-009](#portal-uc-009--reject-with-comment) | ✓ |

---

## PORTAL-UC-007 — Approval SEO content

| # | Actor | Màn hình | Thao tác | Gate |
|---|-------|----------|----------|------|
| 1 | Approver | `/seo/content` | Pending list | ✓ |
| 2 | Approver | `/seo/content/[id]` | Read draft preview | ✓ |
| 3 | Approver | **Approve** / **Reject** | ✓ pipeline advances |

---

## PORTAL-UC-008 — Approval email campaign

| # | Actor | Màn hình | Thao tác | Gate |
|---|-------|----------|----------|------|
| 1 | Approver | `/email/approvals` | Inbox | ✓ |
| 2 | Approver | Preview subject + template | ✓ |
| 3 | Approver | **Approve** | unlock send | ✓ |
| 4 | Approver | **Reject** | comment | ✓ |

---

## PORTAL-UC-009 — Reject with comment

| # | Actor | Màn hình | Thao tác | Input | Gate |
|---|-------|----------|----------|-------|------|
| 1 | Approver | Any approval screen | Click **Reject** | — | ✓ |
| 2 | Approver | Modal/form | Nhập comment ≥ min length | text | ✓ block if empty |
| 3 | System | — | Status rejected + notify staff | ✓ |
| 4 | Staff | ops module | Item back to draft | ✓ |

---

## PORTAL-UC-010 — Export & download artifact

| # | Actor | Màn hình | Thao tác | Gate |
|---|-------|----------|----------|------|
| 1 | Viewer | `/meta`, `/seo/reports`, `/dashboard` | **Export CSV/PDF** | ✓ signed URL |
| 2 | System | — | Log download audit | ✓ |
| 3 | Viewer | Link expiry | Re-export if expired | ✓ |

---

## PORTAL-UC-EXTRA — Settings (approver)

| # | Actor | Màn hình | Thao tác | Gate |
|---|-------|----------|----------|------|
| 1 | Approver | `/settings` | Edit display name, logo URL | ✓ |
| 2 | Approver | Same | AM contact info | ✓ |
