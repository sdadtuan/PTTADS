# Zalo Ads — Implementation Backlog

**Date:** 2026-07-25  
**Status:** Backlog — ready for sprint planning  
**Owner:** Engineering / PO  
**Depends on:** [`SPEC_ZALO_ADS_OPERATING_SYSTEM.md`](../SPEC_ZALO_ADS_OPERATING_SYSTEM.md) · [`2026-07-25-wave-z1-zalo-ads-e2e-design.md`](2026-07-25-wave-z1-zalo-ads-e2e-design.md)  
**Use cases:** [`08-ZALO-ADS.md`](../use-cases/08-ZALO-ADS.md) · [`08-ZALO-ACTIONS.md`](../use-cases/actions/08-ZALO-ACTIONS.md)

---

## 1. Mục tiêu & phạm vi backlog

| Mục tiêu | Mô tả |
|----------|--------|
| **MVP** | Wave Z0 (done) + **Z1** (hub/sync/portal) + **Z2** (form poll + leads UI + orchestrator) |
| **Pattern** | Google B6-S6 parity trước; Meta-depth (ads-ops, intelligence) **out of MVP** |
| **Reuse** | `client_channel_accounts`, `hub_campaign_map`, `daily_performance`, `crm_leads`, CRM creatives workflow |

**Out of backlog MVP:** Wave Z4 campaign API write (phụ thuộc quyền Zalo Business API).

---

## 2. Trạng thái maturity (as-is)

| Thành phần | Status | Ref |
|------------|--------|-----|
| Channel account `zalo` CRUD | ✅ Z0 | `agency.service.ts`, `AgencyClientDetailContent.tsx` |
| Hub map `channel=zalo` | ✅ Z0 | `HubCampaignMapsPanel.tsx` |
| Webhook lead Zalo → CRM | ✅ Z0 | `zalo-webhook.parser.ts`, `ptt_channel/adapters/zalo.py` |
| Normalized schema `channel=zalo` | ✅ Z0 | `schemas/channel/normalized-daily-performance.schema.json` |
| Cap `crm_zalo_ads` | ❌ | — |
| Hub `/zalo/zalo-ads` | ❌ | — |
| Job `zalo_insights_sync` | ❌ | — |
| Portal `/zalo` | ❌ | — |
| OAuth / token vault Zalo | ❌ stub | `ZaloAdapter.validate_credentials` |
| Form poll + `/zalo/leads` | ❌ | — |
| Onboard orchestrator Zalo steps | ❌ | `onboarding-orchestrator.service.ts` |
| Performance API `channel=zalo` | ❌ | `performance.types.ts` |

**Ước lượng hoàn thành MVP:** ~25% (Z0 only).

---

## 3. Ma trận UC → Wave → backlog ID

| UC | Tên | P | Wave | Backlog prefix |
|----|-----|---|------|----------------|
| ZALO-UC-001 | Kết nối Zalo Ads/OA | P0 | Z1 | Z1-B*, Z1-U7–U8 |
| ZALO-UC-002 | Hub map campaign | P0 | Z0 | ✅ Z0-V* |
| ZALO-UC-003 | Sync insights | P0 | Z1 | Z1-W*, Z1-B5–B7 |
| ZALO-UC-004 | Hub CPL staff | P0 | Z1 | Z1-B3–B4, Z1-U1–U3 |
| ZALO-UC-005 | Portal performance | P0 | Z1 | Z1-P*, Z1-B10 |
| ZALO-UC-011 | Webhook lead | P0 | Z0 | ✅ Z0-V3 |
| ZALO-UC-012 | Poll form lead | P0 | Z2 | Z2-B*, Z2-W* |
| ZALO-UC-013 | Dedup lead | P0 | Z2 | Z2-B8 |
| ZALO-UC-014 | CRM pipeline | P0 | Z0 | ✅ (shared CRM) |
| ZALO-UC-015 | CRM status → hub CPA | P1 | Z2 | Z2-B9 |
| ZALO-UC-016 | Xuất báo cáo KH | P1 | Z3 | Z3-5 |
| ZALO-UC-017 | Cảnh báo bất thường | P1 | Z3 | Z3-3, Z3-4 |
| ZALO-UC-018 | Phân tích đa chiều | P2 | Z4 | Z4-6 |
| ZALO-UC-006–008 | Brief / draft / duyệt | P1 | Z3 | Z3-1, Z3-2 (shared CRM) |
| ZALO-UC-009–010 | Campaign API write | P2 | Z4 | Z4-* |
| ZALO-UC-019–020 | Client approve / notify | P1 | Z3 | Z3-7, Z3-8 |
| ZALO-UC-021 | Onboard orchestrator | P1 | Z2 | Z2-U3 |

