# Hướng dẫn sử dụng & triển khai phân hệ Meta Enterprise Ops

> **Phiên bản:** 1.0 · **Ngày:** 2026-07-25  
> **Đối tượng:** Super Admin, GDKD, Account Manager, Media Buyer, Tracking/Tech, Data/BI  
> **Phạm vi:** Setup đầy đủ trên **VPS/staging** + hướng dẫn sử dụng từng màn hình ops-web & portal  
> **URL staff:** `https://ops.pttads.vn` · `https://rs.pttads.vn` (redirect)  
> **URL client:** `https://portal.pttads.vn/meta`  
> **Spec tham chiếu:**  
> - [`SPEC_META_ENTERPRISE_PTTADS.md`](SPEC_META_ENTERPRISE_PTTADS.md) — master spec kỹ thuật & nghiệp vụ  
> - [`specs/2026-07-24-meta-enterprise-ui-ux-architecture-design.md`](specs/2026-07-24-meta-enterprise-ui-ux-architecture-design.md) — UI/UX ops-web & portal  
> - [`SPEC_AGENCY_OPERATING_PLATFORM.md`](SPEC_AGENCY_OPERATING_PLATFORM.md) — BC-04 Channel Integration (Meta)  
>
> **Lưu ý:** Phân hệ Meta là bounded context **riêng** với SEO/AEO (SEO spec §1.5 — paid media thuộc Agency Ops / Meta Ads). Tài liệu này không thay thế spec master; dùng khi vận hành và go-live.

---

## Mục lục

