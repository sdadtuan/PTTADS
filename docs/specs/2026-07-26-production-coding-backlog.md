# Production Coding Backlog — PTTADS

**Date:** 2026-07-26  
**Status:** Backlog — ready for sprint planning  
**Owner:** Engineering / PO  
**Depends on:**  
- [`ACTION-GAP-ANALYSIS.md`](../use-cases/ACTION-GAP-ANALYSIS.md)  
- [`actions/README.md`](../use-cases/actions/README.md) (Phase A–C complete ~105/122 UC)  
- [`handover/06-NGHIEM-THU-VA-BAO-CAO.md`](../handover/06-NGHIEM-THU-VA-BAO-CAO.md)  
**Related specs:** [`2026-07-23-wave-b5-s4-finance-handoff-design.md`](2026-07-23-wave-b5-s4-finance-handoff-design.md) · [`2026-07-25-zalo-ads-implementation-backlog.md`](2026-07-25-zalo-ads-implementation-backlog.md)

---

## 1. Mục tiêu & phạm vi

| Mục tiêu | Mô tả |
|----------|--------|
| **Production** | Khách hàng và AM **tự phục vụ end-to-end** theo action docs — không workaround thủ công cho luồng P0 |
| **Nghiệm thu** | Pass checklist [`handover/06`](../handover/06-NGHIEM-THU-VA-BAO-CAO.md) §2–3 + gate scripts |
| **Pattern** | Reuse SEO/Email `report_schedule`, Meta `campaign-writes`, staff `notification_inbox` |

**In scope:** Coding BE/FE/worker/DDL/E2E cho gap P0–P1 từ action analysis.  
**Out of scope (Phase này):** Phase D doc-only (SYS 006–012 expand); P2 white-label full; ClickHouse portal embed (có thể defer).

---

## 2. Trạng thái maturity (as-is vs action docs)

| Thành phần | Doc UC | Code | Gap ID |
|------------|--------|------|--------|
| Use case action tables | ~105/122 ✅ | — | Phase A–C done |
| Meta hub + launch + CAPI | META-001–008 | ✅ | — |
| Zalo Z1–Z3 hub/poll/alerts/PDF | ZALO-001–021 | ✅ (pilot/stub flags) | Prod cutover |
| CRM leads + lifecycle + finance panel | CRM/SVC | ✅ partial | GAP-P1-01 strict |
| SEO/Email report **schedule** | SEO-013, EM-013 | ✅ worker | — |
| Meta/Zalo report **schedule** | SYS-005, META-013, ZALO-016 | ❌ | **PROD-P0-RPT** |
| Portal approval inbox | PORTAL-006/008 | ✅ | — |
| Portal **client notification** center | ZALO-020, SYS-004 | ✅ Prod-S1 | — |
| Portal email notify (creative/reset) | PORTAL-001 | ✅ webhook wired | — |
| CSKH board `/crm/cskh-board` | CRM-UC-008 | ❌ route missing | **PROD-P0-CSKH** |
| Onboard orchestrator deep-links | SYS-001, SVC-002 | ✅ | **PROD-P1-WIZ** UX |
| Finance gate warn+confirm | SVC-004 | ✅ B5-S4 | **PROD-P1-FIN** strict mode |
| Zalo campaign API write | ZALO-009/010 | ❌ manual | **GAP-Z4-01** |
| Email journeys prod | EM-011 | ⚠ flag off | **PROD-P1-JRN** |
| Grafana portal embed | EM-013, SEO-014 | ❌ | **GAP-P1-03** |
| E2E prod smoke all modules | PLAT-010 | ⚠ partial | **PROD-H-E2E** |

**Ước lượng code prod-ready:** ~**75–80%** (doc ~86%, gap chủ yếu notify + schedule + polish).

---

## 3. Ma trận Gap → UC → Backlog prefix

