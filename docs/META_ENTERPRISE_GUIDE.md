# Hướng dẫn Setup & Sử dụng — Meta Enterprise trên PTTADS

> **Canonical (đầy đủ):** [`huong-dan-meta-enterprise-ops.md`](huong-dan-meta-enterprise-ops.md) — bản vận hành chính thức, cùng cấu trúc với [`huong-dan-seo-aeo-ops.md`](huong-dan-seo-aeo-ops.md).  
> **Phiên bản tài liệu:** 1.0 · **Ngày:** 2026-07-25  
> **Canonical spec:** [`SPEC_META_ENTERPRISE_PTTADS.md`](SPEC_META_ENTERPRISE_PTTADS.md)  
> **Đối tượng:** Super Admin, GDKD, Account Manager, Media Buyer, Tracking/Tech, Data/BI  
> **Môi trường:** `https://ops.pttads.vn` (staff) · `https://portal.pttads.vn` (client)

---

## Mục lục

1. [Tổng quan phân hệ Meta](#1-tổng-quan-phân-hệ-meta)
2. [Yêu cầu & tiên quyết](#2-yêu-cầu--tiên-quyết)
3. [Setup hệ thống (đầy đủ)](#3-setup-hệ-thống-đầy-đủ)
4. [Bật tính năng theo wave (pilot → prod)](#4-bật-tính-năng-theo-wave-pilot--prod)
5. [RBAC, quyền & governance](#5-rbac-quyền--governance)
6. [Bản đồ UI ops-web & portal](#6-bản-đồ-ui-ops-web--portal)
7. [Hướng dẫn sử dụng từng màn hình](#7-hướng-dẫn-sử-dụng-từng-màn-hình)
8. [Luồng nghiệp vụ end-to-end](#8-luồng-nghiệp-vụ-end-to-end)
9. [KPI, attribution & báo cáo](#9-kpi-attribution--báo-cáo)
10. [Jobs, alerts & observability](#10-jobs-alerts--observability)
11. [Gates, nghiệm thu & rollback](#11-gates-nghiệm-thu--rollback)
12. [Troubleshooting thường gặp](#12-troubleshooting-thường-gặp)
13. [Phụ lục — env flags & API](#13-phụ-lục--env-flags--api)

---

## 1. Tổng quan phân hệ Meta

Meta Enterprise trên PTTADS là **bounded context quảng cáo Meta đa client** trên nền Agency Operating Platform — không phải tab CRM lẻ hay Flask monolith cũ.

### 1.1. Vòng đời closed-loop

```
Onboard client → Kết nối ad account (Meta) → Sync insights T-1
              → Hub map campaign ↔ CRM → Tính CPL/ROAS
              → Lead webhook (Nest) → CAPI + CRM conversions
              → Intelligence (anomaly, recommend) → Governed write (Temporal)
              → Launch/Edit Ads Ops wizard (B15) → Client portal performance
              → Offboard & revoke token
```

### 1.2. Thành phần kỹ thuật

| Lớp | Thành phần | Vai trò |
|-----|------------|---------|
| **UI staff** | ops-web `/meta/*` | Hub, tracking, intelligence, ads-ops |
| **UI client** | portal-web `/meta` | Performance read-only |
| **API** | NestJS `ptt-crm-api` | Hub, tracking, alerts, ads-ops, webhooks |
| **Workers** | `ptt_worker` + `ptt_jobs` | Insights sync, CAPI, alerts eval, archive |
| **Domain** | `ptt_meta/*` | Insights, CAPI, alerts, ads ops helpers |
| **DB** | PostgreSQL | `daily_performance`, `hub_campaign_map`, `capi_event_log`, … |
| **Governance** | Temporal + `campaign_write_requests` | Mọi mutate Graph phải approve |

### 1.3. Nguyên tắc vận hành quan trọng

1. **`client_id` first** — mọi dữ liệu Meta scope theo client UUID.
2. **Canonical UI** — staff dùng ops-web `/meta/facebook-ads`; Flask `/crm/facebook-ads` redirect (Horizon 1).
3. **Governance before mutate** — pause/budget/create/edit đều qua campaign-writes + approve.
4. **Feature flags + pilot allowlist** — bật từng wave, soak ≥7 ngày trước khi mở rộng prod.
5. **Không clone Ads Manager** — audience phức tạp, catalog, Advantage+ → deep link Meta.

---

## 2. Yêu cầu & tiên quyết

### 2.1. Hạ tầng

| Thành phần | Yêu cầu |
|------------|---------|
| PostgreSQL | DDL v1 + v3-performance + v4 meta enterprise (v5 conversion, v9 creative registry nếu dùng B12) |
| Nest API | `ptt-crm-api` chạy, staff auth + caps seed |
| ops-web | Next.js build với env `NEXT_PUBLIC_*` khớp backend |
| ptt_worker | Consumer `job_queue` active |
| Token vault | `PTT_TOKEN_VAULT_KEY` — token Meta mã hóa per client |
| Meta App | Webhook URL, `ads_management`, System User token |
| Temporal | Campaign write workflow (B6) — bắt buộc cho mutate |

### 2.2. Tiên quyết theo wave

| Wave | Phụ thuộc | Ghi chú |
|------|-----------|---------|
| H1 + B6 | Client, channel account, hub cơ bản | Foundation |
| B8 | DDL v4 `meta_alerts` | Measurement parity |
| B9 | B8 + CAPI pilot soak 30d khuyến nghị | Conversion OS |
| B10–B11 | B9 tracking ổn định | Intelligence |
| B12 | DDL v9 creative registry | Link ad ↔ creative |
| B13 | B8 alerts + webhook Meta | Ops webhooks |
| B14 | ClickHouse stack | Warehouse BI |
| B15 | B6 write + B9 Launch QA + B12 (partial OK) | Ads Ops UI |

### 2.3. Tài khoản Meta cần chuẩn bị

- **Ad account** (`act_*`) per client — lưu trong `client_channel_accounts`.
- **Pixel ID** + **Facebook Page ID** — JSON field `meta` trên channel account.
- **System User** với quyền `ads_management` (B15 create/edit).
- **Webhook subscriptions** — leadgen, ad account status (B13).

---

## 3. Setup hệ thống (đầy đủ)

### 3.1. Thứ tự apply DDL PostgreSQL

Chạy trên server có `DATABASE_URL`:

```bash
cd /path/to/PTTADS

# Nền tảng (nếu chưa có)
psql "$DATABASE_URL" -f docs/specs/2026-07-17-postgresql-ddl-v1.sql
# … v3-leads-oltp, v3-performance (bắt buộc cho daily_performance)

# B8+ Meta Enterprise
psql "$DATABASE_URL" -f docs/specs/2026-07-24-postgresql-ddl-v4-meta-enterprise.sql

# B9 Conversion OS (nếu dùng tracking/CAPI đầy đủ)
./scripts/apply_pg_ddl_v5_meta_conversion.sh

# B12 Creative registry (nếu dùng link ad ↔ creative)
./scripts/apply_pg_ddl_v9_meta_creative_registry.sh
```

**Kiểm tra:** bảng `meta_alerts`, `meta_conversion_rules`, `daily_performance`, `hub_campaign_map`, `capi_event_log` tồn tại.

### 3.2. Seed quyền staff Meta

```bash
cd /path/to/PTTADS
python3 scripts/seed_staff_meta_permissions.py
```

Gán caps cho từng role theo ma trận §5. Staff mới login lại ops-web để nhận caps.

### 3.3. Cấu hình môi trường backend (Nest + worker)

Copy các dòng cần thiết từ template env vào file deploy thực tế (ví dụ `.env` trên VPS):

| Template | Wave | File |
|----------|------|------|
| Horizon 1 | H1 | `deploy/env.horizon1-meta-ads.example` |
| B8 | Measurement | `deploy/env.meta-enterprise-b8.example` |
| B9 | Tracking/CAPI | `deploy/env.meta-enterprise-b9.example` |
| B10 | Intelligence | `deploy/env.meta-enterprise-b10.example` |
| B11 | Advanced | `deploy/env.meta-enterprise-b11.example` |
| B8.1 | Breakdown | `deploy/env.meta-enterprise-b8-1.example` |
| B12 | Creative registry | `deploy/env.meta-enterprise-b12.example` |
| B13 | Ops webhooks | `deploy/env.meta-enterprise-b13.example` |
| B14 | Warehouse BI | `deploy/env.meta-enterprise-b14.example` |
| B15 | Ads Ops UI | `deploy/env.meta-enterprise-b15.example` |

**Biến nền (luôn cần):**

```bash
# Token vault — KHÔNG commit secret
PTT_TOKEN_VAULT_KEY=<32-byte-key>

# Insights sync (prod thường = 1)
PTT_META_INSIGHTS_SYNC=1
PTT_META_INSIGHTS_STUB=0

# Webhook Nest (H1)
PTT_WEBHOOKS_NEST_META=1
```

### 3.4. Cấu hình ops-web (Next.js)

Mỗi feature UI có flag public tương ứng — **phải khớp backend**:

```bash
# Ví dụ bật tracking + ads ops trên ops-web
NEXT_PUBLIC_PTT_META_TRACKING_ENABLED=1
NEXT_PUBLIC_PTT_META_ALERTS_ENABLED=1
NEXT_PUBLIC_PTT_META_ADS_OPS_ENABLED=1
NEXT_PUBLIC_PTT_META_CREATIVE_REGISTRY_ENABLED=1
NEXT_PUBLIC_PTT_META_INSIGHTS_BREAKDOWN=0   # B8.1
```

Rebuild ops-web sau khi đổi env:

```bash
cd services/ops-web && npm run build
```

### 3.5. Systemd / timers (VPS)

| Unit | Mô tả |
|------|--------|
| `ptt-meta-insights.timer` | Sync insights hàng ngày T-1 |
| `ptt-meta-token-refresh.timer` | Refresh token Meta |
| `ptt-lead-created-capi.timer` | Drain CAPI queue |
| `ptt-worker.service` | Job consumer |
| `ptt-meta-clickhouse-export.timer` | B14 warehouse (nếu bật) |

Chi tiết: [`runbooks/vps-production-operations.md`](runbooks/vps-production-operations.md)

### 3.6. Onboard client Meta (bước admin)

1. **Agency → Clients → [client]** — tạo hoặc mở client.
2. **Channel accounts** — thêm account `channel=meta`:
   - `external_account_id`: `act_1234567890`
   - OAuth hoặc paste token → vault mã hóa
   - `meta.pixel_id`, `meta.facebook_page_id`
   - `meta.capi_enabled=1` (khi sẵn sàng CAPI)
   - `meta.target_cpl_vnd` (ngưỡng alert CPL)
3. **Sync insights backfill:**
   ```http
   POST /api/v1/clients/{client_id}/sync/insights
   ```
   Hoặc nút sync trên agency client detail.
4. **Hub map** — map campaign Meta ↔ hub campaign (manual hoặc suggest B8).
5. **Launch QA** — `/crm/launch-qa?client_id=...` — pixel, CAPI test, map coverage.
6. **Pilot flags** — thêm `client_id` vào allowlist tương ứng (`PTT_CAPI_PILOT_CLIENTS`, `PTT_META_ADS_OPS_PILOT_CLIENTS`, …).

---

## 4. Bật tính năng theo wave (pilot → prod)

Quy trình khuyến nghị cho mỗi wave:

```
1. Apply DDL (nếu có)
2. Deploy code + env flags = 0
3. Chạy gate script → PASS
4. Bật flag staging + 1–2 pilot clients
5. Soak ≥7 ngày (B9 CAPI khuyến nghị 30 ngày)
6. Mở rộng prod (bỏ pilot hoặc thêm clients)
7. Regression gate wave trước
```

### 4.1. B8 — Measurement & alerts

```bash
PTT_META_ALERTS_ENABLED=1
PTT_META_ALERT_CPL_PCT=15
PTT_META_ALERT_UNMAPPED_SPEND_PCT=15
```

Gate: `./scripts/wave_b8_gate.sh`

**UI:** Hub badges unmapped, tab Alerts PG, sync status chip.

### 4.2. B8.1 — Breakdown & RBAC

```bash
PTT_META_INSIGHTS_BREAKDOWN=1
NEXT_PUBLIC_PTT_META_INSIGHTS_BREAKDOWN=1
```

**UI:** Nút **Breakdown** trên campaign row (publisher_platform, …).

### 4.3. B9 — Conversion OS / Tracking

```bash
PTT_CAPI_ENABLED=1
PTT_CAPI_PILOT_CLIENTS=<uuid1>,<uuid2>
PTT_META_TRACKING_ENABLED=1
NEXT_PUBLIC_PTT_META_TRACKING_ENABLED=1
PTT_LAUNCH_QA_META_STRICT=0   # 1 = strict launch_ready
```

Gate: `./scripts/wave_b9_gate.sh`

**UI:** `/meta/tracking` — health, CAPI events, conversion rules, test pixel.

### 4.4. B10–B11 — Intelligence

```bash
PTT_META_ANOMALY_ENABLED=1
PTT_META_ROAS_ENABLED=1
NEXT_PUBLIC_PTT_META_ANOMALY_ENABLED=1
NEXT_PUBLIC_PTT_META_ROAS_ENABLED=1
# B11 optional:
PTT_META_ANOMALY_STAT_ENABLED=1
PTT_META_FORECAST_ENABLED=1
PTT_META_PIXELS_ENABLED=1
```

Gate: `./scripts/wave_b10_gate.sh`, `./scripts/wave_b11_gate.sh`

**UI:** `/meta/intelligence` — ROAS, anomaly, recommend, forecast, multi-pixel.

### 4.5. B12 — Creative registry

```bash
PTT_META_CREATIVE_REGISTRY_ENABLED=1
NEXT_PUBLIC_PTT_META_CREATIVE_REGISTRY_ENABLED=1
```

**UI:** Panel **Meta ad link** trên `/crm/creatives` — gắn `external_ad_id` ↔ creative approved.

### 4.6. B13 — Ops webhooks

```bash
PTT_META_OPS_WEBHOOKS=1
PTT_META_ALERTS_ENABLED=1
```

Webhook Meta → `POST /api/v1/webhooks/meta` — alert `meta_account_disabled`, `ad_disapproved`.

Gate: `./scripts/wave_b13_gate.sh`

### 4.7. B14 — Warehouse BI

```bash
PTT_META_WAREHOUSE_EXPORT=1
CLICKHOUSE_URL=http://127.0.0.1:8123
# Import deploy/grafana/meta-ops-dashboard.json
```

Gate: `./scripts/wave_b14_gate.sh`

### 4.8. B15 — Ads Ops UI

```bash
PTT_META_ADS_OPS_ENABLED=1
NEXT_PUBLIC_PTT_META_ADS_OPS_ENABLED=1
PTT_META_ADS_OPS_PILOT_CLIENTS=<uuid1>,<uuid2>
```

Gate: `./scripts/wave_b15_gate.sh`

**UI:** `/meta/ads-ops` — Launch wizard + Edit wizard.

---

## 5. RBAC, quyền & governance

### 5.1. Capability keys (staff)

| Cap | Action | Quyền Meta |
|-----|--------|------------|
| `crm_facebook_ads` | view | Xem hub, export, alerts |
| `crm_agency` | configure | Channel account, map, sync, rules |
| `meta_campaign_write` | view | Xem campaign-writes queue |
| `meta_campaign_write` | approve | Approve → Temporal execute Graph |
| `meta_ads_ops` | submit | Submit launch/edit qua wizard B15 |
| `crm_board` | edit | Submit budget/pause write (B6) |
| `crm_facebook_ads` | edit | Submit ads ops (fallback cap) |

### 5.2. Ma trận vai trò (tóm tắt)

| Vai trò | Hub | Map/sync | Tracking rules | Alerts ack | Write submit | Ads Ops | Approve |
|---------|:---:|:--------:|:--------------:|:----------:|:------------:|:-------:|:-------:|
| Super Admin | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Account Manager | ✓ | ✓ client | view | ✓ | ✓ | ✓ | — |
| Media Buyer | ✓ | ✓ client | view | ✓ | ✓ | ✓ | — |
| Tracking/Tech | ✓ | pixel | ✓ | ✓ | — | — | — |
| Data/BI | ✓ export | view | view | view | — | — | — |

### 5.3. Quy tắc governance (bắt buộc tuân thủ)

1. **Mọi mutate Graph** → `campaign_write_requests` → approver → Temporal.
2. **Create ad** — chỉ qua `/meta/ads-ops` Launch wizard, không API/UI khác.
3. **Edit creative/copy** — chỉ `update_ad_creative` / `update_ad_copy` qua Edit tab + approve.
4. **Creative swap** — bắt buộc `crm_creatives.status=approved`.
5. **Ad DISAPPROVED** — phải tick ack trước khi submit edit.
6. **Client offboard** (`tenant_locked`) — block sync, CAPI, launch, edit.
7. **Recommendations (B10)** — read-only; Buyer tự tạo write request nếu cần.

---

## 6. Bản đồ UI ops-web & portal

### 6.1. Menu Agency → Meta (ops-web)

| Route | Tên nav | Wave | Mô tả ngắn |
|-------|---------|------|------------|
| `/meta/facebook-ads` | Meta Ads | H1+ | Hub chính — KPI, clients, campaigns, alerts |
| `/meta/ads-ops` | Meta Ads Ops | B15 | Launch + Edit wizard |
| `/meta/tracking` | Meta Tracking | B9 | CAPI health, rules, test pixel |
| `/meta/intelligence` | Meta Intelligence | B10+ | ROAS, anomaly, recommend |
| `/meta/ads-combined` | Ads CPL | B6 | Meta + Google summary |
| `/meta/migration` | Meta Migration | H1 | Horizon 1 signoff |

Nav items phụ thuộc **feature flag + cap** — nếu không thấy menu, kiểm tra §4 và §5.

### 6.2. CRM liên quan Meta

| Route | Mô tả |
|-------|--------|
| `/crm/campaign-writes` | Hàng đợi approve mutate (pause, budget, create, edit) |
| `/crm/launch-qa` | Checklist launch — gate trước create ads |
| `/crm/creatives` | Creative inbox + registry link B12 |
| `/agency/clients/:id` | Channel accounts, sync, onboarding |

### 6.3. Portal client

| Route | Mô tả |
|-------|--------|
| `/meta` | Performance Meta read-only |
| `/dashboard` | KPI tổng hợp |

Client **không** có quyền write, rules, hay ads-ops wizard.

---

## 7. Hướng dẫn sử dụng từng màn hình

### 7.1. Meta Ads Hub — `/meta/facebook-ads`

**Mục đích:** Trung tâm điều hành Meta đa client — spend, leads, CPL, map, alerts.

#### Layout

```
┌─────────────────────────────────────────────────────────────┐
│ Meta Ads Hub                    [Sync status] [Migration]   │
├─────────────────────────────────────────────────────────────┤
│ Filters: Client · Khoảng ngày · Status · Search · Export    │
├──────────┬──────────┬──────────┬──────────┬─────────────────┤
│ Spend    │ Leads CRM│ CPL      │ Unmapped │ Inline alerts   │
├──────────┴──────────┴──────────┴──────────┴─────────────────┤
│ Tabs: [Clients] [Campaigns] [Alerts]                        │
└─────────────────────────────────────────────────────────────┘
```

#### Thao tác từng bước

1. **Đăng nhập** ops-web với staff có cap `crm_facebook_ads` view.
2. **Lọc client / ngày** — dropdown client, preset 7/14/30 ngày hoặc custom range.
3. **Đọc KPI grid** — Spend, Leads CRM, CPL, % unmapped spend.
4. **Footer attribution** — model `last_touch_crm`, `data_freshness`, `unmapped_spend_pct`.
5. **Tab Clients** — health từng client: token, CAPI, map coverage; click → agency client detail.
6. **Tab Campaigns** — bảng campaign:
   - **Badges:** hub mapped, over target CPL
   - **CPL Δ** — so với target
   - **Breakdown** (B8.1) — placement/device nếu flag bật
   - **Map suggest** — auto-map UTM/name cho campaign chưa map
7. **Tab Alerts** (B8+) — inbox `meta_alerts` PG:
   - Ack alert đã xử lý
   - Alert `ad_disapproved` → nút **Edit ad** → `/meta/ads-ops?mode=edit&...`
8. **Export CSV** — chọn scope (filtered / all clients) → tải file.

#### Badges cần hiểu

| Badge | Ý nghĩa | Hành động |
|-------|---------|-----------|
| Unmapped | Spend chưa map hub | Map campaign / suggest |
| Token error | Token hết hạn/revoked | Refresh OAuth / vault |
| Tenant locked | Client offboard | Không mutate |
| Over target | CPL > target × threshold | Review creative/targeting |
| CAPI thiếu pixel | Pixel chưa config | Agency client → meta JSON |

---

### 7.2. Meta Ads Ops — `/meta/ads-ops` (B15)

**Mục đích:** Launch campaign/ad mới và edit creative/copy có governance — **không** thay Ads Manager đầy đủ.

**Điều kiện hiển thị:** `NEXT_PUBLIC_PTT_META_ADS_OPS_ENABLED=1` + cap view/submit.

#### Tab Launch — wizard 5 bước

| Bước | Nội dung | Ghi chú |
|------|----------|---------|
| 1. Client & account | UUID client + `act_*` | Block nếu offboard / không trong pilot |
| 2. Objective & budget | Template RE Lead / Traffic, budget VND, tên campaign/adset/ad | Template mặc định: `re_lead_default` |
| 3. Creative | Chọn creative **approved** từ CRM | Chỉ status `approved` |
| 4. Tracking | Preflight checklist (pixel, CAPI, map) | Link Launch QA board |
| 5. Review & submit | Tóm tắt + submit for approval | → `/crm/campaign-writes` |

**Sau submit:** Request `change_type=create_campaign` vào queue → approver approve → Temporal execute Graph.

**Deep link:** Nút **Mở Ads Manager ↗** — audience/catalog phức tạp làm trên Meta native.

#### Tab Edit — wizard 4 bước

| Bước | Nội dung | Ghi chú |
|------|----------|---------|
| 1. Chọn ad | Client UUID + `external_ad_id` | Snapshot Graph (cached) |
| 2. Creative / copy | Swap creative HOẶC sửa headline/primary text | Action: `update_ad_creative` / `update_ad_copy` |
| 3. Diff review | So sánh old vs new | Audit bắt buộc |
| 4. Submit | Submit edit for approval | DISAPPROVED → tick ack |

**Entry points:**

- Hub tab Alerts → **Edit ad** (từ alert disapproved)
- CRM creatives → registry link → **Edit ad**
- URL trực tiếp: `/meta/ads-ops?mode=edit&client_id=...&ad_id=...&ack=1`

#### Preflight (chặn submit nếu fail)

| Check | Nguồn |
|-------|--------|
| Pixel + page | `client_channel_accounts.meta` |
| CAPI test OK | Tracking health |
| Hub map / UTM | `hub_campaign_map` |
| Creative approved | `crm_creatives` |
| Client not locked | Offboard B7 |
| Pilot allowlist | `PTT_META_ADS_OPS_PILOT_CLIENTS` |

---

### 7.3. Meta Tracking — `/meta/tracking` (B9)

**Mục đích:** Giám sát CAPI, conversion rules, pixel test, launch preflight.

**Điều kiện:** `NEXT_PUBLIC_PTT_META_TRACKING_ENABLED=1` + cap view/configure.

#### Các khối UI

1. **Chọn client** — filter `?client_id=` hoặc dropdown.
2. **KPI grid 7 ngày** — sent / failed / skipped / latency CAPI.
3. **Preflight checklist** — pixel, CAPI recent, map (đồng bộ Launch QA).
4. **Account/pixel table** — per channel account; nút **Test pixel** (Graph probe).
5. **CAPI events table** — log `capi_event_log`; retry failed.
6. **Conversion rules CRUD** — map `lead_status` → Meta event (admin/tracking cap).

#### Quy trình CAPI pilot

1. Bật `PTT_CAPI_ENABLED=1` + pilot client UUID.
2. Config pixel + `capi_enabled` trên channel account.
3. Gửi test lead qua Meta webhook → kiểm tra event **Lead** trong Events Manager <5 phút.
4. Chuyển lead CRM qualified → rule fire `CompleteRegistration` (nếu config).
5. Theo dõi fail rate alert (<10% khuyến nghị).

---

### 7.4. Meta Intelligence — `/meta/intelligence` (B10–B11)

**Mục đích:** ROAS, anomaly, budget recommend, forecast — **read-only**, không auto-mutate.

#### Các panel

| Panel | Wave | Mô tả |
|-------|------|--------|
| ROAS KPI + chart | B10 | `conversion_value / spend` |
| Anomalies (median) | B10 | Spike spend/CPL |
| Stat anomalies (z-score) | B11 | 14d z-score |
| Budget recommendations | B10 | Read-only; link → campaign-writes |
| Forecast | B11 | CPL slope 7 ngày |
| Adset insights table | B10 | Khi `PTT_META_INSIGHTS_LEVEL=adset` |
| Multi-pixel table | B11 | Primary pixel routing |

**CTA mutate:** Intelligence chỉ **gợi ý** — Media Buyer tạo write request thủ công tại `/crm/campaign-writes` hoặc hub.

---

### 7.5. Campaign Writes — `/crm/campaign-writes`

**Mục đích:** Hàng đợi governance cho mọi thay đổi Graph.

| change_type | Nguồn | Mô tả |
|-------------|-------|--------|
| `daily_budget`, `status`, `name` | Hub / CRM | B6 mutate |
| `create_campaign` | Ads Ops Launch | B15 |
| `update_ad_creative`, `update_ad_copy` | Ads Ops Edit | B15 |

**Approver flow:**

1. Mở request pending → xem old/new value JSON.
2. **Approve** → Temporal workflow → Graph API.
3. **Reject** → ghi note; không execute.
4. Theo dõi status: `executed` / `execution_failed`.

---

### 7.6. Launch QA — `/crm/launch-qa`

**Mục đích:** Gate trước khi client `launch_ready` và trước Ads Ops create.

Checklist Meta (B9):

- Pixel configured
- CAPI test event OK
- Hub map coverage ≥80% spend (khuyến nghị)
- CAPI sent trong 48h (strict mode nếu `PTT_LAUNCH_QA_META_STRICT=1`)

Link từ Ads Ops bước 4 Tracking → **Launch QA board**.

---

### 7.7. CRM Creatives + Registry — `/crm/creatives` (B12)

1. Creative submit → review → **approved**.
2. Mở creative row → **Meta ad link** → gắn `external_ad_id`.
3. Link active hiển thị → **Edit ad** → Ads Ops Edit tab.

Registry bridge B12 ↔ B15 upload creative lên Graph khi launch/edit.

---

### 7.8. Portal — `/meta` (client)

- KPI cards: spend, leads, CPL, delta vs target.
- Bảng performance campaign (read-only).
- Export CSV (tenant-isolated JWT).
- ROAS hiển thị khi B10 bật và không stub.

---

## 8. Luồng nghiệp vụ end-to-end

### 8.1. Onboard client Meta mới

```
AM tạo client
  → Configure channel account (act_*, pixel, page, token)
  → POST sync/insights (backfill 35d)
  → Map campaigns (manual + suggest)
  → Launch QA checklist pass
  → Thêm vào pilot allowlists (CAPI, ads-ops nếu cần)
  → Client portal /meta live
```

### 8.2. Ngày vận hành hàng ngày (Media Buyer)

```
08:00 — Insights T-1 sync xong (timer)
  → Mở /meta/facebook-ads — review CPL Δ, alerts
  → Ack alerts đã xử lý
  → Campaign chưa map → Map suggest
  → CPL cao → /meta/intelligence xem anomaly
  → Cần pause/budget → submit campaign-write (B6)
  → Cần launch mới → /meta/ads-ops Launch
  → Ad disapproved → Alerts → Edit ad → submit edit
```

### 8.3. Launch campaign mới (B15)

```
Creative approved (/crm/creatives)
  → /meta/ads-ops Launch wizard 5 bước
  → Preflight pass (hoặc ack nếu policy cho phép)
  → Submit for approval
  → GDKD approve (/crm/campaign-writes)
  → Temporal MetaCampaignCreateWorkflow
  → Verify campaign trên Ads Manager / hub sync ngày sau
```

### 8.4. Edit ad disapproved (B13 + B15)

```
Webhook ad_disapproved → meta_alerts
  → Hub Alerts tab → Edit ad
  → Edit wizard: swap creative approved HOẶC sửa copy
  → Tick ack DISAPPROVED
  → Diff review → Submit
  → Approve → Graph execute
  → Verify status PENDING_REVIEW/ACTIVE
```

### 8.5. Offboard client (B7)

```
POST /clients/:id/offboard
  → Revoke token vault
  → tenant_locked = true
  → Cancel pending jobs/workflows
  → Block sync, CAPI, ads-ops submit
```

---

## 9. KPI, attribution & báo cáo

### 9.1. KPI chính

| KPI | Công thức | Nguồn |
|-----|-----------|--------|
| Spend | SUM(spend) | `daily_performance` |
| Leads CRM | SUM(leads_crm) | PG leads attributed |
| CPL CRM | spend / leads_crm | Derived |
| ROAS | conversion_value / spend | B10 CRM deals |
| Unmapped % | unmapped spend / total | B8 hub map |

### 9.2. Thứ tự attribution lead

1. `hub_campaign_map.utm_campaign` = lead `utm_campaign`
2. Lead `meta_json.campaign_id`
3. Fallback client-level — flag **Unmapped**

### 9.3. Export

| Nguồn | Format | Audience |
|-------|--------|----------|
| Hub Export CSV | CSV | Staff |
| Portal export | CSV | Client |
| B11 snapshot | gzip artifact | Data/BI |
| B14 warehouse | ClickHouse + Grafana | Executive BI |
| B14 compliance | JSON API | Compliance review |

---

## 10. Jobs, alerts & observability

### 10.1. Job types Meta

| job_type | Trigger |
|----------|---------|
| `meta_insights_sync` | Daily cron, manual |
| `meta_token_refresh` | Timer |
| `capi_dispatch` | Lead created, cron 5m |
| `meta_alerts_eval` | Post sync |
| `meta_ops_webhook` | B13 webhook |
| `meta_clickhouse_export` | B14 daily |

### 10.2. Alert catalog (chọn lọc)

| alert_type | Ý nghĩa |
|------------|---------|
| `cpl_high` | CPL vượt target |
| `unmapped_spend_high` | >15% spend chưa map |
| `sync_failed` | Token lỗi >24h |
| `capi_fail_rate` | CAPI fail >10% |
| `meta_account_disabled` | Account bị vô hiệu (B13) |
| `ad_disapproved` | Ad bị từ chối (B13) |

Dedupe key: `{alert_type}:{client_id}:{campaign_id}:{date}`

### 10.3. Observability

- Gate reports: `.local-dev/wave_b*_gate_report.json`
- Soak evidence: `.local-dev/horizon1-meta-ads-soak-evidence.jsonl`
- Runbooks: [`meta-insights-replay.md`](runbooks/meta-insights-replay.md), [`meta-token-refresh.md`](runbooks/meta-token-refresh.md)

---

## 11. Gates, nghiệm thu & rollback

### 11.1. Gate scripts

| Wave | Command |
|------|---------|
| H1 | `./scripts/horizon1_meta_ads_pack.sh` |
| B8 | `./scripts/wave_b8_gate.sh` |
| B9 | `./scripts/wave_b9_gate.sh` |
| B10 | `./scripts/wave_b10_gate.sh` |
| B11 | `./scripts/wave_b11_gate.sh` |
| B8.1 | `./scripts/wave_b8_1_gate.sh` |
| B12 | `./scripts/wave_b12_gate.sh` |
| B13 | `./scripts/wave_b13_gate.sh` |
| B14 | `./scripts/wave_b14_gate.sh` |
| B15 | `./scripts/wave_b15_gate.sh` |

Regression: mỗi gate wave N thường skip hoặc chạy gate wave N-1 (`WAVE_B15_SKIP_B14=1` mặc định).

### 11.2. Rollback nhanh (feature flags)

| Tắt | Hiệu ứng |
|-----|----------|
| `PTT_META_ALERTS_ENABLED=0` | Ngừng alert mới |
| `PTT_CAPI_ENABLED=0` | Ngừng enqueue CAPI |
| `PTT_META_ADS_OPS_ENABLED=0` | Ẩn wizard, block API create/edit |
| `NEXT_PUBLIC_PTT_META_*_ENABLED=0` | Ẩn nav/UI tương ứng |

**Không** rollback DDL — dùng flags.

---

## 12. Troubleshooting thường gặp

### Hub không có data / spend = 0

1. Kiểm tra `client_channel_accounts.token_status=active`.
2. Chạy manual sync: `POST /clients/:id/sync/insights`.
3. Xem sync status chip trên hub.
4. Staging: đảm bảo `PTT_META_INSIGHTS_STUB=0`.

### CPL / leads CRM = 0 nhưng Meta có lead

1. Hub map chưa có — campaign unmapped.
2. Lead thiếu UTM / `meta_json.campaign_id`.
3. Chạy map suggest; kiểm tra webhook lead ingest.

### Menu Meta Ads Ops / Tracking không hiện

1. Backend flag = 1?
2. `NEXT_PUBLIC_*` khớp + rebuild ops-web?
3. Staff caps đủ? (`crm_facebook_ads` view, `meta_ads_ops` submit)

### Launch wizard preflight fail

1. Pixel/page trên channel account.
2. CAPI test trên `/meta/tracking`.
3. Creative chưa approved.
4. Client `tenant_locked` (offboard).
5. Client không trong `PTT_META_ADS_OPS_PILOT_CLIENTS`.

### Campaign write execution_failed

1. Token thiếu scope `ads_management`.
2. Graph rate limit — retry sau.
3. Xem Temporal workflow logs + request `new_value` JSON.

### Alert ad_disapproved không có nút Edit ad

1. `NEXT_PUBLIC_PTT_META_ADS_OPS_ENABLED=1`.
2. Parse ad_id từ message alert — format `Meta ad {id} disapproved`.

---

## 13. Phụ lục — env flags & API

### 13.1. Master feature flags (default prod-safe)

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

### 13.2. API staff chính (prefix `/api/v1/`)

| Method | Path | Màn hình |
|--------|------|----------|
| GET | `/facebook-ads/hub` | Meta Ads Hub |
| GET | `/facebook-ads/hub/export` | Export CSV |
| GET | `/meta/alerts` | Tab Alerts |
| PATCH | `/meta/alerts/:id/ack` | Ack alert |
| GET | `/meta/tracking/health` | Tracking |
| GET/POST | `/meta/conversion-rules` | Rules CRUD |
| GET | `/meta/anomalies`, `/meta/roas` | Intelligence |
| GET | `/meta/ads-ops/templates` | Ads Ops |
| POST | `/meta/ads-ops/launch` | Launch submit |
| POST | `/meta/ads-ops/edit/submit` | Edit submit |
| GET/POST | `/crm/campaign-writes/*` | Approve queue |

### 13.3. Tài liệu liên quan

| Tài liệu | Nội dung |
|----------|----------|
| [`SPEC_META_ENTERPRISE_PTTADS.md`](SPEC_META_ENTERPRISE_PTTADS.md) | Master spec kỹ thuật |
| [`runbooks/horizon1-meta-ads-migration-checklist.md`](runbooks/horizon1-meta-ads-migration-checklist.md) | Migration Flask → ops-web |
| [`docs/pr/merge-meta-b15-ads-ops-into-main.md`](pr/merge-meta-b15-ads-ops-into-main.md) | B15 test plan |
| `deploy/env.meta-enterprise-b*.example` | Env template từng wave |

---

*Tài liệu này phản ánh trạng thái codebase sau wave B15 (2026-07-25). Khi spec cập nhật, đối chiếu lại §14–§18 trong SPEC_META_ENTERPRISE_PTTADS.md.*
