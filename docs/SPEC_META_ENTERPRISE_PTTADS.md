# Meta Ads Enterprise Platform — PTTADS Master Specification

> **Phiên bản:** 1.2.1 · **Ngày:** 2026-07-24  
> **Trạng thái:** Target architecture — **foundation shipped (Horizon 1, B6, B7)** · **core B8–B11** · **Tier A/B B8.1–B14** · **Ads Ops UI B15** (create + edit creative/copy)  
> **Codebase:** `PTTADS/` (NestJS `ptt-crm-api` · Next.js `ops-web` / `portal-web` · Python `ptt_worker` / `ptt_meta`)  
> **Production:** `https://ops.pttads.vn` · `https://portal.pttads.vn` · `https://rs.pttads.vn` (legacy redirect)  
> **Loại tài liệu:** Business + Technical master spec (bounded context Meta Enterprise)  
> **Nguồn domain (port, không duplicate Flask PTT):**  
> - [`../PTT/docs/SPEC_META_OPERATING_SYSTEM.md`](../PTT/docs/SPEC_META_OPERATING_SYSTEM.md) — Meta-OS P1–P4 domain backlog  
> - [`../PTT/docs/facebook_ads_agency_architecture.md`](../PTT/docs/facebook_ads_agency_architecture.md) — Agency 7-layer reference  
> **Tài liệu PTTADS liên quan:**  
> - [`SPEC_AGENCY_OPERATING_PLATFORM.md`](SPEC_AGENCY_OPERATING_PLATFORM.md) — Master agency platform  
> - [`SPEC_MIGRATION_FLASK_EXECUTION_PLAN.md`](SPEC_MIGRATION_FLASK_EXECUTION_PLAN.md) — Strangler migration (EXECUTING)  
> - [`runbooks/horizon1-meta-ads-migration-checklist.md`](runbooks/horizon1-meta-ads-migration-checklist.md) — Hub canonical ops-web  
> - [`specs/2026-07-23-wave-b6-s4-campaign-write-e2e-design.md`](specs/2026-07-23-wave-b6-s4-campaign-write-e2e-design.md) — Temporal campaign write  
> - [`specs/2026-07-23-wave-b6-s7-portal-mvp-prod-design.md`](specs/2026-07-23-wave-b6-s7-portal-mvp-prod-design.md) — Portal Meta performance  
> - [`specs/2026-07-23-wave-b7-offboarding-flask-retire-design.md`](specs/2026-07-23-wave-b7-offboarding-flask-retire-design.md) — Client offboard  
> - [`specs/2026-07-17-postgresql-ddl-v3-performance.sql`](specs/2026-07-17-postgresql-ddl-v3-performance.sql) — `daily_performance`, `capi_event_log`  
> - [`specs/2026-07-16-channel-adapter-design.md`](specs/2026-07-16-channel-adapter-design.md) — `MetaAdapter`  

---

## Mục lục

