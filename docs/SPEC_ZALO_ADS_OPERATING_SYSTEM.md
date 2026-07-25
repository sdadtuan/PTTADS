# PTTADS — Zalo Ads Operating System (Target Specification)

> **Phiên bản:** 1.0 · **Ngày:** 2026-07-25  
> **Trạng thái:** Target specification — tích hợp vào PTT Agency Operating Platform  
> **Codebase:** `PTTADS/` · Nest `ptt-crm-api` · `ops-web` · `portal-web` · Python workers  
> **Nguồn yêu cầu:**  
> - *Xây dựng hệ thống quản lý và tích hợp Zalo Ads chuyên nghiệp cho công ty Marketing quy mô lớn*  
> - *Use Case cho spec hệ thống quản lý và tích hợp Zalo Ads*  
> - *Kiến trúc hệ thống chi tiết cho agency marketing multi-tenant Zalo Ads*  
> **Tài liệu liên quan:**  
> - [`SPEC_AGENCY_OPERATING_PLATFORM.md`](SPEC_AGENCY_OPERATING_PLATFORM.md) — nền tảng agency (BC-04 Channel Integration)  
> - [`SPEC_META_ENTERPRISE_PTTADS.md`](SPEC_META_ENTERPRISE_PTTADS.md) — mẫu enterprise ads depth  
> - [`specs/2026-07-23-wave-b6-s6-google-ads-e2e-design.md`](specs/2026-07-23-wave-b6-s6-google-ads-e2e-design.md) — mẫu MVP hub + portal  
> - [`specs/2026-07-16-channel-adapter-design.md`](specs/2026-07-16-channel-adapter-design.md) — ChannelAdapter  
> - [`use-cases/08-ZALO-ADS.md`](use-cases/08-ZALO-ADS.md) · [`use-cases/actions/08-ZALO-ACTIONS.md`](use-cases/actions/08-ZALO-ACTIONS.md)

---

## Mục lục

