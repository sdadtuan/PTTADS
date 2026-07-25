# Use Case — System Overview (Cross-Module)

> **Prefix:** SYS · **Phiên bản:** 1.0 · **Ngày:** 2026-07-25  
> **Index:** [`README.md`](README.md)

---

## SYS-UC-001 — Onboard client mới end-to-end

| Thuộc tính | Giá trị |
|------------|---------|
| **Actor chính** | Account Manager (AM) |
| **Actor phụ** | Admin, Tracking/Tech, Email/SEO Strategist |
| **Priority** | P0 |
| **Trigger** | Hợp đồng mới ký; chuyển stage lifecycle → Onboard |

**Preconditions:** Lead đã convert hoặc customer CRM tồn tại; staff đăng nhập ops-web với cap CRM/agency.

**Main flow:**

1. AM mở `/crm/hub` hoặc `/crm/customers` — xác nhận customer master.
2. AM tạo / liên kết **service lifecycle** → stage **Onboard** ([SVC-UC-001](02-AGENCY-SERVICE-DELIVERY.md)).
3. AM hoàn thành **onboarding checklist** ([SVC-UC-002](02-AGENCY-SERVICE-DELIVERY.md)).
4. Theo dịch vụ trong HĐ, AM thực hiện onboard module:
   - Meta: map ad account ([META-UC-001](03-META-ENTERPRISE.md))
   - SEO: workspace + OAuth GSC/GA4 ([SEO-UC-001](04-SEO-AEO.md))
   - Email: workspace + domain wizard ([EM-UC-001](05-EMAIL-MARKETING.md))
5. Tracking/Tech verify webhook + CAPI ([META-UC-004](03-META-ENTERPRISE.md), [META-UC-005](03-META-ENTERPRISE.md)).
6. AM tạo **portal users** viewer/approver ([PORTAL-UC-001](06-CLIENT-PORTAL.md)).
7. Lifecycle chuyển **Deliver** khi checklist pass.

**Extensions:**

- **E1 — Chỉ CRM, chưa ads:** Bỏ bước 4 Meta; ghi defer trong checklist.
- **E2 — Client từ chối portal:** Portal optional; AM gửi báo cáo manual.

**Postconditions:** Client `active`; module flags bật theo HĐ; portal map (nếu có).

**Business rules:** BR-SYS-01 — Không map ad account trước khi billing/onboarding legal OK.

**Traceability:** `/crm/service-delivery`, `/agency/clients/:id`, handover §2.2

---

## SYS-UC-002 — Closed-loop Spend → Lead → Revenue

| Thuộc tính | Giá trị |
|------------|---------|
| **Actor chính** | Media Buyer, AM |
| **Actor phụ** | System (sync, CAPI), Sales |
| **Priority** | P0 |
| **Trigger** | Chiến dịch Meta đang chạy; có lead CRM |

**Preconditions:** Ad account mapped; insights sync T-1 OK; CRM lead ingest hoạt động.

**Main flow:**

1. Worker sync **Meta spend** T-1 → hub ([META-UC-003](03-META-ENTERPRISE.md)).
2. Webhook lead form → CRM lead mới ([META-UC-004](03-META-ENTERPRISE.md), [CRM-UC-001](01-CRM-CORE.md)).
3. CSKH/Sales cập nhật pipeline → Won deal ([CRM-UC-009](01-CRM-CORE.md)).
4. CAPI gửi conversion events ([META-UC-005](03-META-ENTERPRISE.md)).
5. Hub tính **CPL, ROAS** (revenue từ CRM nếu có).
6. AM review trên `/meta/facebook-ads` + báo cáo client ([SYS-UC-005](00-SYSTEM-OVERVIEW.md)).

**Extensions:**

- **E1 — Unmapped spend:** CPL cảnh báo vàng; AM map campaign ([META-UC-002](03-META-ENTERPRISE.md)).
- **E2 — Không có revenue data:** ROAS ẩn; chỉ CPL.

**Postconditions:** KPI closed-loop visible trên hub và portal.

**Business rules:** BR-SYS-02 — Lead CRM dedup trước khi tính CPL.

**Traceability:** SPEC Agency §1.1 closed-loop; META spec §21 attribution

