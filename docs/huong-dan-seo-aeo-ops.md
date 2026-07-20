# Hướng dẫn sử dụng phân hệ SEO/AEO Ops

> **Phiên bản:** 1.0 · **Ngày:** 2026-07-19  
> **Đối tượng:** Admin VPS, Head SEO/AEO, vận hành agency  
> **Phạm vi tài liệu:** Triển khai trên **VPS** + hướng dẫn sử dụng từng module đã triển khai  
> **URL CRM:** `https://pttads.vn` (production) · `https://staging.pttads.vn` (staging)  
> **Spec tham chiếu:** [`SPEC_SEO_AEO_OPERATING_SYSTEM.md`](SPEC_SEO_AEO_OPERATING_SYSTEM.md) · [`SPEC_UI_UX_SEO_AEO.md`](SPEC_UI_UX_SEO_AEO.md)

---

## Mục lục

1. [Tổng quan phân hệ](#1-tổng-quan-phân-hệ)
2. [Kiến trúc trên VPS](#2-kiến-trúc-trên-vps)
3. [Triển khai lên VPS](#3-triển-khai-lên-vps)
4. [Truy cập & phân quyền](#4-truy-cập--phân-quyền)
5. [Hướng dẫn từng module](#5-hướng-dẫn-từng-module)
6. [Cron & tự động hóa](#6-cron--tự-động-hóa)
7. [Client Portal SEO](#7-client-portal-seo)
8. [Xử lý sự cố thường gặp](#8-xử-lý-sự-cố-thường-gặp)
9. [Checklist go-live](#9-checklist-go-live)

---

## 1. Tổng quan phân hệ

**SEO/AEO Ops** là phân hệ vận hành vòng đời SEO + Answer Engine Optimization trên PTTADS CRM:

```
Chiến lược → Nghiên cứu → Sản xuất nội dung → QA kỹ thuật
         → Tối ưu AEO → Publish → Giám sát → Refresh → Báo cáo
```

### 1.1. Module đã triển khai

| Nhóm | Module | Route chính |
|------|--------|-------------|
| Hub | Tổng quan Executive | `/crm/seo` |
| Client | Workspace khách hàng SEO | `/crm/seo/clients/:id` |
| Strategy | OKR/KPI & Roadmap | `/crm/seo/strategy` |
| Research | Nghiên cứu (keyword, cluster, SERP…) | `/crm/seo/research` |
| Content | Pipeline nội dung | `/crm/seo/content` |
| Technical | Kỹ thuật, GSC/GA4, CWV, crawl | `/crm/seo/technical` |
| AEO | AEO Console | `/crm/seo/aeo` |
| Authority | Mentions & citations | `/crm/seo/authority` |
| Reports | Báo cáo & attribution | `/crm/seo/reports` |
| Ranks | Rank tracker & SOV | `/crm/seo/ranks` |
| Automations | Cảnh báo & rule | `/crm/seo/automations` |
| Governance | Chính sách publish | `/crm/seo/governance` |
| Experiments | A/B SEO | `/crm/seo/experiments` |
| Freshness | Hàng đợi refresh | `/crm/seo/freshness` |
| Portal | Client xem/duyệt (Next.js) | `/seo` (portal) |

### 1.2. Luồng dữ liệu chính

- **CRM master** (khách hàng, lifecycle): SQLite `crm_customers`
- **SEO/AEO domain** (content, GSC, GA4, issues…): **PostgreSQL** schema `seo_aeo.*`
- **Tích hợp:** Google OAuth (GSC/GA4), CMS webhook, ClickHouse BI, Slack/Teams alerts

---

## 2. Kiến trúc trên VPS

```
┌─────────────────────────────────────────────────────────────┐
│  VPS (vd. /var/www/ptt)                                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │ systemd: ptt │  │ ptt-worker   │  │ portal-web (opt) │  │
│  │ Flask :5000  │  │ job queue    │  │ Next.js :3000    │  │
│  └──────┬───────┘  └──────┬───────┘  └────────┬─────────┘  │
│         │                 │                    │            │
│         └────────┬────────┴────────────────────┘            │
│                  ▼                                          │
│         PostgreSQL (seo_aeo.*) + SQLite (CRM)               │
│                  │                                          │
│    systemd timers: GSC sync · GA4 sync · Gate D · ClickHouse │
└─────────────────────────────────────────────────────────────┘
```

**Đường dẫn mặc định trên VPS:**

| Thành phần | Path |
|------------|------|
| Repo | `/var/www/ptt` |
| Env | `/var/www/ptt/.env` |
| User SSH deploy | `deploy` |
| Service Flask | `ptt` |
| Log cron SEO | `/var/log/seo_aeo_cron_*.log` |

---

## 3. Triển khai lên VPS

> Thực hiện **staging trước**, soak ≥ 7 ngày, rồi mới production.  
> Runbook chi tiết: [`runbooks/seo-aeo-pg-oauth-uat-cutover.md`](runbooks/seo-aeo-pg-oauth-uat-cutover.md)

### 3.1. Điều kiện tiên quyết

- [ ] PostgreSQL production (`DATABASE_URL`) hoạt động
- [ ] Google Cloud OAuth client với redirect:
  - `https://<domain>/api/v1/seo/gsc/oauth/callback`
  - `https://<domain>/api/v1/seo/ga4/oauth/callback`
- [ ] APIs bật: Search Console, Analytics Data, Analytics Admin
- [ ] `PTT_TOKEN_VAULT_KEY` — mã hóa refresh token OAuth
- [ ] Backup: `pg_dump` + copy `ptt.db`

### 3.2. Bước 1 — PostgreSQL cutover (bắt buộc)

Trên VPS:

```bash
cd /var/www/ptt
export DATABASE_URL=postgresql://...
export PILOT_CUSTOMER_ID=<CRM_CUSTOMER_ID>

# Dry-run
APPLY=0 ./scripts/seo_aeo_prod_cutover.sh

# Thực thi
sudo -E APPLY=1 ./scripts/seo_aeo_prod_cutover.sh
sudo systemctl restart ptt ptt-temporal-worker
```

**Biến môi trường cốt lõi** (thêm/sửa trong `/var/www/ptt/.env`):

```bash
SEO_AEO_DB=pg
DATABASE_URL=postgresql://...

# GSC OAuth
PTT_GSC_OAUTH_CLIENT_ID=...
PTT_GSC_OAUTH_CLIENT_SECRET=...
PTT_GSC_OAUTH_REDIRECT_URI=https://pttads.vn/api/v1/seo/gsc/oauth/callback
PTT_GSC_SYNC_ENABLED=1

# GA4 OAuth (có thể dùng chung client với GSC)
PTT_GA4_OAUTH_CLIENT_ID=...
PTT_GA4_OAUTH_CLIENT_SECRET=...
PTT_GA4_OAUTH_REDIRECT_URI=https://pttads.vn/api/v1/seo/ga4/oauth/callback
PTT_GA4_SYNC_ENABLED=1

PTT_TOKEN_VAULT_KEY=...
PTT_JOBS_ENABLED=1
PTT_JOBS_SYNC_FALLBACK=1
PTT_SEO_CRON_SECRET=<secret-mạnh>
```

Bật timer đồng bộ hàng ngày:

```bash
sudo systemctl enable --now ptt-seo-gsc-sync.timer ptt-seo-ga4-sync.timer
sudo systemctl restart ptt
```

**Verify:**

```bash
python3 scripts/verify_seo_aeo_oauth_uat.py --customer-id <PILOT_ID>
# SQL: SELECT COUNT(*) FROM seo_aeo.seo_gsc_daily_stats WHERE customer_id=<PILOT_ID>;
```

### 3.3. Bước 2 — Gate D (BI, CWV, Teams, AEO schedule)

**Từ máy local có SSH** (hoặc chạy trực tiếp trên VPS):

```bash
# Dry-run
PTT_VPS_HOST=<IP-staging> APPLY=0 ./scripts/staging_seo_gate_d_deploy.sh

# Apply + timer
PTT_VPS_HOST=<IP-staging> APPLY=1 ./scripts/staging_seo_gate_d_deploy.sh

# Code chưa push git
LOCAL_SYNC=1 PTT_VPS_HOST=<IP> APPLY=1 ./scripts/staging_seo_gate_d_deploy.sh
```

**Trên VPS trực tiếp:**

```bash
cd /var/www/ptt
./scripts/apply_seo_gate_d_schema.sh
sudo ./scripts/install_seo_gate_d_systemd.sh
sudo systemctl enable --now ptt-seo-gate-d.timer
```

**Env Gate D** (merge từ `deploy/env.staging-seo-gate-d.example`):

```bash
PTT_CWV_ENABLED=1
PAGESPEED_API_KEY=...          # staging pilot: PTT_CWV_STUB=1
PTT_CRAWL_REMINDER_ENABLED=1
PTT_SEO_TEAMS_WEBHOOK=https://outlook.office.com/webhook/...
PTT_AEO_SCHEDULE_ENABLED=1
PTT_AEO_AUTO_DRAFT_ENABLED=1
```

ClickHouse + Grafana: [`runbooks/seo-aeo-clickhouse-bi.md`](runbooks/seo-aeo-clickhouse-bi.md)

### 3.4. Bước 3 — Gate E (OKR, crawl connector, rank, CMS auto-publish)

```bash
# Dry-run
PTT_VPS_HOST=<IP> APPLY=0 ./scripts/staging_seo_gate_e_deploy.sh

# Apply + restart + seed CMS pilot
PTT_VPS_HOST=<IP> APPLY=1 PILOT_CUSTOMER_ID=<CRM_ID> ./scripts/staging_seo_gate_e_deploy.sh
```

**Trên VPS trực tiếp:**

```bash
cd /var/www/ptt
./scripts/apply_seo_gate_e_schema.sh
grep PTT_SEO_CMS_AUTO_PUBLISH .env   # phải = 1 khi pilot auto-publish
sudo systemctl restart ptt
python3 scripts/seed_cms_webhook_pilot.py --customer-id <CRM_ID>
```

**Env Gate E** (`deploy/env.staging-seo-gate-e.example`):

```bash
PTT_SEO_ENTERPRISE_ENABLED=1
PTT_CRAWL_CONNECTOR_ENABLED=1
PTT_RANK_LIVE_ENABLED=1
PTT_SERP_PROVIDER=stub           # prod live: serpapi hoặc dataforseo
PTT_SEO_CMS_AUTO_PUBLISH=1         # chỉ bật sau pilot CMS
PTT_SEO_CMS_WEBHOOK_SECRET=...
PTT_FLASK_MONOLITH_URL=https://pttads.vn
```

### 3.5. Bước 4 — Cron tổng hợp

Cài crontab hoặc dùng systemd (khuyến nghị):

```bash
# Daily — GSC + GA4 + report schedules (06:15)
15 6 * * * cd /var/www/ptt && ./scripts/seo_aeo_cron_daily.sh >> /var/log/seo_aeo_cron_daily.log 2>&1

# Weekly — freshness + SERP + Gate D/E bundle (Chủ nhật 03:00)
0 3 * * 0 cd /var/www/ptt && ./scripts/seo_aeo_cron_weekly.sh >> /var/log/seo_aeo_cron_weekly.log 2>&1
```

Hoặc gọi API cron (Bearer `PTT_SEO_CRON_SECRET`):

```bash
curl -X POST -H "Authorization: Bearer $PTT_SEO_CRON_SECRET" \
  https://pttads.vn/api/v1/seo/cron/daily?days=28

curl -X POST -H "Authorization: Bearer $PTT_SEO_CRON_SECRET" \
  https://pttads.vn/api/v1/seo/cron/weekly

curl -X POST -H "Authorization: Bearer $PTT_SEO_CRON_SECRET" \
  https://pttads.vn/api/v1/seo/cron/gate-d

curl -X POST -H "Authorization: Bearer $PTT_SEO_CRON_SECRET" \
  https://pttads.vn/api/v1/seo/cron/gate-e
```

Chi tiết: [`runbooks/seo-aeo-cron.md`](runbooks/seo-aeo-cron.md)

### 3.6. Bước 5 — Phase 5 flags (Governance, Portal, Experiments)

**Production mặc định an toàn:**

| Biến | Prod default | Ý nghĩa |
|------|--------------|---------|
| `PTT_SEO_GOVERNANCE_ENABLED` | `1` | Bật policy publish |
| `PTT_PORTAL_SEO_ENABLED` | `0` | Portal client — bật sau UAT |
| `PTT_SEO_EXPERIMENTS_ENABLED` | `0` | A/B test — bật sau UAT nội bộ |

Cutover có kiểm soát:

```bash
cd /var/www/ptt
chmod +x scripts/phase5_prod_cutover_gate.sh scripts/close_phase5_prod_cutover.sh

# Bước 1 — Governance
APPLY=1 PHASE5_ENABLE_GOVERNANCE=1 sudo -E ./scripts/close_phase5_prod_cutover.sh

# Bước 2 — Portal (sau seed map client)
python3 scripts/seed_portal_seo_pilot_map.py --apply --client-id <UUID> --customer-id <CRM_ID>
APPLY=1 PHASE5_ENABLE_PORTAL=1 PTT_PORTAL_SEO_SERVICE_TOKEN=<secret> \
  sudo -E ./scripts/close_phase5_prod_cutover.sh

# Bước 3 — Experiments
APPLY=1 PHASE5_ENABLE_EXPERIMENTS=1 sudo -E ./scripts/close_phase5_prod_cutover.sh
```

Soak ≥ 7 ngày: `./scripts/phase5_soak_record.sh` hàng ngày.

### 3.7. Rollback nhanh

| Tình huống | Hành động |
|------------|-----------|
| Lỗi PG cutover | `SEO_AEO_DB=sqlite` trong `.env` → `sudo systemctl restart ptt` |
| Portal lỗi | `PTT_PORTAL_SEO_ENABLED=0` → restart portal + CRM API |
| CMS auto-publish lỗi | `PTT_SEO_CMS_AUTO_PUBLISH=0` → restart `ptt` |

---

## 4. Truy cập & phân quyền

### 4.1. Đăng nhập

1. Truy cập `https://pttads.vn/admin` (hoặc domain CRM của agency)
2. Sidebar → **CRM · SEO/AEO Ops**
3. Legacy AEO: `/crm/aeo` tự redirect → `/crm/seo/aeo`

### 4.2. Section keys (Admin → Phân quyền trang)

| Key | Quyền |
|-----|-------|
| `crm_seo_aeo` | Xem toàn phân hệ |
| `crm_seo_aeo_write` | Tạo/sửa research, content |
| `crm_seo_aeo_approve` | Duyệt workflow content |
| `crm_seo_aeo_technical` | Import crawl, sửa issue |
| `crm_seo_aeo_settings` | OAuth, CMS, lịch báo cáo |
| `crm_seo_aeo_reports` | Export PDF, ClickHouse |

**Gợi ý gán theo vai trò:**

| Vai trò | Keys |
|---------|------|
| Head SEO / MKT-01 | Cả 6 keys |
| Strategist | view + write + reports |
| Writer | view + write (không approve) |
| Tech SEO | view + technical |
| AM / KD-01 | view + settings + reports |

### 4.3. Nút UI theo quyền

Template ẩn/hiện nút qua flags: `can_seo_write`, `can_seo_approve`, `can_seo_configure`, `can_seo_export`, `can_seo_technical`.

---

## 5. Hướng dẫn từng module

### 5.1. S-01 — Tổng quan Executive (`/crm/seo`)

**Mục đích:** Dashboard cấp lãnh đạo — KPI tổng, client health, issue nghiêm trọng, tiến độ content.

**Cách sử dụng:**

1. Mở **CRM · SEO/AEO Ops → Tổng quan**
2. Lọc theo client / thời gian (nếu có filter bar)
3. Click hàng **Client health** → vào workspace client (drill-down ≤ 3 click)
4. Xem badge nav (critical issues, overdue content) qua API nav-badges

**Dữ liệu cần:** GSC sync, content pipeline, technical issues đã nhập.

---

### 5.2. S-02 / S-03 / S-04 — Khách hàng SEO & Workspace

**Routes:** `/crm/seo/clients` · `/crm/seo/clients/:id` · tab Cài đặt

**Tính năng workspace (tabs):**

| Tab | Chức năng |
|-----|-----------|
| Tổng quan | KPI client, roadmap, lifecycle |
| Roadmap | Initiatives 30/60/90 ngày |
| Tasks | Task CRM + issue kỹ thuật mở |
| Nghiên cứu | Shortcut research theo client |
| Nội dung | Pipeline client |
| Kỹ thuật | Issue backlog client |
| AEO | Coverage client |
| Authority | Mentions client |
| Báo cáo | Dashboard theo client |
| Cài đặt | Domain, integrations, approvers |

**Cài đặt client (S-04) — cần quyền `crm_seo_aeo_settings`:**

1. **Domains / markets / languages** — phạm vi SEO
2. **Brand & SEO guidelines** — JSON hướng dẫn nội dung
3. **Integrations** — GSC site, GA4 property (qua OAuth UI hoặc JSON)
4. **CMS Publish** — webhook URL, secret, test connectivity
5. **Approvers** — chuỗi duyệt client_review

**Onboard client mới:**

1. Tạo/chọn customer trong CRM
2. Vào `/crm/seo/clients/:id/settings` → lưu domain + tier
3. Technical Console → kết nối GSC + GA4 OAuth
4. Research → import keyword CSV
5. (Tuỳ chọn) Seed CMS pilot: **Áp dụng pilot mặc định**

---

### 5.3. S-05 — Chiến lược & OKR (`/crm/seo/strategy`)

**Tính năng (Gate E1):**

- Cây **Goal → KPI → Initiative**
- Refresh KPI từ metric live (GSC clicks, organic revenue…)
- Link initiative vào goal

**Cách sử dụng:**

1. Chọn client ở filter bar
2. Xem cây OKR hiện có (load tự động)
3. **Refresh KPI** — cập nhật `current_value` từ backend
4. Tạo goal/KPI qua API hoặc form (nếu đã bật trên UI)

**API tham khảo:**

- `GET /api/v1/seo/clients/:id/strategy/okr`
- `POST .../strategy/goals` · `POST .../strategy/kpis`
- `POST .../strategy/kpis/refresh`

---

### 5.4. S-06 — Research Console (`/crm/seo/research`)

**7 tabs:** Keywords · Questions · Entities · Clusters · SERP · Pages · Opportunities

**Quy trình nghiên cứu điển hình:**

1. **Keywords** — import CSV hoặc thêm thủ công  
   `POST /api/v1/seo/clients/:id/keywords/import`
2. **Clusters** — gom keyword, gán cluster  
   Tab Clusters → tạo cluster → assign keyword
3. **SERP** — capture snapshot (SerpAPI/DataForSEO hoặc stub)  
   Nút **Capture SERP** · env `PTT_SERP_PROVIDER`
4. **Pages** — sync page inventory từ GSC  
   **Sync GSC pages**
5. **Entities** — graph entity + **Auto-link clusters** (Gate E4)
6. **Opportunities** — xem điểm cơ hội, chọn keyword → **Tạo brief**

**Flow tạo brief → content (F1):**

1. Chọn keyword → **Tạo brief** (modal)
2. Chọn nguồn: AI (Anthropic) hoặc template
3. Preview brief → **Tạo content** → card xuất hiện trên Pipeline

---

### 5.5. S-07 / S-08 — Content Pipeline & Detail

**Pipeline (`/crm/seo/content`):**

- Kanban 13 giai đoạn workflow
- Filter client, owner, status
- Review kanban (Gate B) cho SEO/AEO review

**13 giai đoạn workflow:**

```
Idea → Researching → Brief Ready → In Writing → SEO Review → AEO Review
     → Technical Review → Client Review → Approved → Published
     → Monitoring → Refresh Required → Archived
```

**Content detail (`/crm/seo/content/:id`):**

| Khu vực | Thao tác |
|---------|----------|
| Workflow | Chuyển stage, Approve/Reject |
| Editor | Lưu version mới |
| Brief | Xem/sửa brief |
| AEO checklist | Checklist readiness |
| Governance | Panel vi phạm policy (Phase 5A) |
| CMS Publish | Publish thủ công → webhook |
| Audit trail | Lịch sử duyệt |

**Publish lên CMS (E5):**

- **Thủ công:** Approved → **Publish → CMS**
- **Tự động:** Khi `PTT_SEO_CMS_AUTO_PUBLISH=1` và chuyển sang **Published** → job webhook tự enqueue

Runbook CMS: [`runbooks/seo-cms-webhook-pilot.md`](runbooks/seo-cms-webhook-pilot.md)

**Governance block:** Nếu thiếu meta title, schema lỗi, chưa QA — hệ thống chặn publish (khi governance bật).

---

### 5.6. S-09 — Technical Console (`/crm/seo/technical`)

**Tính năng:**

| Khu vực | Mô tả |
|---------|-------|
| Issue backlog | Import crawl CSV, triage severity, gán fix |
| GSC OAuth | Kết nối Google, sync clicks/impressions |
| GA4 OAuth | Kết nối GA4, sync sessions/conversions/revenue |
| Core Web Vitals | Panel CWV pass rate, LCP, CLS (Gate E3) |
| Crawl connector | Lịch webhook ingest (Gate E2) |

**Onboard GSC/GA4 (pilot client):**

1. Vào `/crm/seo/technical?customer_id=<ID>`
2. Nhập GA4 Property ID (nếu cần)
3. **Kết nối Google** (GSC) → consent → callback OK
4. Lặp lại cho GA4
5. **Sync OAuth** — chờ job hoặc sync inline
6. Verify stats: clicks > 0, sessions > 0

**Import crawl CSV:**

1. Chọn client
2. Upload CSV (cột: url, issue_type, severity, description)
3. Issue xuất hiện backlog → **Tạo task** CRM nếu cần

**Crawl connector schedule (E2):**

1. Panel **Crawl connector** → set frequency (ngày), webhook secret
2. Tool crawl bên ngoài POST:

```bash
curl -X POST \
  -H "X-PTT-Crawl-Secret: <secret>" \
  -H "Content-Type: application/json" \
  https://pttads.vn/api/v1/seo/internal/crawl-ingest/<CUSTOMER_ID> \
  -d '{"issues":[{"url":"https://example.com/x","issue_type":"404","severity":"high"}]}'
```

**CWV:** Cron Gate D ingest PageSpeed → xem panel CRM. Staging: `PTT_CWV_STUB=1`.

---

### 5.7. S-10 — AEO Console (`/crm/seo/aeo`)

**Tính năng:**

- Question bank + coverage map
- Batch scan (Anthropic API)
- AI mention trends
- Readiness score

**Cách sử dụng:**

1. Chọn client
2. Thêm câu hỏi (question matrix) hoặc import từ research
3. **Batch scan** — enqueue job quét AI visibility
4. Xem coverage %, mentions, gap notes
5. Tạo content FAQ từ gap (manual hoặc auto draft qua Gate D schedule)

**Lịch AEO tự động (Gate D):** `PTT_AEO_SCHEDULE_ENABLED=1` — cron weekly tạo draft khi brand không visible.

---

### 5.8. S-11 — Authority Console (`/crm/seo/authority`)

**Tính năng:** Theo dõi mentions, citations, backlink quality.

**Cách sử dụng:**

1. Chọn client tại `/crm/seo/authority`
2. Xem summary mentions/citations
3. Thêm mention thủ công hoặc import (nếu có connector)
4. Dùng trong executive dashboard (authority block)

---

### 5.9. S-12 — Reporting Center (`/crm/seo/reports`)

**Dashboard types:** Executive · SEO/GSC · Content · Technical · Ops · BI/Warehouse

**Cách sử dụng:**

1. Chọn **Client** + **Dashboard type**
2. **Tải** — render KPI cards + charts (GSC sparkline, content/severity bar)
3. **Export PDF** (cần `crm_seo_aeo_reports`)
4. **Export → ClickHouse** (dashboard BI)

**Organic attribution panel (E7):**

- Hiển thị khi đã chọn client
- KPI: organic sessions, conversions, revenue, rev/session, conv. rate
- Bảng + chart top landing pages organic
- **Điều kiện:** GA4 đã sync với revenue (`totalRevenue` từ GA4 Data API)

**Lịch báo cáo tự động:**

1. Chọn client
2. Form **Lịch báo cáo tự động** — email nhận, CC/BCC, cadence weekly/monthly
3. **Tạo lịch gửi** — cron daily gửi email
4. **Gửi ngay** — test schedule

---

### 5.10. S-17 — Rank Tracker (`/crm/seo/ranks`)

**Tính năng (Gate E6):**

- Theo dõi keyword ranking
- Import CSV
- **Capture SERP** live
- **Share of Voice** (top 10)

**Cách sử dụng:**

1. Chọn client
2. Thêm keyword tracked hoặc import CSV
3. **Capture SERP** — chụp vị trí hiện tại (stub hoặc SerpAPI)
4. Xem SOV cards + lịch sử position

**Env:** `PTT_RANK_LIVE_ENABLED=1`, `PTT_SERP_PROVIDER=serpapi` (production live).

---

### 5.11. S-13 — Automations & Alerts (`/crm/seo/automations`)

**Tính năng:**

- Rule cảnh báo (critical issues, sync failed, freshness urgent…)
- Danh sách alert open/resolved
- Chạy check thủ công

**Cách sử dụng:**

1. Vào `/crm/seo/automations`
2. Xem alert đang mở
3. **Run checks** — trigger anomaly detection
4. Alerts gửi Slack (`PTT_SEO_SLACK_WEBHOOK`) và/hoặc Teams (`PTT_SEO_TEAMS_WEBHOOK`)

---

### 5.12. S-14 — Governance Hub (`/crm/seo/governance`)

**Bật khi:** `PTT_SEO_GOVERNANCE_ENABLED=1`

**Tính năng:**

- Policy engine — required fields trước publish
- Link SOP/checklist
- Override (Head SEO / Super Admin)

**Cách sử dụng:**

1. Cấu hình rule tại Governance hub
2. Khi publish content — modal hiện vi phạm nếu thiếu metadata
3. QA/Compliance review trên content detail trước **Approved**

---

### 5.13. S-16 — Experiments (`/crm/seo/experiments`)

**Bật khi:** `PTT_SEO_EXPERIMENTS_ENABLED=1`

**Tính năng:** A/B test title/meta, theo dõi GSC metrics theo variant.

**Cách sử dụng:**

1. Tạo experiment gắn page/URL
2. Define variant A/B
3. Chạy thử nội bộ trước khi bật prod flag

---

### 5.14. Freshness Queue (`/crm/seo/freshness`)

**Tính năng:** Hàng đợi content cần refresh (decay score, traffic giảm).

**Cách sử dụng:**

1. Cron weekly scan (`PTT_FRESHNESS_SCAN_ENABLED=1`)
2. Vào Freshness queue → ưu tiên refresh
3. Chuyển content → **Refresh Required** trên pipeline

---

## 6. Cron & tự động hóa

### 6.1. Bảng job tự động

| Job | Tần suất | Script / API |
|-----|----------|--------------|
| GSC sync | Daily 06:xx | `sync_seo_gsc_daily.sh` · cron daily |
| GA4 sync (+ revenue) | Daily | `sync_seo_ga4_daily.sh` · cron daily |
| Report email schedules | Daily | cron daily |
| Freshness scan | Weekly | cron weekly |
| SERP capture | Weekly | cron weekly / gate-e |
| Gate D bundle | Weekly timer | `ptt-seo-gate-d.timer` |
| Gate E (crawl + rank) | Weekly | cron gate-e |
| ClickHouse export | Daily 04:00 VN | `ptt-seo-clickhouse-export.timer` |

### 6.2. Kiểm tra timer trên VPS

```bash
systemctl list-timers | grep -E 'seo|ptt-seo'
journalctl -u ptt-seo-gsc-sync.service -n 50
journalctl -u ptt-seo-ga4-sync.service -n 50
tail -f /var/log/seo_aeo_cron_daily.log
```

### 6.3. Worker queue

Job types: `seo_gsc_sync`, `seo_ga4_sync`, `seo_freshness_scan`, `seo_report_schedules`, `seo_cms_publish`.

Nếu queue down: `PTT_JOBS_SYNC_FALLBACK=1` chạy inline khi user bấm Sync.

---

## 7. Client Portal SEO

**Bật khi:** `PTT_PORTAL_SEO_ENABLED=1` (sau UAT)

| Route portal | Chức năng |
|--------------|-----------|
| `/seo` | Dashboard KPI read-only |
| `/seo/reports` | Báo cáo executive |
| `/seo/content` | Duyệt content ở stage `client_review` |

**Deploy portal trên VPS:**

```bash
python3 scripts/seed_portal_seo_pilot_map.py --apply --client-id <UUID> --customer-id <CRM_ID>
sudo systemctl restart ptt-crm-api
cd services/portal-web && npm run build && pm2 restart portal-web
# Sau smoke: PTT_PORTAL_SEO_ENABLED=1 trong .env
```

**Rollback:** `PTT_PORTAL_SEO_ENABLED=0` — ẩn nav SEO; CRM approve vẫn hoạt động.

---

## 8. Xử lý sự cố thường gặp

| Triệu chứng | Nguyên nhân | Cách xử lý |
|-------------|-------------|------------|
| SEO menu không hiện | Thiếu quyền `crm_seo_aeo` | Admin → Phân quyền trang |
| GSC sync 0 rows | OAuth chưa kết nối / site sai | Technical → reconnect OAuth |
| GA4 revenue = 0 | Property chưa có revenue events | Bật e-commerce events GA4; sync lại |
| Attribution panel trống | Chưa sync GA4 organic | Sync GA4 → đợi cron daily |
| Publish CMS fail | Webhook URL/secret sai | Client settings → Test webhook |
| CWV panel trống | Chưa chạy Gate D cron | `curl .../cron/gate-d` hoặc bật timer |
| Rank capture stub | `PTT_SERP_PROVIDER=stub` | Set SerpAPI key + provider |
| Cron 401 | Sai `PTT_SEO_CRON_SECRET` | Đồng bộ secret .env + crontab |
| PG lỗi relation | Schema chưa apply | `./scripts/apply_seo_gate_e_schema.sh` |

**Log hữu ích:**

```bash
journalctl -u ptt -f
grep -i seo /var/www/ptt/logs/*.log
```

---

## 9. Checklist go-live

### Staging

- [ ] `SEO_AEO_DB=pg` + backfill verified
- [ ] GSC + GA4 OAuth pilot client OK
- [ ] Gate D timer active (CWV, Teams test)
- [ ] Gate E schema + CMS pilot (nếu dùng auto-publish)
- [ ] Cron daily/weekly chạy 7 ngày không lỗi
- [ ] S-12 attribution có data sau GA4 sync
- [ ] Grafana dashboard 1 pilot client

### Production

- [ ] Backup PG + SQLite trước cutover
- [ ] Tắt stub: `# PTT_GSC_SYNC_STUB=0`, `# PTT_GA4_SYNC_STUB=0`
- [ ] `PTT_SEO_GOVERNANCE_ENABLED=1`
- [ ] Portal/Experiments bật tuần tự sau soak
- [ ] Sign-off: [`runbooks/phase5-prod-signoff-checklist.md`](runbooks/phase5-prod-signoff-checklist.md)

---

## Phụ lục — Runbook chuyên sâu

| Chủ đề | File |
|--------|------|
| PG cutover + OAuth UAT | [`runbooks/seo-aeo-pg-oauth-uat-cutover.md`](runbooks/seo-aeo-pg-oauth-uat-cutover.md) |
| Cron VPS | [`runbooks/seo-aeo-cron.md`](runbooks/seo-aeo-cron.md) |
| Gate D BI/CWV | [`runbooks/seo-aeo-gate-d.md`](runbooks/seo-aeo-gate-d.md) |
| Gate E enterprise | [`runbooks/seo-aeo-gate-e.md`](runbooks/seo-aeo-gate-e.md) |
| ClickHouse + Grafana | [`runbooks/seo-aeo-clickhouse-bi.md`](runbooks/seo-aeo-clickhouse-bi.md) |
| CMS webhook | [`runbooks/seo-cms-webhook-pilot.md`](runbooks/seo-cms-webhook-pilot.md) |
| Gate C (SerpAPI, Temporal) | [`runbooks/seo-aeo-p3-gate-c.md`](runbooks/seo-aeo-p3-gate-c.md) |

---

*Cập nhật khi có thay đổi spec — liên hệ team platform để bổ sung module mới.*
