# Meta Enterprise — Implementation Plan: Phase 0 + B8

> **Phiên bản:** 1.0 · **Ngày:** 2026-07-24  
> **Phạm vi:** Foundation UI refactor (Phase 0) + Measurement parity UI (B8)  
> **Nguồn:**  
> - [`../SPEC_META_ENTERPRISE_PTTADS.md`](../SPEC_META_ENTERPRISE_PTTADS.md) v1.2.1 §18 B8  
> - [`2026-07-24-meta-enterprise-ui-ux-architecture-design.md`](2026-07-24-meta-enterprise-ui-ux-architecture-design.md)  
> **Ước lượng:** Phase 0 ~3–5 ngày · B8 ~10–14 ngày (2 dev parallel: backend + frontend)

---

## Mục lục

1. [Tổng quan & thứ tự thực thi](#1-tổng-quan--thứ-tự-thực-thi)
2. [Definition of Done](#2-definition-of-done)
3. [Phase 0 — Foundation (~3–5 ngày)](#3-phase-0--foundation-35-ngày)
4. [B8 Backend (~5–7 ngày)](#4-b8-backend-57-ngày)
5. [B8 ops-web (~4–5 ngày)](#5-b8-ops-web-45-ngày)
6. [B8 portal-web (~1–2 ngày)](#6-b8-portal-web-12-ngày)
7. [B8 Gates, tests & deploy (~2 ngày)](#7-b8-gates-tests--deploy-2-ngày)
8. [Ma trận phụ thuộc file](#8-ma-trận-phụ-thuộc-file)
9. [Checklist tổng (copy sang sprint)](#9-checklist-tổng-copy-sang-sprint)

---

## 1. Tổng quan & thứ tự thực thi

### 1.1. Song song được phép

```text
Tuần 1
├── [P0] Phase 0 frontend (ops + portal CSS)     ← bắt đầu ngay, không đổi API
└── [B8-BE-1] DDL + ptt_meta/alerts skeleton   ← song song

Tuần 2
├── [P0] Done + merge
├── [B8-BE-2] Nest meta-alerts + hub extend
└── [B8-FE-1] Hub tabs shell (mock/stub API OK)

Tuần 3
├── [B8-FE-2] Campaigns tab + badges + sync chip
├── [B8-FE-3] Alerts tab + map suggest
└── [B8-PORTAL] CPL delta + attribution footer

Tuần 4
├── [B8-QA] gates + E2E + soak
└── merge B8
```

### 1.2. Quy tắc merge

| Phase | Merge khi |
|-------|-----------|
| **Phase 0** | Hub regression pass · không đổi DOM contract · snapshot/visual OK |
| **B8** | `wave_b8_gates.py` PASS · §18 B8 acceptance · H1 regression |

### 1.3. Feature flags

| Flag | Phase 0 | B8 UI |
|------|---------|-------|
| `PTT_META_ALERTS_ENABLED` | — | Tab Alerts + API gated |
| Hub tabs | luôn hiện Clients | Campaigns/Alerts ẩn nếu flag off |

---

## 2. Definition of Done

### Phase 0 DoD

- [ ] `MetaFacebookAdsContent` ≤ ~150 lines (shell only)
- [ ] 6 shared components extracted, hub behavior identical
- [ ] `useMetaHub` hook dùng cho load/filter/export
- [ ] Portal `.channel-badge`, `.over-target` render đúng
- [ ] `npm run build` ops-web + portal-web pass
- [ ] Manual: filter URL sync, export CSV, alerts list unchanged

### B8 DoD (spec §18)

- [ ] ≥2 clients insights 7d; spend ±1% Ads Manager (data — backend soak)
- [ ] `meta_alerts` CPL high synthetic → dedupe
- [ ] Hub unmapped spend % + suggest map inserts row
- [ ] Sync status API → UI chip
- [ ] H1 gates + hub tests regression pass
- [ ] Portal CPL delta column + attribution footer

---

## 3. Phase 0 — Foundation (~3–5 ngày)

> **Mục tiêu:** Tách component + hook; **zero** thay đổi API/behavior. PR nhỏ, dễ review.

### P0-1 · Shared types & format (~0.5 ngày)

| # | File | Hành động | Chi tiết |
|---|------|-----------|----------|
| P0-1a | `services/ops-web/src/lib/meta/types.ts` | **CREATE** | Re-export / mirror `FacebookHubResponse`, `FacebookHubClient`, `FacebookHubAlert`, `FacebookHubQuery`, `MetaBadgeVariant` |
| P0-1b | `services/ops-web/src/lib/meta/format.ts` | **CREATE** | Move `fmtVnd`, `yesterdayIso` từ `MetaFacebookAdsContent` |
| P0-1c | `services/ops-web/src/lib/meta/caps.ts` | **CREATE** | `canViewMetaHub(user)`, `canConfigureMeta(user)` wrappers around `hasCap` |
| P0-1d | `services/ops-web/src/lib/api.ts` | **MODIFY** | Re-export types từ `lib/meta/types` (backward compat) hoặc import types từ meta/types |

**Acceptance:** Typecheck pass; không duplicate interface definitions llong term.

---

### P0-2 · Design tokens (~0.5 ngày)

| # | File | Hành động | Chi tiết |
|---|------|-----------|----------|
| P0-2a | `services/ops-web/src/app/globals.css` | **MODIFY** | Add `.meta-badge`, `--meta-badge-*`, `.summary-grid` alignment notes |
| P0-2b | `services/portal-web/src/app/globals.css` | **MODIFY** | Add `.channel-badge`, `.over-target` (green/red CPL emphasis) |

**Acceptance:** Storybook không có — verify bằng render portal table row over-target.

---

### P0-3 · Core components (~1.5 ngày)

| # | File | Hành động | Props / responsibility |
|---|------|-----------|----------------------|
| P0-3a | `services/ops-web/src/components/meta/MetaBadge.tsx` | **CREATE** | `variant: ok\|warn\|error\|muted`, `children` |
| P0-3b | `services/ops-web/src/components/meta/MetaPageShell.tsx` | **CREATE** | `user`, `onLogout`, `title`, `subtitle`, `actions?`, `migration?`, `children` — wraps OpsNav + maxWidth 1200 |
| P0-3c | `services/ops-web/src/components/meta/MetaHubFilters.tsx` | **CREATE** | Controlled: `days`, `dateTo`, `dateFrom`, `clientId`, `status`, `q`, `clientOptions`, `onChange`, `onRefresh`, `loading` |
| P0-3d | `services/ops-web/src/components/meta/MetaHubKpiGrid.tsx` | **CREATE** | `summary: Record<string, unknown>` — 6 cards; dùng `.summary-grid` |
| P0-3e | `services/ops-web/src/components/meta/MetaClientTable.tsx` | **CREATE** | `rows`, `loading` — extract table từ hub hiện tại |
| P0-3f | `services/ops-web/src/components/meta/MetaHubAlertsList.tsx` | **CREATE** | `alerts`, `opsWebLink` — extract alerts card |

**Acceptance:** Each component renders in isolation with mock props.

---

### P0-4 · Hook (~0.5 ngày)

| # | File | Hành động | Chi tiết |
|---|------|-----------|----------|
| P0-4a | `services/ops-web/src/hooks/meta/useMetaHub.ts` | **CREATE** | `ensureAuth`, `hubQuery` from URL, `loadHub`, `syncUrl`, `handleExport`, states: `hub`, `loading`, `error`, `exportBusy` |
| P0-4a | `services/ops-web/src/hooks/meta/useMetaHubAuth.ts` | **CREATE** (optional) | Extract `ensureAuth` nếu hook quá dài |

**Acceptance:** Hook unit-test optional; manual hub page works.

---

### P0-5 · Refactor hub page (~1 ngày)

| # | File | Hành động | Chi tiết |
|---|------|-----------|----------|
| P0-5a | `services/ops-web/src/app/meta/facebook-ads/MetaFacebookAdsContent.tsx` | **MODIFY** | Compose: `MetaPageShell` + `MetaHubFilters` + `MetaHubKpiGrid` + `MetaHubAlertsList` + `MetaClientTable`; delegate logic to `useMetaHub` |
| P0-5b | `services/ops-web/src/app/meta/facebook-ads/page.tsx` | **VERIFY** | No change expected (`Suspense` wrapper) |

**Acceptance:** Diff DOM structure minimal; E2E/manual checklist P0 §2 pass.

---

### P0-6 · Portal CSS fix (~0.5 ngày)

| # | File | Hành động | Chi tiết |
|---|------|-----------|----------|
| P0-6a | `services/portal-web/src/components/PerformanceTable.tsx` | **MODIFY** | No logic change; verify `.over-target` applies |
| P0-6b | `services/portal-web/e2e/portal.spec.ts` | **MODIFY** (optional) | Snapshot Meta tab still loads |

**PR boundary:** Phase 0 = tasks P0-1 → P0-6 only. **Không** thêm tabs B8.

---

## 4. B8 Backend (~5–7 ngày)

> UI B8 phụ thuộc backend. Track này có thể start song song Phase 0.

### B8-BE-1 · DDL & scripts (~1 ngày)

| # | File | Hành động | Chi tiết |
|---|------|-----------|----------|
| B8-BE-1a | `docs/specs/2026-07-24-postgresql-ddl-v4-meta-enterprise.sql` | **CREATE** | `meta_alerts` table (spec §7.2); indexes on `client_id`, `dedupe_key` |
| B8-BE-1b | `scripts/apply_pg_ddl_v4_meta_enterprise.sh` | **CREATE** | Idempotent apply + verify `\d meta_alerts` |
| B8-BE-1c | `deploy/env.meta-enterprise-b8.example` | **CREATE** | `PTT_META_ALERTS_ENABLED=0`, pilot vars |

---

### B8-BE-2 · Python alerts engine (~2 ngày)

| # | File | Hành động | Chi tiết |
|---|------|-----------|----------|
| B8-BE-2a | `ptt_meta/alerts.py` | **CREATE** | `evaluate_meta_alerts(client_id, date)` — `cpl_high`, `unmapped_spend_high`, `sync_failed`; dedupe_key |
| B8-BE-2b | `ptt_jobs/handlers/meta_alerts_eval.py` | **CREATE** | Post `meta_insights_sync` hook |
| B8-BE-2c | `tests/test_meta_alerts.py` | **CREATE** | Dedupe, CPL threshold synthetic |
| B8-BE-2d | `ptt_meta/hub_map_suggest.py` | **CREATE** | UTM/name fuzzy → suggest `hub_campaign_map` rows |

---

### B8-BE-3 · Nest meta-alerts module (~1.5 ngày)

| # | File | Hành động | Chi tiết |
|---|------|-----------|----------|
| B8-BE-3a | `services/ptt-crm-api/src/meta-alerts/meta-alerts.module.ts` | **CREATE** | |
| B8-BE-3b | `services/ptt-crm-api/src/meta-alerts/meta-alerts.controller.ts` | **CREATE** | `GET /meta/alerts`, `PATCH /meta/alerts/:id/ack` |
| B8-BE-3c | `services/ptt-crm-api/src/meta-alerts/meta-alerts.service.ts` | **CREATE** | List, ack, filter client_id |
| B8-BE-3d | `services/ptt-crm-api/src/meta-alerts/meta-alerts.repository.ts` | **CREATE** | PG queries |
| B8-BE-3e | `services/ptt-crm-api/src/meta-alerts/guards/staff-meta-alerts.guard.ts` | **CREATE** | `crm_facebook_ads.view` |
| B8-BE-3f | `services/ptt-crm-api/src/app.module.ts` | **MODIFY** | Import `MetaAlertsModule` |

---

### B8-BE-4 · Hub & sync extend (~1.5 ngày)

| # | File | Hành động | Chi tiết |
|---|------|-----------|----------|
| B8-BE-4a | `services/ptt-crm-api/src/agency/agency.types.ts` | **MODIFY** | Add `FacebookHubCampaignRow`, `attribution` block on `FacebookHubResponse`, `sync_status` chip fields |
| B8-BE-4b | `services/ptt-crm-api/src/agency/agency.repository.ts` | **MODIFY** | `facebookHubCampaigns()` — reuse export query logic, return JSON rows |
| B8-BE-4c | `services/ptt-crm-api/src/agency/agency.service.ts` | **MODIFY** | `facebookHubCampaigns()`, extend `facebookHub()` summary: `unmapped_spend_pct`, attribution metadata §9.4 |
| B8-BE-4d | `services/ptt-crm-api/src/agency/agency-ops.controller.ts` | **MODIFY** | `GET facebook-ads/hub/campaigns`; `GET meta/sync/status`; `POST meta/hub-campaign-map/suggest` |
| B8-BE-4e | `services/ptt-crm-api/src/agency/clients.controller.ts` | **MODIFY** | `PATCH .../alert-config` CPL targets (spec §10.2) |
| B8-BE-4f | `services/ptt-crm-api/test/facebook-hub-b8.e2e-spec.ts` | **CREATE** | Campaigns endpoint, attribution fields |

---

### B8-BE-5 · Performance attribution (portal) (~0.5 ngày)

| # | File | Hành động | Chi tiết |
|---|------|-----------|----------|
| B8-BE-5a | `services/ptt-crm-api/src/performance/performance.types.ts` | **MODIFY** | Add top-level `attribution_model`, `unmapped_spend_pct`, `data_freshness` on `PerformanceListResponse` |
| B8-BE-5b | `services/ptt-crm-api/src/performance/performance.service.ts` | **MODIFY** | Compute unmapped spend % from rows |
| B8-BE-5c | `services/ptt-crm-api/test/performance.e2e-spec.ts` | **MODIFY** | Assert new fields |

> `cpl_delta_*`, `hub_mapped` **đã có** — không cần BE task cho delta column.

---

## 5. B8 ops-web (~4–5 ngày)

> **Prerequisite:** Phase 0 merged. B8-FE-2+ cần B8-BE-4 endpoints (có thể stub với fixture trước).

### B8-FE-1 · API client layer (~0.5 ngày)

| # | File | Hành động | Chi tiết |
|---|------|-----------|----------|
| B8-FE-1a | `services/ops-web/src/lib/meta/types.ts` | **MODIFY** | Add `MetaAlert`, `MetaSyncStatus`, `FacebookHubCampaignRow`, `HubAttributionMeta` |
| B8-FE-1b | `services/ops-web/src/lib/meta/api.ts` | **CREATE** | `fetchMetaAlerts`, `patchMetaAlertAck`, `fetchMetaSyncStatus`, `fetchFacebookHubCampaigns`, `postMetaHubMapSuggest` |
| B8-FE-1c | `services/ops-web/src/lib/api.ts` | **MODIFY** | Re-export hoặc delegate to `lib/meta/api.ts` |
| B8-FE-1d | `services/ops-web/src/lib/meta/flags.ts` | **CREATE** | `metaAlertsEnabled()` from `NEXT_PUBLIC_PTT_META_ALERTS_ENABLED` |

---

### B8-FE-2 · Hub tabs shell (~1 ngày)

| # | File | Hành động | Chi tiết |
|---|------|-----------|----------|
| B8-FE-2a | `services/ops-web/src/components/meta/MetaHubTabs.tsx` | **CREATE** | Tabs: `clients` \| `campaigns` \| `alerts`; URL `?tab=` sync |
| B8-FE-2b | `services/ops-web/src/hooks/meta/useMetaHubTab.ts` | **CREATE** | Tab state + URL sync |
| B8-FE-2c | `services/ops-web/src/app/meta/facebook-ads/MetaFacebookAdsContent.tsx` | **MODIFY** | Wrap tables in `MetaHubTabs`; Clients tab = existing `MetaClientTable` |

**Acceptance:** Tab switch không reload full page; URL shareable `?tab=campaigns`.

---

### B8-FE-3 · Campaigns tab (~1 ngày)

| # | File | Hành động | Chi tiết |
|---|------|-----------|----------|
| B8-FE-3a | `services/ops-web/src/components/meta/MetaCampaignTable.tsx` | **CREATE** | Columns: campaign, client, spend, leads, CPL, vs target, badges |
| B8-FE-3b | `services/ops-web/src/components/meta/MetaHubBadges.tsx` | **CREATE** | Compose `MetaBadge` for row: unmapped, token, tenant_locked (if field exists) |
| B8-FE-3c | `services/ops-web/src/hooks/meta/useMetaHubCampaigns.ts` | **CREATE** | Fetch campaigns with same filters as hub |
| B8-FE-3d | `services/ops-web/src/app/meta/facebook-ads/MetaFacebookAdsContent.tsx` | **MODIFY** | Campaigns tab content |

**Acceptance:** Campaign count ≈ export CSV campaigns scope.

---

### B8-FE-4 · Sync status + KPI attribution (~0.5 ngày)

| # | File | Hành động | Chi tiết |
|---|------|-----------|----------|
| B8-FE-4a | `services/ops-web/src/components/meta/MetaSyncStatusChip.tsx` | **CREATE** | Green/yellow/red from `fetchMetaSyncStatus` |
| B8-FE-4b | `services/ops-web/src/components/meta/MetaHubKpiGrid.tsx` | **MODIFY** | Show `unmapped_spend_pct` card; attribution footnote |
| B8-FE-4c | `services/ops-web/src/components/meta/MetaPageShell.tsx` | **MODIFY** | Slot `headerExtra` for sync chip |

---

### B8-FE-5 · Alerts tab (~1 ngày)

| # | File | Hành động | Chi tiết |
|---|------|-----------|----------|
| B8-FE-5a | `services/ops-web/src/components/meta/MetaAlertsTable.tsx` | **CREATE** | Columns: type, client, campaign, severity, date, ack button |
| B8-FE-5b | `services/ops-web/src/hooks/meta/useMetaAlerts.ts` | **CREATE** | List + ack + reload |
| B8-FE-5c | `services/ops-web/src/app/meta/facebook-ads/MetaFacebookAdsContent.tsx` | **MODIFY** | Alerts tab; hide if `!metaAlertsEnabled()` |
| B8-FE-5d | `services/ops-web/src/components/meta/MetaHubAlertsList.tsx` | **MODIFY** | Keep inline summary alerts OR merge into PG alerts — **giữ inline summary** + tab = PG `meta_alerts` |

**Acceptance:** Ack → PATCH → row marked acked; dedupe không duplicate UI rows.

---

### B8-FE-6 · Map suggest CTA (~0.5 ngày)

| # | File | Hành động | Chi tiết |
|---|------|-----------|----------|
| B8-FE-6a | `services/ops-web/src/components/meta/MetaMapSuggestButton.tsx` | **CREATE** | On campaign row with unmapped badge → POST suggest → toast + link `/crm/hub` |
| B8-FE-6b | `services/ops-web/src/components/meta/MetaCampaignTable.tsx` | **MODIFY** | Add action column |
| B8-FE-6c | `services/ops-web/src/components/OpsNav.tsx` | **MODIFY** | Optional: pending alerts count badge on Meta Ads link (if API stats endpoint added) |

---

### B8-FE-7 · Hub attribution display (~0.5 ngày)

| # | File | Hành động | Chi tiết |
|---|------|-----------|----------|
| B8-FE-7a | `services/ops-web/src/components/meta/MetaAttributionFooter.tsx` | **CREATE** | `last_touch_crm`, unmapped %, through_date |
| B8-FE-7b | `services/ops-web/src/hooks/meta/useMetaHub.ts` | **MODIFY** | Pass through attribution from hub response |

---

## 6. B8 portal-web (~1–2 ngày)

> Backend `cpl_delta_*` + `hub_mapped` đã sẵn. Chủ yếu UI.

### B8-PORTAL-1 · Types & API (~0.25 ngày)

| # | File | Hành động | Chi tiết |
|---|------|-----------|----------|
| B8-P-1a | `services/portal-web/src/lib/api.ts` | **MODIFY** | Extend `PerformanceListResponse` with attribution block (match BE B8-BE-5) |

---

### B8-PORTAL-2 · Table columns (~0.5 ngày)

| # | File | Hành động | Chi tiết |
|---|------|-----------|----------|
| B8-P-2a | `services/portal-web/src/components/PerformanceTable.tsx` | **MODIFY** | Add columns: **CPL Δ** (`cpl_delta_vnd` + `%`), **Map** badge when `!hub_mapped` |
| B8-P-2b | `services/portal-web/src/lib/format.ts` | **MODIFY** | `fmtDeltaVnd`, `fmtDeltaPct` helpers |

---

### B8-PORTAL-3 · Panel footer (~0.5 ngày)

| # | File | Hành động | Chi tiết |
|---|------|-----------|----------|
| B8-P-3a | `services/portal-web/src/components/PerformancePanel.tsx` | **MODIFY** | Attribution footer under table; KPI card "Over target" uses summary |
| B8-P-3b | `services/portal-web/src/components/PortalAttributionFooter.tsx` | **CREATE** (optional) | Reusable footer component |

---

### B8-PORTAL-4 · E2E (~0.5 ngày)

| # | File | Hành động | Chi tiết |
|---|------|-----------|----------|
| B8-P-4a | `services/portal-web/e2e/portal.spec.ts` | **MODIFY** | Assert CPL delta column header visible on `/meta` |
| B8-P-4b | `services/portal-web/e2e/portal.spec.ts` | **MODIFY** | Assert no write buttons (regression) |

---

## 7. B8 Gates, tests & deploy (~2 ngày)

### B8-QA-1 · Gate scripts

| # | File | Hành động | Chi tiết |
|---|------|-----------|----------|
| B8-QA-1a | `ptt_crm/wave_b8_gates.py` | **CREATE** | Checks: DDL meta_alerts, alerts eval, API routes, flag default off |
| B8-QA-1b | `scripts/wave_b8_gate.sh` | **CREATE** | Run gates + nest test subset |
| B8-QA-1c | `tests/test_facebook_ads_hub.py` | **MODIFY** | Attribution fields, campaigns endpoint |

---

### B8-QA-2 · ops-web E2E

| # | File | Hành động | Scenario |
|---|------|-----------|----------|
| B8-QA-2a | `services/ops-web/e2e/meta-hub.spec.ts` | **CREATE** | E2E-M1: filter client syncs URL |
| B8-QA-2b | `services/ops-web/e2e/meta-hub.spec.ts` | **CREATE** | E2E-M2: tab campaigns loads table |
| B8-QA-2c | `services/ops-web/e2e/meta-hub.spec.ts` | **CREATE** | E2E-M3: alerts ack (if seed fixture) |

---

### B8-QA-3 · Deploy checklist

| # | Task | Chi tiết |
|---|------|----------|
| B8-QA-3a | Apply DDL v4 on staging PG | `./scripts/apply_pg_ddl_v4_meta_enterprise.sh` |
| B8-QA-3b | Deploy Nest + ops-web + portal-web | rebuild containers |
| B8-QA-3c | Enable `PTT_META_ALERTS_ENABLED=1` pilot 1 client | soak 7d before widen |
| B8-QA-3d | Run `horizon1_meta_ads_gates.py` + `wave_b8_gates.py` | regression |

---

## 8. Ma trận phụ thuộc file

```text
Phase 0
  lib/meta/types.ts ──┬──► MetaHubKpiGrid, MetaClientTable, useMetaHub
  lib/meta/format.ts ─┘
  MetaPageShell ──────► MetaFacebookAdsContent (refactor)

B8 Backend
  ddl v4 ──► meta-alerts.repository ──► meta-alerts.controller
  alerts.py ──► meta_alerts_eval job
  agency.repository ──► hub/campaigns API ──► useMetaHubCampaigns

B8 Frontend
  lib/meta/api.ts ──► MetaAlertsTable, MetaSyncStatusChip, MetaMapSuggestButton
  MetaHubTabs ──► MetaFacebookAdsContent
  performance.service (attribution) ──► PortalAttributionFooter
```

**Critical path:** `P0-5 merge` → `B8-BE-4 hub/campaigns` → `B8-FE-3 MetaCampaignTable` → `B8-QA`.

---

## 9. Checklist tổng (copy sang sprint)

### Sprint A — Phase 0 (5 tasks)

```
[ ] P0-1  lib/meta/types.ts + format.ts + caps.ts
[ ] P0-2  globals.css ops + portal badges
[ ] P0-3  MetaBadge, MetaPageShell, MetaHubFilters, MetaHubKpiGrid, MetaClientTable, MetaHubAlertsList
[ ] P0-4  hooks/meta/useMetaHub.ts
[ ] P0-5  Refactor MetaFacebookAdsContent.tsx
[ ] P0-6  Portal CSS verify
[ ] PR: "meta phase0 component extraction" → merge
```

### Sprint B — B8 Backend (5 tasks)

```
[ ] B8-BE-1  DDL v4 + apply script + env example
[ ] B8-BE-2  ptt_meta/alerts.py + job handler + tests
[ ] B8-BE-3  Nest meta-alerts module
[ ] B8-BE-4  Hub campaigns API + sync status + map suggest + attribution
[ ] B8-BE-5  PerformanceListResponse attribution fields
[ ] PR: "meta B8 backend measurement parity"
```

### Sprint C — B8 Frontend ops (7 tasks)

```
[ ] B8-FE-1  lib/meta/api.ts + types + flags
[ ] B8-FE-2  MetaHubTabs + URL tab sync
[ ] B8-FE-3  MetaCampaignTable + MetaHubBadges + useMetaHubCampaigns
[ ] B8-FE-4  MetaSyncStatusChip + KPI unmapped %
[ ] B8-FE-5  MetaAlertsTable + useMetaAlerts
[ ] B8-FE-6  MetaMapSuggestButton
[ ] B8-FE-7  MetaAttributionFooter
[ ] PR: "meta B8 ops-web hub enhanced"
```

### Sprint D — B8 Portal + QA (4 tasks)

```
[ ] B8-P-1..3  Portal delta + footer
[ ] B8-P-4     portal e2e
[ ] B8-QA-1    wave_b8_gates.py
[ ] B8-QA-2    ops-web e2e meta-hub.spec.ts
[ ] B8-QA-3    staging deploy + pilot flag
[ ] PR: "meta B8 portal + gates"
```

---

## Phụ lục — File count summary

| Track | CREATE | MODIFY | Total files |
|-------|--------|--------|-------------|
| Phase 0 | 10 | 5 | ~15 |
| B8 Backend | 12 | 8 | ~20 |
| B8 ops-web | 14 | 6 | ~20 |
| B8 portal | 1 | 4 | ~5 |
| B8 QA | 4 | 2 | ~6 |
| **Total** | **~41** | **~25** | **~66** |

---

## Phụ lục — Out of scope (B8)

| Item | Wave |
|------|------|
| `/meta/tracking` full page | B9 |
| `/meta/intelligence` | B10 |
| `/meta/ads-ops` | B15 |
| Breakdown charts | B8.1 |
| Hub row Edit/Pause actions | B15 / B6 extend |
| `MetaRowActions` component | B15 (stub link only in B8 optional) |

---

*Implementation plan Phase 0 + B8 · PTTADS · v1.0 · 2026-07-24*

*Prev: [`2026-07-24-meta-enterprise-ui-ux-architecture-design.md`](2026-07-24-meta-enterprise-ui-ux-architecture-design.md)*