---

## SYS-UC-003 — Launch campaign đa kênh có governance

| Thuộc tính | Giá trị |
|------------|---------|
| **Actor chính** | Media Buyer, Creative Lead |
| **Actor phụ** | Client Approver, Compliance |
| **Priority** | P0 |
| **Trigger** | Yêu cầu go-live campaign mới |

**Preconditions:** Client onboard; creative assets sẵn sàng; Launch QA policy bật.

**Main flow:**

1. Creative upload → Creative Hub ([SVC-UC-006](02-AGENCY-SERVICE-DELIVERY.md)).
2. Launch QA checklist pass ([SVC-UC-005](02-AGENCY-SERVICE-DELIVERY.md)).
3. Buyer mở **Ads Ops wizard** ([META-UC-007](03-META-ENTERPRISE.md)).
4. Submit → **Campaign Write queue** / Temporal ([SVC-UC-007](02-AGENCY-SERVICE-DELIVERY.md)).
5. Client approver duyệt trên portal ([PORTAL-UC-006](06-CLIENT-PORTAL.md)) nếu policy yêu cầu.
6. Governance pass → launch API Meta.
7. Monitor hub + alerts ([META-UC-009](03-META-ENTERPRISE.md)).

**Extensions:**

- **E1 — Reject creative:** Quay bước 1 với comment.
- **E2 — Budget over threshold:** Thêm approver nội bộ GDKD.

**Postconditions:** Campaign live trên Meta; audit log đầy đủ.

**Business rules:** BR-SYS-03 — Không launch nếu Launch QA fail (warn-only theo config PO).

**Traceability:** `/crm/launch-qa`, `/meta/ads-ops`, `/crm/campaign-writes`

---

## SYS-UC-004 — Client approval cross-module

| Thuộc tính | Giá trị |
|------------|---------|
| **Actor chính** | Client Approver |
| **Actor phụ** | AM, Strategist (staff submitter) |
| **Priority** | P0 |
| **Trigger** | Staff submit item cần client sign-off |

**Preconditions:** Portal user approver active; item ở trạng thái `pending_client_approval`.

**Main flow:**

1. Staff submit (Meta creative / SEO content / Email campaign).
2. System notify portal ([PORTAL-UC-006…008](06-CLIENT-PORTAL.md)).
3. Approver login → inbox → preview.
4. **Approve** → status cập nhật → staff nhận notification.
5. Staff tiếp tục launch/publish/send theo module.

**Extensions:**

- **E1 — Reject:** [PORTAL-UC-009](06-CLIENT-PORTAL.md) — comment bắt buộc.
- **E2 — SLA quá 24h:** AM escalate (manual).

**Postconditions:** Audit ghi approver, timestamp, decision.

**Business rules:** BR-SYS-04 — Approver JWT scoped một `client_id`.

**Traceability:** Temporal workflows; portal `/approvals`

---

## SYS-UC-005 — Báo cáo định kỳ cho khách hàng

| Thuộc tính | Giá trị |
|------------|---------|
| **Actor chính** | AM (chuẩn bị), Client Viewer (nhận) |
| **Actor phụ** | System (scheduler, PDF worker) |
| **Priority** | P0 |
| **Trigger** | Lịch weekly/monthly hoặc on-demand |

**Preconditions:** Module sync OK; portal hoặc email recipient configured.

**Main flow:**

1. Scheduler trigger (Meta RPT-M3, SEO PDF, Email schedule).
2. Worker aggregate KPI T-1 / period.
3. Generate PDF hoặc enable portal view.
4. Deliver email webhook hoặc portal notification.
5. AM confirm client đã nhận (hypercare).

**Extensions:**

- **E1 — Sync fail:** Báo cáo partial + disclaimer yellow banner.

**Postconditions:** Artifact stored; delivery log.

**Business rules:** BR-SYS-05 — Disclaimer attribution trên mọi báo cáo client-facing.

**Traceability:** META spec §23; SEO reports; EM E-12 schedules

---

## SYS-UC-006 — Offboard client & thu hồi quyền

| Thuộc tính | Giá trị |
|------------|---------|
| **Actor chính** | AM, Admin |
| **Actor phụ** | Tracking, DevOps |
| **Priority** | P1 |
| **Trigger** | HĐ chấm dứt; lifecycle → Offboarding |

