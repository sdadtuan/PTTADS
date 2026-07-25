# Chi tiết hành động — Email Marketing (EM)

> **UC gốc:** [`../05-EMAIL-MARKETING.md`](../05-EMAIL-MARKETING.md) · **Ops:** [`../../huong-dan-email-marketing-ops.md`](../../huong-dan-email-marketing-ops.md)

---

## EM-UC-001 — Onboard email workspace & domain

| # | Actor | Màn hình | Thao tác | Input | Gate |
|---|-------|----------|----------|-------|------|
| 1 | Strategist | `/email/clients` | Open/create workspace | client | ✓ |
| 2 | Strategist | `/email/deliverability` | **+ Thêm domain** | domain name | ✓ |
| 3 | Strategist | **Wizard E-11** | Copy SPF, DKIM, DMARC records | DNS at registrar | ✓ |
| 4 | Strategist | Wizard | **Verify DNS** button | — | pass/fail | ✓ pass |
| 5 | Strategist | `/email/hub` | Filter client — deliverability green | ✓ |
| 6 | AM | Doc warm-up plan | external SOP | ○ |

---

## EM-UC-002 — Capture form → consent

| # | Actor | Màn hình | Thao tác | Input | Gate |
|---|-------|----------|----------|-------|------|
| 1 | Subscriber | Client website form | Submit email + consent checkbox | email | ✓ |
| 2 | System | `POST /email/contacts/capture` | Record consent log | source, IP hash | ✓ |
| 3 | Subscriber | Email inbox | Double opt-in click (if enabled) | ✓ |
| 4 | Subscriber | `/email/public/confirm/[token]` | Confirm page | ✓ subscribed |
| 5 | Strategist | `/email/consent` | Verify consent record | ✓ |

---

## EM-UC-003 — Import contacts CSV

| # | Actor | Màn hình | Thao tác | Input | Gate |
|---|-------|----------|----------|-------|------|
| 1 | Strategist | `/email/contacts` | **Bulk import** | CSV file | ✓ |
| 2 | Strategist | Column mapper | Map email, name, tags | ✓ |
| 3 | System | Preview | Dedup + suppression check | ✓ |
| 4 | Strategist | **Confirm import** | — | job log | ✓ |
| 5 | Strategist | `/email/suppression` | Review quarantine if bounce list | ✓ |

---

## EM-UC-004 — Segment compute (RFM/behavior)

| # | Actor | Màn hình | Thao tác | Input | Gate |
|---|-------|----------|----------|-------|------|
| 1 | Strategist | `/email/segments` | **+ Segment** | name | ✓ |
| 2 | Strategist | SegmentBuilder | Tab **Rules** / Static / Lifecycle / **RFM** / **Behavior** | criteria | ✓ |
| 3 | Strategist | Client dropdown | Select client scope | client_id | ✓ |
| 4 | Strategist | **Compute** | — | member count | ✓ |
| 5 | Strategist | **Save** segment version | — | ✓ |

---

## EM-UC-005 — Template studio + preflight

| # | Actor | Màn hình | Thao tác | Input | Gate |
|---|-------|----------|----------|-------|------|
| 1 | Strategist | `/email/templates` | **+ Tạo template** | name | ✓ |
| 2 | Strategist | `/email/templates/[id]` | Edit blocks, merge tags | HTML/blocks | ✓ |
| 3 | Strategist | **Preflight** | Run check | links, alt, spam | ✓ pass |
| 4 | Creative | Preview mobile/dark | — | ✓ |

---

## EM-UC-006 — Campaign broadcast F1

| # | Actor | Màn hình | Thao tác | Input | Gate |
|---|-------|----------|----------|-------|------|
| 1 | Strategist | `/email/campaigns` | **+ Tạo campaign** | name | ✓ |
| 2 | Strategist | `/email/campaigns/[id]` | Select segment, template, subject, from | fields | ✓ |
| 3 | Strategist | **Test send** | staff emails | ✓ |
| 4 | Strategist | `/email/campaigns/[id]/review` | Submit internal review | ✓ |
| 5 | Strategist | Submit for approval | → client if policy | ✓ |
| 6 | System | After approve | Queue ESP send | ✓ |