| Gap / Theme | UC chính | Priority | Prefix |
|-------------|----------|----------|--------|
| Portal client notifications | GAP-P1-02, ZALO-020, PORTAL-006/008, SYS-004 | P0 | **PROD-P0-NOTIFY** |
| Scheduled reports Meta/Zalo | SYS-005, META-013, ZALO-016 | P0 | **PROD-P0-RPT** |
| Zalo production cutover | ZALO-001, 003, 012, 017 | P0 | **PROD-P0-ZALO** |
| CSKH SLA board | CRM-UC-008, CRM-UC-001 | P0 | **PROD-P0-CSKH** |
| Onboard wizard UX | SYS-001, SVC-002, ZALO-021 | P1 | **PROD-P1-WIZ** |
| Finance gate strict | SVC-004, GAP-P1-01 | P1 | **PROD-P1-FIN** |
| Zalo campaign write API | GAP-Z4-01, ZALO-009/010 | P1 | **PROD-Z4** |
| Email journeys prod | EM-011 | P1 | **PROD-P1-JRN** |
| Portal Grafana BI | GAP-P1-03 | P2 | **PROD-P2-BI** |
| Production hardening | SYS-008/009/011, PLAT-010 | P0 | **PROD-H-*** |

---

## 4. Wave PROD-P0 — Blockers Production

**PO gate:** Không sign-off nghiệm thu A4 cho luồng khách tự phục vụ cho đến khi PROD-P0-* PASS trên staging.

### 4.1 PROD-P0-NOTIFY — Portal notification + email prod

**Mục tiêu:** Client approver thấy pending approval + milestone; staff email không stub.

| ID | Task | Layer | Files (new/modify) | Effort | UC |
|----|------|-------|-------------------|--------|-----|
| P0-N-D1 | DDL `portal_notification` (hoặc view scoped) | DDL | `docs/specs/ddl-portal-notifications.sql` | S | GAP-P1-02 |
| P0-N-B1 | `PortalNotificationService` CRUD + list | BE | `portal/portal-notification.*` | M | — |
| P0-N-B2 | Routes `GET/PATCH /portal/notifications` | BE | `portal.controller.ts` | S | — |
| P0-N-B3 | Emit on: creative pending, email pending, milestone | BE | `creatives.service.ts`, `portal-email`, `campaign-milestone-notify` | M | ZALO-020 |
| P0-N-B4 | Wire `PTT_PORTAL_NOTIFY_WEBHOOK` — remove stub path | BE | `portal-creative-notify.service.ts`, `portal-password-reset-notify` | S | PORTAL-001 |
| P0-N-U1 | Portal `/notifications` page + mark read | FE | `portal-web/src/app/notifications/` | M | — |
| P0-N-U2 | Dashboard widget: pending count all modules | FE | `portal-web/dashboard`, `PortalNav` badges | M | PORTAL-002 |
| P0-N-U3 | Email + SEO approval badge on nav | FE | extend `PortalNav` | S | PORTAL-007/008 |
| P0-N-Q1 | E2E: submit creative → client sees notification | QA | `portal-web/e2e/notifications.spec.ts` | M | — |

**API checklist:**

- [x] `GET /portal/notifications?unread_only=1`
- [x] `PATCH /portal/notifications/:id/read`
- [x] `PATCH /portal/notifications/read-all`
- [x] Webhook env documented in handover

**Env:**

```bash
PTT_PORTAL_NOTIFY_WEBHOOK=https://...   # email delivery for staff + optional client
PTT_PORTAL_CLIENT_NOTIFY=1            # enable client inbox
```

---

### 4.2 PROD-P0-RPT — Scheduled reports Meta + Zalo

**Mục tiêu:** SYS-UC-005 — weekly/monthly PDF/CSV tự gửi (parity SEO/Email).

| ID | Task | Layer | Files | Effort | UC |
|----|------|-------|-------|--------|-----|
| P0-R-D1 | DDL `meta_report_schedules`, `zalo_report_schedules` | DDL | new SQL spec | S | SYS-005 |
| P0-R-B1 | Nest CRUD schedules (staff) | BE | `meta-reports/`, `zalo-ads/` modules | M | META-013, ZALO-016 |
| P0-R-W1 | Worker `meta_report_schedules` job | Worker | `ptt_jobs/handlers/meta_report_schedule.py` | M | — |
| P0-R-W2 | Worker `zalo_report_schedules` job (reuse PDF export) | Worker | `ptt_zalo/report_export.py` | M | ZALO-016 |
| P0-R-W3 | Pre-send gate: unmapped=0, sync green T-1 | Worker | shared util | S | META-002 |
| P0-R-U1 | Ops UI schedule config Meta hub | FE | `/meta/facebook-ads` settings tab | M | — |
| P0-R-U2 | Ops UI schedule config Zalo hub | FE | `/zalo/zalo-ads` settings tab | S | — |
| P0-R-U3 | Portal self-serve download link in email | FE/BE | signed URL pattern | S | PORTAL-010 |

