# Hướng dẫn sử dụng & triển khai phân hệ SEO/AEO Ops

> **Phiên bản:** 2.0 · **Ngày:** 2026-07-25  
> **Đối tượng:** Admin VPS, Head SEO/AEO, Strategist, Writer, Tech SEO, AM, vận hành agency  
> **Phạm vi:** Setup đầy đủ trên **VPS/staging/local** + hướng dẫn sử dụng từng màn hình ops-web & portal  
> **URL staff:** `https://ops.pttads.vn/seo/*` · `https://rs.pttads.vn/seo/*` (redirect)  
> **URL client:** `https://portal.pttads.vn/seo`  
> **Spec tham chiếu:**  
> - [`SPEC_SEO_AEO_OPERATING_SYSTEM.md`](SPEC_SEO_AEO_OPERATING_SYSTEM.md) — master spec kỹ thuật & nghiệp vụ  
> - [`SPEC_UI_UX_SEO_AEO.md`](SPEC_UI_UX_SEO_AEO.md) — UI/UX screens S-01…S-17  
> - [`SEO_AEO_COMPLETION_ROADMAP.md`](SEO_AEO_COMPLETION_ROADMAP.md) — lộ trình & trạng thái migration  
> - [`specs/2026-07-19-seo-aeo-architecture.md`](specs/2026-07-19-seo-aeo-architecture.md) — kiến trúc C4 & API

---

## Mục lục

