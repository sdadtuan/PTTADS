# Use Case — Email Marketing Enterprise Ops

> **Prefix:** EM · **Phiên bản:** 1.0 · **Ngày:** 2026-07-25  
> **Index:** [`README.md`](README.md) · **Spec:** [`SPEC_EMAIL_MARKETING_OPERATING_SYSTEM.md`](../SPEC_EMAIL_MARKETING_OPERATING_SYSTEM.md) · **Ops:** [`huong-dan-email-marketing-ops.md`](../huong-dan-email-marketing-ops.md)

---

## EM-UC-001 — Onboard email workspace & domain

| Thuộc tính | Giá trị |
|------------|---------|
| **Actor chính** | Email Strategist, AM |
| **Priority** | P0 |
| **Trigger** | HĐ Email Marketing |

**Preconditions:** `PTT_EMAIL_ENABLED=1`; customer active.

**Main flow:**

1. Tạo email workspace per client.
2. **Domain onboarding wizard** E-11: SPF, DKIM, DMARC, ESP domain verify.
3. Warm-up plan documented.
4. Hub `/email/hub` shows deliverability status.

**Extensions:**

- **E1 — DNS pending:** Yellow status until verify pass.

**Postconditions:** Sending domain authenticated; workspace ready.

**Traceability:** `/email/deliverability`, wizard E-11; [SYS-UC-001](00-SYSTEM-OVERVIEW.md)

---

## EM-UC-002 — Capture form → consent

| Thuộc tính | Giá trị |
|------------|---------|
| **Actor chính** | End Subscriber |
| **Actor phụ** | System |
| **Priority** | P0 |
| **Trigger** | Public form submit |

**Main flow:**

1. Embed form POST → capture API.
2. Record consent timestamp, source, IP (hashed).
3. Double opt-in email if policy enabled.
4. Contact created `subscribed` or `pending_confirm`.

**Postconditions:** GDPR/consent log immutable.

**Business rules:** BR-EM-01 — No marketing send without documented consent.

**Traceability:** `POST /email/contacts/capture`, form embed docs

---

## EM-UC-003 — Import contacts CSV

| Thuộc tính | Giá trị |
|------------|---------|
| **Actor chính** | Email Strategist |
| **Priority** | P0 |

**Main flow:**