**Template:** `ptt_email/report_schedule.py`, `ptt_seo/report_schedule.py`.

**Worker registration:** `ptt_worker/__main__.py` — add job types + cron enqueue.

---

### 4.3 PROD-P0-ZALO — Production cutover (no stub)

**Mục tiêu:** Zalo chạy prod thật — OAuth, insights, poll, alerts.

| ID | Task | Layer | Effort | UC |
|----|------|-------|--------|-----|
| P0-Z-C1 | Prod env checklist + runbook update | Ops | S | ZALO-001 |
| P0-Z-C2 | `PTT_ZALO_ADS_STUB=0` staging soak 7d | Ops | M | — |
| P0-Z-B1 | Token refresh job / expiry alert on hub | BE | M | ZALO-001 |
| P0-Z-B2 | Remove pilot banner for non-pilot clients (verify) | FE | S | — |
| P0-Z-W1 | Verify `zalo_insights_sync` prod API (non-stub) | Worker | M | ZALO-003 |
| P0-Z-W2 | Monitor `zalo_form_lead_poll` SLA alert | Worker | S | ZALO-012 |
| P0-Z-Q1 | `./scripts/staging_zalo_wave_z2_gate.sh` on prod-like | QA | S | PLAT-010 |
| P0-Z-Q2 | E2E zalo: connect → sync → lead → Won → CPA | QA | L | ZALO-014/015 |

**Env (prod):**

```bash
PTT_ZALO_APP_ID=
PTT_ZALO_APP_SECRET=
PTT_ZALO_OAUTH_REDIRECT_URI=https://ops.pttads.vn/zalo/oauth/callback
CRM_ZALO_WEBHOOK_SECRET=
PTT_ZALO_INSIGHTS_SYNC=1
PTT_ZALO_FORM_POLL=1
PTT_ZALO_ALERTS_ENABLED=1
PTT_ZALO_ADS_STUB=0
PTT_ZALO_ADS_PILOT=0          # or scoped PTT_ZALO_ADS_PILOT_CLIENTS
PTT_ZALO_SLACK_WEBHOOK=        # optional
```

---

### 4.4 PROD-P0-CSKH — CSKH board + SLA

**Mục tiêu:** CRM-UC-008 — board SLA breach, bulk reassign, export standup.

| ID | Task | Layer | Files | Effort |
|----|------|-------|-------|--------|
| P0-C-B1 | API `GET /crm/cskh-board` — SLA query | BE | `leads/` or new module | M |
| P0-C-B2 | API bulk reassign + reschedule | BE | extend leads-write | S |
| P0-C-U1 | Page `/crm/cskh-board` | FE | `ops-web/src/app/crm/cskh-board/` | M |
| P0-C-U2 | Link from OpsNav CRM section | FE | `OpsNav.tsx` | S |
| P0-C-Q1 | Unit test SLA 15m rule | QA | spec | S |

**SLA rule (from actions):** Lead **Mới** → first call logged ≤ **15 phút** ([CRM-UC-001](../use-cases/actions/01-CRM-ACTIONS.md)).

---

### 4.5 PROD-H — Production hardening (song song P0)

| ID | Task | Layer | Effort | Ref |
|----|------|-------|--------|-----|
| PROD-H-E2E | Playwright suite: onboard, meta launch, portal approve, email send | QA | L | handover F1–F7 |
| PROD-H-GATE | CI run gate scripts on staging | DevOps | M | PLAT-010 |
| PROD-H-MON | Webhook error rate alert >1% | DevOps | M | SYS-008 |
| PROD-H-PEN | Automate multi-tenant isolation tests | QA | M | SYS-011 |
| PROD-H-FLAG | Staged module cutover runbook execute | DevOps | M | SYS-009 |
| PROD-H-STUB | Audit + disable dev stub caps in prod | BE | S | PLAT-001 |

---

## 5. Wave PROD-P1 — Enterprise depth

### 5.1 PROD-P1-WIZ — Onboard wizard (giảm deep-link)