---

## 4. Wave Z0 — Verify & document (✅ shipped, còn việc nhỏ)

| ID | Task | Layer | Effort | Owner | Deps | Done |
|----|------|-------|--------|-------|------|------|
| Z0-V1 | Verify `zalo` in `VALID_CHANNELS` / `VALID_HUB_CHANNELS` | BE | S | — | — | ☐ |
| Z0-V2 | Verify hub map UI channel zalo E2E | FE | S | — | — | ☐ |
| Z0-V3 | Webhook fixture test green | QA | S | — | — | ☐ |
| Z0-V4 | Runbook webhook prod URL | Docs | S | — | — | ☐ |
| Z0-V5 | Update ACTION-GAP-ANALYSIS Zalo Z0 | Docs | S | — | — | ☐ |

---

## 5. Wave Z1 — Hub + Sync + Portal (MVP core)

**PO gate:** ✅ Signed off 2026-07-25 — [`2026-07-25-wave-z1-zalo-ads-e2e-design.md`](2026-07-25-wave-z1-zalo-ads-e2e-design.md) (`Execute: go`). **Sprint S1–S2 cleared to start.**

### 5.1 Data / DDL

| ID | Task | Deliverable | Effort | Deps |
|----|------|-------------|--------|------|
| Z1-D1 | DDL `zalo_insights_sync_state` | `docs/specs/2026-07-25-postgresql-ddl-zalo-insights-sync-state.sql` | S | — |
| Z1-D2 | Apply migration prod/staging runbook | deploy note | S | Z1-D1 |

### 5.2 Backend — Nest (`ptt-crm-api`)

| ID | Task | Files (new/modify) | Template | Effort | UC |
|----|------|-------------------|----------|--------|-----|
| Z1-B1 | Seed cap `crm_zalo_ads` view + export | `staff-auth.service.ts` | `crm_google_ads` | S | — |
| Z1-B2 | `StaffZaloAdsViewGuard` | `guards/staff-agency-view.guard.ts` | Google guard | S | — |
| Z1-B3 | `zaloHub()` + repository summary | `agency.service.ts`, `agency.repository.ts` | `googleHub()` | L | UC-004 |
| Z1-B4 | Routes: hub, export, pilot-status | `agency-ops.controller.ts` | `google-ads/*` | M | UC-004 |
| Z1-B5 | `syncZaloClientInsights()` + controller POST | `agency.service.ts`, `clients.controller.ts` | Google sync | M | UC-003 |
| Z1-B6 | Side-effects idempotency key | `agency-side-effects.service.ts` | google pattern | S | UC-003 |
| Z1-B7 | `GET .../zalo/sync-status` | `clients.controller.ts`, repo | google sync state | M | UC-003 |
| Z1-B8 | `zalo-oauth.util.ts` start/callback | new + controller routes | `google-oauth.util.ts` | L | UC-001 |
| Z1-B9 | `zalo-ads-pilot.util.ts` stub/pilot | new | `google-ads-pilot.util.ts` | M | UC-001 |
| Z1-B10 | Extend `PerformanceChannel` + service filter `zalo` | `performance.types.ts`, `performance.service.ts` | google | M | UC-005 |
| Z1-B11 | Unit tests hub + sync + pilot | `agency.service.spec.ts` | google specs | M | — |
| Z1-B12 | Env config Zalo vars | `app-config.service.ts` | Google env | S | — |