1. [Tổng quan & phạm vi](#1-tổng-quan--phạm-vi)
2. [Vị trí trong PTTADS](#2-vị-trí-trong-pttads)
3. [Kiến trúc hệ thống](#3-kiến-trúc-hệ-thống)
4. [Tích hợp Zalo Platform](#4-tích-hợp-zalo-platform)
5. [Mô hình dữ liệu](#5-mô-hình-dữ-liệu)
6. [Luồng nghiệp vụ lõi](#6-luồng-nghiệp-vụ-lõi)
7. [Đặc tả API](#7-đặc-tả-api)
8. [UX/UI — ops-web & portal-web](#8-uxui--ops-web--portal-web)
9. [Phân quyền & bảo mật](#9-phân-quyền--bảo-mật)
10. [Jobs, workers & đồng bộ](#10-jobs-workers--đồng-bộ)
11. [Lộ trình triển khai (Wave Z0–Z4)](#11-lộ-trình-triển-khai-wave-z0z4)
12. [Ma trận deliverables & acceptance](#12-ma-trận-deliverables--acceptance)
13. [Mapping nguồn → PTTADS](#13-mapping-nguồn--pttads)
14. [Rủi ro & giả định](#14-rủi-ro--giả-định)

---

## 1. Tổng quan & phạm vi

### 1.1. Vision

**Zalo Ads Operating System** trên PTTADS cho phép agency marketing quy mô lớn:

- Quản lý **nhiều khách hàng, nhiều OA, nhiều tài khoản quảng cáo Zalo** trên một nền tảng tập trung (`client_id` scoped).
- Chuẩn hóa luồng **brief → duyệt → triển khai → lead → CRM → báo cáo → tối ưu**.
- Đồng bộ **lead form Zalo Ads/OA** về CRM theo thời gian gần thực (webhook + polling form API).
- Closed-loop: **Spend (Zalo) → Lead (form/webhook) → Deal (CRM) → CPL/CPA/ROAS**.
- Phân quyền chặt theo vai trò PTTADS hiện có; audit log; không bắt nhân sự thao tác trên nhiều tài khoản Zalo rời rạc.

### 1.2. Nguyên tắc thiết kế trên PTTADS

| # | Nguyên tắc | Áp dụng |
|---|------------|---------|
| D1 | **Reuse agency primitives** | `clients`, `client_channel_accounts`, `hub_campaign_map`, `daily_performance`, `crm_leads` |
| D2 | **ChannelAdapter pattern** | `ptt_channel/adapters/zalo.py` — mở rộng, không fork logic lead |
| D3 | **Google-parity MVP trước Meta-depth** | Hub + sync + portal performance trước; ads-ops wizard / intelligence sau |
| D4 | **Nest canonical** | API staff trên `ptt-crm-api`; Flask chỉ worker/legacy nếu cần |
| D5 | **Human-in-the-loop** | Campaign write, budget lớn, creative client approval — qua workflow PTTADS |
| D6 | **Idempotency** | Lead dedup, sync job key, campaign push retry |

### 1.3. Personas (map từ nguồn → PTTADS)

| Persona nguồn | Persona PTTADS | Cap chính |
|---------------|----------------|-----------|
| Admin hệ thống | Super Admin | `platform_admin` |
| Quản lý agency / Manager | AM Lead, GDKD | `crm_agency`, `crm_board` |
| Media Buyer | Media Buyer | `crm_zalo_ads` write |
| Creative / Content | Creative Lead | `crm_creatives` |
| Account Manager | AM | `crm_agency`, lifecycle |
| Data Analyst / BI | Analyst | `crm_zalo_ads` export |
| Khách hàng | Client Viewer / Approver | portal JWT scoped |
| CRM System | — | internal API |
| Zalo Ads / Zalo OA | — | external API + webhook |

### 1.4. Phạm vi IN / OUT

**IN scope (v1 target):**

- Kết nối Zalo OA / Zalo Ads account per agency client.
- Hub CPL/performance staff + portal read-only (mirror Google B6-S6).
- Lead ingest: webhook + form API polling (`openapi.zalo.me/v2.0/oa/form/get`).
- Hub campaign map `channel=zalo`.
- Insights sync → `daily_performance` (`zalo_insights_sync` job).
- Workflow duyệt creative/budget tích hợp module CRM creatives + portal approval.
- Cảnh báo cơ bản: token hết hạn, lead sync chậm, CPL vượt target.
- Onboard orchestrator: thêm bước Zalo (account, OA, form, sync green).

**OUT scope (v1 — backlog v2+):**

- Multi-agency SaaS (PTTADS là single-agency multi-client).
- Full campaign create/edit trên Zalo qua API (phụ thuộc quyền API Zalo Business — hiện adapter `supports_campaign_write=False`).
- Zalo CAPI / server events (adapter `supports_server_events=False`).
- BI warehouse riêng (dùng `daily_performance` + CRM joins trước).
- Mini App Zalo ecosystem mở rộng.

---

## 2. Vị trí trong PTTADS

### 2.1. Hiện trạng (as-is trên main)

| Thành phần | Trạng thái | File tham chiếu |
|------------|------------|-----------------|
| Channel account `zalo` | ✅ CRUD | `agency.service.ts`, `AgencyClientDetailContent.tsx` |
| Hub map `channel=zalo` | ✅ API + UI | `HubCampaignMapsPanel.tsx` |
| Webhook lead Zalo | ✅ Nest parser | `zalo-webhook.parser.ts`, `ptt_channel/adapters/zalo.py` |
| Normalized schema | ✅ `channel=zalo` | `schemas/channel/normalized-daily-performance.schema.json` |
| Zalo hub page | ❌ | — |
| Insights sync job | ❌ | — |
| Portal `/zalo` | ❌ | — |
| OAuth / token vault Zalo | ❌ stub | `ZaloAdapter.validate_credentials` |
| Onboard orchestrator Zalo steps | ❌ | `onboarding-orchestrator.service.ts` (Meta-only) |
| Performance API filter zalo | ❌ | `performance.types.ts` |

### 2.2. Bounded context map

```
┌─────────────────────────────────────────────────────────────────┐
│                    PTT Agency Operating Platform                 │
├──────────────┬──────────────────────┬───────────────────────────┤
│  CRM Core    │  Service Delivery    │  Platform (Auth/Webhook)  │
│  leads       │  lifecycle, onboard  │  staff JWT, portal JWT    │
├──────────────┴──────────────────────┴───────────────────────────┤
│              BC-04 Channel Integration (shared)                  │
│  client_channel_accounts · hub_campaign_map · daily_performance  │
├──────────────┬──────────────────────┬───────────────────────────┤
│ Meta Enterprise│ Google Ads (Track G)│ Zalo Ads OS (NEW)         │
│ meta-tracking  │ agency hub only     │ zalo-leads + zalo hub     │
│ meta-ads-ops   │                     │ (phase Z2+: zalo-ads-ops) │
└──────────────┴──────────────────────┴───────────────────────────┘
```

### 2.3. Closed-loop Zalo trên PTTADS

```mermaid
flowchart LR
  subgraph Zalo
    ZA[Zalo Ads / OA]
    ZF[Lead Form]
  end
  subgraph PTTADS
    WH[Webhook / Form poll]
    CRM[(crm_leads)]
    SYNC[zalo_insights_sync]
    DP[(daily_performance)]
    HUB[/zalo/zalo-ads hub]
    PORTAL[portal /zalo]
  end
  ZA --> SYNC --> DP
  ZF --> WH --> CRM
  DP --> HUB
  DP --> PORTAL
  CRM --> HUB
```

**KPI chính:** Spend, Impressions, Clicks, CTR, Leads, CPL, CPA (Won), ROAS — cùng công thức `PerformanceService` như Meta/Google.

---

## 3. Kiến trúc hệ thống

### 3.1. Lớp trình bày

| App | Route prefix | Vai trò |
|-----|--------------|---------|
| **ops-web** | `/zalo/*` | Hub, form lead monitor, sync status, alerts |
| **ops-web** | `/agency/clients/[id]?tab=channels` | Zalo account + OA + token |
| **ops-web** | `/crm/creatives`, `/crm/campaign-writes` | Duyệt + launch gate (shared) |
| **portal-web** | `/zalo` | Performance read-only cho client |
| **portal-web** | `/creatives` | Client approve (shared) |

### 3.2. Lớp API (Nest — `ptt-crm-api`)

| Module | Vị trí đề xuất | Giai đoạn |
|--------|----------------|-----------|
| **AgencyModule** (hub, sync) | `agency-ops.controller.ts` | Z1 |
| **ZaloLeadsModule** | `src/zalo-leads/` — form poll, lead status | Z1 |
| **WebhooksModule** (existing) | mở rộng parser form events | Z0 ✅ |
| **PerformanceModule** (existing) | thêm `channel=zalo` filter | Z1 |
| **ZaloAdsOpsModule** (optional) | launch wizard khi API Zalo mở write | Z3 |

### 3.2.1. Zalo adapter layer (Python + Nest)

```
ZaloAuthAdapter      — OAuth app, OA token refresh, vault
ZaloCampaignAdapter  — read campaigns/ad sets (phase Z2+)
ZaloLeadAdapter      — webhook parse + form/get polling
ZaloReportingAdapter — daily insights → normalized performance
```

Implementation path:

- Python: `ptt_zalo/` (mirror `ptt_google/`, `ptt_meta/`)
- Nest: thin controllers; business logic delegate worker hoặc repository

### 3.3. Lớp hạ tầng (reuse PTTADS)

| Thành phần | Công nghệ |
|------------|-----------|
| Operational DB | PostgreSQL (agency + CRM PG) |
| Queue | `job_queue` table + `ptt_worker` |
| Cache | Redis (optional rate limit Zalo API) |
| Secrets | `access_token_encrypted` vault pattern (Meta/Google) |
| Observability | job status, sync state table, hub banner alerts |

---

## 4. Tích hợp Zalo Platform

### 4.1. Tài khoản & OAuth

1. Tạo **Zalo Developer App** trên [developers.zalo.me](https://developers.zalo.me).
2. Liên kết **Official Account (OA)** với app; xin quyền API theo chức năng.
3. Lưu `app_id`, `app_secret`, `oa_id`, refresh token vào vault (`client_channel_accounts.meta` JSON).
4. Staff connect qua ops-web (pattern Google OAuth pilot).

**Env đề xuất:**

```bash
PTT_ZALO_APP_ID=
PTT_ZALO_APP_SECRET=
PTT_ZALO_OAUTH_REDIRECT_URI=https://ops.pttads.vn/zalo/oauth/callback
CRM_ZALO_WEBHOOK_SECRET=          # webhook HMAC
PTT_ZALO_INSIGHTS_SYNC=1
PTT_ZALO_ADS_STUB=0               # dev stub
PTT_ZALO_ADS_PILOT=1
PTT_ZALO_ADS_PILOT_CLIENTS=uuid1,uuid2
```

### 4.2. Lead form API

- **Endpoint tham chiếu:** `GET openapi.zalo.me/v2.0/oa/form/get` (theo kiến trúc nguồn).
- **Polling:** worker `zalo_form_lead_poll` mỗi 5–15 phút per OA có form active.
- **Webhook:** OA events → `POST /webhooks/zalo` (đã có parser).
- **Lead fingerprint dedup:** `phone_normalized + client_id + form_id + received_date` (align CRM dedup).

### 4.3. Insights / reporting API

- Phase Z1: daily campaign-level metrics → map vào `daily_performance` (`channel=zalo`).
- Phase Z2: ad group / creative breakdown nếu API hỗ trợ.
- Stub mode: `PTT_ZALO_ADS_STUB=1` sinh dữ liệu pilot (mirror Google stub).

### 4.4. Campaign write (deferred Z3+)

Adapter hiện tại: `supports_campaign_write=False`. Khi Zalo Business API mở:

- Launch wizard ops-web → payload queue → Temporal/worker → Zalo API.
- Gate: Launch QA + client approval + budget threshold (`campaign-writes` module).

---

## 5. Mô hình dữ liệu

### 5.1. Bảng reuse (không tạo song song)

| Bảng | Vai trò Zalo |
|------|--------------|
| `clients` | Agency client = workspace KH |
| `client_channel_accounts` | `channel='zalo'`, `external_account_id`= ad account / OA id, `meta` JSON: `{ oa_id, form_ids[], app_id }` |
| `hub_campaign_map` | `channel='zalo'`, map external campaign → hub contract |
| `daily_performance` | Facts T-1: spend, impressions, clicks, leads |
| `crm_leads` | `channel='zalo'`, `agency_client_id`, attribution fields |
| `job_queue` | `zalo_insights_sync`, `zalo_form_lead_poll` |

### 5.2. Bảng mới đề xuất

**`zalo_insights_sync_state`** (mirror Google):

```sql
CREATE TABLE zalo_insights_sync_state (
  client_id           UUID NOT NULL REFERENCES clients(id),
  channel_account_id  UUID NOT NULL REFERENCES client_channel_accounts(id),
  last_sync_date      DATE,
  last_sync_at        TIMESTAMPTZ,
  last_status         VARCHAR(16),  -- ok | partial | error
  last_error          TEXT,
  PRIMARY KEY (client_id, channel_account_id)
);
```

**`zalo_lead_form_sync_cursor`** (form polling):

```sql
CREATE TABLE zalo_lead_form_sync_cursor (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  client_id           UUID NOT NULL REFERENCES clients(id),
  oa_id               VARCHAR(64) NOT NULL,
  form_id             VARCHAR(64) NOT NULL,
  last_form_data_id   VARCHAR(128),
  last_polled_at      TIMESTAMPTZ,
  UNIQUE (client_id, oa_id, form_id)
);
```

**`zalo_lead_events`** (audit trail lead pipeline):

```sql
CREATE TABLE zalo_lead_events (
  id          BIGSERIAL PRIMARY KEY,
  lead_id     UUID REFERENCES crm_leads(id),
  event_type  VARCHAR(32),  -- received | deduped | pushed_crm | failed
  payload_json JSONB,
  created_at  TIMESTAMPTZ DEFAULT NOW()
);
```

### 5.3. Quan hệ (từ kiến trúc nguồn → PTTADS)

| Quan hệ nguồn | Map PTTADS |
|---------------|------------|
| tenant → client accounts | `clients` (1 agency, N clients) |
| client → zalo_accounts / oa_accounts | `client_channel_accounts` rows |
| campaign → ad_groups → creatives | `hub_campaign_map` + external IDs; detail table phase Z2 |
| lead_form → leads | form cursor + `crm_leads` |
| lead → lead_events | `zalo_lead_events` + CRM timeline |

---

## 6. Luồng nghiệp vụ lõi

### 6.1. Luồng A — Onboard Zalo cho client mới

1. AM tạo agency client (SYS-UC-001).
2. Tracking thêm **channel account Zalo** + OA id (`/agency/clients/[id]?tab=channels`).
3. Connect OAuth / lưu token vault.
4. Cấu hình webhook URL trên Zalo Developer → `POST /webhooks/zalo`.
5. Map hub campaigns (`/agency/clients/[id]?tab=campaigns`, channel=zalo).
6. Chạy **Sync Zalo insights** + verify lead test.
7. Onboard orchestrator auto-tick bước Zalo (phase Z1).

### 6.2. Luồng B — Lead form Zalo → CRM

```
Zalo form submit
  → (A) Webhook realtime HOẶC (B) Worker poll form/get
  → ZaloLeadAdapter normalize
  → Dedup (phone/email/uid)
  → Insert crm_leads (agency_client_id, campaign attribution)
  → zalo_lead_events log
  → Notification CSKH (optional P1)
  → CRM status sync back (UC-16 nguồn) via lead patch webhook
```

### 6.3. Luồng C — Campaign brief → duyệt → launch

```
AM brief (lifecycle consult)
  → Buyer draft campaign nội bộ (CRM / zalo draft — phase Z2)
  → Creative upload → internal approve → client approve (portal)
  → Launch QA pass
  → (Z3) Push Zalo API HOẶC (v1) manual launch + map campaign ID vào hub
  → Insights sync → hub CPL
```

### 6.4. Luồng D — Báo cáo & cảnh báo

1. Scheduler/worker sync T-1 insights.
2. `PerformanceService` join spend + CRM leads + Won revenue.
3. Hub `/zalo/zalo-ads` + portal `/zalo`.
4. Rule engine: CPL > target_cpl_vnd, CTR drop, zero leads 24h → Slack/email (reuse alert infra P1).

---

## 7. Đặc tả API

### 7.1. Staff — Hub & sync (AgencyModule)

| Method | Path | Cap | Mô tả |
|--------|------|-----|-------|
| GET | `/api/v1/zalo-ads/hub` | `crm_zalo_ads` view | Hub summary per client |
| GET | `/api/v1/zalo-ads/hub/export` | export | CSV export |
| GET | `/api/v1/zalo-ads/pilot-status` | view | Pilot/stub banner |
| GET | `/api/v1/zalo-ads/oauth/start` | `crm_agency` write | OAuth URL |
| GET | `/api/v1/zalo-ads/oauth/callback` | public | OAuth callback |
| POST | `/api/v1/clients/:id/sync/zalo-insights` | write | Enqueue sync job |
| GET | `/api/v1/clients/:id/zalo/sync-status` | view | Last sync state |

### 7.2. Staff — Leads & forms (ZaloLeadsModule)

| Method | Path | Cap | Mô tả |
|--------|------|-----|-------|
| GET | `/api/v1/zalo/leads` | view | List leads (filter client, date) |
| GET | `/api/v1/zalo/forms` | view | Registered forms per OA |
| POST | `/api/v1/zalo/forms/:formId/poll` | write | Manual poll trigger |
| GET | `/api/v1/zalo/leads/:id/events` | view | Lead event trail |

### 7.3. Platform — Webhook (existing)

| Method | Path | Mô tả |
|--------|------|-------|
| POST | `/webhooks/zalo` | OA / form events; HMAC verify |

### 7.4. Portal — Performance (reuse)

| Method | Path | Mô tả |
|--------|------|-------|
| GET | `/api/v1/performance?channel=zalo&client_id=…` | Portal scoped JWT |

### 7.5. Response hub (ví dụ)

```json
{
  "date_from": "2026-07-01",
  "date_to": "2026-07-24",
  "summary": {
    "spend_vnd": 125000000,
    "leads": 342,
    "cpl_vnd": 365497,
    "unmapped_spend_vnd": 0
  },
  "clients": [
    {
      "client_id": "uuid",
      "client_name": "Brand A",
      "sync_status": "green",
      "campaigns": []
    }
  ]
}
```

---

## 8. UX/UI — ops-web & portal-web

### 8.1. Information architecture

```
ops-web
├── /zalo
│   ├── /zalo/zalo-ads          ← Hub CPL chính (mirror /google/google-ads)
│   ├── /zalo/leads             ← Lead monitor + form sync status
│   └── /zalo/oauth/callback    ← OAuth redirect
├── /agency/clients/[id]
│   ├── tab channels            ← Zalo account + OA + Connect + Sync
│   ├── tab campaigns           ← Hub map channel=zalo
│   └── tab onboard             ← Orchestrator step Zalo
├── /meta/ads-combined          ← Thêm cột/filter Zalo CPL (Z2)
└── /crm/...                    ← Creatives, Launch QA, campaign-writes (shared)

portal-web
├── /zalo                       ← PerformancePanel channel=zalo
└── /creatives                  ← Client approve (shared)
```

**Nav (OpsNav):** thêm section **Zalo Ads** sau Google, trước SEO:

```
Zalo Ads
  ├── Hub CPL      /zalo/zalo-ads
  └── Leads        /zalo/leads
```

### 8.2. Màn hình chi tiết

#### Z-UI-01 — `/zalo/zalo-ads` (Hub CPL)

| Vùng | Thành phần |
|------|------------|
| Header | Filter: client, date T-7/T-30/custom, search |
| KPI row | Spend · Leads · CPL · CTR · Unmapped spend (yellow) |
| Table | Client → campaigns: spend, leads, CPL, sync status dot |
| Actions | Export CSV, link map campaigns, link client channels |
| Banner | Pilot/stub warning (`ZaloPilotBanner`) |

**Wireframe:**

```
┌─────────────────────────────────────────────────────────────┐
│ Zalo Ads Hub          [Client ▼] [T-7|T-30|Custom] [Export] │
├─────────────────────────────────────────────────────────────┤
│ Spend 125M │ Leads 342 │ CPL 365K │ CTR 1.2% │ ⚠ Unmapped 0│
├─────────────────────────────────────────────────────────────┤
│ Client      │ Campaign        │ Spend  │ Leads │ CPL │ Sync │
│ Brand A     │ zalo_camp_001   │ 50M    │ 120   │ 417K│ 🟢   │
│ Brand B     │ (unmapped)      │ 10M    │ —     │ —   │ 🟡   │
└─────────────────────────────────────────────────────────────┘
```

#### Z-UI-02 — Agency client tab Channels (Zalo)

| Field | Mô tả |
|-------|-------|
| Channel | `zalo` (select) |
| External account ID | Zalo ad account / OA id |
| Display name | Tuỳ chọn |
| OA ID | `meta.oa_id` — routing webhook |
| Form IDs | Danh sách form lead gắn OA |
| **Connect Zalo** | OAuth button (Z1) |
| **Sync Zalo insights** | Enqueue job (Z1) |
| Token status | valid / expired / missing |

#### Z-UI-03 — `/zalo/leads`

| Cột | Mô tả |
|-----|-------|
| Received | Timestamp |
| Client | Agency client name |
| Form / Campaign | form_id, campaign attribution |
| Name / Phone | Lead fields |
| CRM status | new / qualified / won |
| Sync | webhook / poll / deduped |

#### Z-UI-04 — Portal `/zalo`

Reuse `PerformancePanel` — cards Spend, Leads, CPL; chart 7 ngày; footer attribution disclaimer.

#### Z-UI-05 — Combined nav `/meta/ads-combined`

Thêm tab/filter **Zalo** cạnh Meta + Google (Z2).

### 8.3. Design tokens & component reuse

| Component nguồn | Reuse cho Zalo |
|-----------------|----------------|
| `GoogleGoogleAdsContent.tsx` | Template hub layout |
| `GooglePilotBanner.tsx` | → `ZaloPilotBanner.tsx` |
| `HubCampaignMapsPanel.tsx` | Đã hỗ trợ channel zalo |
| `PerformancePanel.tsx` | Portal — thêm `channel="zalo"` |
| `MetaHubFilters.tsx` | Pattern filter client/status |
| `ClientOnboardOrchestrator` | Thêm steps `zalo_*` |

### 8.4. Trạng thái UI (sync health)

| Màu | Điều kiện |
|-----|-----------|
| 🟢 green | Sync T-1 OK + token valid |
| 🟡 yellow | Partial sync / unmapped spend > 0 |
| 🔴 red | Token expired / sync fail 24h |
| ⚪ gray | Chưa cấu hình account |

---

## 9. Phân quyền & bảo mật

### 9.1. Capability mới

| Cap | view | write | export |
|-----|------|-------|--------|
| `crm_zalo_ads` | Hub, leads list | — | CSV |
| `crm_agency` | Client channels | Add account, sync | — |
| `crm_agency` configure | OAuth app-level | — | — |

Guard: `StaffZaloAdsViewGuard` (mirror `StaffGoogleAdsViewGuard`).

### 9.2. Portal scope

- JWT `client_id` scoped — client chỉ thấy performance Zalo của mình.
- Approver: creatives pending (shared PORTAL module).

### 9.3. Bảo mật

- Token/secret trong vault encrypted; không log plaintext.
- Webhook HMAC bắt buộc prod (`CRM_ZALO_WEBHOOK_SECRET`).
- Audit: campaign map changes, token refresh, manual poll, export.
- Tenant isolation: mọi query filter `client_id` / staff cap client list.

---

## 10. Jobs, workers & đồng bộ

| Job type | Handler | Trigger | Idempotency key |
|----------|---------|---------|-----------------|
| `zalo_insights_sync` | `ptt_zalo/insights_sync.py` | Manual button, cron T+1 | `zalo_insights_sync:{client_id}:{date}` |
| `zalo_form_lead_poll` | `ptt_zalo/form_lead_poll.py` | Cron 5–15 min | `zalo_form_poll:{oa_id}:{form_id}:{cursor}` |

Worker registration: `ptt_worker/__main__.py`  
Enqueue: `agency-side-effects.service.ts` (post token save, post map)

---

## 11. Lộ trình triển khai (Wave Z0–Z4)

| Wave | Tên | Deliverables | UC unblock |
|------|-----|--------------|------------|
| **Z0** | Foundation (shipped) | Channel account, hub map, webhook parser | ZALO-UC-004 partial, UC-12 partial |
| **Z1** | Hub + sync + portal MVP | Hub page, sync job, portal `/zalo`, cap, performance filter | ZALO-UC-001,002,003,017 |
| **Z2** | Lead form poll + monitor | Form cursor, `/zalo/leads`, dedup hardening, onboard steps | ZALO-UC-012–015 |
| **Z3** | Workflow + alerts | Creative approval path, CPL alerts, combined nav | ZALO-UC-006–011,019 |
| **Z4** | Campaign API write | Launch wizard, Temporal, budget gate | ZALO-UC-010 (full auto) |

**MVP (theo nguồn + PTTADS priority):** Z0 + Z1 + Z2.

---

## 12. Ma trận deliverables & acceptance

| ID | Deliverable | Acceptance |
|----|-------------|------------|
| ZA-01 | `crm_zalo_ads` cap + guards | Staff without cap → 403 |
| ZA-02 | GET `/zalo-ads/hub` | Returns CPL matching manual calc ± rounding |
| ZA-03 | `zalo_insights_sync` job | Rows in `daily_performance` channel=zalo |
| ZA-04 | ops `/zalo/zalo-ads` | Filter client/date; export CSV |
| ZA-05 | portal `/zalo` | Client JWT scoped; no cross-client leak |
| ZA-06 | Sync button on agency channels | Job enqueued; toast + job label |
| ZA-07 | Webhook lead → CRM | Deduped; appears in `/crm/leads` |
| ZA-08 | Form poll worker | New form leads within 15 min SLA |
| ZA-09 | Hub map zalo | Unmapped spend yellow on hub |
| ZA-10 | Onboard orchestrator zalo steps | Auto-detect account + sync green |
| ZA-11 | E2E spec | `ops-web/e2e/zalo-ads.spec.ts` green |
| ZA-12 | DDL migration | `zalo_insights_sync_state` applied |

---

## 13. Mapping nguồn → PTTADS

| UC nguồn | PTTADS UC | Ghi chú |
|----------|-----------|---------|
| UC-01 Login | PLAT-UC-001 | Staff SSO existing |
| UC-02 Tenant | SVC-UC-001 | Agency client |
| UC-03 RBAC | PLAT-UC-002 | Cap `crm_zalo_ads` |
| UC-04 Zalo config | ZALO-UC-001 | OAuth + channel account |
| UC-05 Audit | PLAT-UC-005 | audit_log |
| UC-06 Brief | SVC-UC-003 | Lifecycle consult |
| UC-07–11 Campaign | ZALO-UC-004–008 | Phase Z3 write |
| UC-12–16 Lead | ZALO-UC-009–013 | Webhook + poll |
| UC-17–20 Reporting | ZALO-UC-014–017 | Hub + alerts |
| UC-21–23 Client | PORTAL-UC-* | Portal performance + approve |

Chi tiết UC: [`use-cases/08-ZALO-ADS.md`](use-cases/08-ZALO-ADS.md)  
Chi tiết thao tác UI: [`use-cases/actions/08-ZALO-ACTIONS.md`](use-cases/actions/08-ZALO-ACTIONS.md)

---

## 14. Rủi ro & giả định

| Rủi ro | Mitigation |
|--------|------------|
| Zalo API thay đổi / hạn chế quyền | Adapter layer; stub pilot |
| Campaign write API không khả dụng | v1 manual launch + hub map |
| Lead trễ vs realtime | Webhook primary + poll fallback |
| Duplicate leads | Fingerprint dedup + idempotency |
| Token OA hết hạn | Alert + re-auth UX (Meta pattern) |

**Giả định:** PTTADS single-agency; Zalo Business API access được cấp cho agency; PostgreSQL agency PG production sẵn sàng.

---

*End of specification v1.0*