**Main flow:**

1. Lifecycle stage **Offboarding** ([SVC-UC-012](02-AGENCY-SERVICE-DELIVERY.md)).
2. Revoke Meta token / pause send email / archive SEO sync.
3. Disable portal users.
4. Export data theo HĐ (nếu yêu cầu).
5. Archive client → **Archived**.

**Postconditions:** Không còn active spend/send; tokens revoked.

**Traceability:** SPEC Agency BC-02 offboarding SOP

---

## SYS-UC-007 — Executive drill-down ≤3 clicks

| Thuộc tính | Giá trị |
|------------|---------|
| **Actor chính** | Head / GDKD, AM |
| **Priority** | P1 |
| **Trigger** | Review sáng hub executive |

**Main flow:**

1. Mở hub module (SEO `/seo/hub`, Email `/email/hub`, Meta `/meta/facebook-ads`).
2. Click client health row (click 1).
3. Client workspace (click 2).
4. Module detail — contacts/issues/campaign (click 3).

**Postconditions:** PO/Head trả lời được "client X health?" trong ≤3 click.

**Traceability:** SEO UI spec §4.5 F5; email-handoff E2E

---

## SYS-UC-008 — Incident P1 webhook down

| Thuộc tính | Giá trị |
|------------|---------|
| **Actor chính** | DevOps, Tracking |
| **Actor phụ** | AM (comms client) |
| **Priority** | P0 |
| **Trigger** | Webhook error rate >1% hoặc zero ingest >15min |

**Main flow:**

1. Alert RPT-M7 / monitoring red.
2. DevOps verify nginx, Nest, signature, Meta app config.
3. Fix hoặc rollback env ([handover §7](../handover/04-KIEN-TRUC-TRIEN-KHAI-BAN-GIAO.md)).
4. Replay failed events nếu có dead letter.
5. Post-mortem + client comms nếu mất lead.

**Postconditions:** Ingest restored; incident log closed.

**Traceability:** META SLA §24; runbook VPS ops

---

## SYS-UC-009 — Staged prod cutover module flag

| Thuộc tính | Giá trị |
|------------|---------|
| **Actor chính** | DevOps, Tech Lead |
| **Priority** | P1 |
| **Trigger** | Gate A / module pilot ready |

**Main flow:**

1. B1: `PTT_EMAIL_ENABLED=1`, send off.
2. Soak ≥3–7 ngày; gate scripts PASS.
3. B2/B3/B4: bật send, portal, journeys theo checklist.
4. Rebuild ops-web `NEXT_PUBLIC_*`.
5. Smoke UAT + sign-off.

**Traceability:** email prod checklist; SEO Gate A; handover §4.3

---

## SYS-UC-010 — Audit trail tra cứu cross-module

| Thuộc tính | Giá trị |
|------------|---------|
| **Actor chính** | Compliance, Admin |
| **Priority** | P1 |

**Main flow:** Tra cứu governance audit (Email E-13, SEO S-14, CRM workflow history, portal approvals) theo `client_id`, date range, actor.

**Traceability:** EM governance audit; SEO governance evaluations

---

## SYS-UC-011 — Multi-client isolation verify

| Thuộc tính | Giá trị |
|------------|---------|
| **Actor chính** | QA, Security |
| **Priority** | P0 |

**Main flow:** User client A login portal → API không trả data client B; staff filter bắt buộc `client_id` trên Meta/SEO/Email APIs.

**Postconditions:** Pen test checklist pass.

**Traceability:** SPEC Agency §10; ADR tenant isolation

---

## SYS-UC-012 — Hypercare post go-live

| Thuộc tính | Giá trị |
|------------|---------|
| **Actor chính** | AM, Tech Lead |
| **Priority** | P1 |
| **Trigger** | Sign-off nghiệm thu ([handover §6](../handover/06-NGHIEM-THU-VA-BAO-CAO.md)) |

**Main flow:** 2–4 tuần daily standup; P1 ack 30min; soak scripts; defect triage; handoff steady-state SLA.

**Postconditions:** Hypercare exit report; PO accept steady state.