1. [Tổng quan phân hệ](#1-tổng-quan-phân-hệ)
2. [Kiến trúc trên VPS](#2-kiến-trúc-trên-vps)
3. [Triển khai & setup đầy đủ](#3-triển-khai--setup-đầy-đủ)
4. [Bật tính năng theo phase & flag](#4-bật-tính-năng-theo-phase--flag)
5. [Truy cập & phân quyền](#5-truy-cập--phân-quyền)
6. [Hướng dẫn từng màn hình (UI/UX)](#6-hướng-dẫn-từng-màn-hình-uiux)
7. [Luồng nghiệp vụ end-to-end](#7-luồng-nghiệp-vụ-end-to-end)
8. [Cron, jobs & tự động hóa](#8-cron-jobs--tự-động-hóa)
9. [Client Portal SEO](#9-client-portal-seo)
10. [Gates, QA & nghiệm thu](#10-gates-qa--nghiệm-thu)
11. [Xử lý sự cố thường gặp](#11-xử-lý-sự-cố-thường-gặp)
12. [Checklist go-live](#12-checklist-go-live)
13. [Phụ lục — env, API, runbook](#13-phụ-lục--env-api-runbook)

---

## 1. Tổng quan phân hệ

**SEO/AEO Enterprise Operating System** là phân hệ vận hành vòng đời SEO + Answer Engine Optimization trên PTTADS:

```
Chiến lược → Nghiên cứu → Sản xuất nội dung → QA kỹ thuật
         → Tối ưu AEO → Publish → Giám sát → Refresh → Báo cáo
```

### 1.1. Stack canonical (2026-07-25)

| Lớp | Thành phần | Ghi chú |
|-----|------------|---------|
| **Staff UI** | ops-web `/seo/*` | ~19 routes — canonical |
| **Staff API** | Nest `ptt-crm-api` `/api/v1/seo/*` | Không proxy Flask |
| **Domain/workers** | Python `ptt_seo/` + `ptt_jobs` | GSC/GA4 sync, freshness, CMS publish |
| **Data** | PostgreSQL `seo_aeo.*` | **PostgreSQL-only** — không build mới trên SQLite SEO |
| **CRM master** | SQLite `crm_customers` | Liên kết `customer_id` |
| **Flask `/crm/seo/*`** | Retired | nginx redirect → `/seo/*` |

### 1.2. Module & route ops-web

| Screen ID | Module | Route | Phase |
|-----------|--------|-------|-------|
| S-01 | Executive Hub | `/seo/hub` | 1+ |
| S-02 | Danh sách client SEO | `/seo/clients` | 1 |
| S-03/04 | Client workspace + settings | `/seo/clients/:id` | 1 |
| S-05 | Chiến lược & OKR/KPI | `/seo/strategy` | Gate E |
| S-06 | Research Console | `/seo/research` | 2 |
| S-07/08 | Content pipeline + detail | `/seo/content` · `/seo/content/:id` | 2 |
| S-09 | Technical Console | `/seo/technical` | 3 |
| S-10 | AEO Console | `/seo/aeo` | 4 |
| S-11 | Authority Console | `/seo/authority` | 4 |
| S-12 | Reporting Center | `/seo/reports` | 3 |
| S-13 | Automations & Alerts | `/seo/automations` | 3 |
| S-14 | Governance Hub | `/seo/governance` | 5A |
| S-16 | Experiments | `/seo/experiments` | 5B |
| S-17 | Rank tracker & SOV | `/seo/ranks` | Gate E |
| — | Freshness queue | `/seo/freshness` | 4 |
| — | BI / Grafana | `/seo/bi` | Gate D |
| — | CMS publish pilot | `/seo/cms` | Gate E |
| — | Gate A go-live | `/seo/gate-a` | Phase 7 |

### 1.3. Luồng dữ liệu chính

- **CRM master:** khách hàng, lifecycle, tasks — SQLite
- **SEO/AEO domain:** content, GSC, GA4, issues, AEO… — PostgreSQL `seo_aeo.*`
- **Tích hợp:** Google OAuth (GSC/GA4), CMS webhook, SerpAPI/DataForSEO, ClickHouse BI, Slack/Teams alerts

### 1.4. Nguyên tắc vận hành

1. **Staff 100% ops-web** — không dùng Flask SEO admin.
2. **`customer_id` / `client_id`** — filter mọi màn hình theo client.
3. **Workflow-driven** — content qua 13 stage rõ ràng.
4. **Governance-heavy** — publish bị chặn nếu thiếu metadata (khi bật).
5. **Pilot → soak → prod** — bật Portal/Experiments sau Gate A.

---

## 2. Kiến trúc trên VPS

```
┌─────────────────────────────────────────────────────────────────────┐
│  VPS (vd. /var/www/ptt)                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐  │
│  │ ops-web :3200│  │ portal-web   │  │ nginx                    │  │
│  │ staff /seo/* │  │ :3001 /seo   │  │ /crm/seo → /seo redirect │  │
│  └──────┬───────┘  └──────┬───────┘  └──────────────────────────┘  │
│         │                 │                                         │
│  ┌──────┴─────────────────┴───────┐                                │
│  │ ptt-crm-api (Nest) :3000       │  ← OAuth callback, cron API    │
│  └──────┬─────────────────────────┘                                │
│         │                                                           │
│  ┌──────┴───────┐  ┌────────────────┐                              │
│  │ ptt_worker   │  │ ptt (Flask CRM)│  ← CRM only, không SEO staff │
│  │ job_queue    │  │ SQLite + jobs  │                              │
│  └──────┬───────┘  └────────────────┘                              │
│         ▼                                                           │
│  PostgreSQL (seo_aeo.*)                                             │
│         │                                                           │
│  systemd timers: GSC · GA4 · Gate D · ClickHouse export             │
└─────────────────────────────────────────────────────────────────────┘
```

| Thành phần | Path / URL |
|------------|------------|
| Repo | `/var/www/ptt` |
| Env | `/var/www/ptt/.env` |
| Staff console | `rs.pttads.vn` hoặc `ops.pttads.vn` |
| PG schema | `deploy/sql/seo_aeo_pg_schema.sql` + migrations |
| Log cron | `/var/log/seo_aeo_cron_*.log` |

---

## 3. Triển khai & setup đầy đủ

> Staging trước → soak ≥7 ngày → production.  
> Runbook PG/OAuth: [`runbooks/seo-aeo-pg-oauth-uat-cutover.md`](runbooks/seo-aeo-pg-oauth-uat-cutover.md)

### 3.1. Điều kiện tiên quyết

- [ ] PostgreSQL production (`DATABASE_URL`)
- [ ] Google Cloud OAuth client:
  - Redirect GSC: `https://<api-domain>/api/v1/seo/gsc/oauth/callback`
  - Redirect GA4: `https://<api-domain>/api/v1/seo/ga4/oauth/callback`
- [ ] APIs bật: Search Console, Analytics Data, Analytics Admin
- [ ] `PTT_TOKEN_VAULT_KEY` — mã hóa refresh token OAuth
- [ ] `ptt-crm-api`, ops-web, `ptt_worker` deploy healthy
- [ ] Backup: `pg_dump seo_aeo` + copy `ptt.db`

### 3.2. Bước 1 — Apply schema PostgreSQL

```bash
cd /var/www/ptt
export DATABASE_URL=postgresql://...

# Schema base + research P2
psql "$DATABASE_URL" -f deploy/sql/seo_aeo_pg_schema.sql
psql "$DATABASE_URL" -f deploy/sql/seo_aeo_research_p2.sql   # nếu có

# Gate D / Gate E (khi cần CWV, OKR, rank, crawl)
./scripts/apply_seo_gate_d_schema.sh
./scripts/apply_seo_gate_e_schema.sh
```

**Verify:**

```bash
psql "$DATABASE_URL" -c "\dt seo_aeo.*"
```

### 3.3. Bước 2 — PostgreSQL cutover & env cốt lõi

```bash
export PILOT_CUSTOMER_ID=<CRM_CUSTOMER_ID>

# Dry-run
APPLY=0 ./scripts/seo_aeo_prod_cutover.sh

# Thực thi
sudo -E APPLY=1 ./scripts/seo_aeo_prod_cutover.sh
sudo systemctl restart ptt-crm-api ptt-worker
```

**Biến môi trường cốt lõi** (`/var/www/ptt/.env`):

```bash
SEO_AEO_DB=pg
DATABASE_URL=postgresql://...

# GSC OAuth
PTT_GSC_OAUTH_CLIENT_ID=...
PTT_GSC_OAUTH_CLIENT_SECRET=...
PTT_GSC_OAUTH_REDIRECT_URI=https://<domain>/api/v1/seo/gsc/oauth/callback
PTT_GSC_SYNC_ENABLED=1

# GA4 OAuth
PTT_GA4_OAUTH_CLIENT_ID=...
PTT_GA4_OAUTH_CLIENT_SECRET=...
PTT_GA4_OAUTH_REDIRECT_URI=https://<domain>/api/v1/seo/ga4/oauth/callback
PTT_GA4_SYNC_ENABLED=1

PTT_TOKEN_VAULT_KEY=...
PTT_JOBS_ENABLED=1
PTT_JOBS_SYNC_FALLBACK=1
PTT_SEO_CRON_SECRET=<secret-mạnh>
PTT_OPS_WEB_URL=https://rs.pttads.vn
```

Template pilot đầy đủ: `deploy/env.seo-aeo-pilot.example`

**Seed pilot client:**

```bash
python3 scripts/seed_seo_pilot_client_settings.py --apply
python3 scripts/seed_portal_seo_pilot_map.py --apply --client-id <UUID> --customer-id <CRM_ID>
```

**Bật timer sync:**

```bash
sudo systemctl enable --now ptt-seo-gsc-sync.timer ptt-seo-ga4-sync.timer
sudo systemctl restart ptt-crm-api ptt-worker
```

**Verify OAuth:**

```bash
python3 scripts/verify_seo_aeo_oauth_uat.py --customer-id <PILOT_ID>
```

### 3.4. Bước 3 — Build & deploy ops-web

```bash
cd services/ops-web
cp .env.example .env.local   # local dev
# Production: set NEXT_PUBLIC_* trong env deploy

npm run build
sudo systemctl restart ops-web   # hoặc pm2/systemd unit tương ứng
```

**CORS Nest** (nếu ops-web domain khác API):

```bash
PTT_OPS_CORS_ORIGINS=https://rs.pttads.vn,https://ops.pttads.vn
```

### 3.5. Bước 4 — Gate D (BI, CWV, Teams, AEO schedule)

```bash
# Remote deploy
PTT_VPS_HOST=<IP> APPLY=1 ./scripts/staging_seo_gate_d_deploy.sh

# Hoặc trên VPS
./scripts/apply_seo_gate_d_schema.sh
sudo ./scripts/install_seo_gate_d_systemd.sh
sudo systemctl enable --now ptt-seo-gate-d.timer
```

**Env** (`deploy/env.staging-seo-gate-d.example`):

```bash
PTT_CWV_ENABLED=1
PAGESPEED_API_KEY=...          # staging: PTT_CWV_STUB=1
PTT_CRAWL_REMINDER_ENABLED=1
PTT_SEO_TEAMS_WEBHOOK=https://outlook.office.com/webhook/...
PTT_AEO_SCHEDULE_ENABLED=1
PTT_AEO_AUTO_DRAFT_ENABLED=1
```

ClickHouse + Grafana: [`runbooks/seo-aeo-clickhouse-bi.md`](runbooks/seo-aeo-clickhouse-bi.md)

### 3.6. Bước 5 — Gate E (OKR, crawl connector, rank, CMS)

```bash
PTT_VPS_HOST=<IP> APPLY=1 PILOT_CUSTOMER_ID=<CRM_ID> ./scripts/staging_seo_gate_e_deploy.sh
```

**Env** (`deploy/env.staging-seo-gate-e.example`):

```bash
PTT_SEO_ENTERPRISE_ENABLED=1
PTT_CRAWL_CONNECTOR_ENABLED=1
PTT_RANK_LIVE_ENABLED=1
PTT_SERP_PROVIDER=stub           # prod live: serpapi | dataforseo
PTT_SEO_CMS_AUTO_PUBLISH=0       # bật sau pilot CMS
PTT_SEO_CMS_WEBHOOK_SECRET=...
```

```bash
python3 scripts/seed_cms_webhook_pilot.py --customer-id <CRM_ID>
```

### 3.7. Bước 6 — Nginx redirect Flask → ops-web (Gate A)

```bash
# include deploy/nginx-seo-gate-a-redirect.conf
sudo nginx -t && sudo systemctl reload nginx
```

Flask `/crm/seo/*`, `/crm/aeo` → `/seo/*`

### 3.8. Setup local dev (developer)

```bash
cd PTTADS
export DATABASE_URL=postgresql://localhost/ptt_crm
export SEO_AEO_DB=pg
export PTT_CRM_API_AUTH_DISABLED=1
export PTT_OPS_WEB_URL=http://127.0.0.1:3200

# Terminal 1 — Nest API
cd services/ptt-crm-api && npm run start:dev

# Terminal 2 — ops-web
cd services/ops-web && npm run dev

# Terminal 3 — worker
export PTT_JOBS_ENABLED=1
python3 -m ptt_worker
```

Hub local: `http://localhost:3200/seo/hub`

QA gates:

```bash
python3 -m pytest tests/test_seo_p1_qa.py tests/test_seo_p2_qa.py tests/test_seo_handoff_qa.py -q
./scripts/seo_handoff_gate.sh
SEO_HANDOFF_SKIP_E2E=0 ./scripts/playwright_ops_seo_handoff_e2e.sh   # cần Nest + ops-web up
```

### 3.9. Rollback nhanh

| Tình huống | Hành động |
|------------|-----------|
| Lỗi PG cutover | `SEO_AEO_DB=sqlite` (legacy) → restart Flask — **chỉ emergency** |
| Portal lỗi | `PTT_PORTAL_SEO_ENABLED=0` |
| CMS auto-publish lỗi | `PTT_SEO_CMS_AUTO_PUBLISH=0` |
| Module UI lỗi | Tắt `NEXT_PUBLIC_PTT_SEO_*` → rebuild ops-web |

---

## 4. Bật tính năng theo phase & flag

### 4.1. Backend flags (prod-safe defaults)

| Biến | Default prod | Ý nghĩa |
|------|--------------|---------|
| `PTT_SEO_GOVERNANCE_ENABLED` | `1` | Policy engine publish |
| `PTT_PORTAL_SEO_ENABLED` | `0` | Portal client SEO |
| `PTT_SEO_EXPERIMENTS_ENABLED` | `0` | A/B test UI |
| `PTT_SEO_ENTERPRISE_ENABLED` | `0→1` | Gate E depth |
| `PTT_CWV_STUB` | `1` staging | CWV stub vs PageSpeed live |
| `PTT_SERP_PROVIDER` | `stub` | SERP capture live |
| `PTT_SEO_CMS_AUTO_PUBLISH` | `0` | Auto webhook khi Published |

### 4.2. ops-web flags (`NEXT_PUBLIC_PTT_SEO_*`)

Mặc định hầu hết = `1`; rebuild sau khi đổi. File: `services/ops-web/src/lib/seo/flags.ts`

| Flag | Route ẩn nếu `0` |
|------|------------------|
| `NEXT_PUBLIC_PTT_SEO_HUB_ENABLED` | `/seo/hub` |
| `NEXT_PUBLIC_PTT_SEO_CLIENT_WORKSPACE_ENABLED` | `/seo/clients/*` |
| `NEXT_PUBLIC_PTT_SEO_RESEARCH_ENABLED` | `/seo/research` |
| `NEXT_PUBLIC_PTT_SEO_CONTENT_ENABLED` | `/seo/content` |
| `NEXT_PUBLIC_PTT_SEO_TECHNICAL_ENABLED` | `/seo/technical` |
| `NEXT_PUBLIC_PTT_SEO_REPORTS_ENABLED` | `/seo/reports` |
| `NEXT_PUBLIC_PTT_SEO_STRATEGY_ENABLED` | `/seo/strategy` |
| `NEXT_PUBLIC_PTT_SEO_AEO_ENABLED` | `/seo/aeo` |
| `NEXT_PUBLIC_PTT_SEO_AUTHORITY_ENABLED` | `/seo/authority` |
| `NEXT_PUBLIC_PTT_SEO_RANKS_ENABLED` | `/seo/ranks` |
| `NEXT_PUBLIC_PTT_SEO_AUTOMATIONS_ENABLED` | `/seo/automations` |
| `NEXT_PUBLIC_PTT_SEO_FRESHNESS_ENABLED` | `/seo/freshness` |
| `NEXT_PUBLIC_PTT_SEO_GOVERNANCE_ENABLED` | `/seo/governance` |
| `NEXT_PUBLIC_PTT_SEO_EXPERIMENTS_ENABLED` | `/seo/experiments` |
| `NEXT_PUBLIC_PTT_SEO_BI_ENABLED` | `/seo/bi` |
| `NEXT_PUBLIC_PTT_SEO_CMS_ENABLED` | `/seo/cms` |
| `NEXT_PUBLIC_PTT_SEO_GATE_A_ENABLED` | `/seo/gate-a` |

Template Gate A prod: `deploy/env.seo-gate-a-prod.example`

### 4.3. Staged prod cutover (Phase 5)

```bash
chmod +x scripts/close_phase5_prod_cutover.sh

# Bước 1 — Governance
APPLY=1 PHASE5_ENABLE_GOVERNANCE=1 sudo -E ./scripts/close_phase5_prod_cutover.sh

# Bước 2 — Portal (sau seed map)
APPLY=1 PHASE5_ENABLE_PORTAL=1 PTT_PORTAL_SEO_SERVICE_TOKEN=<secret> \
  sudo -E ./scripts/close_phase5_prod_cutover.sh

# Bước 3 — Experiments
APPLY=1 PHASE5_ENABLE_EXPERIMENTS=1 sudo -E ./scripts/close_phase5_prod_cutover.sh
```

Soak hàng ngày: `./scripts/phase5_soak_record.sh`

---

## 5. Truy cập & phân quyền

### 5.1. Đăng nhập staff

1. `https://rs.pttads.vn/login` hoặc `ops.pttads.vn/login`
2. Sidebar → **Agency & Hub** → **SEO/AEO Hub**
3. Legacy Flask `/crm/seo` redirect tự động → `/seo/hub`

### 5.2. Section keys (Admin → Phân quyền trang)

| Key | Quyền |
|-----|-------|
| `crm_seo_aeo` | Xem toàn phân hệ |
| `crm_seo_aeo_write` | Tạo/sửa research, content |
| `crm_seo_aeo_approve` | Duyệt workflow content |
| `crm_seo_aeo_technical` | Import crawl, sửa issue |
| `crm_seo_aeo_settings` | OAuth, CMS, lịch báo cáo |
| `crm_seo_aeo_reports` | Export PDF, ClickHouse |

**Gợi ý theo vai trò** (spec §4):

| Vai trò | Keys |
|---------|------|
| Head SEO / MKT-01 | Cả 6 keys |
| Strategist | view + write + reports |
| Writer | view + write (không approve) |
| Tech SEO | view + technical |
| AM / KD-01 | view + settings + reports |

Helpers: `ptt_seo/rbac.py` · Nest guards `StaffSeo*Guard`

### 5.3. Nút UI theo quyền

ops-web ẩn action nếu thiếu cap (không chỉ dựa API 403):

- `can_seo_write` — tạo/sửa research, content
- `can_seo_approve` — approve workflow
- `can_seo_configure` — settings, OAuth
- `can_seo_export` — PDF, BI export
- `can_seo_technical` — crawl import, issue edit

### 5.4. Navigation rules (UI/UX spec §3.4)

| Điều kiện | UI |
|-----------|-----|
| Client chưa config domain | Banner vàng trên workspace |
| Critical issues > 0 | Badge đỏ tab Kỹ thuật + sidebar |
| Content overdue | Badge cam tab Nội dung |
| AEO coverage < 50% | Badge vàng tab AEO |
| Sync job failed | Banner Hub + Automations |

---

## 6. Hướng dẫn từng màn hình (UI/UX)

> Screen ID theo [`SPEC_UI_UX_SEO_AEO.md`](SPEC_UI_UX_SEO_AEO.md) §5.  
> Layout: card pattern, `--primary` green, dense tables, tiếng Việt.

### 6.1. S-01 — Executive Hub (`/seo/hub`)

**Mục đích:** Dashboard lãnh đạo — KPI tổng, client health, critical issues, content delivery.

**Layout:**

```
┌─────────────────────────────────────────────────────────────┐
│ SEO/AEO Hub                          [Sync banner nếu lỗi]  │
├──────────┬──────────┬──────────┬──────────┬─────────────────┤
│ Clients  │ GSC clk  │ Content  │ Critical │ AEO coverage    │
├──────────┴──────────┴──────────┴──────────┴─────────────────┤
│ Client health table → drill-down /seo/clients/:id           │
│ Content delivery · Technical summary · SeoScoreMeter (P2)   │
└─────────────────────────────────────────────────────────────┘
```

**Thao tác:**

1. Mở **SEO/AEO Hub**
2. Lọc client / thời gian
3. Click hàng client health → workspace (≤3 click)
4. Link drill-down P2: content delivery → `/seo/content`; critical → `/seo/technical`; AEO → `/seo/aeo`
5. Badge nav: critical issues, overdue content (API nav-badges)

**Dữ liệu cần:** GSC sync, pipeline content, technical issues.

---

### 6.2. S-02 / S-03 / S-04 — Clients & Workspace (`/seo/clients`, `/seo/clients/:id`)

**Client workspace nav (P1):** component `SeoClientWorkspaceNav` — 3 tab nội bộ + 7 link module với `?customer_id=X`.

| Tab / link | Route |
|------------|-------|
| Tổng quan | tab trong workspace |
| Roadmap | tab |
| Tasks | tab |
| Nghiên cứu | `/seo/research?customer_id=` |
| Nội dung | `/seo/content?customer_id=` |
| Kỹ thuật | `/seo/technical?customer_id=` |
| AEO | `/seo/aeo?customer_id=` |
| Authority | `/seo/authority?customer_id=` |
| Báo cáo | `/seo/reports?customer_id=` |
| Cài đặt | tab Settings |

**Context bar:** Client name · Domain · Market · Owner · Contract tier

**Cài đặt client (S-04)** — cap `crm_seo_aeo_settings`:

1. Domains / markets / languages
2. Brand & SEO guidelines (JSON)
3. Integrations — GSC site, GA4 property (OAuth)
4. CMS Publish — webhook URL, secret, test
5. Approvers — chuỗi client_review

**Onboard client mới:**

1. Tạo customer CRM
2. `/seo/clients/:id` → Settings → domain + tier
3. `/seo/technical` → OAuth GSC + GA4
4. `/seo/research` → import keyword CSV
5. (Tuỳ chọn) CMS pilot seed

---

### 6.3. S-05 — Chiến lược & OKR (`/seo/strategy`)

**Tính năng Gate E1 + P1 KPI editor:**

- Cây **Goal → KPI → Initiative**
- **Refresh KPI** từ metric live (GSC clicks, organic revenue…)
- **Tạo/sửa KPI** — form create/edit (P1: `PATCH .../strategy/kpis/:kpiId`)

**Thao tác:**

1. Chọn client ở filter (`?customer_id=`)
2. Xem cây OKR
3. **Refresh KPI** — cập nhật `current_value`
4. Thêm goal/KPI qua form hoặc API

**API:**

- `GET /api/v1/seo/clients/:id/strategy/okr`
- `POST .../strategy/goals` · `POST .../strategy/kpis`
- `PATCH .../strategy/kpis/:kpiId` (P1)
- `POST .../strategy/kpis/refresh`

---

### 6.4. S-06 — Research Console (`/seo/research`)

**7 tabs:** Keywords · Questions · Entities · Clusters · **SERP** · **Pages** · Opportunities

**P1/P2 — tabs SERP & Pages (thật, không còn stub Phase 3):**

| Tab | Thao tác | API (Nest) |
|-----|----------|------------|
| SERP | Bảng snapshot · **Capture SERP** | `POST .../research/serp` |
| Pages | Page inventory GSC · **Sync GSC pages** | `POST .../research/pages/sync-gsc` |
| Entities | **Auto-link clusters** | `POST .../entities/autolink` |

**Quy trình nghiên cứu:**

1. **Keywords** — import CSV hoặc thêm thủ công
2. **Clusters** — gom keyword, gán cluster
3. **SERP** — Capture (stub/live qua `PTT_SERP_PROVIDER`)
4. **Pages** — Sync GSC pages
5. **Entities** — Auto-link clusters
6. **Opportunities** — chọn keyword → **Tạo brief**

**Flow F1 — Brief → Content:**

1. Chọn keyword → **Tạo brief** (modal)
2. Template hoặc AI (Anthropic)
3. Preview → **Tạo content** → card trên Pipeline

---

### 6.5. S-07 / S-08 — Content Pipeline & Detail

**Pipeline (`/seo/content`):**

- Kanban 13 giai đoạn
- Filter client, owner, status
- **P2 view filters:** Full / Review only / Cần refresh
- URL sync filter trên query string

**13 stages:**

```
Idea → Researching → Brief Ready → In Writing → SEO Review → AEO Review
     → Technical Review → Client Review → Approved → Published
     → Monitoring → Refresh Required → Archived
```

**Content detail (`/seo/content/:id`):**

| Khu vực | Thao tác |
|---------|----------|
| Workflow | Chuyển stage, Approve/Reject |
| Editor | Lưu version mới |
| Brief | Xem/sửa brief |
| AEO checklist | Readiness |
| Governance | Vi phạm policy (5A) |
| CMS Publish | Publish thủ công → webhook |
| Audit trail | Lịch sử duyệt |

**Publish CMS (E5):**

- Thủ công: Approved → **Publish → CMS**
- Tự động: `PTT_SEO_CMS_AUTO_PUBLISH=1` → job webhook khi Published

Runbook: [`runbooks/seo-cms-webhook-pilot.md`](runbooks/seo-cms-webhook-pilot.md)

---

### 6.6. S-09 — Technical Console (`/seo/technical`)

| Khu vực | Mô tả |
|---------|-------|
| Issue backlog | Import crawl CSV, triage, gán fix |
| GSC OAuth | Kết nối Google, sync clicks/impressions |
| GA4 OAuth | Sessions, conversions, revenue |
| Core Web Vitals | Pass rate, LCP, CLS (Gate E3) |
| Crawl connector | Webhook ingest lịch (Gate E2) |

**Onboard GSC/GA4:**

1. `/seo/technical?customer_id=<ID>`
2. Nhập GA4 Property ID (nếu cần)
3. **Kết nối Google** (GSC) → consent → callback OK
4. Lặp GA4
5. **Sync OAuth** — job hoặc inline
6. Verify: clicks > 0, sessions > 0

**Crawl ingest (E2):**

```bash
curl -X POST \
  -H "X-PTT-Crawl-Secret: <secret>" \
  -H "Content-Type: application/json" \
  https://<api>/api/v1/seo/internal/crawl-ingest/<CUSTOMER_ID> \
  -d '{"issues":[{"url":"https://example.com/x","issue_type":"404","severity":"high"}]}'
```

**CWV:** `PTT_CWV_STUB=1` staging; prod `PTT_CWV_STUB=0` + `PAGESPEED_API_KEY`

**P2 a11y partial:** GSC chart có `<details>` table fallback cho screen reader.

---

### 6.7. S-10 — AEO Console (`/seo/aeo`)

- Question bank + coverage map
- Batch scan (Anthropic)
- AI mention trends, readiness score
- **P2:** `aria-live="polite"` cho kết quả scan

**Thao tác:**

1. Chọn client
2. Thêm câu hỏi hoặc import từ research
3. **Batch scan**
4. Xem coverage %, gaps
5. Tạo content FAQ từ gap

Lịch auto: `PTT_AEO_SCHEDULE_ENABLED=1` (Gate D weekly draft).

---

### 6.8. S-11 — Authority Console (`/seo/authority`)

Theo dõi mentions, citations, backlink quality — summary + import thủ công.

---

### 6.9. S-12 — Reporting Center (`/seo/reports`)

**Dashboard types:** Executive · SEO/GSC · Content · Technical · Ops · BI

**P1 — Organic attribution panel:**

- KPI: organic sessions, conversions, revenue, conv. rate
- Top landing pages table + charts
- **Điều kiện:** GA4 sync với revenue

**Thao tác:**

1. Chọn client + dashboard type
2. **Tải** — KPI + sparkline GSC + bar charts
3. **Export PDF** (`crm_seo_aeo_reports`)
4. **Export → ClickHouse** (BI)
5. **Lịch báo cáo tự động** — email weekly/monthly

---

### 6.10. S-17 — Rank Tracker (`/seo/ranks`)

- Keyword tracking, import CSV
- **Capture SERP** live
- Share of Voice (top 10)

**Env:** `PTT_RANK_LIVE_ENABLED=1`, `PTT_SERP_PROVIDER=serpapi|dataforseo`

---

### 6.11. S-13 — Automations (`/seo/automations`)

- Rule alerts: critical issues, sync failed, freshness urgent
- **Run checks** thủ công
- Slack (`PTT_SEO_SLACK_WEBHOOK`) / Teams (`PTT_SEO_TEAMS_WEBHOOK`)

Grafana ops: `deploy/grafana/seo-ops-alert-rules.json` — path `/seo/technical` (P2 fix).

---

### 6.12. S-14 — Governance (`/seo/governance`)

Bật: `PTT_SEO_GOVERNANCE_ENABLED=1`

- Policy engine — required metadata trước publish
- Link SOP/checklist
- Override Head SEO / Super Admin

---

### 6.13. S-16 — Experiments (`/seo/experiments`)

Bật: `PTT_SEO_EXPERIMENTS_ENABLED=1` (sau UAT nội bộ)

A/B title/meta, theo dõi GSC theo variant.

---

### 6.14. Freshness Queue (`/seo/freshness`)

Decay score, traffic giảm → hàng đợi refresh → chuyển content **Refresh Required**.

Cron: `PTT_FRESHNESS_SCAN_ENABLED=1` (weekly).

---

### 6.15. BI & CMS pilot

| Route | Mục đích |
|-------|----------|
| `/seo/bi` | ClickHouse export, Grafana link |
| `/seo/cms` | CMS webhook pilot, test publish |

---

### 6.16. Gate A — Go-live (`/seo/gate-a`)

Panel readiness: env flags, soak evidence, nginx redirect, handoff QA.

**Automated QA (P0):**

```bash
./scripts/seo_handoff_gate.sh
SEO_HANDOFF_SKIP_E2E=0 ./scripts/playwright_ops_seo_handoff_e2e.sh
./scripts/seo_gate_a_cutover_gate.sh
```

E2E spec: `services/ops-web/e2e/seo-handoff.spec.ts`

---

### 6.17. UX patterns chung

| Pattern | Quy ước |
|---------|---------|
| URL-synced filters | `?customer_id=` trên mọi module |
| Drill-down | Hub → client → content ≤3 click |
| Empty state | Tiếng Việt + link hành động tiếp theo |
| Workflow-visible | Stage + next action trên mọi card |
| Desktop-first | Tablet minimum; kanban scroll ngang |

---

## 7. Luồng nghiệp vụ end-to-end

### 7.1. Onboard client SEO mới

```
Tạo customer CRM
  → /seo/clients/:id/settings (domain, tier, approvers)
  → /seo/technical (GSC + GA4 OAuth + sync)
  → /seo/research (import keywords, clusters)
  → /seo/strategy (OKR nếu Gate E)
  → Hub hiển thị KPI sau sync T+1
  → (Tuỳ chọn) Portal map + PTT_PORTAL_SEO_ENABLED=1
```

### 7.2. Research → Publish (F1 + F2)

```
Research keyword → Tạo brief → Content Brief Ready
  → In Writing → SEO Review → AEO Review → Technical Review
  → Client Review (optional) → Approved → Published
  → CMS webhook (manual hoặc auto) → Monitoring
```

### 7.3. Technical issue → fix

```
Import crawl CSV → triage severity → gán owner
  → Tạo task CRM (optional) → fix → resolve issue
  → Reflect trên Hub critical count
```

### 7.4. Refresh content (freshness)

```
Weekly freshness scan → /seo/freshness queue
  → Prioritize → Pipeline Refresh Required
  → Writer update → re-publish workflow
```

---

## 8. Cron, jobs & tự động hóa

### 8.1. Bảng job

| Job | Tần suất | Trigger |
|-----|----------|---------|
| GSC sync | Daily 06:xx | `ptt-seo-gsc-sync.timer` |
| GA4 sync | Daily | `ptt-seo-ga4-sync.timer` |
| Report email | Daily | cron daily |
| Freshness scan | Weekly | cron weekly |
| SERP capture | Weekly | cron gate-e |
| Gate D bundle | Weekly | `ptt-seo-gate-d.timer` |
| ClickHouse export | Daily 04:00 VN | `ptt-seo-clickhouse-export.timer` |

### 8.2. Cron scripts

```bash
# Daily 06:15
15 6 * * * cd /var/www/ptt && ./scripts/seo_aeo_cron_daily.sh >> /var/log/seo_aeo_cron_daily.log 2>&1

# Weekly Chủ nhật 03:00
0 3 * * 0 cd /var/www/ptt && ./scripts/seo_aeo_cron_weekly.sh >> /var/log/seo_aeo_cron_weekly.log 2>&1
```

**API cron** (Bearer `PTT_SEO_CRON_SECRET`):

```bash
curl -X POST -H "Authorization: Bearer $PTT_SEO_CRON_SECRET" \
  https://<api>/api/v1/seo/cron/daily?days=28
```

Chi tiết: [`runbooks/seo-aeo-cron.md`](runbooks/seo-aeo-cron.md)

### 8.3. Worker job types

`seo_gsc_sync`, `seo_ga4_sync`, `seo_freshness_scan`, `seo_report_schedules`, `seo_cms_publish`, `seo_aeo_scan`

Fallback inline: `PTT_JOBS_SYNC_FALLBACK=1` khi user bấm Sync thủ công.

### 8.4. Kiểm tra timer

```bash
systemctl list-timers | grep -E 'seo|ptt-seo'
journalctl -u ptt-seo-gsc-sync.service -n 50
tail -f /var/log/seo_aeo_cron_daily.log
```

---

## 9. Client Portal SEO

**Bật:** `PTT_PORTAL_SEO_ENABLED=1` (sau Gate A step 2)

| Route | Chức năng |
|-------|-----------|
| `/seo` | Dashboard KPI read-only |
| `/seo/reports` | Báo cáo executive |
| `/seo/content` | Duyệt content stage `client_review` |

**Deploy:**

```bash
python3 scripts/seed_portal_seo_pilot_map.py --apply --client-id <UUID> --customer-id <CRM_ID>
sudo systemctl restart ptt-crm-api
cd services/portal-web && npm run build && pm2 restart portal-web
```

Template: `deploy/env.seo-portal-pilot.example`

E2E gate: `./scripts/phase5_portal_seo_e2e_gate.sh`

**Rollback:** `PTT_PORTAL_SEO_ENABLED=0` — ẩn nav; staff approve vẫn trên ops-web.

---

## 10. Gates, QA & nghiệm thu

| Gate | Script | Nội dung |
|------|--------|----------|
| Handoff §12 (P0) | `seo_handoff_gate.sh` | Python QA + Playwright E2E ops-web |
| Gate D | `staging_seo_gate_d_deploy.sh` | CWV, Teams, AEO schedule |
| Gate E | `staging_seo_gate_e_deploy.sh` | OKR, crawl, rank, CMS |
| Gate A | `seo_gate_a_cutover_gate.sh` | Prod sign-off + soak |
| B5 Portal | `wave_seo_b5_gate.sh` | Portal E2E |

**Soak:** `./scripts/phase5_soak_record.sh` hàng ngày ≥7 ngày trước Gate A ký.

Sign-off: [`runbooks/phase5-prod-signoff-checklist.md`](runbooks/phase5-prod-signoff-checklist.md)

Tests P1/P2:

```bash
python3 -m pytest tests/test_seo_p1_qa.py tests/test_seo_p2_qa.py tests/test_seo_handoff_qa.py -q
```

---

## 11. Xử lý sự cố thường gặp

| Triệu chứng | Nguyên nhân | Cách xử lý |
|-------------|-------------|------------|
| SEO menu không hiện | Thiếu cap hoặc flag `0` | Admin phân quyền + `NEXT_PUBLIC_PTT_SEO_*` |
| GSC sync 0 rows | OAuth chưa kết nối | Technical → reconnect |
| GA4 revenue = 0 | Chưa có revenue events | GA4 e-commerce → sync lại |
| Attribution panel trống | Chưa sync GA4 organic | Sync + đợi cron daily |
| SERP/Pages tab trống | Chưa capture/sync | Nút Capture SERP / Sync GSC pages |
| Publish CMS fail | Webhook URL/secret sai | Client settings → test |
| CWV panel trống | Gate D chưa chạy | Bật timer hoặc `curl .../cron/gate-d` |
| Rank stub only | `PTT_SERP_PROVIDER=stub` | SerpAPI key + provider live |
| Cron 401 | Sai `PTT_SEO_CRON_SECRET` | Đồng bộ .env |
| PG relation missing | Schema chưa apply | `apply_seo_gate_*_schema.sh` |
| E2E handoff fail | Nest down | Start `ptt-crm-api` :3000 |

**Log:**

```bash
journalctl -u ptt-crm-api -f
journalctl -u ptt-worker -f
grep -i seo /var/www/ptt/logs/*.log
```

---

## 12. Checklist go-live

### Staging

- [ ] `SEO_AEO_DB=pg` + backfill verified
- [ ] GSC + GA4 OAuth pilot OK
- [ ] ops-web 19 routes load không 403
- [ ] Gate D timer (CWV, Teams test)
- [ ] Gate E schema (nếu dùng OKR/rank/CMS)
- [ ] Cron daily/weekly 7 ngày không lỗi
- [ ] S-12 attribution có data
- [ ] `seo_handoff_gate.sh` PASS
- [ ] P1/P2 QA pytest PASS

### Production (Gate A)

- [ ] Backup PG trước cutover
- [ ] Nginx `/crm/seo` → `/seo` active
- [ ] Tắt stub: `PTT_GSC_SYNC_STUB=0`, `PTT_GA4_SYNC_STUB=0`
- [ ] `PTT_SEO_GOVERNANCE_ENABLED=1`
- [ ] Portal/Experiments staged cutover + soak
- [ ] `seo_gate_a_cutover_gate.sh` PASS
- [ ] Human sign-off: `docs/evidence/seo-gate-a-signoff.template.json`
- [ ] Grafana alert rules imported

---

## 13. Phụ lục — env, API, runbook

### 13.1. Env template files

| File | Mục đích |
|------|----------|
| `deploy/env.seo-aeo-pilot.example` | Phase 0 + B1 pilot |
| `deploy/env.staging-seo-gate-d.example` | Gate D |
| `deploy/env.staging-seo-gate-e.example` | Gate E |
| `deploy/env.seo-portal-pilot.example` | Portal B5 |
| `deploy/env.seo-gate-a-prod.example` | Gate A prod |
| `deploy/env.seo-bi-gate-de.example` | BI ClickHouse |

### 13.2. API Nest chính (prefix `/api/v1/seo/`)

| Nhóm | Paths |
|------|-------|
| Hub/Clients | `GET /hub`, `GET /clients`, `GET /clients/:id`, `PUT .../settings`, `POST .../sync/:source` |
| OAuth | `GET /gsc/oauth/callback`, `GET /ga4/oauth/callback`, `GET .../gsc/oauth/url` |
| Research | `GET .../research`, `POST .../keywords/import`, `POST .../research/serp`, `POST .../pages/sync-gsc` |
| Content | `GET /content/pipeline`, `GET/PATCH /content/:id`, `POST .../approve` |
| Technical | `GET/POST .../issues`, `POST .../issues/import`, `GET .../cwv` |
| Reports | `GET .../dashboard/:type`, `GET .../reports/export`, `GET .../attribution` |
| Strategy | `GET .../strategy/okr`, `PATCH .../strategy/kpis/:kpiId` |
| AEO | `GET/POST .../aeo/queries`, `POST .../aeo/scan` |
| Cron | `POST /cron/daily`, `/cron/weekly`, `/cron/gate-d`, `/cron/gate-e` |

Danh sách đầy đủ: `deploy/env.seo-aeo-pilot.example` comments + spec §10 architecture doc.

### 13.3. Runbook chuyên sâu

| Chủ đề | File |
|--------|------|
| PG cutover + OAuth UAT | [`runbooks/seo-aeo-pg-oauth-uat-cutover.md`](runbooks/seo-aeo-pg-oauth-uat-cutover.md) |
| Cron VPS | [`runbooks/seo-aeo-cron.md`](runbooks/seo-aeo-cron.md) |
| Gate D BI/CWV | [`runbooks/seo-aeo-gate-d.md`](runbooks/seo-aeo-gate-d.md) |
| Gate E enterprise | [`runbooks/seo-aeo-gate-e.md`](runbooks/seo-aeo-gate-e.md) |
| ClickHouse + Grafana | [`runbooks/seo-aeo-clickhouse-bi.md`](runbooks/seo-aeo-clickhouse-bi.md) |
| CMS webhook | [`runbooks/seo-cms-webhook-pilot.md`](runbooks/seo-cms-webhook-pilot.md) |
| Gate A sign-off | [`runbooks/phase5-prod-signoff-checklist.md`](runbooks/phase5-prod-signoff-checklist.md) |
| Gate C (SerpAPI) | [`runbooks/seo-aeo-p3-gate-c.md`](runbooks/seo-aeo-p3-gate-c.md) |
| Meta (tách biệt) | [`huong-dan-meta-enterprise-ops.md`](huong-dan-meta-enterprise-ops.md) |

### 13.4. Tài liệu đào tạo team SEO

| Tài liệu | Mô tả | Cách dùng |
|----------|--------|-----------|
| [`SEO_AEO_Ops_Training.pptx`](SEO_AEO_Ops_Training.pptx) | Slide đào tạo ~45 phút (22 slide) | Buổi onboard team SEO/AEO |
| [`forms/seo-aeo-ops-checklist-a4.html`](forms/seo-aeo-ops-checklist-a4.html) | Checklist in A4 — daily / weekly / onboard / publish | Mở browser → **Cmd+P** → A4 |
| `scripts/generate_seo_aeo_training_pptx.py` | Tạo lại PPT sau khi cập nhật spec | `python3 scripts/generate_seo_aeo_training_pptx.py` |

**Nội dung slide deck:** vision · stack ops-web · module map · RBAC · từng màn S-01→S-12 · luồng hàng ngày · onboard · troubleshooting · Gate A.

**Checklist A4 gồm 7 phần:** A hàng ngày · B hàng tuần · C onboard client · D publish gate · E Research→Content · F RBAC · G ghi chú sự cố + ký duyệt.

---

*Tài liệu v2.0 phản ánh codebase post P0/P1/P2 hardening (2026-07-25). Đối chiếu [`SEO_AEO_COMPLETION_ROADMAP.md`](SEO_AEO_COMPLETION_ROADMAP.md) khi spec cập nhật.*