| ID | Task | Layer | Effort | UC |
|----|------|-------|--------|-----|
| P1-W-U1 | Inline stepper component on onboard tab | FE | L | SYS-001 |
| P1-W-U2 | Embed channel connect / portal user / launch QA in wizard | FE | L | SVC-002 |
| P1-W-B1 | API enforce **Deliver** block if checklist <100% | BE | M | BR-SVC-01 |
| P1-W-B2 | Optional auto-advance lifecycle on orchestrator 100% | BE | S | SVC-001 |

---

### 5.2 PROD-P1-FIN — Finance gate strict mode

**As-is:** B5-S4 warn + `finance_confirm` ✅ ([`2026-07-23-wave-b5-s4-finance-handoff-design.md`](2026-07-23-wave-b5-s4-finance-handoff-design.md)).

| ID | Task | Layer | Effort |
|----|------|-------|--------|
| P1-F-B1 | Env `PTT_FINANCE_GATE_STRICT=1` — block without Finance role confirm | BE | M |
| P1-F-B2 | Real-time AR from `/crm/financials` in `advance-info.payment_gate` | BE | M |
| P1-F-B3 | Audit log table `lifecycle_finance_confirm` | BE/DDL | S |
| P1-F-U1 | Finance role-only override UI | FE | S |

---

### 5.3 PROD-P1-JRN — Email journeys production

| ID | Task | Layer | Effort |
|----|------|-------|--------|
| P1-J-O1 | Enable `PTT_EMAIL_JOURNEYS_ENABLED=1` post Gate A soak | Ops | S |
| P1-J-W1 | Journey enrollment scale test + DLQ | Worker | M |
| P1-J-Q1 | `./scripts/email_p1_gate.sh` PASS evidence | QA | S |

---

### 5.4 PROD-P1-MAP — Campaign map bulk (GAP-P1-04)

| ID | Task | Layer | Effort |
|----|------|-------|--------|
| P1-M-B1 | `POST /hub-campaign-maps/bulk` CSV import | BE | M |
| P1-M-B2 | Optional suggest endpoint accept batch | BE | M |
| P1-M-U1 | Bulk map UI on `/meta/facebook-ads` | FE | M |

---

### 5.5 PROD-P1-EMB — Double opt-in embed (GAP-P1-05)

| ID | Task | Layer | Effort |
|----|------|-------|--------|
| P1-E-U1 | Ops snippet generator for capture form | FE | M |
| P1-E-B1 | Public script tag + docs | BE/Docs | S |

---

## 6. Wave PROD-Z4 — Zalo campaign API write (GAP-Z4-01)

**Depends on:** Zalo Business API write permissions from client/OA.

| ID | Task | Layer | Template | Effort | UC |
|----|------|-------|----------|--------|-----|
| Z4-B1 | `ZaloCampaignWriteAdapter` | BE | Meta write adapter | L | ZALO-009 |
| Z4-B2 | Extend `campaign-writes` queue `channel=zalo` | BE | existing queue | M | SVC-007 |
| Z4-B3 | Auto hub map on create success | BE | ZALO-002 | S | — |
| Z4-B4 | Pause/update/stop API | BE | ZALO-010 | M | — |
| Z4-W1 | Worker execute Zalo write jobs | Worker | campaign-writes worker | L | — |
| Z4-U1 | Launch path in ops (optional wizard) | FE | meta ads-ops pattern | M | — |
| Z4-Q1 | Integration test sandbox Zalo | QA | L | — |

**Until Z4 ships:** Manual go-live per [`08-ZALO-ACTIONS.md`](../use-cases/actions/08-ZALO-ACTIONS.md) nhánh E1/M1.

---

## 7. Wave PROD-P2 — Optional

| ID | Task | Gap | Effort |
|----|------|-----|--------|
| P2-BI-1 | Portal Grafana signed embed | GAP-P1-03 | L |
| P2-BI-2 | ClickHouse export self-serve | GAP-P2-01 | L |
| P2-META-1 | Horizon migration client UAT UI | GAP-P2-02 | M |
| P2-PORT-1 | Portal white-label full | GAP-P2-03 | L |
| P2-ROAS-1 | Meta ROAS non-stub from CRM Won | roas_stub | M |

---

## 8. Dependency graph (critical path)