**API checklist (Z1):**

- [ ] `GET /api/v1/zalo-ads/hub`
- [ ] `GET /api/v1/zalo-ads/hub/export`
- [ ] `GET /api/v1/zalo-ads/pilot-status`
- [ ] `GET /api/v1/zalo-ads/oauth/start`
- [ ] `GET /api/v1/zalo-ads/oauth/callback`
- [ ] `POST /api/v1/clients/:id/sync/zalo-insights`
- [ ] `GET /api/v1/clients/:id/zalo/sync-status`
- [ ] `GET /api/v1/performance?channel=zalo` (portal)

### 5.3 Workers — Python

| ID | Task | Files | Template | Effort | UC |
|----|------|-------|----------|--------|-----|
| Z1-W1 | Package `ptt_zalo/` scaffold | `ptt_zalo/__init__.py`, config | `ptt_google/` | S | — |
| Z1-W2 | `insights_sync.py` → `daily_performance` | `ptt_zalo/insights_sync.py` | `ptt_google/insights_sync.py` | L | UC-003 |
| Z1-W3 | Job handler registration | `ptt_jobs/handlers/zalo_insights_sync.py` | google handler | M | UC-003 |
| Z1-W4 | Worker dispatch | `ptt_worker/__main__.py` | existing | S | UC-003 |
| Z1-W5 | Stub mode `PTT_ZALO_ADS_STUB` | insights_sync | Google stub | M | — |
| Z1-W6 | Wire `ZaloAdapter.validate_credentials` | `ptt_channel/adapters/zalo.py` | — | M | UC-001 |
| Z1-W7 | Integration test job → PG rows | `tests/` | google test | M | — |

### 5.4 ops-web — Staff UI

| ID | Task | Route / file | Template | Effort | UC |
|----|------|--------------|----------|--------|-----|
| Z1-U1 | Hub page | `/zalo/zalo-ads/page.tsx` | — | S | UC-004 |
| Z1-U2 | `ZaloZaloAdsContent.tsx` KPI + table + filters | `src/app/zalo/` | `GoogleGoogleAdsContent.tsx` | L | UC-004 |
| Z1-U3 | `ZaloPilotBanner.tsx` | `src/components/` | `GooglePilotBanner.tsx` | S | — |
| Z1-U4 | API helpers | `src/lib/zalo/api.ts` or `lib/api.ts` | google helpers | M | — |
| Z1-U5 | Cap helpers | `src/lib/zalo/caps.ts` | meta/google | S | — |
| Z1-U6 | OpsNav section Zalo Ads | `OpsNav.tsx` | Google block | S | — |
| Z1-U7 | Agency channels: Connect Zalo + Sync Zalo | `AgencyClientDetailContent.tsx` | Google OAuth/sync | M | UC-001, UC-003 |
| Z1-U8 | Channel form: OA ID, form_ids meta | same | Meta pixel meta | M | UC-001 |
| Z1-U9 | Job label `zalo_insights_sync` | `job-labels.ts` | existing | S | — |
| Z1-U10 | E2E `zalo-ads.spec.ts` | `ops-web/e2e/` | google e2e | L | ZA-11 |
| Z1-U11 | OAuth callback route | `/zalo/oauth/callback` | google callback | S | UC-001 |

### 5.5 portal-web

| ID | Task | File | Effort | UC |
|----|------|------|--------|-----|
| Z1-P1 | Route `/zalo/page.tsx` | mirror `google/page.tsx` | M | UC-005 |
| Z1-P2 | `PerformancePanel channel="zalo"` | extend if needed | S | UC-005 |
| Z1-P3 | PortalNav link Zalo | `PortalNav.tsx` | S | UC-005 |
| Z1-P4 | Middleware protect `/zalo` | `middleware.ts` | S | UC-005 |
| Z1-P5 | API fetchPerformance zalo | `portal-web/src/lib/api.ts` | S | UC-005 |
| Z1-P6 | E2E tenant isolation | `portal-web/e2e/` | M | ZA-05 |

