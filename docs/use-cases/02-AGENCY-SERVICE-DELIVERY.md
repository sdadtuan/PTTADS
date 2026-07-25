# Use Case — Service Delivery & Agency

> **Prefix:** SVC · **Phiên bản:** 1.0 · **Ngày:** 2026-07-25  
> **Index:** [`README.md`](README.md) · **Spec:** [`SPEC_AGENCY_OPERATING_PLATFORM.md`](../SPEC_AGENCY_OPERATING_PLATFORM.md)

---

## SVC-UC-001 — Workflow lifecycle 7 stage

| Thuộc tính | Giá trị |
|------------|---------|
| **Actor chính** | AM |
| **Actor phụ** | Strategist, Finance |
| **Priority** | P0 |
| **Trigger** | Customer convert / HĐ active |

**Preconditions:** Customer record exists; service line selected from HĐ.

**Main flow:**

1. System khởi tạo lifecycle: **Prospect → Onboard → Deliver → Optimize → Handover → Retain → Offboarding**.
2. AM chuyển stage manual hoặc auto khi checklist pass.
3. Mỗi stage có gate items (SVC-UC-002…004).
4. Hub hiển thị stage badge per client.

**Extensions:**

- **E1 — Skip stage (pilot):** Admin override + audit reason.

**Postconditions:** Stage history immutable log.

**Business rules:** BR-SVC-01 — Không Deliver nếu onboard checklist incomplete.

**Traceability:** `/agency/clients/:id/lifecycle`, lifecycle API

---

## SVC-UC-002 — Onboard checklist client

| Thuộc tính | Giá trị |
|------------|---------|
| **Actor chính** | AM, Tracking |
| **Priority** | P0 |
| **Trigger** | Stage = Onboard |

**Main flow:**

1. Mở onboard checklist template theo service bundle.
2. Items: legal docs, billing, ad account access, pixel, GSC, email domain, portal users.
3. Mark done per item; attach evidence links.
4. **Complete onboard** khi 100% required items pass.

