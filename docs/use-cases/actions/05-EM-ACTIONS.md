# Chi tiết hành động — Email Marketing (EM)

> **UC gốc:** [`../05-EMAIL-MARKETING.md`](../05-EMAIL-MARKETING.md)  
> **Ops:** [`../../huong-dan-email-marketing-ops.md`](../../huong-dan-email-marketing-ops.md)  
> **Cross-system:** [`06-PORTAL-ACTIONS.md`](06-PORTAL-ACTIONS.md) · [`07-PLAT-ACTIONS.md`](07-PLAT-ACTIONS.md)

---

## EM-UC-001 — Onboard email workspace & domain

**Mục tiêu khách hàng:** *"Domain email authenticated — deliverability green trước gửi campaign."*

**Actors:** Email Strategist, AM

| # | Actor | Màn hình | Thao tác | Input | Phản hồi | Gate |
|---|-------|----------|----------|-------|----------|------|
| 1 | Strategist | `/email/clients` | Open/create **workspace** | client id | Active | ✓ |
| 2 | Strategist | `/email/deliverability` | **+ Thêm domain** | domain name | Row created | ✓ |
| 3 | Strategist | **Wizard E-11** | Copy SPF, DKIM, DMARC records | DNS at registrar | Instructions | ✓ |
| 4 | Client IT | DNS registrar | Paste DNS records | TXT/CNAME | Propagated | ✓ external |
| 5 | Strategist | Wizard | **Verify DNS** button | — | pass/fail | ✓ pass |
| 6 | Strategist | `/email/hub` | Filter client — deliverability **green** | — | Badge | ✓ |
| 7 | AM | [`00-SYSTEM-ACTIONS.md`](00-SYSTEM-ACTIONS.md#sys-uc-001--onboard-client-mới-end-to-end) | Email branch onboard | — | Checklist | ✓ |
| 8 | AM | Doc warm-up plan | External SOP attach | — | Note | ○ |

#### Nhánh E1 — DNS fail
Wizard shows missing records → client IT fix → retry bước 5.

#### Tiêu chí nghiệm thu
- [ ] SPF + DKIM pass verification
- [ ] Hub deliverability green

---

## EM-UC-002 — Capture form → consent

**Mục tiêu khách hàng:** *"Subscriber opt-in có consent log — compliant GDPR/local."*

| # | Actor | Màn hình | Thao tác | Input | Phản hồi | Gate |
|---|-------|----------|----------|-------|----------|------|
| 1 | Subscriber | Client website form | Submit email + **consent checkbox** | email | 200 OK | ✓ |
| 2 | System | `POST /email/contacts/capture` | Record consent log | source, IP hash | contact id | ✓ |
| 3 | System | — | Double opt-in email (if enabled) | — | Email sent | ○ |
| 4 | Subscriber | Email inbox | Click confirm link | — | Token valid | ✓ |
| 5 | Subscriber | `/email/public/confirm/[token]` | Confirm page **Subscribe** | — | Subscribed | ✓ |
| 6 | Strategist | `/email/consent` | Verify consent record | email | Row + timestamp | ✓ |
| 7 | Strategist | `/email/contacts` | Contact status **subscribed** | — | Active | ✓ |

#### Tiêu chí nghiệm thu
- [ ] No consent checkbox → reject capture
- [ ] Consent log has source + timestamp

---

## EM-UC-003 — Import contacts CSV

**Mục tiêu khách hàng:** *"Import list an toàn — dedup, suppression, preview trước confirm."*

| # | Actor | Màn hình | Thao tác | Input | Phản hồi | Gate |
|---|-------|----------|----------|-------|----------|------|
| 1 | Strategist | `/email/contacts` | **Bulk import** | CSV file | Upload OK | ✓ |
| 2 | Strategist | Column mapper | Map email, name, tags | columns | Mapped | ✓ |
| 3 | System | Preview | Dedup + **suppression** check | — | Error/warn count | ✓ |
| 4 | Strategist | Preview | Fix errors / exclude rows | — | Clean preview | ✓ |
| 5 | Strategist | **Confirm import** | — | job log | N imported | ✓ |
| 6 | Strategist | `/email/suppression` | Review quarantine bounce list | — | No conflict | ✓ |
| 7 | Strategist | `/email/segments` | Verify segment counts | — | Updated | ○ |

#### Tiêu chí nghiệm thu
- [ ] Suppressed emails not imported as active
- [ ] Invalid email rows blocked at preview

---

## EM-UC-004 — Segment compute (RFM/behavior)

**Mục tiêu khách hàng:** *"Segment đúng audience — RFM, behavior, lifecycle rules."*

| # | Actor | Màn hình | Thao tác | Input | Phản hồi | Gate |
|---|-------|----------|----------|-------|----------|------|
| 1 | Strategist | `/email/segments` | **+ Segment** | name | Draft id | ✓ |
| 2 | Strategist | SegmentBuilder | Tab **Rules** / Static / Lifecycle / **RFM** / **Behavior** | criteria | Builder UI | ✓ |
| 3 | Strategist | Client dropdown | Select **client scope** | client_id | Scoped | ✓ |
| 4 | Strategist | Same | Preview rule logic | — | SQL-like readable | ✓ |
| 5 | Strategist | **Compute** | — | member count | Number | ✓ |
| 6 | Strategist | **Save** segment version | — | version id | Saved | ✓ |
| 7 | Strategist | `/email/campaigns/new` | Pick segment in campaign | segment id | Available | ✓ [UC-006](#em-uc-006--campaign-broadcast-f1) |

#### Tiêu chí nghiệm thu
- [ ] Compute excludes suppression list
- [ ] Segment version immutable after campaign send

---

## EM-UC-005 — Template studio + preflight

**Mục tiêu khách hàng:** *"Template đẹp mọi client — preflight pass trước gửi."*

| # | Actor | Màn hình | Thao tác | Input | Phản hồi | Gate |
|---|-------|----------|----------|-------|----------|------|
| 1 | Strategist | `/email/templates` | **+ Tạo template** | name | Template id | ✓ |
| 2 | Strategist | `/email/templates/[id]` | Edit blocks, merge tags | HTML/blocks | Preview | ✓ |
| 3 | Strategist | Same | Insert footer unsub link | merge tag | Required | ✓ |
| 4 | Strategist | **Preflight** | Run check | — | links, alt, spam | ✓ pass |
| 5 | Creative | Preview mobile/dark mode | — | Render OK | ✓ |
| 6 | Strategist | Save version | — | version locked | ✓ |
| 7 | Compliance | `/email/governance` | Template passes rules | — | No block | ✓ [UC-012](#em-uc-012--governance-rule-crud) |

#### Tiêu chí nghiệm thu
- [ ] Preflight fail blocks campaign attach
- [ ] Unsub merge tag present

---

## EM-UC-006 — Campaign broadcast F1

**Mục tiêu khách hàng:** *"Broadcast campaign F1 — test send, review, approval, queue send."*

| # | Actor | Màn hình | Thao tác | Input | Phản hồi | Gate |
|---|-------|----------|----------|-------|----------|------|
| 1 | Strategist | `/email/campaigns` | **+ Tạo campaign** | name | Campaign id | ✓ |
| 2 | Strategist | `/email/campaigns/[id]` | Select segment, template, subject, from | fields | Valid | ✓ |
| 3 | Strategist | Same | **Test send** | staff emails | Inbox received | ✓ |
| 4 | Strategist | `/email/campaigns/[id]/review` | Submit **internal review** | — | pending internal | ✓ |
| 5 | Compliance | Same | Internal pass | comment | approved internal | ✓ |
| 6 | Strategist | Same | **Submit for client approval** | — | pending_client | ✓ [UC-007](#em-uc-007--staff--client-approval) |
| 7 | System | After approve | Queue **ESP send** | schedule | Job queued | ✓ [UC-008](#em-uc-008--esp-send--webhook-engagement) |
| 8 | Strategist | Same | Monitor send progress | — | Stats tab | ✓ |

#### Tiêu chí nghiệm thu
- [ ] Test send before client approval
- [ ] Send blocked if domain not green

---

## EM-UC-007 — Staff + client approval

**Mục tiêu khách hàng:** *"Khách duyệt email campaign trước gửi — reject có comment."*

| # | Actor | Màn hình | Thao tác | Input | Phản hồi | Gate |
|---|-------|----------|----------|-------|----------|------|
| 1 | Compliance | `/email/campaigns/[id]/review` | Internal review pass | checklist | approved | ✓ |
| 2 | Strategist | Same | Submit → **pending_client** | — | Portal visible | ✓ |
| 3 | Client | portal `/email/approvals` | Preview subject + template | — | Full render | ✓ [PORTAL-UC-008](06-PORTAL-ACTIONS.md) |
| 4 | Client | Same | **Approve** / **Reject** + comment | comment if reject | Decision | ✓ |
| 5 | Strategist | ops campaign | Refresh → **approved** | — | Schedule enabled | ✓ |
| 6 | Strategist | Same | Set send schedule | datetime | Queued | ✓ |
| 7 | System | notification_inbox | Notify staff on decision | — | Inbox | ✓ |

#### Tiêu chí nghiệm thu
- [ ] Reject requires comment
- [ ] Send disabled until approved

---

## EM-UC-008 — ESP send & webhook engagement

**Mục tiêu khách hàng:** *"Email gửi qua ESP — stats delivered/open/click/bounce realtime."*

| # | Actor | Màn hình | Thao tác | Input | Phản hồi | Gate |
|---|-------|----------|----------|-------|----------|------|
| 1 | System | Send worker | Batch **ESP API** send | campaign id | Batches OK | ✓ |
| 2 | System | ESP webhook | delivered/open/click/bounce | events | Parsed | ✓ [PLAT-UC-006](07-PLAT-ACTIONS.md) |
| 3 | Strategist | `/email/campaigns/[id]` | **Stats** tab refresh | — | Metrics update | ✓ |
| 4 | System | Bounce handler | Hard bounce → suppression | email | Added | ✓ [UC-009](#em-uc-009--suppression--one-click-unsub) |
| 5 | Strategist | `/email/hub` | Verify campaign stats aggregate | — | Match ESP | ✓ |
| 6 | Client | portal `/email` | View campaign stats read-only | — | Scoped | ✓ [PORTAL-UC-005](06-PORTAL-ACTIONS.md) |

#### Tiêu chí nghiệm thu
- [ ] Webhook lag ≤ 5 min
- [ ] Bounce auto-suppresses

---

## EM-UC-009 — Suppression & one-click unsub

**Mục tiêu khách hàng:** *"Unsub one-click — không gửi lại subscriber đã opt-out."*

| # | Actor | Màn hình | Thao tác | Input | Phản hồi | Gate |
|---|-------|----------|----------|-------|----------|------|
| 1 | Subscriber | Email footer | Click **Unsubscribe** | — | Token URL | ✓ |
| 2 | Subscriber | `/email/public/unsubscribe/[token]` | Confirm unsub | — | Success page | ✓ |
| 3 | System | — | Add to **suppression** list | email | Global suppress | ✓ |
| 4 | Strategist | `/email/suppression` | Verify entry | search email | Row | ✓ |
| 5 | Strategist | `/email/segments` | Recompute segment | — | Excluded count | ✓ |
| 6 | System | Next campaign send | Skip suppressed | — | Not sent | ✓ |

#### Tiêu chí nghiệm thu
- [ ] Suppressed never receives broadcast
- [ ] Unsub logged with timestamp

---

## EM-UC-010 — Deliverability incident F3

**Mục tiêu khách hàng:** *"Incident deliverability P1 — pause sends, fix DNS, resume sau soak."*

| # | Actor | Màn hình | Thao tác | Input | Phản hồi | Gate |
|---|-------|----------|----------|-------|----------|------|
| 1 | System | `/email/hub` | Alert banner + Slack/Teams | bounce spike | P1 alert | ✓ |
| 2 | Strategist | Same | **Pause sends** client/domain | toggle | Sends stopped | ✓ |
| 3 | DevOps | Runbook F3 | DNS/ESP/IP investigation | — | Root cause | ✓ |
| 4 | Strategist | `/email/deliverability` | **Re-verify DNS** | — | Green | ✓ |
| 5 | Strategist | Test send | Small batch soak | 100 contacts | Bounce OK | ✓ |
| 6 | Strategist | Same | **Resume sends** | toggle | Normal | ✓ |
| 7 | AM | Client comms | Notify if client-facing delay | — | Log | ○ |
| 8 | PO | Incident log | Post-mortem | — | Documented | ○ |

#### Tiêu chí nghiệm thu
- [ ] P1 ack ≤ 30 min
- [ ] Soak pass before full resume

---

## EM-UC-011 — Journey automation activate

**Mục tiêu khách hàng:** *"Journey email tự động — welcome, nurture, re-engage."*

| # | Actor | Màn hình | Thao tác | Input | Phản hồi | Gate |
|---|-------|----------|----------|-------|----------|------|
| 1 | Strategist | Env check | `PTT_EMAIL_JOURNEYS=1` | — | Flag on | ⚠ prod gate |
| 2 | Strategist | `/email/journeys` | **+ Tạo journey** | name | Journey id | ✓ |
| 3 | Strategist | `/email/journeys/[id]` | Canvas: trigger→wait→send→branch | nodes | Saved | ✓ |
| 4 | Strategist | Same | **Test mode** enroll contact | test email | Steps fire | ✓ |
| 5 | Strategist | Same | Review test logs | — | Expected path | ✓ |
| 6 | Strategist | **Activate** | — | live | Enrolling | ✓ |
| 7 | Strategist | `/email/hub` | Monitor journey volume | — | Stats | ✓ |

#### Tiêu chí nghiệm thu
- [ ] Test mode before activate
- [ ] Journey respects suppression

---

## EM-UC-012 — Governance rule CRUD

**Mục tiêu khách hàng:** *"Compliance rules block/warn campaign vi phạm — audit log."*

| # | Actor | Màn hình | Thao tác | Input | Phản hồi | Gate |
|---|-------|----------|----------|-------|----------|------|
| 1 | Compliance | `/email/governance` E-13 | **+ Add rule** | rate, footer, banned words | Rule id | ✓ |
| 2 | Compliance | Row | **Edit** / **Delete** | — | Audit log | ✓ |
| 3 | System | Campaign submit | Evaluate block/warn | campaign | pass/fail | ✓ |
| 4 | Strategist | Campaign review | Fix if blocked | — | Re-submit | ✓ |
| 5 | Compliance | Tab audit | Review eval history | date | Immutable | ✓ |

#### Tiêu chí nghiệm thu
- [ ] Block prevents send queue
- [ ] Rule delete logged

---

## EM-UC-013 — Reports & Grafana BI

**Mục tiêu khách hàng:** *"AM xem email performance — export CSV; staff Grafana BI."*

| # | Actor | Màn hình | Thao tác | Input | Phản hồi | Gate |
|---|-------|----------|----------|-------|----------|------|
| 1 | AM | `/email/reports` E-12 | Filter client, period | T-30 | Table | ✓ |
| 2 | AM | Same | **Export CSV** | — | File | ✓ |
| 3 | AM | BI status card | `GET /reports/bi-status` | — | Status OK | ✓ |
| 4 | AM | Grafana section | Open **embed link** | — | Dashboard | ✓ staff |
| 5 | Client | portal | ⚠ No Grafana | PDF/portal stats | ⚠ GAP-P1-03 |

#### Tiêu chí nghiệm thu
- [ ] CSV matches hub stats
- [ ] Grafana staff-only auth

---

## EM-UC-014 — Public preference center

**Mục tiêu khách hàng:** *"Subscriber tự quản lý preferences — list, frequency, unsub."*

| # | Actor | Màn hình | Thao tác | Input | Phản hồi | Gate |
|---|-------|----------|----------|-------|----------|------|
| 1 | Subscriber | Email link | Open preference center token | token | Valid | ✓ |
| 2 | Subscriber | `/email/public/preferences/[token]` | View **lists** subscribed | — | Checkboxes | ✓ |
| 3 | Subscriber | Same | Toggle list preferences | selections | Saved | ✓ |
| 4 | Subscriber | Same | **Unsubscribe all** | confirm | Suppressed | ✓ [UC-009](#em-uc-009--suppression--one-click-unsub) |
| 5 | System | — | Update contact + consent log | — | Audit | ✓ |
| 6 | Strategist | `/email/contacts` | Verify preference change | email | Status | ✓ |

#### Tiêu chí nghiệm thu
- [ ] Token single-use or expiring
- [ ] Unsub all → global suppression

---

## Luồng Email end-to-end

| # | UC | Mục tiêu |
|---|-----|----------|
| 1 | EM-001 | Domain authenticated |
| 2 | EM-003/004 | Contacts + segment |
| 3 | EM-005 | Template preflight |
| 4 | EM-006/007 | Campaign approve |
| 5 | EM-008 | Send + stats |
| 6 | EM-009/014 | Unsub compliant |

**Liên kết SYS:** [SYS-UC-004](00-SYSTEM-ACTIONS.md) email approval inbox.