1. [Tổng quan phân hệ](#1-tổng-quan-phân-hệ)
2. [Kiến trúc trên VPS](#2-kiến-trúc-trên-vps)
3. [Triển khai & setup đầy đủ](#3-triển-khai--setup-đầy-đủ)
4. [Bật tính năng theo wave (pilot → prod)](#4-bật-tính-năng-theo-wave-pilot--prod)
5. [Truy cập & phân quyền](#5-truy-cập--phân-quyền)
6. [Hướng dẫn từng màn hình (UI/UX)](#6-hướng-dẫn-từng-màn-hình-uiux)
7. [Luồng nghiệp vụ end-to-end](#7-luồng-nghiệp-vụ-end-to-end)
8. [Jobs, alerts & observability](#8-jobs-alerts--observability)
9. [Client Portal Meta](#9-client-portal-meta)
10. [Xử lý sự cố thường gặp](#10-xử-lý-sự-cố-thường-gặp)
11. [Checklist go-live](#11-checklist-go-live)
12. [Phụ lục — env, API, tài liệu liên quan](#12-phụ-lục--env-api-tài-liệu-liên-quan)

---

## 1. Tổng quan phân hệ

**Meta Enterprise Ops** là phân hệ quảng cáo Meta **đa client** trên PTTADS Agency Operating Platform — không phải tab CRM lẻ hay Flask monolith cũ.

### 1.1. Vòng đời closed-loop

```
Onboard client → Kết nối ad account (Meta) → Sync insights T-1
              → Hub map campaign ↔ CRM → Tính CPL/ROAS
              → Lead webhook (Nest) → CAPI + CRM conversions
              → Intelligence (anomaly, recommend) → Governed write (Temporal)
              → Launch/Edit Ads Ops wizard (B15) → Client portal performance
              → Offboard & revoke token
```

**Chuỗi giá trị agency:**

`Spend (Meta API) → Lead (webhook/CRM) → Pipeline status → CAPI conversion → Deal revenue → ROAS → Launch QA / Campaign write (approved) → Client report`

### 1.2. Module & route đã triển khai

Staff console: **ops-web** tại `/meta/*` (Nest API `ptt-crm-api`). Flask `/crm/facebook-ads` redirect sang ops-web (Horizon 1).

| Nhóm | Module | Route chính | Wave |
|------|--------|-------------|------|
| Hub | Meta Ads Hub | `/meta/facebook-ads` | H1+ |
| Ads Ops | Launch + Edit wizard | `/meta/ads-ops` | B15 |
| Tracking | CAPI health, rules, pixel test | `/meta/tracking` | B9 |
| Intelligence | ROAS, anomaly, forecast | `/meta/intelligence` | B10–B11 |
| Cross-channel | Ads CPL (Meta + Google) | `/meta/ads-combined` | B6 |
| Migration | Horizon 1 signoff | `/meta/migration` | H1 |
| Governance | Campaign write queue | `/crm/campaign-writes` | B6+B15 |
| Launch gate | Launch QA checklist | `/crm/launch-qa` | B9 |
| Creative | Creative inbox + registry link | `/crm/creatives` | B12 |
| Agency | Channel accounts, sync | `/agency/clients/:id` | H1 |
| Portal | Client performance read-only | `/meta` (portal-web) | B6-S7 |

### 1.3. Thành phần kỹ thuật

| Lớp | Thành phần | Vai trò |
|-----|------------|---------|
| **UI staff** | ops-web `/meta/*` | Hub, tracking, intelligence, ads-ops |
| **UI client** | portal-web `/meta` | Performance read-only + export |
| **API** | NestJS `ptt-crm-api` | Hub, tracking, alerts, ads-ops, webhooks |
| **Workers** | `ptt_worker` + `ptt_jobs` | Insights sync, CAPI, alerts eval, archive |
| **Domain** | `ptt_meta/*` | Insights, CAPI, alerts, ads ops helpers |
| **DB** | PostgreSQL | `daily_performance`, `hub_campaign_map`, `capi_event_log`, `meta_alerts`, … |
| **Governance** | Temporal + `campaign_write_requests` | Mọi mutate Graph phải approve |

### 1.4. Nguyên tắc vận hành (bắt buộc)

1. **`client_id` first** — mọi dữ liệu Meta scope theo client UUID.
2. **Canonical UI** — staff dùng ops-web; không build thêm trên Flask Meta admin.
3. **Governance before mutate** — pause/budget/create/edit đều qua campaign-writes + approve + Temporal.
4. **Feature flags + pilot allowlist** — bật từng wave, soak ≥7 ngày (CAPI khuyến nghị 30 ngày).
5. **Không clone Ads Manager** — audience phức tạp, catalog, Advantage+ → deep link Meta native.

---

## 2. Kiến trúc trên VPS

```
┌─────────────────────────────────────────────────────────────────────┐
│  VPS (vd. /var/www/ptt)                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐  │
│  │ ops-web :3200│  │ portal-web   │  │ nginx                    │  │
│  │ staff /meta/*│  │ :3001 /meta  │  │ rs.pttads.vn → ops-web   │  │
│  └──────┬───────┘  └──────┬───────┘  └──────────────────────────┘  │
│         │                 │                                         │
│  ┌──────┴─────────────────┴───────┐                                │
│  │ ptt-crm-api (Nest) :3000       │  ← webhook Meta, hub API       │
│  └──────┬─────────────────────────┘                                │
│         │                                                           │
│  ┌──────┴───────┐  ┌────────────────┐  ┌─────────────────────────┐ │
│  │ ptt_worker   │  │ Temporal worker│  │ ptt-fb-autosync (opt)   │ │
│  │ job_queue    │  │ campaign write │  │ lead autosync PG        │ │
│  └──────┬───────┘  └────────────────┘  └─────────────────────────┘ │
│         │                                                           │
│         ▼                                                           │
│  PostgreSQL — daily_performance, hub_campaign_map, capi_event_log,  │
│               meta_alerts, meta_conversion_rules, client_channel_*  │
│         │                                                           │
│  systemd timers: meta-insights · token-refresh · capi · clickhouse  │
└─────────────────────────────────────────────────────────────────────┘
         │
         ▼
  Meta Graph API · Lead Ads webhook · Events Manager (CAPI)
```

**Đường dẫn mặc định trên VPS:**

| Thành phần | Path / URL |
|------------|------------|
| Repo | `/var/www/ptt` |
| Env | `/var/www/ptt/.env` |
| Staff console | `ops.pttads.vn` hoặc `rs.pttads.vn` |
| Nest API | `ptt-crm-api` (systemd) |
| Webhook Meta | `POST /api/v1/webhooks/meta` |
| Runbook migration | [`runbooks/horizon1-meta-ads-migration-checklist.md`](runbooks/horizon1-meta-ads-migration-checklist.md) |

---

## 3. Triển khai & setup đầy đủ

> Thực hiện **staging trước**, chạy gate script PASS, soak ≥7 ngày, rồi mở rộng production.

### 3.1. Điều kiện tiên quyết

- [ ] PostgreSQL production (`DATABASE_URL`) hoạt động
- [ ] Nest `ptt-crm-api` + ops-web + `ptt_worker` deploy và healthy
- [ ] `PTT_TOKEN_VAULT_KEY` — mã hóa token Meta per client (32 byte, base64url)
- [ ] **Meta App** (Business Manager):
  - Webhook URL trỏ Nest
  - Permissions: `ads_management`, `ads_read`, `leads_retrieval`, …
  - **System User** token cho insights sync & campaign write
- [ ] **Temporal** — workflow campaign write (B6-S4)
- [ ] Backup: `pg_dump` + snapshot env trước cutover

### 3.2. Bước 1 — Apply DDL PostgreSQL

Chạy trên server có `DATABASE_URL`:

```bash
cd /var/www/ptt

# Nền tảng (nếu chưa có)
psql "$DATABASE_URL" -f docs/specs/2026-07-17-postgresql-ddl-v1.sql
psql "$DATABASE_URL" -f docs/specs/2026-07-17-postgresql-ddl-v3-performance.sql

# Meta Enterprise core (B8+)
psql "$DATABASE_URL" -f docs/specs/2026-07-24-postgresql-ddl-v4-meta-enterprise.sql

# Conversion OS / CAPI (B9 — khi bật tracking)
./scripts/apply_pg_ddl_v5_meta_conversion.sh

# Creative registry (B12 — khi link ad ↔ creative)
./scripts/apply_pg_ddl_v9_meta_creative_registry.sh
```

**Verify bảng:**

```sql
SELECT tablename FROM pg_tables
WHERE tablename IN (
  'daily_performance', 'hub_campaign_map', 'capi_event_log',
  'meta_alerts', 'meta_conversion_rules', 'client_channel_accounts'
);
```

### 3.3. Bước 2 — Horizon 1 foundation (H1)

Copy và chỉnh env từ template:

```bash
cp deploy/env.horizon1-meta-ads.example .env.horizon1
# Chỉnh: DATABASE_URL, PTT_TOKEN_VAULT_KEY, CRM_FACEBOOK_* secrets
set -a && source .env.horizon1 && set +a
```

**Biến cốt lõi Horizon 1:**

```bash
PTT_WEBHOOKS_NEST_ENABLED=1
PTT_WEBHOOKS_NEST_META=1
PTT_WEBHOOKS_FLASK_FALLBACK=0
PTT_JOBS_ENABLED=1
PTT_TOKEN_VAULT_KEY=<secret-32-byte>
CRM_FACEBOOK_VERIFY_TOKEN=<meta-app-verify-token>
CRM_FACEBOOK_APP_SECRET=<meta-app-secret>
PTT_META_INSIGHTS_SYNC=1
PTT_META_INSIGHTS_STUB=0          # staging pilot có thể =1
PTT_FLASK_META_ADS_ADMIN_RETIRED=1
```

**Seed quyền staff Meta:**

```bash
python3 scripts/seed_staff_meta_permissions.py
# Hoặc seed full admin:
python3 scripts/seed_super_admin_full_access.py
```

Staff **đăng xuất / đăng nhập lại** ops-web để nhận caps mới.

**Chạy gate Horizon 1:**

```bash
chmod +x scripts/horizon1_meta_ads_pack.sh
./scripts/horizon1_meta_ads_pack.sh preflight
./scripts/horizon1_meta_ads_pack.sh soak    # mỗi ngày ≥7 ngày
./scripts/horizon1_meta_ads_pack.sh evaluate
```

Chi tiết: [`runbooks/horizon1-meta-ads-migration-checklist.md`](runbooks/horizon1-meta-ads-migration-checklist.md)

### 3.4. Bước 3 — Cấu hình Meta App & webhook

1. **Meta Developers** → App → Webhooks:
   - Callback URL: `https://<api-domain>/api/v1/webhooks/meta`
   - Verify token: khớp `CRM_FACEBOOK_VERIFY_TOKEN`
   - Subscribe: `leadgen`, `ad_account` (B13: account disabled, ad disapproved)
2. **Page** — gắn Page access token hoặc dùng per-client vault (ưu tiên).
3. **System User** — token dài hạn cho insights + write; lưu vào channel account qua OAuth hoặc admin paste (vault mã hóa).

### 3.5. Bước 4 — Systemd timers & worker

| Unit | Mô tả |
|------|--------|
| `ptt-meta-insights.timer` | Sync insights hàng ngày T-1 |
| `ptt-meta-token-refresh.timer` | Refresh token Meta |
| `ptt-lead-created-capi.timer` | Drain CAPI queue (B9) |
| `ptt-worker.service` | Job consumer |
| `ptt-fb-autosync.service` | Autosync lead standalone (H1) |
| `ptt-meta-clickhouse-export.timer` | B14 warehouse (nếu bật) |

```bash
sudo systemctl enable --now ptt-meta-insights.timer ptt-meta-token-refresh.timer ptt-worker.service
sudo systemctl status ptt-meta-insights.timer ptt-worker.service
```

Runbook VPS: [`runbooks/vps-production-operations.md`](runbooks/vps-production-operations.md)

### 3.6. Bước 5 — Cấu hình ops-web (Next.js)

Mỗi feature UI có flag `NEXT_PUBLIC_*` — **phải khớp backend** và rebuild sau khi đổi:

```bash
# Ví dụ bật đầy đủ sau soak từng wave
NEXT_PUBLIC_PTT_META_ALERTS_ENABLED=1
NEXT_PUBLIC_PTT_META_TRACKING_ENABLED=1
NEXT_PUBLIC_PTT_META_ANOMALY_ENABLED=1
NEXT_PUBLIC_PTT_META_ROAS_ENABLED=1
NEXT_PUBLIC_PTT_META_ADS_OPS_ENABLED=1
NEXT_PUBLIC_PTT_META_CREATIVE_REGISTRY_ENABLED=1
NEXT_PUBLIC_PTT_META_INSIGHTS_BREAKDOWN=0   # B8.1

cd services/ops-web && npm run build
sudo systemctl restart ops-web   # hoặc unit tương ứng trên VPS
```

Template đầy đủ: `services/ops-web/.env.example`, `deploy/env.meta-enterprise-b*.example`

### 3.7. Bước 6 — Onboard client Meta (admin)

1. **Agency → Clients → [client]** — tạo hoặc mở client (UUID).
2. **Channel accounts** — thêm account `channel=meta`:
   - `external_account_id`: `act_1234567890`
   - OAuth hoặc paste token → vault mã hóa
   - JSON `meta`: `pixel_id`, `facebook_page_id`, `capi_enabled`, `target_cpl_vnd`
3. **Sync insights backfill:**
   ```http
   POST /api/v1/clients/{client_id}/sync/insights
   ```
   Hoặc nút sync trên agency client detail.
4. **Hub map** — map campaign Meta ↔ hub campaign (manual hoặc suggest B8).
5. **Launch QA** — `/crm/launch-qa?client_id=...` — pixel, CAPI test, map coverage.
6. **Pilot allowlists** — thêm UUID vào env tương ứng khi rollout có kiểm soát:
   - `PTT_CAPI_PILOT_CLIENTS`
   - `PTT_META_ADS_OPS_PILOT_CLIENTS`

### 3.8. Setup local dev (developer)

```bash
cd PTTADS

# PostgreSQL local + env
export DATABASE_URL=postgresql://...
export PTT_TOKEN_VAULT_KEY=<dev-key>
export PTT_CRM_API_AUTH_DISABLED=1   # chỉ local

# Nest API
cd services/ptt-crm-api && npm run start:dev

# ops-web
cd services/ops-web
cp .env.example .env.local
# NEXT_PUBLIC_API_URL=http://127.0.0.1:3000
npm run dev

# Worker (terminal riêng)
export PTT_JOBS_ENABLED=1
python3 -m ptt_worker
```

Hub local: `http://localhost:3200/meta/facebook-ads`

E2E gate scripts: `./scripts/wave_b8_gate.sh` … `./scripts/wave_b15_gate.sh`

### 3.9. Rollback nhanh (feature flags)

| Tình huống | Hành động |
|------------|-----------|
| Alerts gây noise | `PTT_META_ALERTS_ENABLED=0` → restart API/worker |
| CAPI lỗi hàng loạt | `PTT_CAPI_ENABLED=0` → restart worker |
| Ads Ops lỗi | `PTT_META_ADS_OPS_ENABLED=0` + `NEXT_PUBLIC_PTT_META_ADS_OPS_ENABLED=0` → rebuild ops-web |
| UI module lỗi | Tắt `NEXT_PUBLIC_PTT_META_*` tương ứng → rebuild |

**Không rollback DDL** — chỉ dùng flags.

---

## 4. Bật tính năng theo wave (pilot → prod)

Quy trình khuyến nghị **mỗi wave**:

```
1. Apply DDL (nếu có)
2. Deploy code + env flags = 0
3. Chạy gate script → PASS
4. Bật flag staging + 1–2 pilot clients
5. Soak ≥7 ngày (B9 CAPI: khuyến nghị 30 ngày)
6. Mở rộng prod (bỏ pilot hoặc thêm clients)
7. Regression gate wave trước
```

| Wave | Env chính | Gate | UI |
|------|-----------|------|-----|
| **H1** | `deploy/env.horizon1-meta-ads.example` | `horizon1_meta_ads_pack.sh` | Hub cơ bản |
| **B8** | `PTT_META_ALERTS_ENABLED=1` | `wave_b8_gate.sh` | Tab Alerts, badges unmapped |
| **B8.1** | `PTT_META_INSIGHTS_BREAKDOWN=1` | `wave_b8_1_gate.sh` | Nút Breakdown campaign |
| **B9** | `PTT_CAPI_ENABLED=1`, `PTT_META_TRACKING_ENABLED=1` | `wave_b9_gate.sh` | `/meta/tracking` |
| **B10** | `PTT_META_ANOMALY_ENABLED=1`, `PTT_META_ROAS_ENABLED=1` | `wave_b10_gate.sh` | `/meta/intelligence` |
| **B11** | forecast, stat anomaly, multi-pixel flags | `wave_b11_gate.sh` | Intelligence nâng cao |
| **B12** | `PTT_META_CREATIVE_REGISTRY_ENABLED=1` | `wave_b12_gate.sh` | Link trên `/crm/creatives` |
| **B13** | `PTT_META_OPS_WEBHOOKS=1` | `wave_b13_gate.sh` | Alert account disabled / ad disapproved |
| **B14** | `PTT_META_WAREHOUSE_EXPORT=1` + ClickHouse | `wave_b14_gate.sh` | Grafana BI |
| **B15** | `PTT_META_ADS_OPS_ENABLED=1` + pilot clients | `wave_b15_gate.sh` | `/meta/ads-ops` |

**Ví dụ B9 — Conversion OS:**

```bash
PTT_CAPI_ENABLED=1
PTT_CAPI_PILOT_CLIENTS=<uuid1>,<uuid2>
PTT_META_TRACKING_ENABLED=1
NEXT_PUBLIC_PTT_META_TRACKING_ENABLED=1
PTT_LAUNCH_QA_META_STRICT=0   # 1 = strict launch_ready
```

**Ví dụ B15 — Ads Ops UI:**

```bash
PTT_META_ADS_OPS_ENABLED=1
NEXT_PUBLIC_PTT_META_ADS_OPS_ENABLED=1
PTT_META_ADS_OPS_PILOT_CLIENTS=<uuid1>,<uuid2>
```

---

## 5. Truy cập & phân quyền

### 5.1. Đăng nhập staff

1. Truy cập `https://ops.pttads.vn/login` (hoặc `rs.pttads.vn`)
2. Sidebar → **Agency & Hub** → **Meta Ads**
3. Flask `/crm/facebook-ads` tự redirect sang `/meta/facebook-ads`

### 5.2. Capability keys

| Cap | Action | Quyền Meta |
|-----|--------|------------|
| `crm_facebook_ads` | view | Xem hub, export, alerts |
| `crm_facebook_ads` | edit | Submit ads ops (fallback), creative registry |
| `crm_agency` | view | Xem hub (fallback) |
| `crm_agency` | configure | Channel account, map, sync, conversion rules |
| `meta_campaign_write` | view | Xem campaign-writes queue |
| `meta_campaign_write` | approve | Approve → Temporal execute Graph |
| `meta_ads_ops` | submit | Submit launch/edit qua wizard B15 |
| `crm_board` | edit | Submit budget/pause write (B6) |

### 5.3. Ma trận vai trò (tóm tắt)

| Vai trò | Hub | Map/sync | Tracking rules | Alerts ack | Write submit | Ads Ops | Approve |
|---------|:---:|:--------:|:--------------:|:----------:|:------------:|:-------:|:-------:|
| Super Admin | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Account Manager | ✓ | ✓ client | view | ✓ | ✓ | ✓ | — |
| Media Buyer (MKT-01/02) | ✓ | ✓ client | view | ✓ | ✓ | ✓ | — |
| Tracking/Tech | ✓ | pixel | ✓ | ✓ | — | — | — |
| Data/BI | ✓ export | view | view | view | — | — | — |
| GDKD | ✓ | view | view | ✓ | — | — | ✓ |

Seed mặc định: `scripts/seed_staff_meta_permissions.py` (MKT-01, MKT-02, AM-01).

### 5.4. Nav ops-web — điều kiện hiển thị

| Link | Điều kiện |
|------|-----------|
| Meta Ads, Ads CPL, Migration | cap `crm_facebook_ads.view` hoặc `crm_agency.view` |
| Meta Ads Ops | cap + `NEXT_PUBLIC_PTT_META_ADS_OPS_ENABLED=1` |
| Meta Tracking | cap + `NEXT_PUBLIC_PTT_META_TRACKING_ENABLED=1` |
| Meta Intelligence | cap + một trong các flag anomaly/ROAS/forecast/pixels |

Nếu **không thấy menu** → kiểm tra §4 (flags) và §5 (caps), rebuild ops-web.

### 5.5. Quy tắc governance (bắt buộc)

1. **Mọi mutate Graph** → `campaign_write_requests` → approver → Temporal.
2. **Create ad** — chỉ qua `/meta/ads-ops` Launch wizard.
3. **Edit creative/copy** — chỉ `update_ad_creative` / `update_ad_copy` qua Edit tab + approve.
4. **Creative swap** — bắt buộc `crm_creatives.status=approved`.
5. **Ad DISAPPROVED** — tick ack trước khi submit edit.
6. **Client offboard** (`tenant_locked`) — block sync, CAPI, launch, edit.
7. **Intelligence** — read-only; Buyer tự tạo write request nếu cần.

---

## 6. Hướng dẫn từng màn hình (UI/UX)

> Layout và component theo [`specs/2026-07-24-meta-enterprise-ui-ux-architecture-design.md`](specs/2026-07-24-meta-enterprise-ui-ux-architecture-design.md).  
> Copy **tiếng Việt**; ID kỹ thuật (campaign_id, act_*) hiển thị monospace phụ.

### 6.1. Meta Ads Hub — `/meta/facebook-ads`

**Mục đích:** Trung tâm điều hành Meta đa client — spend, leads, CPL, map, alerts.

**Layout:**

```
┌─────────────────────────────────────────────────────────────┐
│ Meta Ads Hub                    [Sync status] [Migration]   │
├─────────────────────────────────────────────────────────────┤
│ Filters: Client · Khoảng ngày · Status · Search · Export CSV  │
├──────────┬──────────┬──────────┬──────────┬─────────────────┤
│ Spend    │ Leads CRM│ CPL      │ Unmapped │ Open alerts     │
├──────────┴──────────┴──────────┴──────────┴─────────────────┤
│ Tabs: [Clients] [Campaigns] [Alerts]                        │
│ Footer: attribution model · data freshness · unmapped %     │
└─────────────────────────────────────────────────────────────┘
```

**Thao tác từng bước:**

1. Đăng nhập với cap `crm_facebook_ads` view.
2. **Lọc** client, preset 7/14/30 ngày hoặc custom range (URL-synced query string).
3. **Đọc KPI grid** — Spend, Leads CRM, CPL, % unmapped spend, alerts mở.
4. **Tab Clients** — health từng client: token, CAPI, map coverage → click vào agency client detail.
5. **Tab Campaigns** — bảng campaign:
   - Badges: hub mapped, over target CPL, token lỗi
   - **CPL Δ** so với `target_cpl_vnd`
   - **Breakdown** (B8.1) — placement/device nếu flag bật
   - **Map suggest** — auto-map UTM/name cho campaign chưa map
   - Row actions: Pause/Budget → campaign-writes; Launch/Edit → ads-ops; **Mở Ads Manager ↗**
6. **Tab Alerts** (B8+) — inbox `meta_alerts`:
   - Ack alert đã xử lý
   - Alert `ad_disapproved` → **Edit ad** → `/meta/ads-ops?mode=edit&...`
7. **Export CSV** — scope filtered hoặc all clients.

**Badges:**

| Badge | Ý nghĩa | Hành động |
|-------|---------|-----------|
| Chưa map | Spend chưa map hub | Map campaign / suggest |
| Token lỗi | Token hết hạn/revoked | Refresh OAuth / vault |
| Tenant locked | Client offboard | Không mutate |
| Vượt target | CPL > target × threshold | Review creative/targeting |
| Thiếu pixel | Pixel chưa config | Agency client → meta JSON |

**Empty state:** "Chưa có client Meta active" → link `/agency/clients`.

---

### 6.2. Meta Ads Ops — `/meta/ads-ops` (B15)

**Mục đích:** Launch campaign/ad mới và edit creative/copy có governance — **không** thay Ads Manager đầy đủ.

**URL state:** `tab=launch|edit`, `step=1..5`, `client_id`, `campaign_id`, `ad_id`, `mode=edit` (alias).

#### Tab Launch — wizard 5 bước

| Bước | Nội dung | Validation |
|------|----------|------------|
| 1. Client & account | UUID client + `act_*` | Block offboard / ngoài pilot |
| 2. Objective & budget | Template RE Lead / Traffic, budget VND, tên campaign/adset/ad | Min budget |
| 3. Creative | Chọn creative **approved** từ CRM | Bắt buộc |
| 4. Tracking | Preflight checklist (pixel, CAPI, map) | Link Launch QA |
| 5. Review & submit | Tóm tắt + preflight all green | Block nếu fail |

**Sau submit:** Request `change_type=create_campaign` → `/crm/campaign-writes` → approve → Temporal → Graph.

**Deep link:** **Mở Ads Manager ↗** — audience/catalog phức tạp làm trên Meta native.

#### Tab Edit — wizard 4 bước

| Bước | Nội dung |
|------|----------|
| 1. Chọn ad | Client + `external_ad_id`; snapshot Graph (cached) |
| 2. Creative / copy | Swap creative HOẶC sửa headline/primary text |
| 3. Diff review | So sánh old vs new (audit bắt buộc) |
| 4. Submit | Preflight edit + tick ack nếu DISAPPROVED |

**Entry points:**

- Hub Alerts → **Edit ad**
- CRM creatives → registry link → **Edit ad**
- URL: `/meta/ads-ops?mode=edit&client_id=...&ad_id=...&ack=1`

**Preflight fail — kiểm tra:**

| Check | Nguồn |
|-------|--------|
| Pixel + page | `client_channel_accounts.meta` |
| CAPI test OK | `/meta/tracking` |
| Hub map / UTM | `hub_campaign_map` |
| Creative approved | `crm_creatives` |
| Client not locked | Offboard B7 |
| Pilot allowlist | `PTT_META_ADS_OPS_PILOT_CLIENTS` |

---

### 6.3. Meta Tracking — `/meta/tracking` (B9)

**Mục đích:** Giám sát CAPI, conversion rules, pixel test, launch preflight.

| Khối UI | Chức năng |
|---------|-----------|
| Chọn client | Filter `?client_id=` hoặc dropdown |
| KPI 7 ngày | sent / failed / skipped / latency CAPI |
| Preflight checklist | Pixel, CAPI recent, map (đồng bộ Launch QA) |
| Account/pixel table | Per channel account; nút **Test pixel** |
| CAPI events | Log `capi_event_log`; retry failed |
| Conversion rules CRUD | Map `lead_status` → Meta event (cap configure) |

**Quy trình CAPI pilot:**

1. Bật `PTT_CAPI_ENABLED=1` + pilot client UUID.
2. Config pixel + `capi_enabled` trên channel account.
3. Gửi test lead qua Meta webhook → event **Lead** trong Events Manager <5 phút.
4. Chuyển lead CRM qualified → rule fire `CompleteRegistration` (nếu config).
5. Theo dõi fail rate alert (<10% khuyến nghị).

---

### 6.4. Meta Intelligence — `/meta/intelligence` (B10–B11)

**Mục đích:** ROAS, anomaly, budget recommend, forecast — **read-only**.

| Panel | Wave | Mô tả |
|-------|------|--------|
| ROAS KPI + chart | B10 | `conversion_value / spend` |
| Anomalies (median) | B10 | Spike spend/CPL |
| Stat anomalies (z-score) | B11 | 14d z-score |
| Budget recommendations | B10 | Read-only; link → campaign-writes |
| Forecast | B11 | CPL slope 7 ngày |
| Adset insights | B10 | Khi `PTT_META_INSIGHTS_LEVEL=adset` |
| Multi-pixel table | B11 | Primary pixel routing |

**CTA mutate:** Intelligence chỉ **gợi ý** — tạo write request tại `/crm/campaign-writes` hoặc hub.

---

### 6.5. Campaign Writes — `/crm/campaign-writes`

**Mục đích:** Hàng đợi governance cho mọi thay đổi Graph.

| change_type | Nguồn |
|-------------|-------|
| `daily_budget`, `status`, `name` | Hub / CRM (B6) |
| `create_campaign` | Ads Ops Launch (B15) |
| `update_ad_creative`, `update_ad_copy` | Ads Ops Edit (B15) |

**Approver flow:**

1. Mở request pending → xem old/new value JSON + human summary.
2. **Approve** → Temporal → Graph API.
3. **Reject** → ghi note bắt buộc; không execute.
4. Theo dõi: `executed` / `execution_failed`.

**UI pattern:** Banner "X write chờ duyệt" khi `stats.pending > 0`.

---

### 6.6. Launch QA — `/crm/launch-qa`

**Mục đích:** Gate trước khi client `launch_ready` và trước Ads Ops create.

Checklist Meta (B9):

- Pixel configured
- CAPI test event OK
- Hub map coverage ≥80% spend (khuyến nghị)
- CAPI sent trong 48h (`PTT_LAUNCH_QA_META_STRICT=1` = strict)

Link từ Ads Ops bước 4 Tracking → **Launch QA board**.

---

### 6.7. CRM Creatives + Registry — `/crm/creatives` (B12)

1. Creative submit → review → **approved**.
2. Mở creative row → **Meta ad link** → gắn `external_ad_id`.
3. Link active → **Edit ad** → Ads Ops Edit tab.

Registry bridge B12 ↔ B15 upload creative lên Graph khi launch/edit.

---

### 6.8. Ads CPL — `/meta/ads-combined`

Tổng hợp CPL Meta + Google — cross-channel view cho AM/GDKD. Drill-down về hub từng kênh.

---

### 6.9. Meta Migration — `/meta/migration`

Panel Horizon 1 — gate report, soak evidence, nginx redirect status. Ẩn dần sau khi Flask Meta admin retired hoàn toàn.

---

### 6.10. UX patterns chung (staff)

| Pattern | Quy ước |
|---------|---------|
| VND | `1.234.567 ₫` (vi-VN) |
| Ngày | `dd/mm/yyyy` hiển thị; ISO trong API |
| Empty | Em dash `—` |
| 403 thiếu cap | Inline "Không có quyền" — ẩn action |
| 422 preflight | Checklist đỏ + block submit |
| Submit write | Modal tóm tắt → "Gửi duyệt" |
| Reject write | Note **bắt buộc** |

---

## 7. Luồng nghiệp vụ end-to-end

### 7.1. Onboard client Meta mới

```
AM tạo client
  → Configure channel account (act_*, pixel, page, token)
  → POST sync/insights (backfill 35d)
  → Map campaigns (manual + suggest)
  → Launch QA checklist pass
  → Thêm vào pilot allowlists (CAPI, ads-ops nếu cần)
  → Client portal /meta live
```

### 7.2. Ngày vận hành (Media Buyer)

```
08:00 — Insights T-1 sync xong
  → /meta/facebook-ads — review CPL Δ, alerts
  → Ack alerts đã xử lý
  → Campaign chưa map → Map suggest
  → CPL cao → /meta/intelligence
  → Pause/budget → campaign-writes
  → Launch mới → /meta/ads-ops Launch
  → Ad disapproved → Alerts → Edit ad
```

### 7.3. Launch campaign mới (B15)

```
Creative approved (/crm/creatives)
  → /meta/ads-ops Launch 5 bước
  → Preflight pass
  → Submit for approval
  → GDKD approve (/crm/campaign-writes)
  → Temporal MetaCampaignCreateWorkflow
  → Verify trên Ads Manager / hub sync ngày sau
```

### 7.4. Edit ad disapproved (B13 + B15)

```
Webhook ad_disapproved → meta_alerts
  → Hub Alerts → Edit ad
  → Swap creative approved HOẶC sửa copy
  → Tick ack DISAPPROVED → Diff → Submit → Approve → Graph
```

### 7.5. Offboard client (B7)

```
POST /clients/:id/offboard
  → Revoke token vault
  → tenant_locked = true
  → Cancel pending jobs/workflows
  → Block sync, CAPI, ads-ops submit
```

---

## 8. Jobs, alerts & observability

### 8.1. Job types Meta

| job_type | Trigger |
|----------|---------|
| `meta_insights_sync` | Daily cron, manual |
| `meta_token_refresh` | Timer |
| `capi_dispatch` | Lead created, cron 5m |
| `meta_alerts_eval` | Post sync |
| `meta_ops_webhook` | B13 webhook |
| `meta_clickhouse_export` | B14 daily |

### 8.2. Alert catalog (chọn lọc)

| alert_type | Ý nghĩa |
|------------|---------|
| `cpl_high` | CPL vượt target |
| `unmapped_spend_high` | >15% spend chưa map |
| `sync_failed` | Token lỗi >24h |
| `capi_fail_rate` | CAPI fail >10% |
| `meta_account_disabled` | Account bị vô hiệu (B13) |
| `ad_disapproved` | Ad bị từ chối (B13) |

Dedupe: `{alert_type}:{client_id}:{campaign_id}:{date}`

### 8.3. Observability

- Gate reports: `.local-dev/wave_b*_gate_report.json`
- Soak: `.local-dev/horizon1-meta-ads-soak-evidence.jsonl`
- Grafana: `deploy/grafana/meta-ops-dashboard.json` (B14)
- Runbooks: [`meta-insights-replay.md`](runbooks/meta-insights-replay.md), [`meta-token-refresh.md`](runbooks/meta-token-refresh.md)

---

## 9. Client Portal Meta

**Route:** `https://portal.pttads.vn/meta`

**Component:** `PerformancePanel channel="meta"` — read-only.

| Tính năng | Ghi chú |
|-----------|---------|
| KPI cards | spend, leads, CPL, delta vs target |
| Bảng campaign | Read-only; CPL delta column (B8) |
| `hub_mapped` badge | Cảnh báo unmapped (B8) |
| Attribution footer | Model + unmapped % + through_date |
| Export CSV | Tenant-isolated JWT |
| ROAS | Hiển thị khi B10 bật và không stub |

**Ràng buộc portal:**

- **Không** nút write, **không** Ads Manager link
- **Không** client picker — `client_id` từ JWT
- Export CSV/PDF only

---

## 10. Xử lý sự cố thường gặp

### Hub không có data / spend = 0

1. `client_channel_accounts.token_status=active`
2. Manual sync: `POST /clients/:id/sync/insights`
3. Sync status chip trên hub
4. Staging: `PTT_META_INSIGHTS_STUB=0`

### CPL / leads CRM = 0 nhưng Meta có lead

1. Hub map chưa có — campaign unmapped
2. Lead thiếu UTM / `meta_json.campaign_id`
3. Map suggest; kiểm tra webhook lead ingest Nest

### Menu Meta Ads Ops / Tracking không hiện

1. Backend flag = 1?
2. `NEXT_PUBLIC_*` khớp + rebuild ops-web?
3. Staff caps đủ?

### Launch wizard preflight fail

1. Pixel/page trên channel account
2. CAPI test trên `/meta/tracking`
3. Creative chưa approved
4. Client `tenant_locked`
5. Client không trong pilot allowlist

### Campaign write execution_failed

1. Token thiếu scope `ads_management`
2. Graph rate limit — retry
3. Temporal logs + request `new_value` JSON

### Webhook lead không vào CRM

1. `PTT_WEBHOOKS_NEST_META=1`, Flask fallback = 0
2. Verify token khớp Meta App
3. Page/form mapping → client_id
4. Log Nest `webhooks/meta`

---

## 11. Checklist go-live

### Horizon 1 (foundation)

- [ ] DDL v1 + v3-performance applied
- [ ] `horizon1_meta_ads_pack.sh preflight` PASS
- [ ] Soak ≥7 ngày evidence
- [ ] ops-web hub live; Flask redirect verified
- [ ] Webhook Nest-only; test lead ingest
- [ ] Staff caps seeded

### B8 — Measurement

- [ ] DDL v4 meta enterprise
- [ ] `wave_b8_gate.sh` PASS
- [ ] Alerts pilot 1–2 clients
- [ ] Hub badges + tab Alerts

### B9 — Conversion OS

- [ ] DDL v5 conversion
- [ ] CAPI pilot soak 30d (khuyến nghị)
- [ ] `/meta/tracking` + Launch QA strict policy
- [ ] `wave_b9_gate.sh` PASS

### B10–B11 — Intelligence

- [ ] ROAS + anomaly không auto-mutate verified
- [ ] Gate B10/B11 PASS

### B12 — Creative registry

- [ ] DDL v9 applied
- [ ] Link creative ↔ ad trên `/crm/creatives`

### B13 — Ops webhooks

- [ ] Webhook subscribe ad account events
- [ ] Alert disapproved → Edit ad flow E2E

### B14 — Warehouse (optional)

- [ ] ClickHouse + export timer + Grafana dashboard

### B15 — Ads Ops

- [ ] Pilot clients trong allowlist
- [ ] Launch + Edit E2E qua approve queue
- [ ] `wave_b15_gate.sh` PASS

### Portal

- [ ] Client JWT isolation verified
- [ ] Export CSV tenant-scoped
- [ ] Không lộ staff-only data

---

## 12. Phụ lục — env, API, tài liệu liên quan

### 12.1. Master feature flags (prod-safe defaults)

| Variable | Default | UI/API |
|----------|---------|--------|
| `PTT_META_INSIGHTS_SYNC` | 1 | Insights job |
| `PTT_META_ALERTS_ENABLED` | 0→1 | Alerts PG |
| `PTT_CAPI_ENABLED` | 0→1 | CAPI dispatch |
| `PTT_META_TRACKING_ENABLED` | 0 | `/meta/tracking` API |
| `NEXT_PUBLIC_PTT_META_TRACKING_ENABLED` | 0 | Nav tracking |
| `PTT_META_ANOMALY_ENABLED` | 0 | Anomaly API |
| `NEXT_PUBLIC_PTT_META_ANOMALY_ENABLED` | 0 | Intelligence nav |
| `PTT_META_ADS_OPS_ENABLED` | 0 | ads-ops API |
| `NEXT_PUBLIC_PTT_META_ADS_OPS_ENABLED` | 0 | `/meta/ads-ops` |
| `PTT_META_OPS_WEBHOOKS` | 0 | B13 parser |
| `PTT_META_WAREHOUSE_EXPORT` | 0 | B14 ETL |

### 12.2. API staff chính (prefix `/api/v1/`)

| Method | Path | Màn hình |
|--------|------|----------|
| GET | `/facebook-ads/hub` | Meta Ads Hub |
| GET | `/facebook-ads/hub/export` | Export CSV |
| GET | `/meta/alerts` | Tab Alerts |
| PATCH | `/meta/alerts/:id/ack` | Ack alert |
| GET | `/meta/tracking/health` | Tracking |
| GET/POST/PATCH/DELETE | `/meta/conversion-rules` | Rules CRUD |
| GET | `/meta/anomalies`, `/meta/roas` | Intelligence |
| GET | `/meta/ads-ops/templates` | Ads Ops |
| POST | `/meta/ads-ops/launch` | Launch submit |
| POST | `/meta/ads-ops/edit/submit` | Edit submit |
| GET/POST | `/crm/campaign-writes/*` | Approve queue |
| POST | `/webhooks/meta` | Meta webhook (public) |

### 12.3. Env templates theo wave

| File | Wave |
|------|------|
| `deploy/env.horizon1-meta-ads.example` | H1 |
| `deploy/env.meta-enterprise-b8.example` | B8 |
| `deploy/env.meta-enterprise-b9.example` | B9 |
| `deploy/env.meta-enterprise-b10.example` | B10 |
| `deploy/env.meta-enterprise-b11.example` | B11 |
| `deploy/env.meta-enterprise-b8-1.example` | B8.1 |
| `deploy/env.meta-enterprise-b12.example` | B12 |
| `deploy/env.meta-enterprise-b13.example` | B13 |
| `deploy/env.meta-enterprise-b14.example` | B14 |
| `deploy/env.meta-enterprise-b15.example` | B15 |

### 12.4. Tài liệu liên quan

| Tài liệu | Nội dung |
|----------|----------|
| [`SPEC_META_ENTERPRISE_PTTADS.md`](SPEC_META_ENTERPRISE_PTTADS.md) | Master spec §1–§28 |
| [`specs/2026-07-24-meta-enterprise-ui-ux-architecture-design.md`](specs/2026-07-24-meta-enterprise-ui-ux-architecture-design.md) | UI/UX route specs |
| [`runbooks/horizon1-meta-ads-migration-checklist.md`](runbooks/horizon1-meta-ads-migration-checklist.md) | Migration Flask → ops-web |
| [`META_ENTERPRISE_GUIDE.md`](META_ENTERPRISE_GUIDE.md) | Bản rút gọn / mirror (cùng nội dung cốt lõi) |
| [`huong-dan-seo-aeo-ops.md`](huong-dan-seo-aeo-ops.md) | Phân hệ SEO/AEO (tách biệt) |

---

*Tài liệu phản ánh codebase sau wave B15 (2026-07-25). Khi spec cập nhật, đối chiếu §14–§18 trong [`SPEC_META_ENTERPRISE_PTTADS.md`](SPEC_META_ENTERPRISE_PTTADS.md).*