**Postconditions:** Gate cleared for Deliver ([SVC-UC-003](#svc-uc-003--deliver-stage--tmmt-chính-thức)).

**Traceability:** `/agency/onboarding`, checklist API; [SYS-UC-001](00-SYSTEM-OVERVIEW.md)

---

## SVC-UC-003 — Deliver stage — TMMT chính thức

| Thuộc tính | Giá trị |
|------------|---------|
| **Actor chính** | AM, Media Buyer |
| **Priority** | P0 |
| **Trigger** | Onboard complete; first campaign ready |

**Main flow:**

1. AM chuyển lifecycle → **Deliver**.
2. Publish **TMMT** (tài liệu mục tiêu marketing) trên client workspace.
3. Launch QA + first campaign go-live ([SYS-UC-003](00-SYSTEM-OVERVIEW.md)).
4. Hypercare clock start ([SYS-UC-012](00-SYSTEM-OVERVIEW.md)).

**Postconditions:** Client officially in delivery; TMMT versioned.

**Traceability:** TMMT doc store; agency client workspace

---

## SVC-UC-004 — Handover → Retain + finance gate

| Thuộc tính | Giá trị |
|------------|---------|
| **Actor chính** | AM, Finance |
| **Priority** | P0 |
| **Trigger** | Deliver period end; KPI stable |

**Main flow:**

1. AM compile handover pack (reports, SOP, contacts).
2. Finance verify billing current ([CRM-UC-011](01-CRM-CORE.md)).
3. Stage → **Handover** → client sign-off meeting.
4. Stage → **Retain** — steady-state SLA.

**Extensions:**

- **E1 — Outstanding invoice:** Block Handover until paid.

**Postconditions:** Retain playbook active; AM primary contact documented.

**Traceability:** handover forms; finance gate flag

---

## SVC-UC-005 — Launch QA checklist

| Thuộc tính | Giá trị |
|------------|---------|
| **Actor chính** | Media Buyer, Creative Lead |
| **Priority** | P0 |
| **Trigger** | Pre-launch campaign |

**Main flow:**

1. Mở `/crm/launch-qa` cho client/campaign.
2. Verify: UTM, pixel, landing page, creative spec, budget cap, audience.
3. Pass/Fail per item; block launch on critical fail (configurable).
4. Export QA sign-off PDF.

**Postconditions:** QA record linked to campaign write job.

**Traceability:** `/crm/launch-qa`, Launch QA API; [META-UC-007](03-META-ENTERPRISE.md)

---

## SVC-UC-006 — Creative Hub upload & review

| Thuộc tính | Giá trị |
|------------|---------|
| **Actor chính** | Creative Lead |
| **Actor phụ** | Client Approver |
| **Priority** | P0 |

**Main flow:**

1. Upload assets (image/video/copy) → Creative Hub.
2. Tag client, campaign, format (1:1, 9:16, …).
3. Internal review → status Approved internal.
4. Submit client approval ([PORTAL-UC-006](06-CLIENT-PORTAL.md)).
5. Approved assets available in Ads wizard.

**Postconditions:** Asset version control; expiry dates optional.

**Traceability:** Creative Hub routes; asset API

---

## SVC-UC-007 — Campaign Write queue approval

| Thuộc tính | Giá trị |
|------------|---------|
| **Actor chính** | Media Buyer, GDKD |
| **Priority** | P0 |
| **Trigger** | Submit campaign create/edit to Meta |

**Main flow:**

1. Buyer submit wizard → job vào **Campaign Write queue**.
2. Policy check: budget threshold → GDKD approve.
3. Temporal workflow ([PLAT-UC-008](07-PLATFORM-AUTH-WEBHOOKS.md)) orchestrate.
4. Approved → Meta API execute; Failed → retry/alert.

**Extensions:**

- **E1 — Meta API error:** Job status failed; buyer fix and resubmit.

**Postconditions:** Audit: submitter, approvers, API response ids.

**Traceability:** `/crm/campaign-writes`, write queue API

---

## SVC-UC-008 — Map channel account (Meta/Google)

| Thuộc tính | Giá trị |
|------------|---------|
| **Actor chính** | AM, Tracking |
| **Priority** | P0 |

**Main flow:**

1. Agency client settings → **Channel accounts**.
2. Link Meta ad account id / Google Ads customer id.
3. Verify OAuth/token valid.
4. Enable sync workers.

**Postconditions:** `client_id` ↔ `ad_account_id` mapping unique.

**Traceability:** [META-UC-001](03-META-ENTERPRISE.md), [SEO-UC-001](04-SEO-AEO.md)

---

## SVC-UC-009 — Agency ingest monitor

| Thuộc tính | Giá trị |
|------------|---------|
| **Actor chính** | Tracking, DevOps |
| **Priority** | P1 |

**Main flow:** Dashboard webhook volume, error rate, lag per channel; drill failed payloads; replay.

**Traceability:** ingest monitor UI; PLAT webhooks

---

## SVC-UC-010 — KPI definitions agency-wide

| Thuộc tính | Giá trị |
|------------|---------|
| **Actor chính** | Head, Admin |
| **Priority** | P1 |

**Main flow:** Define KPI formulas (CPL, ROAS, rank delta); assign to roles; hub widgets consume definitions.

**Traceability:** KPI config admin; SVC-UC-010 settings

---

## SVC-UC-011 — SOP & marketing plan

| Thuộc tính | Giá trị |
|------------|---------|
| **Actor chính** | Strategist, AM |
| **Priority** | P1 |

**Main flow:** Upload SOP per client; quarterly marketing plan template; link to lifecycle stage Optimize.

**Traceability:** client workspace documents

---

## SVC-UC-012 — Offboarding SOP

| Thuộc tính | Giá trị |
|------------|---------|
| **Actor chính** | AM, Admin |
| **Priority** | P1 |
| **Trigger** | HĐ terminate |

**Main flow:** Checklist revoke access, export data, final report, archive; stage Offboarding → Archived ([SYS-UC-006](00-SYSTEM-OVERVIEW.md)).

**Postconditions:** All tokens revoked; client read-only archive.

**Traceability:** offboarding checklist; SPEC Agency BC-02