---

## EM-UC-007 — Staff + client approval

| # | Actor | Màn hình | Thao tác | Gate |
|---|-------|----------|----------|------|
| 1 | Compliance | `/email/campaigns/[id]/review` | Internal pass | ✓ |
| 2 | Client | portal `/email/approvals` | Preview campaign | ✓ |
| 3 | Client | **Approve** / **Reject** + comment | ✓ |
| 4 | Strategist | ops campaign | Status → approved → schedule send | ✓ |

---

## EM-UC-008 — ESP send & webhook engagement

| # | Actor | Màn hình | Thao tác | Gate |
|---|-------|----------|----------|------|
| 1 | System | Send worker | Batch ESP API | ✓ |
| 2 | System | ESP webhook | delivered/open/click/bounce | ✓ |
| 3 | Strategist | `/email/campaigns/[id]` | Stats tab refresh | ✓ |
| 4 | System | Bounce → `/email/suppression` | auto add | ✓ |

---

## EM-UC-009 — Suppression & one-click unsub

| # | Actor | Màn hình | Thao tác | Gate |
|---|-------|----------|----------|------|
| 1 | Subscriber | Email footer link | One-click unsub | ✓ |
| 2 | Subscriber | `/email/public/unsubscribe/[token]` | Confirm | ✓ |
| 3 | Strategist | `/email/suppression` | Verify entry | ✓ |
| 4 | Strategist | Next send | Excluded from segment | ✓ |

---

## EM-UC-010 — Deliverability incident F3

| # | Actor | Màn hình | Thao tác | Gate |
|---|-------|----------|----------|------|
| 1 | System | `/email/hub` | Alert banner + Slack/Teams | ✓ P1 |
| 2 | Strategist | Pause sends client/domain | toggle | ✓ |
| 3 | DevOps | DNS/ESP fix | runbook F3 | ✓ |
| 4 | Strategist | `/email/deliverability` | Re-verify DNS | ✓ green |
| 5 | Strategist | Resume sends | soak | ✓ |

---

## EM-UC-011 — Journey automation activate

| # | Actor | Màn hình | Thao tác | Gate |
|---|-------|----------|----------|------|
| 1 | Strategist | `/email/journeys` | **+ Tạo journey** | ✓ flag on |
| 2 | Strategist | `/email/journeys/[id]` | Canvas: trigger→wait→send→branch | ✓ |
| 3 | Strategist | Test mode enroll | test contact | ✓ |
| 4 | Strategist | **Activate** | — | ✓ live |

---

## EM-UC-012 — Governance rule CRUD

| # | Actor | Màn hình | Thao tác | Input | Gate |
|---|-------|----------|----------|-------|------|
| 1 | Compliance | `/email/governance` E-13 | **+ Add rule** | rate, footer, banned words | ✓ |
| 2 | Compliance | Row | Edit / **Delete** | ✓ audit log |
| 3 | System | Campaign submit | Evaluate block/warn | ✓ |

---

## EM-UC-013 — Reports & Grafana BI

| # | Actor | Màn hình | Thao tác | Gate |
|---|-------|----------|----------|------|
| 1 | AM | `/email/reports` E-12 | Filter client, period | ✓ |
| 2 | AM | **Export** CSV | ✓ |
| 3 | AM | BI status card | `GET /reports/bi-status` | ✓ |
| 4 | AM | Grafana section | Open embed link | ✓ staff |

---

## EM-UC-014 — Public preference center

| # | Actor | Màn hình | Thao tác | Gate |
|---|-------|----------|----------|------|
| 1 | Subscriber | `/email/public/preferences/[token]` | View lists | ✓ |
| 2 | Subscriber | Toggle preferences | save | ✓ |
| 3 | Subscriber | Unsubscribe all | confirm | ✓ suppression |
