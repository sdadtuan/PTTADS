# Hướng dẫn vận hành PTT Agency trên VPS production

> **Phiên bản:** 1.2 · **Cập nhật:** 2026-07-18  
> **⚠️ Deploy greenfield / stack mới (Nest + ops-web, Flask retired):** dùng **[`vps-full-system-deploy.md`](./vps-full-system-deploy.md)** — tài liệu này giữ chi tiết phase cũ, một số mục Flask đã lỗi thời.  
> **Repo trên VPS:** `/var/www/ptt`  
> **Domain production (client-facing):** **`https://portal.pttads.vn`** — Portal Next.js + Nest API (`/api/v1`, `/health`) cùng origin qua Nginx  
> **Staff console:** **`https://ops.pttads.vn`** — ops-web `:3200` + Nest `/api/`  
> **Legacy rs:** **`https://rs.pttads.vn`** → redirect ops-web (sau Phase 5 cutover)

Tài liệu này là **runbook tổng hợp** để triển khai, cutover và vận hành hàng ngày trên VPS thật. Chi tiết từng phase xem các runbook con được liên kết ở cuối mục.

> **⚠️ Local vs VPS:** Cutover dry-run trên **máy dev** chạy trực tiếp `./scripts/close_phase3_prod_cutover.sh` — **không** set `PTT_VPS_HOST=127.0.0.1` (SSH vào localhost sẽ `connection refused`). Chỉ dùng `phase3_prod_cutover_vps.sh` khi `PTT_VPS_HOST` là **IP/domain VPS thật**.

---

## Mục lục