1. [Tổng quan & phạm vi](#1-tổng-quan--phạm-vi)
2. [Chiến lược: PTTADS + Meta-OS domain](#2-chiến-lược-pttads--meta-os-domain)
3. [Trạng thái hiện tại (as-is)](#3-trạng-thái-hiện-tại-as-is)
4. [Kiến trúc Meta Enterprise trên PTTADS](#4-kiến-trúc-meta-enterprise-trên-pttads)
5. [Bounded context & module map](#5-bounded-context--module-map)
6. [Personas, RBAC & governance](#6-personas-rbac--governance)
7. [Mô hình dữ liệu PostgreSQL](#7-mô-hình-dữ-liệu-postgresql)
8. [Luồng nghiệp vụ cốt lõi](#8-luồng-nghiệp-vụ-cốt-lõi)
9. [KPI dictionary & attribution](#9-kpi-dictionary--attribution)
10. [API catalog (target)](#10-api-catalog-target)
11. [UI — ops-web & portal](#11-ui--ops-web--portal)
12. [Jobs, workers & scheduler](#12-jobs-workers--scheduler)
13. [Alerts, digest & observability](#13-alerts-digest--observability)
14. [Wave B8–B15 — lộ trình thực thi](#14-wave-b8b15--lộ-trình-thực-thi)
15. [Ma trận deliverables ME1–ME35 (core)](#15-ma-trận-deliverables-me1me35-core)
16. [Yêu cầu phi chức năng](#16-yêu-cầu-phi-chức-năng)
17. [Triển khai, gates & rollback](#17-triển-khai-gates--rollback)
18. [Tiêu chí nghiệm thu theo wave](#18-tiêu-chí-nghiệm-thu-theo-wave)
19. [Rủi ro & giảm thiểu](#19-rủi-ro--giảm-thiểu)
20. [Định vị cạnh tranh & market tier](#20-định-vị-cạnh-tranh--market-tier)
21. [Attribution — mô hình & giới hạn](#21-attribution--mô-hình--giới-hạn)
22. [Insights breakdown & granularity](#22-insights-breakdown--granularity)
23. [Client deliverables & báo cáo](#23-client-deliverables--báo-cáo)
24. [SLA, support tiers & ops excellence](#24-sla-support-tiers--ops-excellence)
25. [Compliance, privacy & data governance](#25-compliance-privacy--data-governance)
26. [Enterprise upgrade roadmap (Tier A/B/C)](#26-enterprise-upgrade-roadmap-tier-abc)
27. [Ma trận deliverables ME36–ME61](#27-ma-trận-deliverables-me36me61)
28. [Phụ lục](#28-phụ-lục)

---

## 1. Tổng quan & phạm vi

### 1.1. Vision

**Meta Ads Enterprise Platform (Meta Enterprise trên PTTADS)** là bounded context quảng cáo Meta **đa client** trên nền Agency Operating Platform — không phải tab CRM lẻ, không phải Flask monolith PTT:

```
Onboard client → Channel account (Meta) → Insights sync → Hub map → CPL/ROAS
              → Lead webhook (Nest) → CAPI + CRM conversions → Tracking health
              → Intelligence (anomaly, recommend) → Governed write (Temporal)
              → Client portal performance → Offboard & revoke
```

**Closed-loop agency:**

`Spend (Meta API) → Lead (webhook/CRM) → Pipeline status → CAPI conversion → Deal revenue → ROAS → Launch QA / Campaign write (approved) → Client report`

### 1.2. Mục tiêu kinh doanh

| Mục tiêu | Chỉ số thành công | Wave |
|----------|-------------------|------|
| Multi-client Meta hub | Staff filter/export theo `client_id`; ≥1 account/client active | H1 ✅ |
| Insights T-1 trước 08:00 ICT | Job success ≥95% / 30 ngày | B8 |
| CPL CRM từ Meta spend | `daily_performance.spend / leads_crm`; unmapped badge | B8 |
| CAPI Lead sau webhook Nest | ≥95% lead `sent` trong 24h (pilot → prod) | B9 |
| Pipeline → Meta conversion | qualified/post_sale ≥90% đủ hash + attribution | B9 |
| Hub map coverage | ≥80% spend có `hub_campaign_map_id` | B8–B9 |
| Portal client Meta KPI | CPL delta, export CSV; tenant isolation | B6-S7 ✅ |
| Campaign write governance | Temporal + `meta_campaign_write` approve | B6-S4 ✅ |
| Anomaly / recommend | Alert + read-only recommend; không auto-mutate | B10 |
| ROAS CRM | `conversion_value / spend` từ deal CRM | B10 |
| Client offboard Meta clean | Token revoke, jobs dead, workflow cancel | B7 ✅ |
| Intelligence snapshot | Weekly export + ops digest | B11 |
| **Ads Ops launch wizard** | Create campaign/ad RE template; approve + Temporal | **B15** |
| **Ads Ops edit creative/copy** | Swap approved creative hoặc sửa copy; diff + approve | **B15 §8.9** |

### 1.3. Nguyên tắc thiết kế

1. **PostgreSQL-only** — mọi entity Meta mới trên PG; không thêm schema Meta trên SQLite Flask.
2. **`client_id` first** — đơn vị isolation; RE project là view/link phụ (`agency_client_id`, lifecycle).
3. **Canonical UI ops-web** — `/meta/facebook-ads`; Flask `/crm/facebook-ads` redirect (Horizon 1).
4. **Workers + job queue** — insights, CAPI, archive, snapshot qua `job_queue` + `ptt_worker`.
5. **Token vault** — `access_token_encrypted`, refresh timer; không plaintext env per prod client.
6. **Governance before mutate** — campaign write qua Temporal approval; recommend read-only.
7. **Port domain logic, not Flask modules** — Meta-OS → `ptt_meta/*`, Nest services, ops-web.
8. **Partial success & idempotency** — sync/CAPI per account; dedupe `event_id`, upsert facts.
9. **Human-in-the-loop intelligence** — rule/stat anomaly; không auto-pause prod without approval.
10. **Strangler** — feature flags, pilot clients, soak ≥7d trước prod widen.

### 1.4. Phạm vi IN

| Lớp | Nội dung |
|-----|----------|
| **L1 Asset & channel** | `client_channel_accounts` (meta), pixel/page meta JSON, OAuth, token refresh |
| **L2 Measurement** | `daily_performance`, insights sync, hub map, CPL, metrics snapshots |
| **L3 Lead loop** | Nest Meta webhook, lead ingest PG, autosync standalone |
| **L4 Conversion** | CAPI dispatch, conversion rules, tracking health |
| **L5 Intelligence** | Anomaly, ROAS engine, budget recommend, forecast |
| **L6 Governance** | Campaign write, Launch QA bridge, offboard, audit |
| **L7 Client-facing** | Portal `/meta`, export, branding settings |
| **L8 Ads Ops UI (B15)** | Launch wizard create + **edit creative/copy** có approve — **không** clone Ads Manager |

### 1.5. Phạm vi OUT (giai đoạn Meta Enterprise v1)

| Hạng mục | Ghi chú |
|----------|---------|
| SaaS multi-agency trên cluster | PTT single agency |
| TikTok / full Google parity trong doc này | Google có hub riêng B6-S6 |
| Creative DAM enterprise | Launch QA + creative bridge B6; full DAM Phase 4+ Agency |
| Deep ML budget optimizer | B11 statistical only; ML → Agency Platform Phase 4+ |
| Meta billing / invoice thay client | Finance module ngoài scope |
| Clone full Ads Manager (audience builder, catalog, dynamic full UI) | Deep link Meta cho tác vụ nâng cao; B15 = **Ads Ops wizard hẹp** |

### 1.6. Vị trí trong Agency Operating Platform

Meta Enterprise là **BC-04 Channel Integration (Meta)** + **BC-07 Event/Tracking** + **BC-Metrics** trong [`SPEC_AGENCY_OPERATING_PLATFORM.md`](SPEC_AGENCY_OPERATING_PLATFORM.md), cùng cấp SEO/AEO OS và Email Marketing OS.

---

## 2. Chiến lược: PTTADS + Meta-OS domain

### 2.1. Không build thêm trên PTT Flask

| Meta-OS (PTT) | Meta Enterprise (PTTADS) |
|---------------|----------------------------|
| `crm_meta_*` SQLite | `daily_performance`, `capi_event_log`, `hub_campaign_map` PG |
| `re_project_id` | `client_id` (+ optional RE link) |
| Flask `/api/crm/meta/*` | Nest `/api/v1/...` + internal worker |
| `crm_hub.html` tab | ops-web `/meta/*`, portal `/meta` |
| `CRM_META_*` env global | `PTT_*` + per-client vault |
| `crm_meta_write_requests` | `campaign_write_requests` + Temporal |

**Meta-OS spec** giữ vai trò **domain reference + acceptance criteria** — logic nghiệp vụ port sang PTTADS, không copy file.

### 2.2. Ánh xạ phase Meta-OS → Wave PTTADS

| Meta-OS | PTTADS wave | Trạng thái |
|---------|-------------|------------|
| P1 Measurement | Horizon 1 + **B8** parity/enforce | H1 partial ✅ |
| P2 Conversion + Hub | CAPI pilot + **B9** | Pilot ✅ / B9 🟡 |
| P2.1 Write API | B6-S4 Temporal write | ✅ |
| P3 Intelligence | **B10** | 🔲 |
| P4 Advanced | **B11** | 🔲 |
| Client portal | B6-S7 | ✅ |
| Offboard | B7 | ✅ |
| Flask retire Meta admin | Horizon 1 B3 | 🟡 in progress |
| **Ads Ops UI (create/mutate wizard)** | **B15** | 🔲 |

---

## 3. Trạng thái hiện tại (as-is)

> Cập nhật baseline **2026-07-24** — trước B8 kickoff.

### 3.1. Shipped / in migration

| Thành phần | Trạng thái | Module / route |
|------------|------------|----------------|
| PG `clients`, `client_channel_accounts` | ✅ | DDL v1 |
| PG `daily_performance`, `capi_event_log`, `metrics_snapshots` | ✅ | DDL v3-performance |
| PG `hub_campaign_map` | ✅ | agency repository |
| Meta insights sync job | ✅ | `ptt_jobs/handlers/meta_insights_sync.py`, `ptt_meta/insights_sync.py` |
| Meta token refresh | ✅ | `ptt_jobs/handlers/meta_token_refresh.py`, timers |
| Token vault | ✅ | `ptt_meta/token_vault.py`, `PTT_TOKEN_VAULT_KEY` |
| Nest Meta webhook | ✅ | `webhooks/meta-webhook.*` |
| Nest hub API + export | ✅ | `GET /api/v1/facebook-ads/hub`, `/hub/export` |
| ops-web Meta hub UI | ✅ | `ops-web/.../meta/facebook-ads/` |
| ops-web combined ads nav | ✅ | `/meta/ads-combined` |
| Portal Meta performance | ✅ | `portal-web/.../meta`, `PerformancePanel` |
| CAPI Lead dispatch pilot | ✅ | `ptt_meta/capi_dispatch.py`, job `capi_dispatch` |
| Campaign write E2E | ✅ | B6-S4, Temporal, Launch QA bridge |
| Client offboard Meta | ✅ | B7 — revoke, cancel jobs/workflows |
| Horizon 1 gates / soak | ✅ | `horizon1_meta_ads_gates.py`, pack scripts |
| ChannelAdapter Meta | ✅ | `ptt_channel/adapters/meta.py` |
| Google hub (cross-channel context) | ✅ | B6-S6 — pattern reuse |

### 3.2. Gap vs Meta Enterprise target (port từ Meta-OS)

| Capability | Meta-OS ref | PTTADS gap |
|------------|-------------|------------|
| Conversion rules CRUD + status hook | P2 M12 | Chỉ Lead (+ Purchase stub) |
| Tracking health UI | P2 M14 | Không tab dedicated |
| Hub map enforce + auto-suggest UX | P2 M13 | Map có; enforce yếu |
| Alert engine (`meta_alerts` table) | P1 M7 | Hub alerts inline only |
| Insights level adset/ad + breakdown | P3 M23, P4 M28 | Campaign-level primary |
| Anomaly median / z-score | P3 M20, P4 M26 | 🔲 |
| Budget recommend API | P3 M22 | 🔲 |
| CPL forecast | P4 M29 | 🔲 |
| Intelligence snapshot + digest | P4 M30–M31 | 🔲 |
| Multi-pixel routing | P4 M27 | Single pixel in account meta JSON |
| `meta_conversion_rules` PG table | P2 | 🔲 |
| Metrics engine ROAS from CRM deals | P3 M21 | Field exists; stub partial |
| Launch QA Meta checklist items | Agency | Partial via lifecycle |
| ClickHouse Meta BI | Agency Phase 4 | Env ready; dashboards TBD |
| **Create campaign/ad via wizard** | B15 | 🔲 mutate only B6 |
| **Edit ad creative/copy (governed)** | B15 §8.9 | 🔲 |
| **Creative → Meta ad link** | B12/B15 | Creative inbox ✅; Graph ad 🔲 |

### 3.3. Prod readiness ước lượng

| Dimension | % | Ghi chú |
|-----------|---|---------|
| Platform (PG, Nest, ops-web, portal, workers) | ~85% | Agency-grade |
| Meta measurement closed-loop | ~55% | Insights + hub CPL |
| Meta conversion (CAPI full) | ~35% | Lead pilot |
| Meta intelligence | ~10% | Spec only |
| Client-facing Meta | ~60% | Portal B6-S7 |
| **Meta Enterprise overall** | **~50%** | B8–B15 + Tier A → ~85%; B15 → ~90% Ads Ops |
| **Enterprise client-ready (target)** | **~85%** | Sau B10–B11 + Tier A |
| **Agency lớn scale (target)** | **~92%** | Sau B12–B14 + Tier B |
| **Ads Ops UI complete (target)** | **~90%** | B15 create + edit creative/copy + B6 mutate |

---

## 4. Kiến trúc Meta Enterprise trên PTTADS

### 4.1. Sơ đồ runtime

```mermaid
flowchart TB
  subgraph meta [Meta Platform]
    GAPI[Marketing API]
    WH[Lead Webhooks]
    CAPI_EP[Conversions API]
  end

  subgraph edge [Edge]
    NGINX[nginx rs / ops / portal]
  end

  subgraph nest [NestJS ptt-crm-api]
    WH_CTRL[MetaWebhookController]
    HUB[FacebookAdsHub]
    AGENCY[AgencyClientsController]
    PERF[PortalPerformance]
    WRITE[CrmCampaignWrites]
    OFF[ClientOffboard]
  end

  subgraph ops [ops-web Next.js]
    META_UI[/meta/facebook-ads]
    TRACK_UI[/meta/tracking — B9]
    INTEL_UI[/meta/intelligence — B10]
  end

  subgraph portal [portal-web]
    PORT_META[/meta performance]
  end

  subgraph worker [ptt_worker + ptt_meta]
    INS[meta_insights_sync]
    CAPI[capi_dispatch]
    TOK[meta_token_refresh]
    ANOM[meta_anomaly — B10]
    SNAP[intel_snapshot — B11]
  end

  subgraph pg [PostgreSQL]
    CCA[(client_channel_accounts)]
    DP[(daily_performance)]
    HCM[(hub_campaign_map)]
    CEL[(capi_event_log)]
    MCR[(meta_conversion_rules — B9)]
    MA[(meta_alerts — B8)]
    JQ[(job_queue)]
    LEADS[(crm_leads)]
  end

  WH --> NGINX --> WH_CTRL --> LEADS
  WH_CTRL --> JQ
  GAPI --> INS --> DP
  CCA --> INS
  HCM --> DP
  LEADS --> DP
  CAPI --> CEL --> CAPI_EP
  LEADS --> CAPI
  nest --> pg
  worker --> pg
  META_UI --> HUB
  PORT_META --> PERF
  WRITE --> GAPI
  OFF --> CCA
```

### 4.2. Ba lớp sản phẩm (Meta)

| Lớp | URL | Người dùng | Capability |
|-----|-----|------------|------------|
| **Staff ops** | `ops.pttads.vn/meta/*` | AM, Buyer, Tracking | Hub, map, sync, rules, write requests |
| **Client portal** | `portal.pttads.vn/meta` | Client viewer | Performance, export, CPL delta |
| **Integration** | `rs.pttads.vn/api/v1/webhooks/meta` | Meta platform | Webhook verify + ingest |

### 4.3. Tích hợp cross-module

| Module PTTADS | Tích hợp Meta Enterprise |
|---------------|--------------------------|
| **Service lifecycle** | Onboarding widget — Meta account, pixel, form |
| **Launch QA** | Budget confirm bridge on campaign write executed |
| **CRM campaign writes** | Temporal pause/resume/budget Meta |
| **CRM creatives** | Link creative → Meta ad (B12 registry + B15 upload) |
| **Client offboard B7** | Revoke token, cancel `meta_insights_sync`, onboarding WF |
| **Google Ads B6-S6** | Shared hub patterns, `/meta/ads-combined` |
| **Domain events** | `DailyPerformanceSynced`, `CapiEventSent`, `MetaAlertRaised` |
| **Owner weekly** | ROAS_min threshold digest |

---

## 5. Bounded context & module map

### 5.1. Python — `ptt_meta/`

| Module | Trách nhiệm | Wave |
|--------|-------------|------|
| `insights_sync.py` | Graph → `daily_performance` | H1 ✅ |
| `graph_insights.py` | Fetch/parse insights | H1 ✅ |
| `token_vault.py` | Encrypt/decrypt token | H1 ✅ |
| `graph_capi.py` | POST pixel events | H1 ✅ |
| `capi_dispatch.py` | Lead/Purchase dispatch, dedupe | B9 extend |
| `conversion_rules.py` | Rules engine (NEW) | B9 |
| `conversion_sync.py` | Backfill status changes (NEW) | B9 |
| `tracking_health.py` | Aggregate CAPI stats (NEW) | B9 |
| `alerts.py` | Evaluate + dedupe alerts (NEW) | B8 |
| `anomaly.py` | Median spike (NEW) | B10 |
| `anomaly_stat.py` | z-score (NEW) | B11 |
| `roas.py` | CRM revenue / spend (NEW) | B10 |
| `budget_recommend.py` | Read-only recommendations (NEW) | B10 |
| `forecast.py` | CPL trend (NEW) | B11 |
| `intelligence_snapshot.py` | Weekly export (NEW) | B11 |
| `insights_archive.py` | Purge facts > retention (NEW) | B9 |
| `meta_ads_ops.py` | Create campaign/adset/ad payloads, templates (NEW) | B15 |
| `meta_creative_upload.py` | Graph ad creative + link `crm_creatives` (NEW) | B15 |
| `meta_ads_edit.py` | Update ad creative/copy Graph handlers (NEW) | B15 |

### 5.2. Python — jobs

| Handler | Job type | Interval |
|---------|----------|----------|
| `meta_insights_sync.py` | `meta_insights_sync` | Daily + manual |
| `meta_token_refresh.py` | `meta_token_refresh` | Timer |
| `capi_dispatch.py` | `capi_dispatch` | 5 min / event-driven |
| `meta_conversion_sync.py` | `meta_conversion_sync` | 60 min (B9) |
| `meta_alerts_eval.py` | `meta_alerts_eval` | Post-sync (B8) |
| `meta_intel_snapshot.py` | `meta_intel_snapshot` | Weekly (B11) |

### 5.3. NestJS — `services/ptt-crm-api/src/`

| Area | Files | Wave |
|------|-------|------|
| Hub | `agency/agency.service.ts`, `agency-ops.controller.ts` | H1 ✅ |
| Clients / sync | `agency/clients.controller.ts`, `agency-side-effects.service.ts` | ✅ |
| Webhook | `webhooks/meta-webhook.*` | H1 ✅ |
| Performance portal | `performance/*` | B6 ✅ |
| Campaign writes | `crm-campaign-writes/*` | B6 ✅ |
| Offboard | `agency/client-offboard.*` | B7 ✅ |
| Meta tracking API | `meta-tracking/*` (NEW) | B9 |
| Meta intelligence API | `meta-intelligence/*` (NEW) | B10–B11 |
| Meta alerts API | `meta-alerts/*` (NEW) | B8 |
| Meta ads ops API | `meta-ads-ops/*` (NEW) | B15 |

### 5.4. ops-web

| Route | Content | Wave |
|-------|---------|------|
| `/meta/facebook-ads` | Hub dashboard, filters, export | H1 ✅ |
| `/meta/migration` | Horizon 1 signoff panel | H1 ✅ |
| `/meta/ads-combined` | Meta + Google summary | B6 ✅ |
| `/meta/tracking` | CAPI health, rules, pixel test | B9 |
| `/meta/intelligence` | ROAS, anomaly, recommend | B10 |
| `/meta/alerts` | Alert inbox (optional B8) | B8 |
| `/meta/ads-ops` | Launch wizard create/mutate + deep link Ads Manager | B15 |
| `/agency/clients/:id` | Channels, sync insights, onboarding | ✅ |

### 5.5. portal-web

| Route | Content | Wave |
|-------|---------|------|
| `/meta` | `PerformancePanel` channel=meta | B6 ✅ |
| `/dashboard` | Combined KPI | B6 ✅ |

---

## 6. Personas, RBAC & governance

### 6.1. Personas (Meta Enterprise)

| Persona | Mục tiêu Meta | Surface |
|---------|---------------|---------|
| **Super Admin / GDKD** | Governance, approve write, rules | ops-web, caps approve |
| **Account Manager** | Client health, CPL, client report | Hub, portal notify |
| **Media Buyer** | Campaign map, sync, write submit, launch wizard | Hub, campaign-writes, `/meta/ads-ops` |
| **Tracking/Tech** | CAPI, pixel, rules, health | `/meta/tracking` |
| **Data/BI** | Export, snapshot, metrics | Hub export, B11 gzip |
| **Client Viewer** | Read-only performance | portal `/meta` |

### 6.2. Staff capability keys

| Cap key | Mô tả | Meta action |
|---------|-------|-------------|
| `crm_facebook_ads` | view | Hub, performance, alerts view |
| `crm_agency` configure | write | Channel accounts, map, rules, sync trigger |
| `meta_campaign_write` view | view | Campaign write hub list |
| `meta_campaign_write` approve | approve | Temporal execute Graph |
| `meta_ads_ops` submit | submit | Launch wizard create_* requests (B15) |
| `crm_board` edit | edit | Submit budget write |
| `portal_meta_readonly` | portal | Client JWT scope |

Seed: `scripts/seed_staff_meta_permissions.py`

### 6.3. Governance rules

1. **Campaign mutate** — luôn qua `campaign_write_requests` + Temporal; pilot allowlist `PTT_META_CAMPAIGN_WRITE_PILOT_*`.
2. **CAPI** — pilot `PTT_CAPI_PILOT_CLIENTS` → widen sau soak; stub flags staging only.
3. **Recommendations** — read-only; Buyer tạo write request từ UI Intelligence.
4. **Offboard** — block sync/CAPI/write; revoke vault; audit trail B7.
5. **Portal** — strict `client_id` JWT; cross-tenant 403 gate B6.
6. **Launch QA Meta gate** — không `launch_ready` nếu thiếu pixel/CAPI test/map (B9).
7. **Create ads (B15)** — chỉ qua `/meta/ads-ops` wizard + approve; không direct Graph từ UI khác.
8. **Edit creative/copy (B15 §8.9)** — chỉ `update_ad_creative` / `update_ad_copy` qua Edit mode + approve; creative swap bắt buộc `crm_creatives.status=approved`.

### 6.4. Ma trận quyền chi tiết (enterprise)

| Vai trò | Hub view | Map / sync | CAPI rules | Alerts ack | Write submit | Ads Ops create | Write approve | Portal |
|---------|:--------:|:----------:|:----------:|:----------:|:------------:|:--------------:|:-------------:|:------:|
| Super Admin | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | — |
| GDKD / Admin Meta | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | — |
| Account Manager | ✓ | ✓ client | view | ✓ | ✓ | ✓ | — | notify |
| Media Buyer | ✓ | ✓ client | view | ✓ | ✓ | ✓ | — | — |
| Tracking / Tech | ✓ | ✓ pixel | ✓ | ✓ | — | — | — | — |
| Data / BI | ✓ export | view | view | view | — | — | — | — |
| Client Viewer | — | — | — | — | — | — | — | ✓ read |
| Client Approver | — | — | — | — | — | — | — | ✓ creative |

**Cap enforcement:** Nest guards per route; ops-web `hasCap()` hide mutate controls.

---

## 7. Mô hình dữ liệu PostgreSQL

### 7.1. Bảng hiện có (reuse)

**`client_channel_accounts`** — registry Meta per client

| Column / meta JSON | Mô tả |
|--------------------|--------|
| `channel = 'meta'` | Meta ad account |
| `external_account_id` | `act_*` normalized |
| `access_token_encrypted` | Vault ciphertext |
| `token_status` | active / revoked / error |
| `meta.pixel_id`, `meta.facebook_page_id` | Tracking |
| `meta.capi_enabled` | B9 — enable CAPI |
| `meta.capi_test_event_code` | B10 — per account test |
| `meta.target_cpl_vnd` | Alert threshold |

**`daily_performance`** — fact table (thay `crm_meta_insights_daily`)

| Column | Meta-OS equivalent |
|--------|------------------|
| `performance_date` | `insight_date` |
| `external_campaign_id` | `meta_campaign_id` |
| `spend`, `impressions`, `clicks`, `reach` | Same |
| `leads_platform` | `leads_meta` |
| `leads_crm` | CRM count |
| `conversion_value` | ROAS numerator |
| `hub_campaign_map_id` | Hub attribution |
| `raw_insights` | `actions_json` / raw |

Unique: `(client_id, channel, external_campaign_id, performance_date)`

**`hub_campaign_map`** — campaign link (thay `crm_meta_campaign_links`)

| Column | Mô tả |
|--------|--------|
| `client_id`, `channel='meta'` | Scope |
| `external_campaign_id` | Meta campaign |
| `hub_campaign_id` | FK hub |
| `utm_campaign` | Match leads |
| `target_cpl_vnd` | Per-campaign target |
| `active` | Soft disable |

**`capi_event_log`** — outbound queue audit (thay `crm_meta_capi_events`)

**`metrics_snapshots`** — CPL, ROAS cached KPI

**`campaign_write_requests`** — write governance (thay `crm_meta_write_requests`)

**Mở rộng B15 — `action` values:**

| `action` | Graph | Wave |
|----------|-------|------|
| `pause` / `resume` | campaign/adset status | B6 ✅ |
| `budget_cap` | daily_budget update | B6 ✅ |
| `create_campaign` | `POST /act_{id}/campaigns` | B15 |
| `create_adset` | `POST /act_{id}/adsets` | B15 |
| `create_ad` | `POST /act_{id}/ads` | B15 |
| `duplicate_campaign` | copy campaign | B15 |
| `rename` | name + UTM validate | B15 |
| `update_ad_creative` | upload creative + `POST/PATCH` ad link | B15 |
| `update_ad_copy` | headline, primary_text, description, CTA | B15 |
| `update_adset_budget` | adset `daily_budget` | B15 |
| `update_adset_targeting` | geo, age, gender (preset hẹp) | B15 |
| `pause_ad` / `resume_ad` | ad `status` | B15 |
| `pause_adset` / `resume_adset` | adset `status` | B15 |

**`update_*` payload (B15 edit):** `old_value` / `new_value` JSON diff bắt buộc — audit + rollback reference.

**`object_type`:** `campaign` | `adset` | `ad` | `creative_link`

### 7.2. Bảng mới (DDL `docs/specs/2026-07-24-postgresql-ddl-v4-meta-enterprise.sql` — B8+)

**`meta_insights_sync_runs`** — audit sync (optional if not in job metadata)

**`meta_alerts`**

```sql
CREATE TABLE IF NOT EXISTS meta_alerts (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id       UUID NOT NULL REFERENCES clients (id) ON DELETE CASCADE,
    channel         VARCHAR(16) NOT NULL DEFAULT 'meta',
    external_campaign_id VARCHAR(128),
    alert_type      VARCHAR(64) NOT NULL,
    severity        VARCHAR(16) NOT NULL DEFAULT 'warning',
    metric_value    NUMERIC(18, 6),
    threshold_value NUMERIC(18, 6),
    message         TEXT NOT NULL DEFAULT '',
    performance_date DATE,
    dedupe_key      VARCHAR(255) NOT NULL,
    notified_at     TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT meta_alerts_dedupe UNIQUE (dedupe_key)
);
```

**`meta_conversion_rules`**

```sql
CREATE TABLE IF NOT EXISTS meta_conversion_rules (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id       UUID REFERENCES clients (id) ON DELETE CASCADE,
    lead_status     VARCHAR(64) NOT NULL,
    event_name      VARCHAR(64) NOT NULL,
    enabled         BOOLEAN NOT NULL DEFAULT TRUE,
    require_meta_attribution BOOLEAN NOT NULL DEFAULT TRUE,
    value_vnd       BIGINT NOT NULL DEFAULT 0,
    notes           TEXT NOT NULL DEFAULT '',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT meta_conversion_rules_uniq
        UNIQUE (COALESCE(client_id, '00000000-0000-0000-0000-000000000000'::uuid), lead_status, event_name)
);
```

**`meta_pixels`** (B11 multi-pixel)

```sql
CREATE TABLE IF NOT EXISTS meta_pixels (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_channel_account_id UUID NOT NULL REFERENCES client_channel_accounts (id) ON DELETE CASCADE,
    pixel_id                VARCHAR(64) NOT NULL,
    label                   VARCHAR(128) NOT NULL DEFAULT '',
    is_primary              BOOLEAN NOT NULL DEFAULT FALSE,
    capi_enabled            BOOLEAN NOT NULL DEFAULT TRUE,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (client_channel_account_id, pixel_id)
);
```

**`meta_intelligence_snapshots`** (B11) — metadata row + S3/path to gzip artifact

### 7.3. `event_id` convention (CAPI dedup — giữ Meta-OS)

| Nguồn | `event_id` |
|-------|------------|
| FB Lead webhook | `leadgen_{facebook_leadgen_id}` |
| CRM qualified | `crm_qualify_{lead_id}_{status_entered_at}` |
| CRM post_sale | `crm_purchase_{lead_id}_{deal_id_or_ts}` |
| Manual resend | `manual_{lead_id}_{uuid}` |

---

## 8. Luồng nghiệp vụ cốt lõi

### 8.1. Client onboarding Meta

1. AM tạo client → lifecycle onboarding widget (B6-S5).
2. Configure `client_channel_accounts` — ad account, page, pixel, OAuth or vault token.
3. `POST /api/v1/clients/:id/sync/insights` — backfill 35d.
4. Map campaigns → `hub_campaign_map` (manual + suggest job B8).
5. Launch QA checklist — pixel/CAPI test before `launch_ready` (B9).

### 8.2. Insights sync

**Trigger:** cron timer, post-map change (`agency-side-effects`), manual button.

**Flow:** `run_meta_insights_sync_job` → `sync_meta_insights()`:

1. Load accounts `channel=meta`, `token_status=active`.
2. Resolve token via vault; skip revoked/offboarded clients.
3. Target date T-1 ICT; reconcile 3d lookback.
4. Graph `level=campaign` (adset/ad B10/B11 flags).
5. Upsert `daily_performance`; join `hub_campaign_map`.
6. Recompute `leads_crm` from PG `crm_leads` (utm / external_campaign_id).
7. Enqueue `meta_alerts_eval` (B8).
8. Partial success per account.

### 8.3. Lead webhook → CRM → CAPI

1. Meta POST → Nest `meta-webhook` → normalize → insert lead PG.
2. Enqueue lead processing jobs (existing funnel).
3. If `PTT_CAPI_ENABLED` + client allowed → `capi_dispatch` job:
   - Build `user_data` hashed SHA-256
   - Insert `capi_event_log` idempotent
   - POST `/{pixel_id}/events`

### 8.4. CRM status → conversion (B9)

Hook Nest lead patch / funnel status change → `evaluate_conversion_rules()`:

| lead_status | event_name | Default |
|-------------|------------|---------|
| `new` | `Lead` | webhook only |
| `qualified` | `CompleteRegistration` | enabled |
| `post_sale` | `Purchase` | value from deal |

Cron `meta_conversion_sync` — backfill 72h.

### 8.5. Campaign write (existing B6-S4)

```
Submit write → pending_approval → meta_campaign_write approve
  → Temporal workflow → Graph API → executed
  → LaunchQaBudgetBridge → budget_confirmed tick
```

Extend B11: `object_type=adset` pause/resume.

### 8.6. Client offboard (B7)

`POST /api/v1/clients/:id/offboard` → revoke tokens, `tenant_locked`, cancel pending jobs, cancel onboarding workflow, follow-up audit.

### 8.7. Intelligence (B10–B11)

| Job | Logic |
|-----|--------|
| Anomaly | Median 7d spend/CPL per campaign; spike thresholds |
| Stat anomaly | z-score 14d (B11) |
| ROAS | SUM conversion_value / spend from `daily_performance` + CRM deals |
| Recommend | Read-only API; link to campaign write |
| Forecast | Linear 7d CPL slope (B11) |
| Snapshot | Weekly gzip to artifact store + digest hook |

### 8.8. Ads Ops launch wizard (B15)

**Route:** ops-web `/meta/ads-ops` · API `/api/v1/meta/ads-ops/*`

**Wizard 5 bước (template RE Lead mặc định):**

```
1. Client + channel account (validate token, offboard block)
2. Objective + budget (lifecycle budget brief pre-fill)
3. Creative — chọn crm_creatives approved → upload/link Graph
4. Tracking — pixel, page, CAPI test, hub map + UTM convention
5. Review → Launch QA checklist → submit campaign_write_requests (create_*)
   → meta_campaign_write approve → Temporal MetaCampaignCreateWorkflow → Graph
```

**Pre-flight (chặn submit nếu fail):**

| Check | Source |
|-------|--------|
| Pixel + page configured | `client_channel_accounts.meta` |
| CAPI test event OK (staging/prod) | tracking health |
| Hub campaign map or UTM auto | hub_campaign_map |
| Creative approved | `crm_creatives.status` |
| Client not tenant_locked | offboard B7 |
| Pilot allowlist (if enabled) | `PTT_META_ADS_OPS_PILOT_CLIENTS` |

**Không trong wizard (deep link Meta):**

- Audience builder phức tạp, Advantage+ full, catalog feed, dynamic creative matrix → nút **「Mở Ads Manager」** (`https://business.facebook.com/adsmanager/...`)

**Quyền Graph:** `ads_management` trên System User; token vault per client.

**Workflow mới:** Temporal `MetaCampaignCreateWorkflow` (create path, tách `CampaignWriteWorkflow` mutate B6).

### 8.9. Ads Ops edit flow — creative / copy (B15)

**Route:** ops-web `/meta/ads-ops?mode=edit` · hub row **Edit ad** · API `/api/v1/meta/ads-ops/edit/*`

**Entry points:**

| Nguồn | Hành vi |
|-------|---------|
| Hub campaign/ad row | Nút **Edit ad** → pre-fill `external_ad_id` |
| `/meta/ads-ops` tab **Edit** | Chọn client → campaign → ad từ insights ad-level (B11) |
| Alert `ad_disapproved` (B13) | CTA **Fix creative** → Edit mode với badge review |

**Edit wizard 4 bước:**

```
1. Chọn ad — validate client_id, offboard block, fetch Graph snapshot (read-only)
2. Creative / copy — swap crm_creatives approved HOẶC sửa headline / primary_text / CTA
3. Diff review — old_value vs new_value side-by-side; UTM/map unchanged warning
4. Submit → campaign_write_requests (update_ad_creative | update_ad_copy)
   → meta_campaign_write approve → Temporal CampaignWriteWorkflow (edit path) → Graph
```

**Pre-flight edit (chặn submit nếu fail):**

| Check | Source |
|-------|--------|
| Ad thuộc `client_id` + account active | Graph + `client_channel_accounts` |
| Creative swap: `crm_creatives.status=approved` | creatives inbox |
| Copy-only: không đổi landing URL ngoài allowlist | UTM convention validator |
| Ad `effective_status=DISAPPROVED` | Require AM ack checkbox |
| Client not tenant_locked | offboard B7 |
| Pilot allowlist (if enabled) | `PTT_META_ADS_OPS_PILOT_CLIENTS` |

**Bảng `update_*` actions (edit scope B15):**

| `action` | Graph API | `object_type` | Ghi chú |
|----------|-----------|---------------|---------|
| `update_ad_creative` | `POST /act_{id}/adcreatives` + `POST /{ad_id}` creative swap | `ad` | ME59 — link registry B12 |
| `update_ad_copy` | `POST /{ad_id}` với `creative` object fields | `ad` | ME59 — headline, message, CTA |
| `update_adset_budget` | `POST /{adset_id}` `daily_budget` | `adset` | Shortcut từ hub |
| `update_adset_targeting` | `POST /{adset_id}` targeting preset | `adset` | Geo/age/gender hẹp only |
| `pause_ad` / `resume_ad` | `POST /{ad_id}` status | `ad` | Granular vs campaign pause B6 |
| `pause_adset` / `resume_adset` | `POST /{adset_id}` status | `adset` | — |

**OUT edit (deep link Meta):** audience lookalike builder, catalog product set, dynamic creative matrix, Advantage+ budget automation.

**Workflow:** reuse `CampaignWriteWorkflow` mutate path (B6 extend) — **không** tách workflow riêng; `change_type` map → `action` enum.

**Post-execute:** refresh ad snapshot cache; nếu `ad_disapproved` alert open → auto-resolve khi status → PENDING_REVIEW/ACTIVE.

---

## 9. KPI dictionary & attribution

### 9.1. KPI codes (`kpi_definitions` / metrics engine)

| KPI code | Công thức | Nguồn |
|----------|-----------|--------|
| `META_SPEND_VND` | SUM(spend) | `daily_performance` |
| `META_LEADS_PLATFORM` | SUM(leads_platform) | Meta actions |
| `META_LEADS_CRM` | SUM(leads_crm) | PG leads |
| `META_CPL_CRM` | spend / NULLIF(leads_crm,0) | Derived |
| `META_CPA_PLATFORM` | spend / NULLIF(leads_platform,0) | Derived |
| `META_ROAS` | conversion_value / NULLIF(spend,0) | B10 — CRM revenue |
| `META_UNMAPPED_SPEND_PCT` | unmapped spend / total | B8 |
| `META_CAPI_MATCH_HINT` | sent / (sent+failed) | B9 health |

### 9.2. Lead attribution priority

1. `hub_campaign_map.utm_campaign` = lead `utm_campaign`
2. Lead `meta_json.campaign_id` / `external_campaign_id`
3. Fallback client-level Meta leads — flag **Unmapped**

### 9.3. Portal vs ops metrics

| Metric | ops-web hub | portal |
|--------|-------------|--------|
| Spend, CPL, delta | ✅ client + campaign rows | ✅ KPI cards + table |
| ROAS | B10 | B10 (hide if stub) |
| Raw campaign names | ✅ | ✅ limited |
| Write / rules | ✅ staff only | ❌ |
| Create ads wizard | ✅ staff B15 | ❌ |
| Edit ad creative/copy | ✅ staff B15 §8.9 | ❌ |

### 9.4. API contract — attribution metadata

Mọi response KPI (`/facebook-ads/hub`, `/portal/performance`, `/meta/roas`) **bắt buộc** gồm:

```json
{
  "attribution_model": "last_touch_crm",
  "unmapped_spend_pct": 6.2,
  "spend_source": "meta_api",
  "data_freshness": { "through_date": "2026-07-21", "synced_at": "2026-07-22T06:12:04+07:00" }
}
```

Chi tiết mô hình & giới hạn — §21.

---

## 10. API catalog (target)

**Prefix staff:** `/api/v1/` · **Portal:** `/api/v1/portal/` · **Webhooks:** `/api/v1/webhooks/meta`

### 10.1. Shipped ✅

| Method | Path | Cap |
|--------|------|-----|
| GET | `/facebook-ads/hub` | crm_facebook_ads view |
| GET | `/facebook-ads/hub/export` | view |
| GET | `/facebook-ads/migration-status` | view |
| POST | `/clients/:id/sync/insights` | crm_agency configure |
| GET/PATCH | `/clients/:id/channel-accounts` | configure |
| POST | `/clients/:id/offboard` | configure + audit |
| GET | `/portal/performance?channel=meta` | portal JWT |
| GET | `/portal/performance/export.csv` | portal |
| POST | `/webhooks/meta` | Meta signature |
| GET/POST | `/crm/campaign-writes/*` | meta_campaign_write |

### 10.2. B8 — Measurement enforce

| Method | Path | Mô tả |
|--------|------|--------|
| GET | `/meta/alerts` | List deduped alerts |
| PATCH | `/meta/alerts/:id/ack` | Acknowledge |
| POST | `/meta/hub-campaign-map/suggest` | Auto-map UTM/name |
| GET | `/meta/sync/status` | Last job per client |
| PATCH | `/clients/:id/channel-accounts/:accId/alert-config` | CPL targets |

### 10.3. B9 — Conversion OS

| Method | Path | Mô tả |
|--------|------|--------|
| GET | `/meta/capi/events` | `capi_event_log` list |
| POST | `/meta/capi/events/:id/retry` | Re-queue failed |
| POST | `/meta/capi/flush` | Manual dispatch |
| GET/POST/PATCH | `/meta/conversion-rules` | Rules CRUD |
| GET | `/meta/tracking/health` | 7d rolling stats |
| POST | `/clients/:id/channel-accounts/:accId/test-pixel` | Graph probe |

### 10.4. B10 — Intelligence

| Method | Path | Mô tả |
|--------|------|--------|
| GET | `/meta/anomalies` | Median spikes |
| GET | `/meta/roas` | ROAS series |
| GET | `/meta/budget-recommendations` | Read-only |
| GET | `/meta/insights/daily?level=adset` | Extended facts |

### 10.5. B11 — Advanced

| Method | Path | Mô tả |
|--------|------|--------|
| GET | `/meta/anomalies?mode=stat` | z-score |
| GET | `/meta/forecast` | CPL/spend trend |
| GET/POST/PATCH | `/meta/pixels` | Multi-pixel CRUD |
| POST | `/meta/intelligence/snapshot` | Manual export |

### 10.6. B8.1 / B10 / B14 — Enterprise APIs

| Method | Path | Wave | Mô tả |
|--------|------|------|--------|
| GET | `/meta/insights/breakdown` | B8.1 | Breakdown dimensions |
| GET | `/meta/budget-pacing` | B10 | Pacing vs monthly cap |
| GET | `/meta/lead-quality` | B10 | Junk rate, win rate |
| GET | `/portal/reports/meta/weekly` | B10 | Latest PDF metadata |
| POST | `/portal/reports/meta/weekly/generate` | B10 | Manual regen (staff) |
| GET | `/meta/compliance/export` | B14 | Compliance bundle |
| GET | `/metrics/cross-channel/summary` | B14 | Meta + Google unified |

### 10.7. B15 — Ads Ops UI

| Method | Path | Mô tả |
|--------|------|--------|
| GET | `/meta/ads-ops/templates` | Lead/RE launch templates (objective, budget defaults) |
| GET | `/meta/ads-ops/preflight` | Launch QA checklist status per client/account |
| POST | `/meta/ads-ops/creative/upload` | Upload/link approved `crm_creatives` → Graph ad creative |
| POST | `/meta/ads-ops/launch` | Submit `campaign_write_requests` (`create_*`) after preflight |
| GET | `/meta/ads-ops/requests/:id` | Poll create workflow status |
| GET | `/meta/ads-ops/deep-link` | Ads Manager URL for account/campaign (audience/catalog OUT) |
| GET | `/meta/ads-ops/edit/snapshot` | Current ad creative/copy from Graph (cached 5m) |
| POST | `/meta/ads-ops/edit/submit` | Submit `update_*` write request after diff review |
| GET | `/meta/ads-ops/edit/preflight` | Edit-specific checks (approved creative, disapproved ack) |

**Reuse B6:** `GET/POST/PATCH /crm/campaign-writes/*` — approve + Temporal execute create **and edit** paths.

---

## 11. UI — ops-web & portal

### 11.1. ops-web `/meta/facebook-ads` (enhanced B8)

**Layout target:**

```
┌─────────────────────────────────────────────────────────────────┐
│ Meta Ads Hub          [Export CSV] [Migration status]           │
├─────────────────────────────────────────────────────────────────┤
│ Filters: Client · Date · Status · Search                        │
├──────────┬──────────┬──────────┬──────────┬─────────────────────┤
│ Spend    │ Leads CRM│ CPL      │ Unmapped │ Alerts              │
├──────────┴──────────┴──────────┴──────────┴─────────────────────┤
│ Tabs: [Clients] [Campaigns] [Alerts] [Tracking] [Intelligence]  │
├─────────────────────────────────────────────────────────────────┤
│ Table rows + drill → client detail / campaign map               │
└─────────────────────────────────────────────────────────────────┘
```

**Badges:** Unmapped spend · Token error · Tenant locked · CAPI OK / Thiếu pixel

### 11.2. `/meta/ads-ops` (B15)

**Tabs:** `[Launch]` · `[Edit]` · deep link Ads Manager

**Layout target — launch wizard (tab Launch):**

```
┌─────────────────────────────────────────────────────────────────┐
│ Meta Ads Ops          [Open in Ads Manager ↗]                   │
├─────────────────────────────────────────────────────────────────┤
│ Step 1 Client · 2 Objective · 3 Creative · 4 Tracking · 5 Review│
├─────────────────────────────────────────────────────────────────┤
│ Preflight checklist (Launch QA B9): pixel · CAPI test · map     │
│ Creative picker — approved crm_creatives only                   │
│ Budget brief pre-fill from lifecycle (optional)                 │
├─────────────────────────────────────────────────────────────────┤
│ [Submit for approval] → campaign_write_requests → approve hub   │
└─────────────────────────────────────────────────────────────────┘
```

**Mutate shortcuts (B6 reuse):** pause/resume/budget cap từ hub row → campaign-writes hub (không qua full wizard).

**Layout target — edit mode (tab Edit, §8.9):**

```
┌─────────────────────────────────────────────────────────────────┐
│ Meta Ads Ops · Edit     [Open in Ads Manager ↗]                 │
├─────────────────────────────────────────────────────────────────┤
│ Ad picker: Client · Campaign · Ad (ad-level insights B11)       │
├─────────────────────────────────────────────────────────────────┤
│ Left: current snapshot (headline, image, CTA, status)           │
│ Right: new creative (crm_creatives) OR copy fields              │
├─────────────────────────────────────────────────────────────────┤
│ Diff panel · disapproved ack (if needed) · preflight checklist  │
│ [Submit for approval] → campaign_write_requests (update_*)      │
└─────────────────────────────────────────────────────────────────┘
```

Hub row actions: **Edit ad** · Pause · Budget (B6) · Open in Ads Manager.

**OUT in UI:** audience builder, catalog, Advantage+ matrix → deep link only.

### 11.3. `/meta/tracking` (B9)

- Health cards: sent/failed/skipped 7d, avg latency
- Account/pixel table + test pixel button
- Conversion rules CRUD (admin)

### 11.4. `/meta/intelligence` (B10)

- ROAS KPI, anomaly table, budget recommendations
- CTA → create campaign write request (link B6 hub)

### 11.5. portal `/meta` (B6-S7 ✅ + B10)

- KPI cards, CPL vs target delta, performance table
- Export CSV; PDF stub; `roas_stub` hide when real ROAS B10

---

## 12. Jobs, workers & scheduler

### 12.1. Job types

| job_type | Handler | Trigger |
|----------|---------|---------|
| `meta_insights_sync` | `ptt_jobs/handlers/meta_insights_sync.py` | Cron, manual, post-map |
| `meta_token_refresh` | `meta_token_refresh.py` | systemd timer |
| `capi_dispatch` | `capi_dispatch.py` | Lead created, cron 5m |
| `meta_conversion_sync` | NEW B9 | Hourly |
| `meta_alerts_eval` | NEW B8 | Post insights sync |
| `meta_insights_archive` | NEW B9 | Weekly |
| `meta_intel_snapshot` | NEW B11 | Weekly |
| `meta_campaign_create` | Temporal create workflow (NEW) | B15 on approve |

### 12.2. systemd / timers (VPS)

| Unit | Mô tả |
|------|--------|
| `ptt-meta-insights.timer` | Daily insights |
| `ptt-meta-token-refresh.timer` | Token rotate |
| `ptt-lead-created-capi.timer` | CAPI drain |
| `ptt-horizon1-meta-soak.timer` | Migration evidence |
| `ptt-worker.service` | Job consumer |

### 12.3. Idempotency keys

| Job | Key pattern |
|-----|-------------|
| insights | `meta_insights_sync:{client_id}:{date}` |
| capi | `(client_id, event_id, event_name)` DB unique |
| snapshot | `meta_intel_snapshot:{client_id}:{week}` |

---

## 13. Alerts, digest & observability

### 13.1. Alert catalog (`meta_alerts.alert_type`)

| alert_type | Wave | Điều kiện |
|------------|------|-----------|
| `cpl_high` | B8 | CPL CRM > target × (1 + pct/100) |
| `cpa_platform_high` | B8 | CPA platform > target |
| `sync_failed` | B8 | Account token error >24h |
| `unmapped_spend_high` | B8 | Unmapped > 15% spend |
| `capi_fail_rate` | B9 | failed/(sent+failed) > 10% / 24h |
| `pixel_missing` | B9 | capi_enabled without pixel |
| `capi_stale` | B9 | No sent 48h + new leads |
| `spend_spike` | B10 | > median × spike_pct |
| `cpl_spike` | B10 | CPL spike + leads ≥ 2 |
| `roas_low` | B10 | ROAS < target, spend > min |
| `spend_zscore` / `cpl_zscore` | B11 | z > threshold |
| `budget_pace_high` | B10 | Spend > monthly cap × pace_pct | Tier A |
| `budget_pace_low` | B10 | Spend < expected pace (under-delivery) | Tier A |
| `creative_fatigue` | B10 | frequency > threshold + CTR drop | Tier A |
| `lead_quality_low` | B10 | junk rate > threshold | Tier A |
| `match_quality_low` | B9 | EM match rate hint < 70% | Tier A |
| `meta_account_disabled` | B13 | Graph account_status ≠ ACTIVE | Tier B |
| `ad_disapproved` | B13 | Ad effective_status DISAPPROVED | Tier B |

**Dedupe:** `{alert_type}:{client_id}:{campaign_id}:{date}`

### 13.2. Notification channels

| Channel | Audience | Wave |
|---------|----------|------|
| Hub inline alerts | Staff | H1 ✅ |
| `meta_alerts` inbox | Staff | B8 |
| Owner weekly pack | GDKD | B10 |
| Portal email webhook | Client AM | B6 optional |
| Slack (reuse SEO pattern) | Ops | B10 optional |

### 13.3. Observability

- **Sentry** — Nest + portal (`SENTRY_DSN`)
- **Horizon soak** — `.local-dev/horizon1-meta-ads-soak-evidence.jsonl`
- **Gate reports** — `wave_b8_gates.py` … `wave_b11_gates.py`, `wave_b15_gates.py` (NEW)
- **Job queue depth** — agency stats API

---

## 14. Wave B8–B15 — lộ trình thực thi

| Wave | Tuần | Meta-OS / Tier | DoD summary |
|------|------|----------------|-------------|
| **B8** Measurement parity | 3–4 | P1 | Alerts PG, map suggest/enforce, sync status API, hub badges |
| **B8.1** Breakdown + RBAC | 2 | Tier A | Placement/device/age facts; granular caps |
| **B9** Conversion OS | 4–5 | P2 | Full CAPI rules, tracking UI, Launch QA Meta gate, archive |
| **B10** Intelligence | 4–5 | P3 + Tier A | Anomaly, ROAS, recommend, pacing, lead quality, client report |
| **B11** Advanced | 3–4 | P4 | z-score, multi-pixel, forecast, snapshot, digest |
| **B12** Creative link | 3 | Agency | ad_id ↔ creative asset registry |
| **B13** Meta webhooks ops | 3–4 | Tier B | Account/ad status webhooks, proactive alerts |
| **B14** Warehouse BI | 4–6 | Tier B | ClickHouse facts, Grafana executive, hourly sync option |
| **B15** Ads Ops UI | 8–12 | Tier A | Launch wizard create, **edit creative/copy**, mutate extend, Temporal workflows |

**Tiên quyết B15:** B9 Launch QA gate ✅ · B12 creative registry (partial OK) · B6 write approve ✅ · token `ads_management`.

**Tiên quyết mỗi wave:** prior wave gates PASS + prod soak ≥7d.

**Không ship B10** trước khi CAPI soak ≥30d (khuyến nghị Meta-OS P3).

**Tier C (ML/MMM/creative automation at scale)** — explicit OUT until separate product charter (§26.3).

---

## 15. Ma trận deliverables ME1–ME35 (core)

> Enterprise extensions **ME36–ME61** — §27.

| ID | Deliverable | Meta-OS | Wave | Owner module |
|----|-------------|---------|------|--------------|
| ME1 | PG channel registry | M2 | H1 ✅ | agency.repository |
| ME2 | Insights → daily_performance | M3 | H1 ✅ | ptt_meta/insights_sync |
| ME3 | Hub staff UI + export | M4 | H1 ✅ | ops-web meta hub |
| ME4 | CPL / hub summary API | M5 | H1 ✅ | agency.service hub |
| ME5 | Campaign hub map | M6 | H1 ✅ | hub_campaign_map |
| ME6 | Token vault + refresh | M9 | H1 ✅ | token_vault |
| ME7 | Nest Meta webhook | — | H1 ✅ | meta-webhook |
| ME8 | Portal Meta performance | — | B6 ✅ | portal performance |
| ME9 | Campaign write Temporal | M18–M19 | B6 ✅ | crm-campaign-writes |
| ME10 | Client offboard Meta | — | B7 ✅ | client-offboard |
| ME11 | meta_alerts table + eval | M7 | B8 | ptt_meta/alerts |
| ME12 | Map suggest + enforce UX | M6 | B8 | Nest + ops-web |
| ME13 | Sync status API | M8 | B8 | agency-ops |
| ME14 | Alert config per account | M7 | B8 | clients API |
| ME15 | conversion_rules PG + engine | M12 | B9 | ptt_meta/conversion_rules |
| ME16 | CAPI full pipeline | M11 | B9 | capi_dispatch extend |
| ME17 | Tracking health UI/API | M14 | B9 | meta-tracking module |
| ME18 | Insights archive job | M15 | B9 | insights_archive |
| ME19 | conversion_sync cron | M16 | B9 | conversion_sync |
| ME20 | Anomaly median | M20 | B10 | ptt_meta/anomaly |
| ME21 | ROAS CRM engine | M21 | B10 | ptt_meta/roas |
| ME22 | Budget recommend API | M22 | B10 | budget_recommend |
| ME23 | Ad set insights level | M23 | B10 | insights_sync flag |
| ME24 | CAPI test code per account | M24 | B10 | channel meta JSON |
| ME25 | Write adset approval | M25 | B10 | campaign-writes extend |
| ME26 | Statistical anomaly | M26 | B11 | anomaly_stat |
| ME27 | Multi-pixel table | M27 | B11 | meta_pixels |
| ME28 | Ad-level insights | M28 | B11 | insights_sync |
| ME29 | CPL forecast API | M29 | B11 | forecast |
| ME30 | Intelligence snapshot job | M30 | B11 | intelligence_snapshot |
| ME31 | Digest intelligence block | M31 | B11 | owner-weekly hook |
| ME32 | Launch QA Meta checklist | Agency | B9 | launch-qa |
| ME33 | Combined ads dashboard | — | B6 ✅ | ads-combined |
| ME34 | Horizon Flask retire | — | H1 🟡 | nginx redirect |
| ME35 | wave gates B8–B11 | M10 | B8+ | ptt_crm/wave_b8_gates.py |

---

## 16. Yêu cầu phi chức năng

### 16.1. SLO (service level objectives)

| Metric | Target | Tier |
|--------|--------|------|
| Insights sync complete | Before 08:00 ICT | Standard |
| Insights sync success rate | ≥95% accounts / 30 rolling days | Standard |
| Webhook ingest latency | p95 < 3s | Standard |
| CAPI dispatch latency | p95 < 5min from lead | Standard |
| Hub API availability | 99.5% monthly | Standard |
| Portal performance API | 99.5% monthly | Standard |
| CAPI backlog drain | pending >100 → page ops within 4h | Enterprise |
| Sync lag alert | No account >36h stale when enabled | Enterprise |
| Client report delivery | Scheduled report ±15min slot | Enterprise |

Chi tiết SLA hợp đồng & escalation — §24.

### 16.2. Security

| ID | Requirement |
|----|-------------|
| SEC-M1 | Tokens encrypted at rest (`PTT_TOKEN_VAULT_KEY`) |
| SEC-M2 | PII CAPI SHA-256 only; no plaintext in logs |
| SEC-M3 | Webhook HMAC verify Meta signature |
| SEC-M4 | Portal JWT scoped `client_id`; cross-tenant 403 |
| SEC-M5 | Staff caps on all mutate routes |
| SEC-M6 | Offboard revokes tokens immediately |
| SEC-M7 | Cron/internal routes require `PTT_CRM_INTERNAL_KEY` or worker context |
| SEC-M8 | Consent basis logged before CAPI send (lead source + timestamp) | B9 |
| SEC-M9 | Right-to-erasure: offboard purges vault; capi log anonymize after retention | B7/B9 |
| SEC-M10 | Audit export JSON for compliance review (staff-only) | B14 |

### 16.3. Performance & retention

| Item | Policy |
|------|--------|
| `daily_performance` retention | 400 days active; archive gzip B9 |
| `capi_event_log` retention | 180 days |
| `meta_alerts` retention | 90 days |
| Insights sync stagger | 2s between accounts |
| Graph rate limit | Circuit breaker reuse `ptt_channel` |
| `daily_performance_breakdown` retention | 180 days (Tier A) | B8.1 |
| ClickHouse facts retention | 36 months (Tier B) | B14 |

### 16.4. Feature flags (master)

| Variable | Default | Wave |
|----------|---------|------|
| `PTT_META_INSIGHTS_SYNC` | `1` prod | H1 |
| `PTT_META_INSIGHTS_STUB` | `0` prod | staging |
| `PTT_CAPI_ENABLED` | `0` → `1` | B9 widen |
| `PTT_CAPI_PILOT_CLIENTS` | uuid list | pilot |
| `PTT_CAPI_STUB` | `0` prod | |
| `PTT_META_ALERTS_ENABLED` | `0` → `1` | B8 |
| `PTT_META_ANOMALY_ENABLED` | `0` → `1` | B10 |
| `PTT_META_ROAS_ENABLED` | `0` → `1` | B10 |
| `PTT_META_INTEL_SNAPSHOT_ENABLED` | `0` | B11 |
| `PTT_META_INSIGHTS_LEVEL` | `campaign` | adset/ad B10/B11 |
| `PTT_META_INSIGHTS_RETENTION_DAYS` | `400` | B9 |
| `PTT_FLASK_META_ADS_ADMIN_RETIRED` | `0` → `1` | H1 |
| `PTT_WEBHOOKS_NEST_META` | `1` | H1 |
| `PTT_META_INSIGHTS_BREAKDOWN` | `0` | B8.1 |
| `PTT_META_BUDGET_PACING_ENABLED` | `0` | B10 |
| `PTT_META_CLIENT_REPORT_WEEKLY` | `0` | B10 |
| `PTT_META_INSIGHTS_HOURLY` | `0` | B14 |
| `PTT_META_WAREHOUSE_EXPORT` | `0` | B14 |
| `PTT_META_OPS_WEBHOOKS` | `0` | B13 |
| `PTT_META_ADS_OPS_ENABLED` | `0` | B15 |
| `PTT_META_ADS_OPS_PILOT_CLIENTS` | uuid list | B15 pilot |

Env templates: `deploy/env.horizon1-meta-ads.example`, `deploy/env.meta-campaign-write-pilot.example`, **`deploy/env.meta-enterprise-b8.example`** (NEW).

---

## 17. Triển khai, gates & rollback

### 17.1. DDL apply order

```bash
cd /path/to/PTTADS
psql "$DATABASE_URL" -f docs/specs/2026-07-17-postgresql-ddl-v1.sql
# … v3-leads-oltp, v3-performance (required)
# B8+:
psql "$DATABASE_URL" -f docs/specs/2026-07-24-postgresql-ddl-v4-meta-enterprise.sql
```

Script: `./scripts/apply_pg_ddl_v4_meta_enterprise.sh` (NEW)

### 17.2. Gate scripts

| Wave | Gate module | Shell |
|------|-------------|-------|
| Horizon 1 | `horizon1_meta_ads_gates.py` | `horizon1_meta_ads_pack.sh` |
| B8 | `wave_b8_gates.py` | `wave_b8_gate.sh` |
| B9 | `wave_b9_gates.py` | `wave_b9_gate.sh` |
| B10 | `wave_b10_gates.py` | `wave_b10_gate.sh` |
| B11 | `wave_b11_gates.py` | `wave_b11_gate.sh` |
| B8.1 | `wave_b8_1_gates.py` | `wave_b8_1_gate.sh` |
| B12–B14 | `wave_b12_gates.py` … | `wave_b12_gate.sh` … |
| B15 | `wave_b15_gates.py` | `wave_b15_gate.sh` |

### 17.3. Rollback

| Tắt | Effect |
|-----|--------|
| `PTT_META_ALERTS_ENABLED=0` | Stop new alerts; keep table |
| `PTT_CAPI_ENABLED=0` | Stop enqueue; pending log kept |
| `PTT_META_ANOMALY_ENABLED=0` | Skip eval; dashboard hide tab |
| Revert nginx Flask hub | Emergency only — runbook H1 |
| DDL rollback | Forward-only migrations; feature flags preferred |
| `PTT_META_ADS_OPS_ENABLED=0` | Hide wizard; block create submit API |

Runbooks: [`runbooks/vps-production-operations.md`](runbooks/vps-production-operations.md) · [`runbooks/meta-insights-replay.md`](runbooks/meta-insights-replay.md) · [`runbooks/meta-token-refresh.md`](runbooks/meta-token-refresh.md)

---

## 18. Tiêu chí nghiệm thu theo wave

### B8 — Measurement parity

1. ≥2 clients insights backfill 7d; spend ±1% Ads Manager
2. `meta_alerts` created for CPL high test case; dedupe works
3. Hub shows unmapped spend %; suggest map inserts rows
4. Sync status API reflects last job outcome
5. Regression: H1 gates + webhook + insights tests pass

### B9 — Conversion OS

1. Webhook lead → CAPI `Lead` in Events Manager <5min (pilot client)
2. Status qualified → `CompleteRegistration` per rule
3. Tracking tab: sent/failed 7d; pixel test OK
4. CAPI fail rate alert fires on synthetic failures
5. Archive job dry-run logs rows >400d
6. Prod widen after 30d pilot soak

### B10 — Intelligence

1. Anomaly fires on synthetic spike; disabled flag skips
2. ROAS matches manual calc from deals sample
3. Budget recommend returns read-only; no Graph mutate
4. Ad set insights rows when `PTT_META_INSIGHTS_LEVEL=adset`
5. Portal shows ROAS when not stub

### B11 — Advanced

1. z-score anomaly distinct from median
2. Multi-pixel primary routes CAPI correctly
3. Forecast API returns slope + 7d projection
4. Weekly snapshot gzip produced; digest block in owner weekly
5. Full regression B8–B11 gates PASS

### B8.1 — Breakdown & RBAC

1. Breakdown rows for ≥1 campaign × publisher_platform
2. API filter returns spend subset ≈ campaign total ±2%
3. Buyer role cannot approve write; Tracking can edit rules

### B10 — Intelligence (+ Tier A)

6. Budget pacing alert on synthetic over-cap
7. Weekly PDF report generated for pilot client
8. Lead quality KPI visible on hub

### B13 — Meta ops webhooks

1. Simulated account disabled → alert + hub badge within 15min

### B14 — Warehouse BI

1. ClickHouse row count ≈ PG sample for 7d
2. Grafana dashboard renders spend trend
3. Compliance export JSON validates schema

### B15 — Ads Ops UI

1. Launch wizard E2E: approved creative → preflight pass → submit `create_campaign` → approve → Temporal → Graph campaign id returned
2. Preflight blocks submit when pixel missing or client `tenant_locked`
3. Mutate path (pause/budget) unchanged — B6 regression pass
4. Creative upload links `crm_creatives.id` → Graph `creative_id` in registry (B12 bridge)
5. Deep link Ads Manager opens correct `act_*` account
6. Pilot allowlist enforced when `PTT_META_ADS_OPS_PILOT_CLIENTS` set
7. `wave_b15_gates.py` PASS + B6–B9 regression
8. Edit E2E: swap approved creative → `update_ad_creative` → approve → Graph ad reflects new asset
9. Copy edit: `update_ad_copy` headline change → diff stored in `old_value`/`new_value`
10. Unapproved creative swap blocked; disapproved ad requires ack checkbox
11. Hub **Edit ad** opens Edit tab with pre-filled ad id

---

## 19. Rủi ro & giảm thiểu

| Rủi ro | Giảm thiểu |
|--------|------------|
| Dual maintenance Flask + Nest Meta | H1 retire Flask admin; no new Flask Meta code |
| SQLite vs PG drift | PG-only policy for Meta Enterprise |
| CAPI match rate thấp | require_meta_attribution; Launch QA pixel gate; §21 |
| ROAS sai do deal value thiếu | Validate `meta_json` deal fields; stub flag portal; §21 limits |
| Write API pause nhầm | Temporal + pilot allowlist + approve cap |
| Scope B8–B15 cùng lúc | Strict wave gates; 7d soak each; Tier C OUT |
| Token leak | Vault + revoke on offboard |
| Graph rate limit | Stagger sync; job retry with backoff |
| Over-promise vs Skai/Smartly | §20 positioning; Tier C separate charter |
| Client report SLA miss | B10 scheduled job + retry + ops alert |
| Meta ad review reject sau create | Wizard disclaimer; alert `ad_disapproved` B13; AM retry via Ads Manager deep link |
| Create sai objective/budget | Launch QA preflight + approve gate; template locked RE Lead; audit payload JSON |
| Swap creative nhầm ad/client | Graph ownership check + client_id guard; diff review mandatory |
| Copy edit trigger re-review | Disclaimer + `ad_disapproved` alert hook B13; AM notified |

---

## 20. Định vị cạnh tranh & market tier

### 20.1. Chúng ta là gì / không phải gì

| PTTADS Meta Enterprise **là** | PTTADS Meta Enterprise **không phải** |
|-------------------------------|--------------------------------------|
| Agency operating system — module Meta gắn CRM + lifecycle | SaaS Skai/Smartly thay Ads Manager |
| Closed-loop: spend → lead → deal → ROAS → governed write | Tool reporting thuần (Supermetrics-only) |
| Multi-client hub + client portal + offboard | Single-project CRM tab (Meta-OS PTT Flask) |
| Human-in-the-loop intelligence + Temporal approval | Auto-bidding / ML optimizer không kiểm soát |
| Vertical RE / agency VN — consent + CAPI + audit | Global MMM / incrementality platform |

### 20.2. Bản đồ cạnh tranh (4 tầng)

```text
T4  Creative automation & cross-channel orchestration — Skai, Smartly, Adobe
T3  Measurement + attribution — Northbeam, Triple Whale (partial)
T2  Agency reporting + multi-client — Supermetrics, AgencyAnalytics, Whatagraph
T1  CRM-attached Meta ops — PTTADS Meta Enterprise (target post B11 + Tier A)
T0  Meta Ads Manager / Business Suite — không thay thế
```

**Sau B11 + Tier A + B15:** đạt **T1+ (strong)** — vượt T2 trên CRM loop, governance, governed create & edit creative/copy; **chưa** cạnh T4.

### 20.3. Ma trận capability vs đối thủ (target v1.2.1)

| Capability | Supermetrics | Skai | PTTADS target |
|------------|:------------:|:----:|:-------------:|
| Multi-client hub | ✅ | ✅ | ✅ |
| CRM closed-loop ROAS | ❌ | partial | ✅ B10 |
| CAPI + CRM conversions | ❌ | ✅ | ✅ B9 |
| Governed campaign write (mutate) | ❌ | ✅ | ✅ B6 |
| **Create campaign/ad (governed wizard)** | ❌ | ✅ | ✅ **B15** |
| **Edit ad creative/copy (governed)** | ❌ | partial | ✅ **B15 §8.9** |
| **Edit budget/pause in-app** | ❌ | ✅ | ✅ B6 + B15 shortcuts |
| Client portal | ✅ | ✅ | ✅ B6 |
| Launch QA / offboard | ❌ | partial | ✅ B7/B9 |
| Breakdown insights | ✅ | ✅ | ✅ B8.1 |
| White-label scheduled report | ✅ | ✅ | ✅ B10 |
| ML budget optimizer | ❌ | ✅ | ❌ Tier C OUT |
| Creative DAM at scale | ❌ | ✅ | partial B12 + B15 upload |

### 20.4. Moat (lợi thế cạnh tranh)

1. **Một stack** với SEO OS, Email OS, Google hub, CRM funnel, RE lifecycle.
2. **Offboard tự động** — token revoke + job cancel (hiếm ở tool reporting).
3. **ROAS từ deal CRM thật** — không chỉ pixel purchase.
4. **Approval culture** — phù hợp agency VN / compliance client BĐS.
5. **Governed launch wizard** — creative approved + Launch QA trước Graph create (B15).
6. **Governed edit path** — CRM creative approval + diff audit trước swap/copy (B15 §8.9).

### 20.5. PTTADS vs Meta native (Ads Manager)

| Tác vụ | PTTADS | Meta Ads Manager |
|--------|:------:|:----------------:|
| View performance / CPL / ROAS | ✅ hub + portal | ✅ |
| Governed pause / budget cap | ✅ B6 | ✅ (no CRM audit) |
| Create campaign/ad (RE Lead template) | ✅ **B15 wizard** | ✅ full UI |
| Edit ad creative / copy | ✅ **B15 Edit** | ✅ full UI |
| Edit audience lookalike / catalog | ❌ deep link | ✅ |
| Catalog / dynamic creative matrix | ❌ deep link | ✅ |
| Advantage+ full setup | ❌ deep link | ✅ |
| CRM creative approval → launch | ✅ B15 | ❌ native |
| Launch QA + CAPI gate before create | ✅ B9+B15 | partial |
| Multi-client agency hub | ✅ | ❌ per account |

---

## 21. Attribution — mô hình & giới hạn

### 21.1. Mô hình mặc định (v1)

**Last-touch hợp nhất CRM + Meta**, ưu tiên thứ tự:

1. `hub_campaign_map.utm_campaign` = lead `utm_campaign`
2. Lead `meta_json.campaign_id` / `external_campaign_id`
3. Lead `source` ∈ meta/facebook + `client_id` — **Unmapped** (badge + alert)

**Spend:** `daily_performance.spend` (Meta API T-1, reconcile 3d).

**CPL CRM:** `spend / leads_crm` — leads loại junk/spam/duplicate theo CRM rules.

**ROAS CRM:** `SUM(deal_value_vnd post_sale) / spend` — deal value từ `meta_json` hoặc conversion rule `value_vnd`.

### 21.2. Giới hạn trung thực (không over-promise)

| Chủ đề | Hỗ trợ v1 | Không hỗ trợ v1 |
|--------|-----------|-----------------|
| View-through attribution | ❌ | Multi-touch MMM |
| Cross-device identity graph | ❌ | CDP enterprise |
| Incrementality / lift test | ❌ | Geo holdout experiments |
| iOS ATT gap | Partial — CAPI + webhook | 100% user-level match |
| Offline call / walk-in | 🔲 Tier A optional | Full call tracking suite |
| Google + Meta unified attribution | Combined dashboard B14 | Single identity graph |

**UI / portal:** mọi ROAS/CPL hiển thị **`attribution_model: last_touch_crm`** và `unmapped_spend_pct`.

### 21.3. Event Match Quality (EMQ)

B9+ Tracking health hiển thị:

- CAPI sent/failed/skipped 7d
- Proxy match hint từ Meta diagnostics API (khi có quyền)
- Alert `match_quality_low` khi hint < 70%

Không cam kết số EMQ khớp 100% Events Manager — mục tiêu **≥80% lead có CAPI sent 24h** (pilot → prod).

---

## 22. Insights breakdown & granularity

### 22.1. Granularity levels

| Level | Env | Wave | Table |
|-------|-----|------|-------|
| `campaign` | default | H1 ✅ | `daily_performance` |
| `adset` | `PTT_META_INSIGHTS_LEVEL=adset` | B10 | same + `insight_level` column |
| `ad` | `PTT_META_INSIGHTS_LEVEL=ad` | B11 | same |
| `breakdown` | `PTT_META_INSIGHTS_BREAKDOWN=1` | B8.1 | `daily_performance_breakdown` |

### 22.2. Breakdown dimensions (B8.1 — Tier A)

Graph API `breakdowns` bắt buộc Phase 1:

| Dimension | Buyer use case |
|-----------|----------------|
| `publisher_platform` | FB vs IG |
| `platform_position` | Feed, Stories, Reels |
| `age` | Audience skew |
| `gender` | Creative targeting review |
| `device_platform` | Mobile vs desktop |
| `country` | Optional — multi geo pilot |

**Schema `daily_performance_breakdown`:**

```sql
CREATE TABLE IF NOT EXISTS daily_performance_breakdown (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id           UUID NOT NULL REFERENCES clients (id) ON DELETE CASCADE,
    channel             VARCHAR(16) NOT NULL DEFAULT 'meta',
    external_campaign_id VARCHAR(128) NOT NULL,
    performance_date    DATE NOT NULL,
    breakdown_type      VARCHAR(32) NOT NULL,
    breakdown_value     VARCHAR(64) NOT NULL,
    spend               NUMERIC(18, 2) NOT NULL DEFAULT 0,
    impressions         BIGINT NOT NULL DEFAULT 0,
    clicks              BIGINT NOT NULL DEFAULT 0,
    leads_platform      INT NOT NULL DEFAULT 0,
    raw_insights        JSONB NOT NULL DEFAULT '{}'::jsonb,
    synced_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT daily_performance_breakdown_unique
        UNIQUE (client_id, channel, external_campaign_id, performance_date, breakdown_type, breakdown_value)
);
```

**API:** `GET /api/v1/meta/insights/breakdown?client_id=&campaign_id=&date=&type=publisher_platform`

### 22.3. Hourly sync (Tier B — B14)

Flag `PTT_META_INSIGHTS_HOURLY=1` + allowlist clients — intraday `spend_spike` cho account spend >500M VND/tháng.

---

## 23. Client deliverables & báo cáo

### 23.1. Catalog deliverable

| ID | Deliverable | Tần suất | Audience | Wave |
|----|-------------|----------|----------|------|
| RPT-M1 | Portal live dashboard | Real-time T-1 | Client viewer | B6 ✅ |
| RPT-M2 | CSV export self-serve | On demand | Client + AM | B6 ✅ |
| RPT-M3 | **Weekly Meta PDF** white-label | Weekly Mon 08:00 | Client email | B10 |
| RPT-M4 | **Monthly executive summary** | Monthly | Client approver | B10 |
| RPT-M5 | AM exception digest | Daily | Internal AM | B8 |
| RPT-M6 | Owner weekly intelligence | Weekly | GDKD | B11 |
| RPT-M7 | SLA / ops status (internal) | Daily | Ops | B14 |

### 23.2. Weekly client report template (RPT-M3)

**Sections (fixed order):**

1. Cover — client name, logo (`portal_client_settings`), period
2. Executive summary — 3 bullet AM narrative (optional text field)
3. KPI cards — spend, leads CRM, CPL, CPL vs target, ROAS (if real)
4. Trend — spend vs leads 7/30d (sparkline)
5. Top / bottom campaigns by CPL
6. Tracking footnote — CAPI status, unmapped spend %, attribution disclaimer §21
7. Appendix — campaign table CSV attachment

**Generation:** worker `meta_client_report_weekly` → HTML → PDF (WeasyPrint or headless stub Phase 1); store artifact path in PG; email via `PTT_PORTAL_EMAIL_WEBHOOK_URL` or ESP.

### 23.3. KPI dictionary (client-facing)

| Label VI | Definition client-safe |
|----------|------------------------|
| Chi tiêu Meta | Số tiền thực tế từ Meta Ads Manager (VND) |
| Lead CRM | Lead hợp lệ ghi nhận trên hệ thống PTT (đã loại trùng/spam) |
| CPL | Chi tiêu ÷ Lead CRM cùng kỳ |
| ROAS | Doanh thu chốt sale ÷ Chi tiêu (nếu có dữ liệu sale) |
| Chưa map campaign | Phần chi tiêu chưa gắn được campaign CRM — có thể lệch CPL |

---

## 24. SLA, support tiers & ops excellence

### 24.1. Support tiers

| Tier | Đối tượng | SLA response | SLA restore | Báo cáo |
|------|-----------|--------------|-------------|---------|
| **Standard** | Internal pods | Best effort | Best effort | Hub only |
| **Enterprise client** | HĐ enterprise | P1: 4h business | P1: 24h | RPT-M3/M4 |
| **Platform ops** | Toàn agency | On-call rotation | Theo runbook VPS | RPT-M7 |

### 24.2. Incident severity (Meta module)

| Sev | Ví dụ | Response | Escalation |
|-----|-------|----------|------------|
| P1 | Webhook down >15min; CAPI fail >50% 1h | 30min ack | GDKD + on-call |
| P2 | Insights sync miss 1 day; hub 5xx | 4h ack | Ops lead |
| P3 | Single client token error | 1 business day | AM + Tracking |
| P4 | UI cosmetic; export delay | Backlog | — |

### 24.3. Ops status signals (RPT-M7)

Daily internal JSON / Slack block:

| Signal | Green | Yellow | Red |
|--------|-------|--------|-----|
| Insights sync | ≥95% accounts OK | 90–95% | <90% |
| CAPI pending backlog | <50 | 50–200 | >200 |
| Webhook error rate 24h | <0.1% | 0.1–1% | >1% |
| Oldest stale account | <24h | 24–36h | >36h |

**Runbook link** in red state — [`runbooks/vps-production-operations.md`](runbooks/vps-production-operations.md).

### 24.4. Change management

- Prod flag widen (`PTT_CAPI_ENABLED=1` global) → change ticket + soak evidence
- Pilot client add/remove → AM sign-off
- DDL v4+ apply → maintenance window + backup verify

---

## 25. Compliance, privacy & data governance

### 25.1. Pháp lý & consent

| Yêu cầu | Implementation |
|---------|----------------|
| Lawful basis lead ads | Lead form consent captured in Meta; CRM stores ingest timestamp |
| CAPI PII | SHA-256 only; no plaintext email/phone in `capi_event_log` |
| Purpose limitation | Events only for ads measurement + optimization per client contract |
| PDPA / GDPR erase | Offboard B7 + anonymize `lead_id` in capi log after 180d retention |
| Client data isolation | PG RLS optional future; app-layer `client_id` mandatory |

### 25.2. Retention & purge

| Data | Retention | Purge job |
|------|-----------|-----------|
| `daily_performance` | 400d active | `insights_archive` B9 |
| `daily_performance_breakdown` | 180d | B8.1 weekly |
| `capi_event_log` | 180d | B9 monthly |
| `meta_alerts` | 90d | B8 monthly |
| Report artifacts | 24 months | B10 quarterly |
| ClickHouse facts | 36 months | B14 TTL |

### 25.3. Audit & export

- **Staff audit:** campaign writes, offboard, conversion rule changes → `domain_events` + PG audit tables
- **Compliance export:** `GET /api/v1/meta/compliance/export?client_id=` (SEC-M10, B14) — JSON bundle token refs redacted
- **Log policy:** no full Graph token, no PII plaintext in application logs

### 25.4. Enterprise procurement checklist (Tier B)

- [ ] SOC2-ready logging & access review quarterly
- [ ] Encryption at rest PG + vault key rotation doc
- [ ] Subprocessor list (Meta, hosting VPS, Sentry, ESP)
- [ ] DPA template with client
- [ ] Incident notification SLA §24.2

---

## 26. Enterprise upgrade roadmap (Tier A/B/C)

### 26.1. Tier A — Agency lớn (bắt buộc sau B11 để “enterprise-ready”)

| ID | Feature | Wave |
|----|---------|------|
| A1 | Insights breakdown table + API | B8.1 |
| A2 | Budget pacing monitor + alerts | B10 |
| A3 | Launch QA Meta hard gate | B9 |
| A4 | Client weekly PDF report | B10 |
| A5 | Event Match Quality dashboard | B9 |
| A6 | Lead quality KPI (junk rate, win rate) | B10 |
| A7 | Granular RBAC matrix enforced | B8.1 |
| A8 | Unified Meta+Google KPI API | B14 (lite) |
| A9 | **Ads Ops launch wizard** (create/mutate governed) | **B15** |
| A10 | **Ads Ops edit** creative/copy governed | **B15 §8.9** |

### 26.2. Tier B — Scale & credibility (30+ Meta accounts)

| ID | Feature | Wave |
|----|---------|------|
| B1 | ClickHouse warehouse + Grafana | B14 |
| B2 | Hourly insights option | B14 |
| B3 | Meta Marketing API webhooks (account/ad status) | B13 |
| B4 | SLA dashboard RPT-M7 | B14 |
| B5 | Creative registry ad_id ↔ asset | B12 |
| B6 | Compliance export API | B14 |

### 26.3. Tier C — Explicit OUT (charter riêng nếu cần)

| ID | Feature | Lý do OUT |
|----|---------|-----------|
| C1 | ML budget / bid optimizer | Cần DS team + warehouse 12mo+ |
| C2 | MMM / incrementality | Khác product category |
| C3 | Creative gen at scale | Smartly territory |
| C4 | Unified cross-channel auto-bidding | Skai territory |

**Quy tắc:** không ghi Tier C vào sprint B8–B15; PO ticket riêng + budget riêng.

### 26.4. Readiness scorecard (target)

| Milestone | Meta Enterprise readiness |
|-----------|---------------------------|
| H1 + B6–B7 shipped | ~50% |
| B8–B9 complete | ~70% |
| B10–B11 + Tier A | ~85% — **enterprise client-ready** |
| B12–B14 + Tier B | ~92% — **agency lớn scale** |
| **B15 Ads Ops UI** | **~90% Ads Ops** — create + edit creative/copy + mutate (not full Ads Manager) |
| Tier C product | 100% vs Skai (không mục tiêu mặc định) |

---

## 27. Ma trận deliverables ME36–ME61 (enterprise extensions)

> Core ME1–ME35 — §15. B15 extensions **ME53–ME61** below.

| ID | Deliverable | Tier | Wave | Module |
|----|-------------|------|------|--------|
| ME36 | `daily_performance_breakdown` + sync | A | B8.1 | `ptt_meta/insights_breakdown.py` |
| ME37 | Breakdown API + ops-web charts | A | B8.1 | Nest + ops-web |
| ME38 | Granular RBAC enforcement tests | A | B8.1 | guards + seed |
| ME39 | Launch QA Meta checklist gate | A | B9 | launch-qa util |
| ME40 | EMQ / match quality panel | A | B9 | tracking_health |
| ME41 | Budget pacing job + alerts | A | B10 | `ptt_meta/budget_pacing.py` |
| ME42 | Lead quality metrics engine | A | B10 | `ptt_meta/lead_quality.py` |
| ME43 | Client weekly PDF report job | A | B10 | `ptt_meta/client_report.py` |
| ME44 | Creative fatigue alert (frequency+CTR) | A | B10 | alerts extend |
| ME45 | Creative ↔ ad_id registry | B | B12 | creatives bridge |
| ME46 | Meta ops webhooks ingest | B | B13 | Nest webhooks |
| ME47 | `meta_account_disabled` alerts | B | B13 | alerts + worker |
| ME48 | ClickHouse Meta facts ETL | B | B14 | `ptt_meta/warehouse_export.py` |
| ME49 | Grafana executive dashboard | B | B14 | deploy/grafana |
| ME50 | Compliance export API | B | B14 | Nest meta-compliance |
| ME51 | Unified cross-channel KPI API | A/B | B14 | agency metrics |
| ME52 | Hourly insights sync | B | B14 | insights_sync flag |
| ME53 | `meta-ads-ops` Nest module + API | A | B15 | Nest `meta-ads-ops/*` |
| ME54 | ops-web `/meta/ads-ops` launch wizard | A | B15 | ops-web wizard UI |
| ME55 | Creative upload → Graph + `crm_creatives` link | A | B15 | `meta_creative_upload.py` |
| ME56 | Pre-flight Launch QA gate before create submit | A | B15 | ads-ops preflight |
| ME57 | Temporal `MetaCampaignCreateWorkflow` | A | B15 | ptt_worker Temporal |
| ME58 | Extend `campaign_write_requests` create actions | A | B15 | crm-campaign-writes |
| ME59 | `update_ad_creative` + `update_ad_copy` Graph handlers | A | B15 | `meta_ads_edit.py` |
| ME60 | ops-web Edit tab + hub **Edit ad** entry + diff UI | A | B15 | ops-web `/meta/ads-ops` |
| ME61 | Edit preflight gate (approved creative, disapproved ack, diff audit) | A | B15 | ads-ops edit preflight |

---

## 28. Phụ lục

### 28.1. Meta-OS → PTTADS field mapping

| Meta-OS (PTT) | PTTADS PG / API |
|---------------|-----------------|
| `re_project_id` | `clients.id` (+ RE link via lifecycle) |
| `crm_meta_ad_accounts.ad_account_id` | `client_channel_accounts.external_account_id` |
| `crm_meta_insights_daily` | `daily_performance` |
| `crm_meta_campaign_links` | `hub_campaign_map` |
| `crm_meta_capi_events` | `capi_event_log` |
| `crm_meta_alerts` | `meta_alerts` |
| `crm_meta_conversion_rules` | `meta_conversion_rules` |
| `crm_meta_write_requests` | `campaign_write_requests` |
| `/api/crm/meta/dashboard/summary` | `/facebook-ads/hub` + `/portal/performance` |

### 28.2. Domain events (target catalog entries)

| Event | Emitter | Consumers |
|-------|---------|-----------|
| `MetaInsightsSynced` | worker | alerts, metrics, anomaly |
| `MetaCapiEventSent` | capi_dispatch | tracking health |
| `MetaAlertRaised` | alerts eval | digest, hub UI |
| `MetaCampaignWriteExecuted` | Temporal | Launch QA bridge |
| `ClientOffboarded` | Nest | revoke, job cancel |
| `MetaClientReportGenerated` | client_report worker | portal notify |
| `MetaBudgetPaceAlert` | budget_pacing | alerts, AM digest |
| `MetaCampaignCreateSubmitted` | ads-ops API | campaign-writes, audit |
| `MetaCampaignCreateExecuted` | Temporal create workflow | hub refresh, registry |
| `MetaAdEditSubmitted` | ads-ops edit API | campaign-writes, audit |
| `MetaAdEditExecuted` | Temporal edit path | registry update, alert resolve |

Add to [`specs/events/catalog.yaml`](specs/events/catalog.yaml) during B8.

### 28.3. Test inventory (target)

| Range | Wave | Focus |
|-------|------|-------|
| H1 tests | Horizon | insights, token, webhook, nginx |
| T-ME1–ME15 | B8 | alerts, map, sync status |
| T-ME16–ME25 | B9 | CAPI rules, health, archive |
| T-ME26–ME32 | B10 | anomaly, ROAS, recommend |
| T-ME33–ME40 | B11 | stat, multi-pixel, forecast, snapshot |
| T-ME41–ME52 | B8.1–B14 | breakdown, pacing, client report, webhooks, warehouse |
| T-ME53–ME58 | B15 | ads-ops wizard, creative upload, create workflow, preflight |
| T-ME59–ME61 | B15 | edit creative/copy, diff audit, disapproved ack gate |

Reuse Meta-OS fixtures pattern: `tests/fixtures/meta_*.json` — no live Graph in CI.

### 28.4. Tài liệu tham chiếu

| Doc | Purpose |
|-----|---------|
| [`../PTT/docs/SPEC_META_OPERATING_SYSTEM.md`](../PTT/docs/SPEC_META_OPERATING_SYSTEM.md) | Domain P1–P4 reference |
| [`SPEC_AGENCY_OPERATING_PLATFORM.md`](SPEC_AGENCY_OPERATING_PLATFORM.md) | Agency master |
| [`runbooks/horizon1-meta-ads-migration-checklist.md`](runbooks/horizon1-meta-ads-migration-checklist.md) | H1 execution |
| [`SPEC_EMAIL_MARKETING_OPERATING_SYSTEM.md`](SPEC_EMAIL_MARKETING_OPERATING_SYSTEM.md) | Parallel OS pattern |
| [`SPEC_SEO_AEO_OPERATING_SYSTEM.md`](SPEC_SEO_AEO_OPERATING_SYSTEM.md) | Parallel OS pattern |

### 28.5. Ví dụ hub summary response (target B8)

```json
{
  "ok": true,
  "date_from": "2026-07-01",
  "date_to": "2026-07-21",
  "summary": {
    "spend_vnd": 248000000,
    "leads_crm": 920,
    "cpl_crm_vnd": 269565,
    "unmapped_spend_pct": 6.2,
    "accounts_sync_ok": 12,
    "accounts_sync_error": 1,
    "open_alerts": 3
  },
  "clients": [],
  "alerts": []
}
```

---

*Meta Ads Enterprise Platform · PTTADS · Master spec v1.2.1 · 2026-07-24*

*Canonical path: waves B8–B15 + Tier A/B. Meta-OS PTT = domain reference only. Tier C = separate product charter. B15 = governed Ads Ops wizard (create + edit creative/copy) — not full Ads Manager clone.*