### 5.6 QA & Docs (Z1)

| ID | Task | Effort |
|----|------|--------|
| Z1-Q1 | Acceptance ZA-01…ZA-06 (spec §12) | M |
| Z1-Q2 | `docs/huong-dan-zalo-ads-ops.md` | L |
| Z1-Q3 | PO sign-off Wave Z1 design | S | ✅ 2026-07-25 |

### 5.7 Z1 Definition of Done

- [ ] Hub CPL khớp tính tay ± rounding (ZA-02)
- [ ] Portal client A không thấy client B (ZA-05)
- [ ] Sync idempotent `zalo_insights_sync:{client_id}:{date}` (ZA-03)
- [ ] E2E `zalo-ads.spec.ts` green CI (ZA-11)
- [ ] Cap 403 khi thiếu `crm_zalo_ads` (ZA-01)

---

## 6. Wave Z2 — Form poll + Leads monitor + Orchestrator

### 6.1 Data / DDL

| ID | Task | DDL file |
|----|------|----------|
| Z2-D1 | `zalo_lead_form_sync_cursor` | `docs/specs/2026-07-25-postgresql-ddl-zalo-leads.sql` |
| Z2-D2 | `zalo_lead_events` | same file |

### 6.2 Backend — ZaloLeadsModule

| ID | Task | API / module | Effort | UC |
|----|------|--------------|--------|-----|
| Z2-B1 | Scaffold `src/zalo-leads/` module | module, controller, service, repo | M | — |
| Z2-B2 | `GET /api/v1/zalo/leads` | list + filters | M | UC-012 |
| Z2-B3 | `GET /api/v1/zalo/forms` | forms per OA | M | UC-012 |
| Z2-B4 | `POST /api/v1/zalo/forms/:formId/poll` | manual poll enqueue | M | UC-012 |
| Z2-B5 | `GET /api/v1/zalo/leads/:id/events` | audit trail | S | UC-013 |
| Z2-B6 | Dedup BR-ZALO-02 (phone+client+24h) | lead ingest path | M | UC-013 |
| Z2-B7 | CRM Won → hub CPA refresh join | performance service | M | UC-015 |
| Z2-B8 | Unit + e2e lead poll | tests | M | — |

### 6.3 Workers

| ID | Task | Handler | Effort | UC |
|----|------|---------|--------|-----|
| Z2-W1 | `zalo_form_lead_poll.py` | `oa/form/get` API | L | UC-012 |
| Z2-W2 | Cron 5–15 min per active form | scheduler | M | UC-012 |
| Z2-W3 | Cursor advance + idempotency | worker | M | UC-012 |

### 6.4 ops-web

| ID | Task | Route | Effort | UC |
|----|------|-------|--------|-----|
| Z2-U1 | `/zalo/leads` page — lead table | Z-UI-03 | L | UC-012 |
| Z2-U2 | Form sync tab — cursor, Poll now | same | M | UC-012 |
| Z2-U3 | Orchestrator steps `zalo_account`, `zalo_token`, `zalo_form`, `zalo_sync`, `zalo_first_lead` | `onboarding-orchestrator.service.ts` | M | UC-021 |
| Z2-U4 | Update SYS-UC-001 actions nhánh Zalo | `00-SYSTEM-ACTIONS.md` | S | — |

### 6.5 Z2 Definition of Done

- [ ] Form lead SLA ≤ 15 phút (ZA-08)
- [ ] Dedup không tạo duplicate CRM row (ZA-07 hardening)
- [ ] Orchestrator auto-detect Zalo steps (ZA-10)
- [ ] `/zalo/leads` E2E green

---

## 7. Wave Z3 — Workflow + Alerts + Reporting polish