1. [Kiến trúc trên VPS](#1-kiến-trúc-trên-vps)
2. [Bản đồ URL & giao diện](#2-bản-đồ-url--giao-diện)
3. [Yêu cầu hạ tầng](#3-yêu-cầu-hạ-tầng)
4. [Cài đặt lần đầu](#4-cài-đặt-lần-đầu)
5. [Biến môi trường (.env)](#5-biến-môi-trường-env)
6. [Docker & dịch vụ nền](#6-docker--dịch-vụ-nền)
7. [Systemd — danh sách unit & timer](#7-systemd--danh-sách-unit--timer)
8. [Cutover theo phase](#8-cutover-theo-phase)
9. [Gate & kiểm tra sau deploy](#9-gate--kiểm-tra-sau-deploy)
10. [Vận hành hàng ngày](#10-vận-hành-hàng-ngày)
11. [Backup & khôi phục](#11-backup--khôi-phục)
12. [Rollback nhanh](#12-rollback-nhanh)
13. [Xử lý sự cố thường gặp](#13-xử-lý-sự-cố-thường-gặp)
14. [Runbook con & tài liệu liên quan](#14-runbook-con--tài-liệu-liên-quan)

---

## 1. Kiến trúc trên VPS

```mermaid
flowchart TB
    subgraph public [Internet — Client]
        CLIENT[Client Viewer / Approver]
    end
    subgraph nginx_portal [Nginx TLS portal.pttads.vn]
        NG_P["/ → Next :3100"]
        NG_A["/api/ /health → Nest :3000"]
    end
    subgraph nginx_internal [Nginx nội bộ — tuỳ chọn]
        NG_F[rs.pttads.vn → Flask :8002]
    end
    subgraph app [Application layer]
        FLASK[Flask Gunicorn ptt.service]
        NEST[Nest ptt-crm-api.service]
        PORTAL[Next.js ptt-portal-web.service]
        WORKER[Temporal worker ptt-temporal-worker.service]
    end
    subgraph docker [Docker Compose]
        PG[(PostgreSQL :5432)]
        TEMP[Temporal :7233]
        CH[(ClickHouse :8123)]
    end

    CLIENT --> nginx_portal
    NG_P --> PORTAL
    NG_A --> NEST
    PORTAL -->|same-origin /api/v1| NEST
    NG_F --> FLASK
    FLASK -->|read + proxy write| NEST
    NEST --> PG
    FLASK --> PG
    WORKER --> TEMP
    WORKER --> PG
    PG -.->|export T-1| CH
```

| URL công khai | Path | Backend nội bộ | Ghi chú |
|---------------|------|------------------|---------|
| `https://portal.pttads.vn/` | `/`, `/login`, `/dashboard`, `/meta`, `/creatives` | Next `:3100` | Client portal |
| `https://portal.pttads.vn/api/v1/*` | `/api/v1/...` | Nest `:3000` | Auth, performance, creatives |
| `https://portal.pttads.vn/health` | `/health` | Nest `:3000` | Health check |
| `https://rs.pttads.vn/` | Agency UI | Flask `:8002` | AM/Admin nội bộ |

**Port nội bộ (chỉ localhost):**

| Dịch vụ | Port | Unit / container |
|---------|------|------------------|
| Nest CRM API | `:3000` | `ptt-crm-api.service` |
| Client Portal | `:3100` | `ptt-portal-web.service` |
| Flask Agency | `:8002` | `ptt.service` |
| PostgreSQL | `:5432` | `ptt-postgres` |
| Temporal | `:7233` | `ptt-temporal` |
| ClickHouse | `:8123` | `ptt-clickhouse` |

---

## 2. Bản đồ URL & giao diện

### 2.1. Client Portal (`portal.pttads.vn`) — khách hàng / approver

| URL | Màn hình | API backend |
|-----|----------|-------------|
| `/login` | Đăng nhập pilot | `POST /api/v1/portal/auth/login` |
| `/dashboard` | Performance Meta + Google (T-7/T-30) | `GET /api/v1/performance` |
| `/meta` | **Meta Performance** — chỉ kênh Facebook/Instagram | `GET /api/v1/performance?channel=meta` |
| `/creatives` | Creative inbox — duyệt creative | `GET /api/v1/creatives/pending` |

**Nav portal:** Performance · Meta (Facebook) · Creative inbox

### 2.2. Agency CRM nội bộ (`rs.pttads.vn` → Flask) — AM / Media Buyer / CSKH

| URL | Màn hình | Ghi chú |
|-----|----------|---------|
| `/crm/agency` | Agency Ops — tổng quan vận hành | Client, ingest, SLA |
| **`/crm/facebook-ads`** | **Facebook Ads hub** — tổng hợp Meta cross-client | Token, CPL, map Hub, link nhanh |
| `/crm/agency/clients/{id}` | Chi tiết client | Tab: Kênh ads, Campaign CPL, Creative… |
| `/crm/leads` | Lead Facebook Lead Ads | Webhook, đồng bộ Page |
| `/crm/hub` | Hub · Meta Campaign ID | Map campaign Hub ↔ Meta |
| `/crm/service-delivery` | Workflow dịch vụ quảng cáo Facebook | Task theo tháng |

> Client **không** thấy Facebook Ads hub — chỉ báo cáo read-only trên portal (`/dashboard`, `/meta`).

### 2.3. Phân quyền Agency (sidebar)

| Section | Quyền (`admin_page_permissions`) | Persona |
|---------|-----------------------------------|---------|
| Facebook Ads hub | `crm_facebook_ads` (hoặc `crm_agency`) | AM, Media Buyer |
| Agency Ops | `crm_agency` | AM, DevOps |
| Quản lý Lead | `crm_leads` | CSKH |

---

## 3. Yêu cầu hạ tầng

### 3.1. Máy chủ

| Mục | Khuyến nghị |
|-----|-------------|
| OS | Ubuntu 22.04 LTS hoặc 24.04 LTS |
| RAM | ≥ 8 GB (Temporal + PG + ClickHouse) |
| Disk | ≥ 80 GB SSD |
| User deploy | `deploy` hoặc `ptt`, thuộc group `www-data` |
| Python | 3.11+ trên VPS (scrypt portal users; macOS dev 3.9 OK local only) |
| Node.js | 22 LTS (Nest + Portal build) |

### 3.2. DNS (bắt buộc cho client portal)

| Record | Trỏ tới | Bắt buộc |
|--------|---------|----------|
| **`portal.pttads.vn`** | VPS IP | **Có** — Portal + API công khai |
| **`rs.pttads.vn`** | VPS IP | **Có** — Agency CRM nội bộ (AM/Admin) |

> **Không cần** subdomain `api.pttads.vn` khi dùng same-origin: Nest được proxy tại `https://portal.pttads.vn/api/`.

**Verify DNS trước cutover:**

```bash
dig +short portal.pttads.vn A
curl -sfI https://portal.pttads.vn/login
curl -sf https://portal.pttads.vn/health
```

### 3.3. Firewall

| Port | Mở ra ngoài | Ghi chú |
|------|-------------|---------|
| 80, 443 | Có | Nginx |
| 5432, 7233, 8123, 3000, 3100, 8002 | **Không** | Chỉ localhost |
| 8088 (Temporal UI) | VPN/admin only | Không public |

### 3.4. Bảng thông tin host (điền trước go-live)

| Mục | Giá trị |
|-----|---------|
| VPS IP / hostname | `________________` |
| SSH user | `deploy` |
| Change window (ICT) | `YYYY-MM-DD HH:MM – HH:MM` |
| Operator on-call | `________________` |
| Pilot client UUID (≥3) | `________________` |

---

## 4. Cài đặt lần đầu

> Thực hiện **một lần** khi VPS mới hoặc rebuild. Các lần deploy sau chỉ `git pull` + build + restart.

### 4.1. Clone repo & Python venv

```bash
sudo mkdir -p /var/www/ptt
sudo chown deploy:www-data /var/www/ptt

sudo -u deploy git clone <REPO_URL> /var/www/ptt
cd /var/www/ptt

python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-temporal.txt   # Temporal worker
```

### 4.2. Nest CRM API

```bash
cd /var/www/ptt/services/ptt-crm-api
npm ci
npm run build

sudo cp /var/www/ptt/deploy/ptt-crm-api.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable ptt-crm-api
# Chưa start — cần .env trước (mục 4)
```

### 4.3. Client Portal (build standalone)

```bash
cd /var/www/ptt/services/portal-web
npm ci
export NEXT_PUBLIC_PTT_API_URL=https://portal.pttads.vn
npm run build
cp -r .next/static .next/standalone/.next/static
cp -r public .next/standalone/public 2>/dev/null || true

sudo cp /var/www/ptt/deploy/ptt-portal-web.service /etc/systemd/system/
```

### 4.4. Flask (Gunicorn)

```bash
sudo cp /var/www/ptt/ptt.service /etc/systemd/system/
# Sửa User/WorkingDirectory nếu khác deploy
sudo systemctl daemon-reload
sudo systemctl enable ptt
```

### 4.5. Nginx — portal.pttads.vn (Portal + API)

File mẫu: `deploy/nginx-portal.conf` — một server block cho cả Portal và Nest:

| Location | Proxy tới |
|----------|-----------|
| `/` | Next.js `127.0.0.1:3100` |
| `/api/` | Nest `127.0.0.1:3000` |
| `/health` | Nest `127.0.0.1:3000/health` |

```bash
sudo cp /var/www/ptt/deploy/nginx-portal.conf /etc/nginx/sites-available/portal.pttads.vn
sudo ln -sf /etc/nginx/sites-available/portal.pttads.vn /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

**Agency Flask (`rs.pttads.vn`):**

```bash
sudo cp /var/www/ptt/deploy/nginx-agency.conf /etc/nginx/sites-available/rs.pttads.vn
sudo ln -sf /etc/nginx/sites-available/rs.pttads.vn /etc/nginx/sites-enabled/
# Lần đầu: dùng HTTP-only (comment block ssl) → certbot → copy lại file đầy đủ
sudo certbot --nginx -d rs.pttads.vn
sudo nginx -t && sudo systemctl reload nginx
```

### 4.6. TLS (Let's Encrypt) — portal.pttads.vn

```bash
sudo apt-get install -y certbot python3-certbot-nginx

# Chỉ cần cert cho portal (API đi chung domain)
sudo CERTBOT_EMAIL=ops@pttads.vn /var/www/ptt/scripts/certbot_portal_vps.sh

# Hoặc thủ công:
sudo certbot --nginx -d portal.pttads.vn
sudo nginx -t && sudo systemctl reload nginx
```

Verify:

```bash
curl -sfI https://portal.pttads.vn/login
curl -sf https://portal.pttads.vn/health
curl -sf https://portal.pttads.vn/api/v1/performance -H 'Authorization: Bearer ...'  # sau login
```

### 4.7. File `.env` master

```bash
cp /var/www/ptt/.env.example /var/www/ptt/.env
sudo chmod 600 /var/www/ptt/.env
sudo chown deploy:www-data /var/www/ptt/.env
nano /var/www/ptt/.env   # điền secrets — xem mục 5
```

### 4.8. Khởi động stack lần đầu

```bash
cd /var/www/ptt
docker compose up -d postgres redis rabbitmq
docker compose -f docker-compose.temporal.yml up -d
docker compose -f docker-compose.clickhouse.yml up -d   # Phase 4

# DDL (theo thứ tự)
./scripts/apply_pg_ddl_v3.sh
./scripts/apply_pg_ddl_v3_events_idempotency.sh
./scripts/apply_pg_ddl_v3_creatives.sh
./scripts/apply_pg_ddl_v3_launch_qa.sh
./scripts/apply_pg_ddl_v3_google_sync.sh
./scripts/apply_pg_ddl_v4_hub_sop.sh
./scripts/apply_pg_ddl_v5_campaign_writes.sh
./scripts/clickhouse_init.sh

# Systemd
sudo ./scripts/install_phase2_systemd_timers.sh
sudo ./scripts/install_phase3_systemd.sh

sudo systemctl start ptt-crm-api ptt ptt-temporal-worker
# Portal sau Phase 3 cutover:
# sudo systemctl start ptt-portal-web
```

---

## 5. Biến môi trường (.env)

File chính: **`/var/www/ptt/.env`** — Nest, Flask, Portal, worker đều đọc qua `EnvironmentFile`.

### 5.1. Core (bắt buộc mọi phase)

```bash
DATABASE_URL=postgresql://ptt:STRONG_PASSWORD@127.0.0.1:5432/ptt_agency
PTT_SQLITE_PATH=/var/www/ptt/ptt.db
FLASK_SECRET_KEY=<random>
PTT_CRM_INTERNAL_KEY=<random-s2s-key>    # Flask → Nest, cron nội bộ
```

### 5.2. Phase 2 — Leads OLTP + Meta closed-loop

```bash
PTT_LEADS_READ_SOURCE=pg
PTT_LEADS_WRITE_ENABLED=1               # Nest write prod
PTT_LEAD_SHADOW_SYNC=1                  # tắt sau soak 30 ngày (mục 7.4)
PTT_META_INSIGHTS_SYNC=1
PTT_META_TOKEN_REFRESH=1
PTT_TOKEN_VAULT_KEY=<base64-32-bytes>
PTT_WRITE_SOAK_LOG=/var/www/ptt/.local-dev/write-soak-evidence.jsonl
SENTRY_DSN=https://...@sentry.io/...
SENTRY_ENVIRONMENT=production
```

Tham chiếu: `deploy/env.staging-phase2-gates.example`

### 5.3. Phase 3 — portal.pttads.vn (Portal + API same-origin)

```bash
# Portal gọi API cùng domain — không cần api.pttads.vn
NEXT_PUBLIC_PTT_API_URL=https://portal.pttads.vn
PORTAL_PORT=3100
PTT_PORTAL_JWT_SECRET=<random-32+-chars>
PTT_PORTAL_ALLOW_STUB=0
PTT_PORTAL_STUB_USERS=
PTT_PORTAL_CORS_ORIGINS=https://portal.pttads.vn

PTT_TEMPORAL_ADDRESS=127.0.0.1:7233
PTT_TEMPORAL_NAMESPACE=default
PTT_TEMPORAL_TASK_QUEUE=ptt-agency

PTT_HUB_READ_SOURCE=1
PTT_SOP_READ_SOURCE=1
# PTT_HUB_PG_PRIMARY=1                  # sau soak staging 7 ngày

PTT_GOOGLE_INSIGHTS_SYNC=1              # optional pilot
```

Tham chiếu: `deploy/env.phase3-prod.example`

### 5.4. Phase 4 — Flask readonly + Meta write + ClickHouse

```bash
PTT_FLASK_MONOLITH_MODE=readonly        # active | readonly | retired
PTT_META_CAMPAIGN_WRITE_STUB=0          # prod pilot: 0
PTT_META_CAMPAIGN_WRITE_PILOT=1
PTT_META_CAMPAIGN_WRITE_PILOT_CLIENTS=<uuid>
PTT_META_CAMPAIGN_WRITE_PILOT_CAMPAIGNS=<meta-campaign-id>

CLICKHOUSE_URL=http://127.0.0.1:8123
CLICKHOUSE_USER=ptt
CLICKHOUSE_PASSWORD=<strong>
```

Tham chiếu: `deploy/env.phase4-prod.example`, `deploy/env.meta-campaign-write-pilot.example`

### 5.5. Temporal worker env riêng (tuỳ chọn)

File `/etc/ptt/temporal.env` (unit `ptt-temporal-worker.service`):

```bash
DATABASE_URL=postgresql://ptt:***@127.0.0.1:5432/ptt_agency
PTT_TEMPORAL_ADDRESS=127.0.0.1:7233
PTT_TEMPORAL_NAMESPACE=default
PTT_TEMPORAL_TASK_QUEUE=ptt-agency
PTT_META_CAMPAIGN_WRITE_STUB=0
```

---

## 6. Docker & dịch vụ nền

### 6.1. Lệnh thường dùng

```bash
cd /var/www/ptt

# Postgres + Redis + RabbitMQ
docker compose up -d
docker compose ps

# Temporal (Phase 3+)
docker compose -f docker-compose.temporal.yml up -d
docker logs ptt-temporal --tail 50

# ClickHouse (Phase 4)
docker compose -f docker-compose.clickhouse.yml up -d
docker logs ptt-clickhouse --tail 30
```

### 6.2. Kiểm tra Postgres

```bash
docker exec -it ptt-postgres psql -U ptt -d ptt_agency -c '\dt'
docker exec ptt-postgres pg_isready -U ptt -d ptt_agency
```

### 6.3. Temporal UI (admin only)

```bash
# Chỉ truy cập qua SSH tunnel — không mở public
ssh -L 8088:127.0.0.1:8088 deploy@YOUR_VPS_IP
# Mở http://127.0.0.1:8088
```

---

## 7. Systemd — danh sách unit & timer

### 7.1. Service chính (luôn chạy)

| Unit | Mô tả | Restart |
|------|-------|---------|
| `ptt.service` | Flask Gunicorn `:8002` | `sudo systemctl restart ptt` |
| `ptt-crm-api.service` | Nest `:3000` | `sudo systemctl restart ptt-crm-api` |
| `ptt-portal-web.service` | Portal `:3100` | `sudo systemctl restart ptt-portal-web` |
| `ptt-temporal-worker.service` | Python Temporal worker | `sudo systemctl restart ptt-temporal-worker` |

### 7.2. Timer Phase 2

Cài: `sudo ./scripts/install_phase2_systemd_timers.sh`

| Timer | Lịch (ICT) | Chức năng |
|-------|------------|----------|
| `ptt-lead-shadow-sync.timer` | mỗi phút | PG → SQLite shadow |
| `ptt-meta-insights.timer` | 02:00 | Meta → `daily_performance` |
| `ptt-meta-token-refresh.timer` | hàng ngày | Refresh Meta token |
| `ptt-write-soak.timer` | hourly | Ghi evidence dual-run |

```bash
systemctl list-timers --no-pager 'ptt-*'
journalctl -u ptt-meta-insights.service -n 30 --no-pager
```

### 7.3. Timer Phase 3–4

Cài Phase 3: `sudo ./scripts/install_phase3_systemd.sh`  
Cài Phase 4 ClickHouse: `close_phase4_prod_cutover.sh` (APPLY=1)

| Timer | Lịch (ICT) | Chức năng |
|-------|------------|----------|
| `ptt-google-insights.timer` | 02:30 | Google → `daily_performance` |
| `ptt-seo-gsc-sync.timer` | 03:00 | GSC OAuth → `seo_aeo.seo_gsc_daily_stats` |
| `ptt-seo-ga4-sync.timer` | 03:30 | GA4 OAuth → `seo_aeo.seo_ga4_daily_stats` |
| `ptt-seo-freshness-scan.timer` | CN 04:00 | Content decay → `refresh_required` |
| `ptt-seo-gate-d.timer` | CN 06:00 | Gate D: CWV + AEO schedule + crawl reminders |
| `ptt-seo-serp-capture.timer` | CN 05:00 | SERP scheduled capture (Gate B) |
| `ptt-seo-clickhouse-export.timer` | 04:00 | SEO facts → ClickHouse |
| `ptt-backup.timer` | (xem unit) | Backup PG + SQLite |

**SEO GSC sync** — cần `.env`: `SEO_AEO_DB=pg`, `DATABASE_URL`, `PTT_GSC_OAUTH_*`, `PTT_GSC_SYNC_ENABLED=1`. Dev stub: `PTT_GSC_SYNC_STUB=1`.

**SEO GA4 sync** — cần `.env`: `SEO_AEO_DB=pg`, `DATABASE_URL`, `PTT_GA4_OAUTH_*` (hoặc dùng chung `PTT_GSC_OAUTH_*`), `PTT_GA4_SYNC_ENABLED=1`. Dev stub: `PTT_GA4_SYNC_STUB=1`. Redirect URI riêng: `/api/v1/seo/ga4/oauth/callback`.

**SEO Freshness scan** — `PTT_FRESHNESS_SCAN_ENABLED=1`, threshold mặc định decay ≥60 → `refresh_required`. Cần GSC/GA4 stats + content `published`/`monitoring`.

```bash
sudo systemctl start ptt-seo-gsc-sync.service
sudo systemctl start ptt-seo-ga4-sync.service
sudo systemctl start ptt-seo-freshness-scan.service
journalctl -u ptt-seo-freshness-scan.service -n 30 --no-pager
```

---

## 8. Cutover theo phase

> **Nguyên tắc:** Luôn **dry-run** (`APPLY=0`) trước, backup trước change window, có người on-call.

### 8.0. Thứ tự cutover khuyến nghị

```
Phase 2 (Leads write PG)     →  soak ≥30 ngày
Phase 3 (Portal + Temporal)  →  soak ≥7 ngày
SEO/AEO PG + GSC/GA4 OAuth   →  sau Phase 3 soak (xem §8.6)
Phase 4 (Flask readonly)     →  soak readonly ≥14 ngày
Lead shadow off              →  sau Phase 2 soak
Hub PG primary               →  sau Phase 3 soak 7 ngày
```

### 8.1. Backup trước mọi cutover

```bash
cd /var/www/ptt
./scripts/backup_ptt_data.sh
ls -lh /var/backups/ptt/
```

---

### 8.2. Phase 2 — Leads write cutover

Chi tiết: [`vps-phase2-production-cutover-checklist.md`](./vps-phase2-production-cutover-checklist.md)

```bash
cd /var/www/ptt
export DATABASE_URL=postgresql://ptt:***@127.0.0.1:5432/ptt_agency

# Staging gate
./scripts/staging_phase2_gate_pack.sh

# Cutover (theo runbook Phase 2 §4–§8)
# Sau cutover:
sudo systemctl restart ptt ptt-crm-api
sudo systemctl enable --now ptt-lead-shadow-sync.timer ptt-write-soak.timer
```

---

### 8.3. Phase 3 — Portal + Temporal + Hub PG

#### Cách A — Từ máy dev qua SSH

```bash
# Trên máy local (repo PTTADS)
export PTT_VPS_HOST=YOUR_VPS_IP
export PTT_VPS_USER=deploy
export PORTAL_PILOT_PASSWORD='your-strong-password'

# Dry-run
APPLY=0 ./scripts/phase3_prod_cutover_vps.sh

# Apply thật
APPLY=1 ./scripts/phase3_prod_cutover_vps.sh
```

#### Cách C — Dry-run trên máy dev (không SSH)

> Dùng khi kiểm tra script cutover **trước** khi chạy trên VPS. **Không** set `PTT_VPS_HOST=127.0.0.1`.

```bash
cd /path/to/PTTADS
source .venv/bin/activate   # nếu có

export APPLY=0
export PTT_CUTOVER_ENV=local          # bỏ qua prod-only JWT check
export PTT_CUTOVER_SKIP_URL_CHECK=1   # không gọi portal.pttads.vn từ local
export PTT_SQLITE_PATH=$PWD/ptt.db
export PTT_PORTAL_JWT_SECRET='local-cutover-dry-run-jwt-secret-32chars-min!!'
export PORTAL_PILOT_PASSWORD='local-cutover-pilot-demo123!'
export PTT_PILOT_SEED_ALLOW_PLAIN=1   # chỉ local — prod dùng scrypt Python 3.11+

./scripts/close_phase3_prod_cutover.sh
```

Phase 4 tương tự:

```bash
export APPLY=0 PTT_CUTOVER_ENV=local PTT_CUTOVER_SKIP_URL_CHECK=1
export PTT_SQLITE_PATH=$PWD/ptt.db
./scripts/close_phase4_prod_cutover.sh
```

**Gate pack đầy đủ (local CI):**

```bash
# Phase 3 QA + Playwright + Phase 4 gates + cutover dry-run
SKIP_CUTOVER=0 ./scripts/run_phase_closure.sh
# Bỏ cutover: SKIP_CUTOVER=1 ./scripts/run_phase_closure.sh
```

---

#### Cách B — Trực tiếp trên VPS

```bash
ssh deploy@YOUR_VPS_IP
cd /var/www/ptt
source .env   # hoặc export thủ công

export DATABASE_URL=postgresql://ptt:***@127.0.0.1:5432/ptt_agency
export PTT_PORTAL_JWT_SECRET='...'
export PORTAL_PILOT_PASSWORD='...'
export PTT_SQLITE_PATH=/var/www/ptt/ptt.db

# Dry-run
APPLY=0 ./scripts/close_phase3_prod_cutover.sh

# Apply (cần sudo — certbot + systemd)
sudo -E APPLY=1 PORTAL_PILOT_PASSWORD="$PORTAL_PILOT_PASSWORD" \
  ./scripts/close_phase3_prod_cutover.sh
```

Script Phase 3 thực hiện:

1. Preflight → `.local-dev/phase3-prod-cutover-preflight.json`
2. DDL v3/v4 + migrate Hub/SOP SQLite → PG
3. Seed portal pilot users (scrypt — **Python 3.11+ trên VPS**)
4. Build portal standalone
5. Docker Temporal up
6. `install_phase3_systemd.sh` + certbot portal + restart services

**Smoke sau Phase 3:**

```bash
curl -sf https://portal.pttads.vn/health
curl -sfI https://portal.pttads.vn/login
journalctl -u ptt-temporal-worker -n 20 --no-pager
journalctl -u ptt-portal-web -n 20 --no-pager

# Playwright từ máy local
PORTAL_E2E_URL=https://portal.pttads.vn \
PORTAL_E2E_API_URL=https://portal.pttads.vn \
PORTAL_E2E_APPROVER_EMAIL=approver.pilot1@pttads.vn \
PORTAL_E2E_APPROVER_PASSWORD='<pilot-password>' \
./scripts/phase3_playwright_e2e_gate.sh
```

Chi tiết: [`vps-phase3-portal-cutover-checklist.md`](./vps-phase3-portal-cutover-checklist.md)

---

### 8.4. Lead shadow sunset (sau soak Phase 2 ≥30 ngày)

Chi tiết: [`lead-shadow-sunset.md`](./lead-shadow-sunset.md)

```bash
# 1. Tắt timer
sudo systemctl stop ptt-lead-shadow-sync.timer
sudo systemctl disable ptt-lead-shadow-sync.timer

# 2. .env
PTT_LEAD_SHADOW_SYNC=0

# 3. Restart
sudo systemctl restart ptt ptt-lead-shadow-sync.service
```

---

### 8.5. Hub PG primary (sau soak staging 7 ngày)

Chi tiết: [`hub-pg-migration.md`](./hub-pg-migration.md)

```bash
# /var/www/ptt/.env
PTT_HUB_READ_SOURCE=1
PTT_SOP_READ_SOURCE=1
PTT_HUB_PG_PRIMARY=1

sudo systemctl restart ptt
python3 scripts/migrate_sqlite_hub_sop_to_pg.py   # idempotent backfill
```

---

### 8.6. Phase 4 — Flask readonly + ClickHouse + Meta pilot

#### Cách A — SSH từ local

```bash
export PTT_VPS_HOST=YOUR_VPS_IP
export PTT_META_CAMPAIGN_WRITE_PILOT_CLIENTS=550e8400-e29b-41d4-a716-446655440000
export PTT_META_CAMPAIGN_WRITE_PILOT_CAMPAIGNS=120210123456789

APPLY=0 ./scripts/phase4_prod_cutover_vps.sh   # dry-run

APPLY=1 \
PTT_FLASK_MONOLITH_MODE=readonly \
PTT_META_CAMPAIGN_WRITE_STUB=0 \
./scripts/phase4_prod_cutover_vps.sh
```

#### Cách B — Trên VPS

```bash
cd /var/www/ptt
export DATABASE_URL=postgresql://ptt:***@127.0.0.1:5432/ptt_agency
export PTT_META_CAMPAIGN_WRITE_PILOT_CLIENTS=<uuid>
export PTT_META_CAMPAIGN_WRITE_PILOT_CAMPAIGNS=<meta-campaign-id>

APPLY=0 ./scripts/close_phase4_prod_cutover.sh

sudo -E APPLY=1 \
  PTT_FLASK_MONOLITH_MODE=readonly \
  PTT_META_CAMPAIGN_WRITE_STUB=0 \
  PTT_META_CAMPAIGN_WRITE_PILOT=1 \
  PTT_META_CAMPAIGN_WRITE_PILOT_CLIENTS="$PTT_META_CAMPAIGN_WRITE_PILOT_CLIENTS" \
  PTT_META_CAMPAIGN_WRITE_PILOT_CAMPAIGNS="$PTT_META_CAMPAIGN_WRITE_PILOT_CAMPAIGNS" \
  ./scripts/close_phase4_prod_cutover.sh
```

**Smoke sau Phase 4:**

```bash
# Flask readonly — POST client bị chặn
curl -s -X POST http://127.0.0.1:8002/api/v1/clients \
  -H 'Content-Type: application/json' -d '{}' | jq .
# → error: flask_monolith_readonly, HTTP 503

# Nest proxy campaign writes vẫn hoạt động
curl -sf http://127.0.0.1:8002/api/v1/clients/<uuid>/campaign-writes

# Meta pilot (1 campaign thật — cần token active)
source deploy/env.meta-campaign-write-pilot.example
./scripts/meta_campaign_write_pilot_smoke.sh

# ClickHouse
./scripts/export_domain_events_clickhouse.sh
curl -s 'http://ptt:PASSWORD@127.0.0.1:8123/?query=SELECT+count()+FROM+ptt.domain_events'
```

Chi tiết: [`phase4-prod-cutover-checklist.md`](./phase4-prod-cutover-checklist.md)

---

### 8.7. SEO/AEO — PostgreSQL cutover + GSC/GA4 OAuth UAT

Chi tiết đầy đủ: [`seo-aeo-pg-oauth-uat-cutover.md`](./seo-aeo-pg-oauth-uat-cutover.md)

```bash
cd /var/www/ptt
export DATABASE_URL=postgresql://ptt:***@127.0.0.1:5432/ptt_agency
export PILOT_CUSTOMER_ID=<seo-pilot-customer-id>

# Dry-run backfill + verify
APPLY=0 ./scripts/seo_aeo_prod_cutover.sh

# Pre-flight env + PG schema
python3 scripts/verify_seo_aeo_oauth_uat.py --customer-id "$PILOT_CUSTOMER_ID"

# Cutover thật
sudo -E APPLY=1 PILOT_CUSTOMER_ID="$PILOT_CUSTOMER_ID" ./scripts/seo_aeo_prod_cutover.sh
```

**UAT OAuth (browser):** Technical Console → Kết nối Google (GSC + GA4) → Sync OAuth → verify `seo_gsc_daily_stats` / `seo_ga4_daily_stats`.

**Smoke timers:**

```bash
sudo systemctl start ptt-seo-gsc-sync.service ptt-seo-ga4-sync.service
journalctl -u ptt-seo-gsc-sync.service -n 30 --no-pager
```

**Rollback:** `SEO_AEO_DB=sqlite` trong `.env` + `sudo systemctl restart ptt`.

---

### 8.8. SEO/AEO Phase 5 — Governance, Portal SEO, Experiments

Chi tiết: [`seo-aeo-pg-oauth-uat-cutover.md`](./seo-aeo-pg-oauth-uat-cutover.md) §10

```bash
cd /var/www/ptt
export DATABASE_URL=postgresql://ptt:***@127.0.0.1:5432/ptt_agency
export SEO_AEO_DB=pg

# Gate trước cutover
./scripts/phase5_prod_cutover_gate.sh

# Staged flags (governance → portal → experiments)
APPLY=1 PHASE5_ENABLE_GOVERNANCE=1 sudo -E ./scripts/close_phase5_prod_cutover.sh

# Soak hàng ngày ≥7 ngày
./scripts/phase5_soak_record.sh
```

**Env template:** `deploy/env.phase5-prod.example`

**Sign-off checklist:** [`phase5-prod-signoff-checklist.md`](./phase5-prod-signoff-checklist.md)

**Rollback:** tắt từng flag (`PTT_SEO_GOVERNANCE_ENABLED=0`, `PTT_PORTAL_SEO_ENABLED=0`, `PTT_SEO_EXPERIMENTS_ENABLED=0`) + restart services.

---

## 9. Gate & kiểm tra sau deploy

Chạy trên VPS (hoặc staging mirror) sau mỗi deploy lớn:

| Gate | Lệnh | Artifact |
|------|------|----------|
| Phase 2 ops | `./scripts/close_phase2_prod_pending.sh` | `.local-dev/phase2-uat-signoff.json` |
| Phase 3 QA (6 gate) | `./scripts/phase3_qa_gate.sh` | `.local-dev/phase3-qa-gate-report.json` |
| Phase 3 portal MVP | `./scripts/phase3_portal_mvp_gate.sh` | cập nhật QA report |
| Phase 3 E2E (4 test) | `./scripts/phase3_playwright_e2e_gate.sh` | cập nhật sign-off |
| Phase 4 (7 gate) | `./scripts/phase4_gate.sh` | `.local-dev/phase4-gate-report.json` |
| **Phase 5 SEO/AEO** | `./scripts/phase5_prod_cutover_gate.sh` | `.local-dev/phase5-gate-report.json` |
| **Closure pack** | `SKIP_CUTOVER=0 ./scripts/run_phase_closure.sh` | `.local-dev/phase-closure-run.log` |

**Checklist sign-off thủ công:** [`phase5-prod-signoff-checklist.md`](./phase5-prod-signoff-checklist.md)

**Gate mới (Meta / Facebook Ads):**

| Gate ID | Kiểm tra |
|---------|----------|
| P3-G06 | `GET /api/v1/performance?channel=meta` — Portal tab `/meta` |
| P3-QA06 | Cross-tenant 403 trên API portal |
| Regression | `tests/test_facebook_ads_hub.py` — CRM hub `/crm/facebook-ads` |

**Checklist sign-off thủ công:** [`phase3-uat-signoff.md`](./phase3-uat-signoff.md)

Các mục prod vẫn cần xác nhận tay trước go-live: TLS portal, pilot users scrypt, creative approve E2E prod, Temporal worker 48h, Google OAuth pilot, Hub PG soak 7 ngày, lead shadow off.

---

## 10. Vận hành hàng ngày

### 10.1. Health check buổi sáng (5 phút)

```bash
cd /var/www/ptt

# HTTP
curl -sf https://portal.pttads.vn/health
curl -sfI https://portal.pttads.vn/login
# Agency nội bộ:
curl -sfI https://rs.pttads.vn/admin

# Systemd
systemctl is-active ptt ptt-crm-api ptt-portal-web ptt-temporal-worker

# Timer 24h
systemctl list-timers --no-pager 'ptt-*' | head -20

# Docker
docker ps --format 'table {{.Names}}\t{{.Status}}' | grep ptt
```

### 10.2. Log thường xem

```bash
# Flask
journalctl -u ptt -f --since "1 hour ago"

# Nest
journalctl -u ptt-crm-api -n 100 --no-pager

# Portal
journalctl -u ptt-portal-web -n 50 --no-pager

# Temporal worker
journalctl -u ptt-temporal-worker -n 100 --no-pager

# Meta sync (timer oneshot)
journalctl -u ptt-meta-insights.service -n 30 --no-pager

# ClickHouse export
journalctl -u ptt-clickhouse-export.service -n 30 --no-pager
```

### 10.3. Deploy code mới (không cutover)

```bash
cd /var/www/ptt
./scripts/backup_ptt_data.sh

git pull origin main
source .venv/bin/activate
pip install -r requirements.txt

# Nest
cd services/ptt-crm-api && npm ci && npm run build
sudo systemctl restart ptt-crm-api

# Portal (nếu có thay đổi FE)
cd /var/www/ptt/services/portal-web
npm ci && NEXT_PUBLIC_PTT_API_URL=https://portal.pttads.vn npm run build
cp -r .next/static .next/standalone/.next/static
sudo systemctl restart ptt-portal-web

# Flask
sudo systemctl restart ptt
sudo systemctl restart ptt-temporal-worker
```

### 10.4. Seed / bảo trì dữ liệu

| Tác vụ | Lệnh |
|--------|------|
| Hub map sync | `./scripts/sync_hub_campaign_map.sh` |
| Hub/SOP → PG | `python3 scripts/migrate_sqlite_hub_sop_to_pg.py` |
| Portal pilot users | `python3 scripts/seed_portal_pilot_users.py --password '...'` |
| Meta insights manual | `./scripts/sync_meta_insights.sh` |
| Google insights manual | `./scripts/sync_google_insights.sh` |

---

## 11. Backup & khôi phục

### 11.1. Backup thủ công

```bash
cd /var/www/ptt
./scripts/backup_ptt_data.sh
# Output: /var/backups/ptt/ptt_agency-YYYYMMDD-HHMM.dump
#         /var/backups/ptt/ptt-YYYYMMDD-HHMM.db
```

Timer: `sudo cp deploy/ptt-backup.{service,timer} /etc/systemd/system/` + enable.

### 11.2. Khôi phục PostgreSQL

```bash
pg_restore -d ptt_agency --clean --if-exists /var/backups/ptt/ptt_agency-YYYYMMDD-HHMM.dump
# Hoặc qua docker:
docker exec -i ptt-postgres pg_restore -U ptt -d ptt_agency --clean --if-exists \
  < /var/backups/ptt/ptt_agency-YYYYMMDD-HHMM.dump
```

### 11.3. Khôi phục SQLite

```bash
cp /var/backups/ptt/ptt-YYYYMMDD-HHMM.db /var/www/ptt/ptt.db
sudo systemctl restart ptt
```

> PG là source of truth cho leads/portal sau Phase 2 cutover. SQLite chủ yếu legacy Hub/SOP.

---

## 12. Rollback nhanh

| Thành phần | Rollback | SLA mục tiêu |
|------------|----------|--------------|
| Phase 4 Flask readonly | `PTT_FLASK_MONOLITH_MODE=active` → `sudo systemctl restart ptt` | ≤ 5 phút |
| Meta campaign write | `PTT_META_CAMPAIGN_WRITE_STUB=1` hoặc `PTT_META_CAMPAIGN_WRITE_PILOT=0` | ≤ 5 phút |
| Portal | `sudo systemctl stop ptt-portal-web` + gỡ nginx portal site | ≤ 10 phút |
| Hub PG read | `PTT_HUB_READ_SOURCE=0` `PTT_SOP_READ_SOURCE=0` → restart `ptt` | ≤ 5 phút |
| Lead shadow | `PTT_LEAD_SHADOW_SYNC=1` + enable timer + `./scripts/sync_lead_shadow.sh` | ≤ 15 phút |
| Nest write | `PTT_LEADS_WRITE_ENABLED=0` + revert nginx upstream flask | Xem Phase 2 runbook |
| ClickHouse | `sudo systemctl disable --now ptt-clickhouse-export.timer` | PG không bị ảnh hưởng |

**Phase 2 rollback chi tiết:** [`cutover-leads-write-phase2.md`](./cutover-leads-write-phase2.md) § Rollback

---

## 13. Xử lý sự cố thường gặp

### SSH `connection refused` (127.0.0.1:22)

- **Nguyên nhân:** `PTT_VPS_HOST=127.0.0.1` — macOS/local không có SSH server.
- **Cách xử lý:** Dry-run local dùng `./scripts/close_phase3_prod_cutover.sh` trực tiếp (mục 8.3 Cách C). Chỉ dùng `phase3_prod_cutover_vps.sh` khi `PTT_VPS_HOST` là IP/domain VPS thật.

### Portal login 401

1. Kiểm tra `PTT_PORTAL_JWT_SECRET` giống nhau trên Nest và `.env`
2. User có trong `portal_client_users` (không dùng stub prod):
   ```sql
   SELECT email, role, active FROM portal_client_users WHERE email LIKE '%pilot%';
   ```
3. `NEXT_PUBLIC_PTT_API_URL=https://portal.pttads.vn` (build portal phải trùng domain trình duyệt)
4. Nginx `/api/` proxy tới Nest `:3000` — test: `curl -sf https://portal.pttads.vn/health`

### Temporal workflow stuck

```bash
journalctl -u ptt-temporal-worker -n 200 --no-pager
docker logs ptt-temporal --tail 50
# SSH tunnel UI :8088 — xem workflow history
```

Chi tiết: [`temporal-workflow-admin.md`](./temporal-workflow-admin.md)

### Meta insights không sync

```bash
journalctl -u ptt-meta-insights.service -n 50 --no-pager
# Token hết hạn → meta-token-refresh runbook
```

Chi tiết: [`meta-token-refresh.md`](./meta-token-refresh.md), [`meta-insights-replay.md`](./meta-insights-replay.md)

### Campaign write `execution_failed`

```sql
SELECT id, status, execution_error, external_campaign_id
FROM campaign_write_requests ORDER BY created_at DESC LIMIT 5;
```

- Kiểm tra pilot lists trong `.env`
- Token Meta trên `client_channel_accounts`
- `PTT_META_CAMPAIGN_WRITE_STUB=0` chỉ khi token thật

### ClickHouse export fail

```bash
journalctl -u ptt-clickhouse-export.service -n 50 --no-pager
docker ps | grep clickhouse
./scripts/clickhouse_export_e2e.sh   # test full pipeline
```

### Flask 503 trên mọi POST (Phase 4 expected)

`PTT_FLASK_MONOLITH_MODE=readonly` — AM phải dùng Nest proxy (`/api/v1/clients/.../campaign-writes`). Nếu không mong muốn → rollback mục 12.

---

## 14. Runbook con & tài liệu liên quan

| Phase | Runbook |
|-------|---------|
| Phase 2 cutover | [`vps-phase2-production-cutover-checklist.md`](./vps-phase2-production-cutover-checklist.md) |
| Phase 2 write | [`cutover-leads-write-phase2.md`](./cutover-leads-write-phase2.md) |
| Phase 3 portal | [`vps-phase3-portal-cutover-checklist.md`](./vps-phase3-portal-cutover-checklist.md) |
| Phase 3 deploy | [`deploy-client-portal.md`](./deploy-client-portal.md) |
| Phase 3 UAT | [`phase3-uat-signoff.md`](./phase3-uat-signoff.md) |
| Hub PG | [`hub-pg-migration.md`](./hub-pg-migration.md) |
| Lead shadow | [`lead-shadow-sunset.md`](./lead-shadow-sunset.md) |
| Phase 4 kickoff | [`phase4-kickoff.md`](./phase4-kickoff.md) |
| Phase 4 cutover | [`phase4-prod-cutover-checklist.md`](./phase4-prod-cutover-checklist.md) |
| Temporal admin | [`temporal-workflow-admin.md`](./temporal-workflow-admin.md) |
| Sentry | [`sentry-phase2-dashboards.md`](./sentry-phase2-dashboards.md) |

**Env templates:**

| File | Mục đích |
|------|----------|
| `deploy/env.phase3-prod.example` | Portal + Temporal + Hub PG |
| `deploy/env.phase4-prod.example` | Flask readonly + ClickHouse + Meta pilot |
| `deploy/env.meta-campaign-write-pilot.example` | Smoke Meta write |
| `deploy/env.staging-hub-pg.example` | Hub PG flags staging |

**Script cutover chính:**

| Script | Mục đích |
|--------|----------|
| `scripts/phase3_prod_cutover_vps.sh` | Phase 3 qua SSH hoặc local dry-run |
| `scripts/close_phase3_prod_cutover.sh` | Phase 3 orchestrator trên VPS |
| `scripts/phase4_prod_cutover_vps.sh` | Phase 4 qua SSH hoặc local dry-run |
| `scripts/close_phase4_prod_cutover.sh` | Phase 4 orchestrator trên VPS |
| `scripts/run_phase_closure.sh` | QA + E2E + Phase 4 gates + cutover dry-run |
| `scripts/backup_ptt_data.sh` | Backup PG + SQLite |

---

## Phụ lục A — Bảng URL production (portal.pttads.vn)

| URL | Backend | Ghi chú |
|-----|---------|---------|
| `https://portal.pttads.vn/` | Next `:3100` | Login, redirect dashboard |
| `https://portal.pttads.vn/dashboard` | Next `:3100` | Performance Meta + Google |
| `https://portal.pttads.vn/meta` | Next `:3100` | Meta Performance (read-only) |
| `https://portal.pttads.vn/creatives` | Next `:3100` | Creative inbox |
| `https://portal.pttads.vn/api/v1/*` | Nest `:3000` | API OLTP — auth, performance, campaign-writes |
| `https://portal.pttads.vn/health` | Nest `:3000` | Health check |
| `https://rs.pttads.vn/admin` | Flask `:8002` | Admin / CMS / CRM |
| `https://rs.pttads.vn/crm/facebook-ads` | Flask `:8002` | Facebook Ads hub (AM/Media Buyer) |
| `http://127.0.0.1:8088` | Temporal UI | SSH tunnel only |

## Phụ lục B — Checklist go-live tổng hợp

- [ ] DNS `portal.pttads.vn` → VPS IP
- [ ] TLS Let's Encrypt cho `portal.pttads.vn`
- [ ] Nginx proxy `/` + `/api/` + `/health` (xem `deploy/nginx-portal.conf`)
- [ ] `NEXT_PUBLIC_PTT_API_URL=https://portal.pttads.vn` trong build portal
- [ ] `.env` prod điền đủ, `chmod 600`
- [ ] Phase 2 gates + write soak evidence
- [ ] Phase 3 portal E2E pass (Playwright prod — gồm tab `/meta`)
- [ ] CRM Facebook Ads hub `/crm/facebook-ads` — AM test token + CPL summary
- [ ] Phase 4 gate 7/7 pass trên staging VPS
- [ ] Backup timer active
- [ ] Sentry dashboards configured
- [ ] AM + DevOps + QA sign-off (`phase3-uat-signoff.json`)
- [ ] Rollback drill documented & tested ≤ 5 phút

---

*Liên hệ vận hành: điền operator on-call vào bảng mục 3.4 trước mỗi change window.*