1. E-04 import UI → upload CSV.
2. Map columns; validate email format.
3. Dedup + suppression check ([EM-UC-009](#em-uc-009--suppression--one-click-unsub)).
4. Preview → confirm batch import.

**Extensions:**

- **E1 — High bounce list:** Quarantine import; compliance review.

**Postconditions:** Import job log; tags applied.

**Traceability:** `/email/contacts`, import API

---

## EM-UC-004 — Segment compute (RFM/behavior)

| Thuộc tính | Giá trị |
|------------|---------|
| **Actor chính** | Email Strategist |
| **Priority** | P0 |

**Main flow:**

1. Segment Builder E-05: tabs Rules / Static / Lifecycle / RFM / Behavior.
2. Define criteria → **Compute** segment size.
3. Save segment version.
4. Use in campaign or journey targeting.

**Postconditions:** Segment member count cached; recompute on schedule.

**Traceability:** `/email/segments`, `POST /segments/:id/compute`

---

## EM-UC-005 — Template studio + preflight

| Thuộc tính | Giá trị |
|------------|---------|
| **Actor chính** | Email Strategist, Creative |
| **Priority** | P0 |

**Main flow:**

1. Template studio E-06: drag blocks, merge tags.
2. Preflight: broken links, alt text, spam score, dark mode preview.
3. Save template version.
4. Attach to campaign.

**Postconditions:** Preflight pass required before send (configurable strict).

**Traceability:** `/email/templates`, preflight API

---

## EM-UC-006 — Campaign broadcast F1

| Thuộc tính | Giá trị |
|------------|---------|
| **Actor chính** | Email Strategist |
| **Priority** | P0 |
| **Trigger** | Schedule or send now |

**Main flow:**

1. Create campaign E-07: name, segment, template, subject, from.
2. Test send to staff list.
3. Submit → staff approval ([EM-UC-007](#em-uc-007--staff--client-approval)).
4. On approve → queue ESP send ([EM-UC-008](#em-uc-008--esp-send--webhook-engagement)).

**Postconditions:** Campaign status scheduled/sending/sent.

**Traceability:** `/email/campaigns`, campaign API; F1 flow spec

---

## EM-UC-007 — Staff + client approval

| Thuộc tính | Giá trị |
|------------|---------|
| **Actor chính** | Compliance, Client Approver |
| **Priority** | P0 |

**Main flow:**

1. Strategist submit → internal compliance review (optional gate).
2. Client approver portal ([PORTAL-UC-008](06-CLIENT-PORTAL.md)).
3. Approve → unlock send; Reject → back to draft with comment.

**Postconditions:** Approval audit: who, when, version id.

**Traceability:** Temporal workflow; portal approvals

---

## EM-UC-008 — ESP send & webhook engagement

| Thuộc tính | Giá trị |
|------------|---------|
| **Actor chính** | System |
| **Priority** | P0 |

**Main flow:**

1. Worker batch send via ESP (SendGrid/SES/etc.).
2. [PLAT-UC-006](07-PLATFORM-AUTH-WEBHOOKS.md) ingest delivered/open/click/bounce.
3. Update campaign stats real-time.
4. Bounce → auto suppression.

**Postconditions:** Engagement metrics on E-12 reports.

**Traceability:** ESP webhook; `/email/campaigns/:id/stats`

---

## EM-UC-009 — Suppression & one-click unsub

| Thuộc tính | Giá trị |
|------------|---------|
| **Actor chính** | End Subscriber, System |
| **Priority** | P0 |

**Main flow:**

1. List-Unsubscribe header + preference link.
2. One-click POST → global suppression list.
3. Future sends exclude contact; audit reason.

**Postconditions:** CAN-SPAM / local law compliance.

**Business rules:** BR-EM-02 — Suppression global per client workspace.

**Traceability:** [EM-UC-014](#em-uc-014--public-preference-center); suppression API

---

## EM-UC-010 — Deliverability incident F3

| Thuộc tính | Giá trị |
|------------|---------|
| **Actor chính** | Email Strategist, DevOps |
| **Priority** | P0 |
| **Trigger** | Bounce rate spike, blocklist, domain fail |

**Main flow:**

1. Hub alert banner + Slack/Teams ([EM-UC-013](#em-uc-013--reports--grafana-bi) alerts).
2. Pause sends for domain/client.
3. DNS/ESP remediation checklist.
4. Resume after verify + soak.

**Postconditions:** Incident ticket closed; post-mortem.

**Traceability:** F3 incident runbook; hub alerts util

---

## EM-UC-011 — Journey automation activate

| Thuộc tính | Giá trị |
|------------|---------|
| **Actor chính** | Email Strategist |
| **Priority** | P1 |
| **Trigger** | `PTT_EMAIL_JOURNEYS=1` prod cutover |

**Main flow:** Build journey graph (trigger → wait → send → branch); test mode; activate; monitor enrollments.

**Postconditions:** Journey version live; enroll cap respected.

**Traceability:** `/email/journeys`, journey engine

---

## EM-UC-012 — Governance rule CRUD

| Thuộc tính | Giá trị |
|------------|---------|
| **Actor chính** | Compliance |
| **Priority** | P1 |

**Main flow:**

1. E-13 governance UI: create/edit/delete rules.
2. Rules: max send rate, required footer, banned keywords, quiet hours.
3. Evaluate on campaign submit; block/warn.
4. Audit log every change.

**Postconditions:** Rules enforced pre-send.

**Traceability:** `POST/PATCH/DELETE /governance/rules`, E-13 UI

---

## EM-UC-013 — Reports & Grafana BI

| Thuộc tính | Giá trị |
|------------|---------|
| **Actor chính** | AM, Strategist |
| **Priority** | P1 |

**Main flow:** E-12 reports: campaign performance, deliverability, segment growth; BI status card; link Grafana if configured.

**Traceability:** `/email/reports`, `GET /reports/bi-status`

---

## EM-UC-014 — Public preference center

| Thuộc tính | Giá trị |
|------------|---------|
| **Actor chính** | End Subscriber |
| **Priority** | P0 |

**Main flow:** Public URL tokenized → view subscriptions → update preferences / unsubscribe all → confirmation page.

**Postconditions:** Consent preferences updated; sync suppression.

**Traceability:** public preference routes; EM spec §preference