| ID | Task | Layer | Effort | UC |
|----|------|-------|--------|-----|
| Z3-1 | Creative submit tag `channel=zalo` | CRM FE/BE | M | UC-008 |
| Z3-2 | Launch QA checklist items Zalo (token+form) | lifecycle | M | UC-008 |
| Z3-3 | Alert: CPL > target_cpl_vnd | alerts | L | UC-017 |
| Z3-4 | Alert: zero leads 24h, CTR drop | alerts | M | UC-017 |
| Z3-5 | Slack/Teams hub banner link `/zalo/zalo-ads` | alerts | S | UC-017 |
| Z3-6 | Export PDF báo cáo KH (template Zalo) | reporting | L | UC-016 |
| Z3-7 | `/meta/ads-combined` tab/filter Zalo | ops-web | M | Z-UI-05 |
| Z3-8 | Notification campaign milestones | notification | M | UC-020 |
| Z3-9 | Handover doc § Zalo | docs | M | — |
| Z3-10 | Portal budget approve flow doc (reuse creatives) | docs | S | UC-019 |

---

## 8. Wave Z4 — Campaign API write (backlog, optional)

> **Blocker:** Zalo Business API campaign write permissions. v1 workaround: manual launch + hub map (Z0).

| ID | Task | Effort |
|----|------|--------|
| Z4-1 | `ZaloAdsOpsModule` (mirror meta-ads-ops) | XL |
| Z4-2 | Launch wizard `/zalo/ads-ops` | L |
| Z4-3 | Temporal + campaign-writes integration | L |
| Z4-4 | Pause/update/stop campaign API | L |
| Z4-5 | `supports_campaign_write=True` adapter | M |
| Z4-6 | BI / Grafana Zalo dashboard | L |

---

## 9. UI/UX screen registry

| Screen ID | Route | Wave | Backlog IDs | Status |
|-----------|-------|------|-------------|--------|
| Z-UI-01 | `/zalo/zalo-ads` | Z1 | Z1-U1, Z1-U2 | ❌ |
| Z-UI-02 | `/agency/clients/[id]?tab=channels` (Zalo) | Z1 | Z1-U7, Z1-U8 | 🟡 partial |
| Z-UI-03 | `/zalo/leads` | Z2 | Z2-U1, Z2-U2 | ❌ |
| Z-UI-04 | portal `/zalo` | Z1 | Z1-P1…P6 | ❌ |
| Z-UI-05 | `/meta/ads-combined` + Zalo | Z3 | Z3-7 | ❌ |
| Z-UI-06 | Onboard orchestrator Zalo steps | Z2 | Z2-U3 | ❌ |
| Z-UI-07 | `/crm/leads?channel=zalo` | Z0 | — | ✅ |
| Z-UI-08 | `/crm/creatives` (zalo tag) | Z3 | Z3-1 | 🟡 shared |
| Z-UI-09 | portal `/creatives` | Z3 | Z3-8 | ✅ shared |
| Z-UI-10 | OpsNav Zalo section | Z1 | Z1-U6 | ❌ |

---

## 10. Deliverables matrix (ZA-01…ZA-12)

| ID | Deliverable | Wave | Backlog | Status |
|----|-------------|------|---------|--------|
| ZA-01 | Cap + guards | Z1 | Z1-B1, Z1-B2 | ❌ |
| ZA-02 | Hub API CPL | Z1 | Z1-B3, Z1-B4 | ❌ |
| ZA-03 | `zalo_insights_sync` job | Z1 | Z1-W2, Z1-W3 | ❌ |
| ZA-04 | ops `/zalo/zalo-ads` | Z1 | Z1-U1, Z1-U2 | ❌ |
| ZA-05 | portal `/zalo` | Z1 | Z1-P1…P6 | ❌ |
| ZA-06 | Sync button channels | Z1 | Z1-U7, Z1-B5 | ❌ |
| ZA-07 | Webhook → CRM | Z0 | Z0-V3 | ✅ |
| ZA-08 | Form poll SLA 15m | Z2 | Z2-W1, Z2-W2 | ❌ |
| ZA-09 | Hub map unmapped yellow | Z0 | Z0-V2 | ✅ |
| ZA-10 | Orchestrator zalo steps | Z2 | Z2-U3 | ❌ |
| ZA-11 | E2E `zalo-ads.spec.ts` | Z1 | Z1-U10 | ❌ |
| ZA-12 | DDL sync_state | Z1 | Z1-D1 | ❌ |