```
PROD-P0-NOTIFY (portal inbox)
  → PROD-H-E2E (portal approve flow)

PROD-P0-RPT (DDL)
  → meta/zalo report workers
    → email webhook delivery
      → SYS-005 sign-off

PROD-P0-ZALO (env + OAuth)
  → insights/poll prod
    → PROD-P0-RPT zalo PDF job
    → PROD-H-GATE zalo gate PASS

PROD-P0-CSKH (parallel)

PROD-P1-FIN (after P0 stable)

PROD-Z4 (independent — Zalo API permission gate)
```

---

## 9. Sprint proposal

| Sprint | Focus | Task IDs | Est. dev-days |
|--------|-------|----------|---------------|
| **Prod-S1** | Portal notify + email webhook | P0-N-* | ~8 |
| **Prod-S2** | Meta/Zalo report schedules | P0-R-* | ~7 |
| **Prod-S3** | Zalo prod cutover + gate | P0-Z-* | ~6 |
| **Prod-S4** | CSKH board + E2E hardening | P0-C-*, PROD-H-E2E | ~8 |
| **Prod-S5** | Onboard wizard + finance strict | P1-W-*, P1-F-* | ~9 |
| **Prod-S6** | Journeys + map bulk + embed | P1-J-*, P1-M-*, P1-E-* | ~7 |
| **Z4** | Zalo campaign write | Z4-* | ~12 |

**Production sign-off target:** Prod-S1–S4 + PROD-H-GATE/PEN (~**29 dev-days**, 2 FTE ≈ 3 tuần).

---

## 10. Acceptance criteria (Production)

| # | Criterion | Verify |
|---|-----------|--------|
| A1 | Client portal: notification within 1 min of creative pending | E2E P0-N-Q1 |
| A2 | Weekly Meta PDF auto-delivered for pilot client | P0-R-W1 job log |
| A3 | Zalo hub sync green T-1, no stub banner prod | P0-Z-Q1 gate |
| A4 | CSKH board shows SLA breach + bulk reassign | Manual UAT CRM-UC-008 |
| A5 | Handover blocked or finance_confirm when AR overdue | P1-F or B5-S4 |
| A6 | `./scripts/email_p1_gate.sh` + zalo gate PASS staging | PROD-H-GATE |
| A7 | handover §2 F1–F7 checklist signed | PO |

---

## 11. Risks & mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Zalo API write permission denied | Z4 blocked | Manual launch + map (documented) |
| Portal email webhook vendor delay | Notify email fails | In-app inbox primary; retry queue |
| Report job spam client | Reputation | Unmapped gate + opt-in schedule per client |
| Finance strict blocks AM workflow | Ops friction | Config flag warn vs strict |
| Scope creep P2 BI | Delay prod | Defer P2 after A7 sign-off |

---

## 12. Liên kết tài liệu hành động (traceability)

| Module | Action file | Production waves |
|--------|-------------|------------------|
| System | [`00-SYSTEM-ACTIONS.md`](../use-cases/actions/00-SYSTEM-ACTIONS.md) | P0-RPT, P1-WIZ, PROD-H |
| CRM | [`01-CRM-ACTIONS.md`](../use-cases/actions/01-CRM-ACTIONS.md) | P0-CSKH |
| SVC | [`02-SVC-ACTIONS.md`](../use-cases/actions/02-SVC-ACTIONS.md) | P1-FIN, P1-WIZ |
| Meta | [`03-META-ACTIONS.md`](../use-cases/actions/03-META-ACTIONS.md) | P0-RPT, P1-MAP |
| Portal | [`06-PORTAL-ACTIONS.md`](../use-cases/actions/06-PORTAL-ACTIONS.md) | P0-NOTIFY |
| Zalo | [`08-ZALO-ACTIONS.md`](../use-cases/actions/08-ZALO-ACTIONS.md) | P0-ZALO, P0-RPT, Z4 |

**Cập nhật sau mỗi sprint:** [`ACTION-GAP-ANALYSIS.md`](../use-cases/ACTION-GAP-ANALYSIS.md) — đánh dấu gap ✅ khi task Done.

---

## 13. Changelog

| Date | Version | Change |
|------|---------|--------|
| 2026-07-26 | 1.0 | Initial backlog from Phase A–C action analysis |