---

## 11. Environment variables

```bash
# OAuth
PTT_ZALO_APP_ID=
PTT_ZALO_APP_SECRET=
PTT_ZALO_OAUTH_REDIRECT_URI=https://ops.pttads.vn/zalo/oauth/callback

# Webhook
CRM_ZALO_WEBHOOK_SECRET=

# Sync / pilot
PTT_ZALO_INSIGHTS_SYNC=1
PTT_ZALO_ADS_STUB=0
PTT_ZALO_ADS_PILOT=1
PTT_ZALO_ADS_PILOT_CLIENTS=uuid1,uuid2
```

---

## 12. Dependency graph (critical path)

```
Z1-D1 (DDL)
  → Z1-W2 (worker insights_sync)
    → Z1-B3/B4 (hub API)
      → Z1-U2 (ops hub UI)
      → Z1-P1 (portal)
        → Z1-U10 (E2E)
          → Z2-D1 (leads DDL)
            → Z2-W1 (form poll)
              → Z2-U1 (/zalo/leads)
                → Z2-U3 (orchestrator)
                  → Z3 (alerts, combined nav)
```

**Parallel tracks after Z1-B3:**

- Track A: Z1-B8 OAuth (UC-001) — có thể song song worker
- Track B: Z1-P* portal — sau Z1-B10 performance filter

---

## 13. Sprint proposal

| Sprint | Focus | Tasks | Est. dev-days |
|--------|-------|-------|---------------|
| **S1** | Z1 BE + Worker | Z1-D*, Z1-B*, Z1-W* | ~9 |
| **S2** | Z1 FE + Portal + E2E | Z1-U*, Z1-P*, Z1-Q* | ~9 |
| **S3** | Z2 Leads + Orchestrator | Z2-* | ~13 |
| **S4** | Z3 Polish | Z3-* | ~9 |

**MVP total (S1–S3):** ~31 dev-days (1 FTE ≈ 6–7 tuần; 2 FTE BE/FE ≈ 3–4 tuần).

---

## 14. Risks & mitigations

| Risk | Impact | Mitigation | Owner |
|------|--------|------------|-------|
| Zalo insights API limited | Hub thiếu metrics | Stub pilot + manual CSV import | Eng |
| OAuth OA ≠ ad account | Mapping confusion | Document `meta.oa_id`; UI hints | AM/Tech |
| Campaign write unavailable | UC-009/010 blocked | Manual launch + hub map (Z0) | PO |
| Lead dedup false +/- | CRM quality | BR-ZALO-02 + events table Z2 | Eng |
| PO Z1 not signed | Sprint blocked | Sign-off Z1 design doc | PO |

---

## 15. Reference files (copy templates)

| Concern | Google (copy from) | Zalo (create) |
|---------|-------------------|---------------|
| Hub service | `agency.service.ts` → `googleHub()` | `zaloHub()` |
| Hub controller | `agency-ops.controller.ts` google-ads | zalo-ads |
| Hub UI | `GoogleGoogleAdsContent.tsx` | `ZaloZaloAdsContent.tsx` |
| OAuth | `google-oauth.util.ts` | `zalo-oauth.util.ts` |
| Pilot | `google-ads-pilot.util.ts` | `zalo-ads-pilot.util.ts` |
| Worker | `ptt_google/insights_sync.py` | `ptt_zalo/insights_sync.py` |
| Portal | `portal-web/.../google/page.tsx` | `zalo/page.tsx` |
| Adapter | — | `ptt_channel/adapters/zalo.py` (extend) |

---

## 16. Changelog

| Date | Change |
|------|--------|
| 2026-07-25 | Initial backlog from SPEC + UC analysis |
| 2026-07-25 | PO sign-off Wave Z1 — Execute: go; S1–S2 unblocked |

---

*End of backlog v1.0*
