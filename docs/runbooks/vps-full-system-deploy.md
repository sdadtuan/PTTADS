# Hướng dẫn deploy toàn hệ thống PTT lên VPS

> **Phiên bản:** 2.0 · **Cập nhật:** 2026-07-20  
> **Kiến trúc:** Nest + ops-web + portal-web + Python workers · **Flask HTTP đã retired (Wave 8)**  
> **Thư mục trên VPS:** `/var/www/ptt`  
> **Runbook bàn giao:** [`handover-production-flask-to-nest.md`](./handover-production-flask-to-nest.md)  
> **Vận hành hàng ngày (chi tiết phase cũ):** [`vps-production-operations.md`](./vps-production-operations.md)

Tài liệu này mô tả **deploy greenfield** (VPS mới) và **nâng cấp cutover** (VPS đang chạy Flask cũ → stack mới).

---

## Mục lục

1. [Kiến trúc & domain](#1-kiến-trúc--domain)
2. [Yêu cầu hạ tầng](#2-yêu-cầu-hạ-tầng)
3. [Chuẩn bị VPS](#3-chuẩn-bị-vps)
4. [Cài đặt lần đầu (greenfield)](#4-cài-đặt-lần-đầu-greenfield)
5. [Cấu hình `.env` production](#5-cấu-hình-env-production)
6. [Nginx & TLS](#6-nginx--tls)
7. [Systemd — dịch vụ & timer](#7-systemd--dịch-vụ--timer)
8. [Seed & smoke test](#8-seed--smoke-test)
9. [Cutover Flask → Nest (VPS cũ)](#9-cutover-flask--nest-vps-cũ)
10. [Deploy bản mới (routine)](#10-deploy-bản-mới-routine)
11. [Gate kiểm tra](#11-gate-kiểm-tra)
12. [Rollback](#12-rollback)
13. [Xử lý sự cố nhanh](#13-xử-lý-sự-cố-nhanh)

---

## 1. Kiến trúc & domain

```mermaid
flowchart TB
    subgraph internet [Internet]
        STAFF[Nhân viên PTT]
        CLIENT[Khách hàng / Approver]
    end
    subgraph nginx [Nginx TLS]
        OPS[ops.pttads.vn]
        PORTAL[portal.pttads.vn]
        RS[rs.pttads.vn redirect]
    end
    subgraph apps [Application localhost]
        OW[ops-web :3200]
        PW[portal-web :3100]
        NEST[Nest ptt-crm-api :3000]
        WRK[ptt-worker]
        FB[ptt-fb-autosync]
        TW[ptt-temporal-worker]
    end
    subgraph infra [Docker]
        PG[(PostgreSQL :5432)]
        TEMP[Temporal :7233]
        CH[(ClickHouse :8123)]
    end
    STAFF --> OPS
    CLIENT --> PORTAL
    OPS --> OW
    OPS --> NEST
    PORTAL --> PW
    PORTAL --> NEST
    RS --> OPS
    NEST --> PG
    WRK --> PG
    FB --> PG
    TW --> TEMP
    TW --> PG
```

| Domain | Vai trò | Backend |
|--------|---------|---------|
| **https://ops.pttads.vn** | Staff console (CRM, SEO, Email, Meta…) | `/` → ops-web `:3200` · `/api/` → Nest `:3000` |
| **https://portal.pttads.vn** | Client portal | `/` → portal-web `:3100` · `/api/` → Nest `:3000` |
| **https://rs.pttads.vn** | Bookmark legacy | **302** → `ops.pttads.vn` · `/api/` → Nest (webhook nội bộ) |

**Webhook công khai (Meta/Zalo/Google/Email):**

```
POST https://ops.pttads.vn/api/v1/webhooks/{meta|zalo|google|email}
GET  https://ops.pttads.vn/api/v1/channels
```

(Có thể dùng `rs.pttads.vn/api/...` nếu DNS webhook đã trỏ subdomain đó.)

---

## 2. Yêu cầu hạ tầng

| Mục | Khuyến nghị |
|-----|-------------|
| OS | Ubuntu 22.04 / 24.04 LTS |
| RAM | ≥ 8 GB (PG + Temporal + ClickHouse + 3 Node apps) |
| Disk | ≥ 80 GB SSD |
| User deploy | `deploy` (group `www-data`) |
| Python | **3.11+** (scrypt portal users) |
| Node.js | **22 LTS** |
| Docker | Compose v2 |
| Nginx + certbot | TLS Let's Encrypt |

**DNS (A record → VPS IP):**

| Record | Bắt buộc |
|--------|----------|
| `ops.pttads.vn` | Có — staff |
| `portal.pttads.vn` | Có — client |
| `rs.pttads.vn` | Khuyến nghị — redirect legacy |

**Firewall:** chỉ mở **80, 443**. Các port `3000`, `3100`, `3200`, `5432`, `7233`, `8123` **không** public.

---

## 3. Chuẩn bị VPS

```bash
# Packages
sudo apt-get update
sudo apt-get install -y git curl nginx certbot python3-certbot-nginx \
  python3.11 python3.11-venv build-essential

# Node 22 (NodeSource hoặc nvm — ví dụ NodeSource)
curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
sudo apt-get install -y nodejs

# Docker
sudo apt-get install -y docker.io docker-compose-v2
sudo usermod -aG docker deploy

# Thư mục app
sudo mkdir -p /var/www/ptt /var/backups/ptt
sudo chown deploy:www-data /var/www/ptt
```

**Bảng điền trước go-live:**

| Mục | Giá trị |
|-----|---------|
| VPS IP | `________________` |
| SSH user | `deploy` |
| Change window | `________________` |
| On-call | `________________` |

---

## 4. Cài đặt lần đầu (greenfield)

> Thực hiện **một lần** trên VPS mới. Các lần sau xem [mục 10](#10-deploy-bản-mới-routine).

### 4.1. Clone repository

```bash
sudo -u deploy git clone <REPO_URL> /var/www/ptt
cd /var/www/ptt
git checkout main   # hoặc tag release
```

### 4.2. Python virtualenv & dependencies

```bash
cd /var/www/ptt
python3.11 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -r requirements.txt
pip install -r requirements-temporal.txt
```

### 4.3. Docker — PostgreSQL, Temporal, ClickHouse

```bash
cd /var/www/ptt

# PostgreSQL (+ init DDL v1/v2 qua docker-entrypoint-initdb.d)
docker compose up -d postgres redis rabbitmq

# Temporal (workflows)
docker compose -f docker-compose.temporal.yml up -d

# ClickHouse (Phase 4 analytics — bật khi cần BI)
docker compose -f docker-compose.clickhouse.yml up -d
```

Chờ Postgres sẵn sàng:

```bash
docker compose exec -T postgres pg_isready -U ptt -d ptt_agency
```

### 4.4. PostgreSQL DDL (theo thứ tự)

```bash
cd /var/www/ptt
source .venv/bin/activate
export DATABASE_URL=postgresql://ptt:STRONG_PASSWORD@127.0.0.1:5432/ptt_agency

# Core CRM
./scripts/apply_pg_ddl_v2_leads.sh
./scripts/apply_pg_ddl_v3.sh
./scripts/apply_pg_ddl_v3_events_idempotency.sh
./scripts/apply_pg_ddl_v3_sprint0.sh
./scripts/apply_pg_ddl_v3_creatives.sh
./scripts/apply_pg_ddl_v3_launch_qa.sh
./scripts/apply_pg_ddl_v3_google_sync.sh
./scripts/apply_pg_ddl_v3_leads_ingest_config.sh
./scripts/apply_pg_ddl_v4_hub_sop.sh
./scripts/apply_pg_ddl_v5_campaign_writes.sh
./scripts/apply_pg_ddl_staff_auth.sh

# Email marketing (nếu dùng module Email)
./scripts/apply_pg_ddl_email_mkt.sh
./scripts/apply_pg_ddl_email_mkt_em1.sh
./scripts/apply_pg_ddl_email_mkt_em3.sh
# Tuỳ wave: em7, em11, em12 — xem deploy/sql/

# ClickHouse init
./scripts/clickhouse_init.sh
```

### 4.5. File `.env` master

```bash
cp deploy/env.phase5-flask-retire.example /var/www/ptt/.env
# Merge thêm secrets từ deploy/env.phase3-prod.example nếu cần portal JWT
nano /var/www/ptt/.env
chmod 600 /var/www/ptt/.env
```

Chi tiết biến: [mục 5](#5-cấu-hình-env-production).

### 4.6. Build Nest CRM API

```bash
cd /var/www/ptt/services/ptt-crm-api
npm ci
npm run build

sudo cp /var/www/ptt/deploy/ptt-crm-api.service /etc/systemd/system/
```

### 4.7. Build ops-web (staff)

```bash
cd /var/www/ptt/services/ops-web
npm ci
export NEXT_PUBLIC_PTT_API_URL=https://ops.pttads.vn
npm run build
cp -r .next/static .next/standalone/.next/static
cp -r public .next/standalone/public 2>/dev/null || true

sudo cp /var/www/ptt/deploy/ptt-ops-web.service /etc/systemd/system/
```

### 4.8. Build portal-web (client)

```bash
cd /var/www/ptt/services/portal-web
npm ci
export NEXT_PUBLIC_PTT_API_URL=https://portal.pttads.vn
npm run build
cp -r .next/static .next/standalone/.next/static
cp -r public .next/standalone/public 2>/dev/null || true

sudo cp /var/www/ptt/deploy/ptt-portal-web.service /etc/systemd/system/
```

### 4.9. Python workers & timers

```bash
cd /var/www/ptt

# Job queue worker
sudo cp deploy/ptt-worker.service /etc/systemd/system/

# Facebook autosync daemon
sudo cp deploy/ptt-fb-autosync.service /etc/systemd/system/

# Cron oneshot + timer (root repo)
sudo cp ptt-fb-sync.service ptt-fb-sync.timer /etc/systemd/system/
sudo cp ptt-meta-insights.service ptt-meta-insights.timer /etc/systemd/system/
sudo cp ptt-meta-token-refresh.service ptt-meta-token-refresh.timer /etc/systemd/system/
sudo cp ptt-owner-weekly-alert.service ptt-owner-weekly-alert.timer /etc/systemd/system/
sudo cp ptt-finance-kpi-alert.service ptt-finance-kpi-alert.timer /etc/systemd/system/

# Phase 3 pack (portal worker, google insights, SEO timers)
sudo ./scripts/install_phase3_systemd.sh

# Phase 2 timers (lead shadow — tắt sau soak)
sudo ./scripts/install_phase2_systemd_timers.sh

# Temporal worker
sudo cp deploy/ptt-temporal-worker.service /etc/systemd/system/

# Backup timer (khuyến nghị)
sudo cp deploy/ptt-backup.service deploy/ptt-backup.timer /etc/systemd/system/

sudo systemctl daemon-reload
```

### 4.10. Nginx & TLS

Xem [mục 6](#6-nginx--tls) — cài 3 site + certbot trước khi start app.

### 4.11. Khởi động stack

```bash
sudo systemctl enable --now ptt-crm-api
sudo systemctl enable --now ptt-ops-web
sudo systemctl enable --now ptt-portal-web
sudo systemctl enable --now ptt-worker
sudo systemctl enable --now ptt-fb-autosync
sudo systemctl enable --now ptt-temporal-worker

# Timers
sudo systemctl enable --now ptt-fb-sync.timer
sudo systemctl enable --now ptt-meta-insights.timer
sudo systemctl enable --now ptt-google-insights.timer
sudo systemctl enable --now ptt-backup.timer
```

**Không cài / không start `ptt.service`** (Flask đã retired).

---

## 5. Cấu hình `.env` production

File: **`/var/www/ptt/.env`** — mọi systemd unit đọc qua `EnvironmentFile=-/var/www/ptt/.env`.

**Mẫu gộp:** `deploy/env.phase5-flask-retire.example` + secrets từ `deploy/env.phase3-prod.example`.

### 5.1. Bắt buộc

```bash
# Database
DATABASE_URL=postgresql://ptt:STRONG_PASSWORD@127.0.0.1:5432/ptt_agency
PTT_SQLITE_PATH=/var/www/ptt/ptt.db

# Nest / CRM
PTT_CRM_INTERNAL_KEY=<random-32+-chars>
PTT_JOBS_ENABLED=1
PTT_WEBHOOK_V1_ENQUEUE=1
PTT_LEADS_READ_SOURCE=pg
PTT_LEADS_WRITE_SOURCE=pg
PTT_LEAD_INGEST_RULES_SOURCE=pg

# Webhooks — Nest only
PTT_WEBHOOKS_NEST_ENABLED=1
PTT_WEBHOOKS_NEST_META=1
PTT_WEBHOOKS_NEST_ZALO=1
PTT_WEBHOOKS_NEST_GOOGLE=1
PTT_WEBHOOKS_NEST_EMAIL=1
PTT_WEBHOOKS_FLASK_FALLBACK=0

# Flask retired
PTT_FLASK_MONOLITH_MODE=retired

# Staff auth (ops-web)
PTT_STAFF_JWT_SECRET=<random-32+-chars>
PTT_STAFF_STUB_USERS=
PTT_OPS_CORS_ORIGINS=https://ops.pttads.vn
PTT_OPS_WEB_URL=https://ops.pttads.vn

# Portal auth
PTT_PORTAL_JWT_SECRET=<random-32+-chars>
PTT_PORTAL_ALLOW_STUB=0
PTT_PORTAL_STUB_USERS=
PTT_PORTAL_CORS_ORIGINS=https://portal.pttads.vn
NEXT_PUBLIC_PTT_API_URL=https://portal.pttads.vn

# Channel secrets (prod)
CRM_FACEBOOK_VERIFY_TOKEN=...
CRM_FACEBOOK_APP_SECRET=...
CRM_FACEBOOK_PAGE_ACCESS_TOKEN=...
CRM_ZALO_WEBHOOK_SECRET=...
CRM_GOOGLE_LEAD_WEBHOOK_KEY=...
CRM_FACEBOOK_SYNC_SECRET=...

# Facebook background
CRM_FACEBOOK_BACKGROUND=1
CRM_FACEBOOK_BACKGROUND_IN_GUNICORN=0
```

### 5.2. Tuỳ chọn theo module

| Module | Biến chính |
|--------|------------|
| Temporal | `PTT_TEMPORAL_ADDRESS=127.0.0.1:7233` |
| Portal SEO | `PTT_PORTAL_SEO_ENABLED=1` |
| Email send | `PTT_EMAIL_SEND_ENABLED=1` + SMTP/ESP keys |
| Meta campaign write | `PTT_META_CAMPAIGN_WRITE_PILOT=1` + pilot client IDs |
| AI features | `ANTHROPIC_API_KEY=...` |

---

## 6. Nginx & TLS

### 6.1. ops.pttads.vn (staff)

```bash
sudo cp /var/www/ptt/deploy/nginx-ops.conf /etc/nginx/sites-available/ops.pttads.vn
sudo ln -sf /etc/nginx/sites-available/ops.pttads.vn /etc/nginx/sites-enabled/
```

### 6.2. portal.pttads.vn (client)

```bash
sudo cp /var/www/ptt/deploy/nginx-portal.conf /etc/nginx/sites-available/portal.pttads.vn
sudo ln -sf /etc/nginx/sites-available/portal.pttads.vn /etc/nginx/sites-enabled/
```

### 6.3. rs.pttads.vn (legacy redirect)

```bash
sudo cp /var/www/ptt/deploy/nginx-rs-flask-retired.conf /etc/nginx/sites-available/rs.pttads.vn
sudo ln -sf /etc/nginx/sites-available/rs.pttads.vn /etc/nginx/sites-enabled/
```

### 6.4. TLS (Let's Encrypt)

```bash
# Lần đầu: comment block ssl trong conf → certbot → copy lại file đầy đủ
sudo certbot --nginx -d ops.pttads.vn -d portal.pttads.vn -d rs.pttads.vn
sudo nginx -t && sudo systemctl reload nginx
```

### 6.5. Webhook routing snippet (tuỳ chọn)

Nếu webhook trỏ domain khác (`pttads.vn`), cài snippet Nest-all:

```bash
sudo ./scripts/apply_webhooks_upstream.sh nest-all
# include snippets/ptt-webhooks-v1-routing.conf trong server block tương ứng
```

---

## 7. Systemd — dịch vụ & timer

### 7.1. Dịch vụ luôn chạy (production)

| Unit | Port / vai trò |
|------|----------------|
| `ptt-crm-api` | Nest `:3000` — API CRM, webhooks, portal API |
| `ptt-ops-web` | ops-web `:3200` — staff UI |
| `ptt-portal-web` | portal-web `:3100` — client UI |
| `ptt-worker` | Poll `job_queue` — ingest lead, email jobs |
| `ptt-fb-autosync` | Facebook Lead background sync |
| `ptt-temporal-worker` | Temporal workflows |

### 7.2. Timer / oneshot (cron systemd)

| Timer | Mục đích |
|-------|----------|
| `ptt-fb-sync.timer` | Gọi sync-cron Facebook (Nest `:3000`) |
| `ptt-meta-insights.timer` | Meta insights sync |
| `ptt-meta-token-refresh.timer` | Refresh Meta token |
| `ptt-google-insights.timer` | Google Ads insights |
| `ptt-seo-gsc-sync.timer` | GSC sync |
| `ptt-seo-ga4-sync.timer` | GA4 sync |
| `ptt-owner-weekly-alert.timer` | Digest tuần chủ DN |
| `ptt-finance-kpi-alert.timer` | Cảnh báo KPI tài chính |
| `ptt-backup.timer` | Backup PG + SQLite |

**Đã retired:** `ptt.service` (Flask Gunicorn `:8002`).

### 7.3. Lệnh kiểm tra

```bash
systemctl status ptt-crm-api ptt-ops-web ptt-portal-web ptt-worker ptt-fb-autosync
systemctl list-timers 'ptt-*' --no-pager
journalctl -u ptt-crm-api -n 50 --no-pager
```

---

## 8. Seed & smoke test

### 8.1. Portal pilot users

```bash
cd /var/www/ptt
source .venv/bin/activate
export DATABASE_URL=postgresql://ptt:***@127.0.0.1:5432/ptt_agency
export PORTAL_PILOT_PASSWORD='<mật-khẩu-ban-đầu-min-8-ký-tự>'
python3 scripts/seed_portal_pilot_users.py --password "$PORTAL_PILOT_PASSWORD"
```

Tài khoản: `viewer.pilot1@pttads.vn`, `approver.pilot1@pttads.vn`, … — xem runbook bàn giao.

### 8.2. Staff users

Production dùng bảng PG `staff_users` (không dùng stub). Tạo user qua quy trình HR/Admin hoặc seed SQL nội bộ.

### 8.3. Smoke test (5 phút)

```bash
curl -sf http://127.0.0.1:3000/health && echo " Nest OK"
curl -sfI https://ops.pttads.vn/login | head -1
curl -sfI https://portal.pttads.vn/login | head -1
curl -sfI https://ops.pttads.vn/crm/leads | head -1
curl -sfI https://rs.pttads.vn/crm/leads | head -1   # expect 302

# Webhook dry-run (empty body, no secret → 401 hoặc 200 tùy channel)
curl -s -o /dev/null -w "%{http_code}\n" \
  -X POST https://ops.pttads.vn/api/v1/webhooks/zalo \
  -H 'Content-Type: application/json' -d '{}'
```

| # | Kiểm tra tay | OK |
|---|--------------|----|
| 1 | Staff login ops → `/crm/leads` | [ ] |
| 2 | Portal login pilot → `/dashboard` | [ ] |
| 3 | Webhook Meta/Zalo → `job_queue` pending | [ ] |
| 4 | Worker xử lý lead mới | [ ] |
| 5 | `systemctl is-active ptt.service` → **inactive** | [ ] |

---

## 9. Cutover Flask → Nest (VPS cũ)

Nếu VPS **đang chạy Flask** (`ptt.service` active), thực hiện sau khi staging gate PASS:

```bash
cd /var/www/ptt
git pull origin main

# Build lại Nest + ops-web + portal (mục 4.6–4.8)
set -a && source deploy/env.phase5-flask-retire.example && set +a
# Chỉnh DATABASE_URL + secrets trong .env

sudo -E ./scripts/close_flask_retirement.sh          # dry-run
sudo -E APPLY=1 ./scripts/close_flask_retirement.sh  # stop ptt.service
```

Script tự:
- Ghi `PTT_FLASK_MONOLITH_MODE=retired`
- Deploy `nginx-rs-flask-retired.conf`
- Stop/disable `ptt.service`
- Restart toàn bộ stack Nest/workers/Next.js

Chi tiết: [`phase5-flask-retirement-checklist.md`](./phase5-flask-retirement-checklist.md)

---

## 10. Deploy bản mới (routine)

```bash
cd /var/www/ptt
./scripts/backup_ptt_data.sh

git pull origin main
source .venv/bin/activate
pip install -r requirements.txt

# Nest API
cd services/ptt-crm-api && npm ci && npm run build
sudo systemctl restart ptt-crm-api

# ops-web
cd /var/www/ptt/services/ops-web
npm ci && NEXT_PUBLIC_PTT_API_URL=https://ops.pttads.vn npm run build
cp -r .next/static .next/standalone/.next/static
sudo systemctl restart ptt-ops-web

# portal-web
cd /var/www/ptt/services/portal-web
npm ci && NEXT_PUBLIC_PTT_API_URL=https://portal.pttads.vn npm run build
cp -r .next/static .next/standalone/.next/static
sudo systemctl restart ptt-portal-web

# Workers
sudo systemctl restart ptt-worker ptt-fb-autosync ptt-temporal-worker

# DDL mới (nếu release có migration)
# ./scripts/apply_pg_ddl_*.sh

curl -sf http://127.0.0.1:3000/health && echo OK
```

---

## 11. Gate kiểm tra

```bash
cd /var/www/ptt
./scripts/wave8_gate.sh                    # Flask removed
./scripts/crm_flask_migration_pack.sh gap   # 100% migrated
./scripts/crm_flask_migration_pack.sh phase5-dry

# Staging full (trước prod cutover lớn)
set -a && source deploy/env.phase5-flask-retire.example && set +a
./scripts/staging_phase5_gate_pack.sh
```

Artifact: `.local-dev/*-gate-report.json`

---

## 12. Rollback

### 12.1. Rollback deploy code (giữ stack Nest)

```bash
cd /var/www/ptt
git checkout <tag-trước-đó>
# rebuild + restart (mục 10)
```

### 12.2. Rollback nginx/env (nhanh)

```bash
sudo cp /etc/nginx/sites-available/rs.pttads.vn.pre-phase5.bak \
        /etc/nginx/sites-available/rs.pttads.vn
sudo nginx -t && sudo systemctl reload nginx
sudo systemctl restart ptt-crm-api ptt-ops-web ptt-portal-web
```

### 12.3. Rollback full Flask

> Repo hiện tại **đã xóa Flask HTTP**. Khôi phục Flask cần **checkout tag pre-Wave-8** hoặc restore backup tarball, rồi `systemctl enable --now ptt.service`.

Chi tiết: [`handover-production-flask-to-nest.md`](./handover-production-flask-to-nest.md) mục 5.

---

## 13. Xử lý sự cố nhanh

| Triệu chứng | Kiểm tra | Hướng xử lý |
|-------------|----------|-------------|
| ops-web 502 | `systemctl status ptt-ops-web` | Rebuild standalone · check `:3200` |
| API 502 | `curl localhost:3000/health` | `journalctl -u ptt-crm-api` · DATABASE_URL |
| Webhook 503 `channel_not_migrated` | `.env` webhook flags | Bật `PTT_WEBHOOKS_NEST_*=1` |
| Lead không vào CRM | `job_queue` + worker | `systemctl status ptt-worker` |
| FB sync dừng | autosync + timer | `ptt-fb-autosync` · `ptt-fb-sync.timer` |
| Portal login fail | PG `portal_client_users` | Re-seed pilot · check JWT secret |

**Log nhanh:**

```bash
journalctl -u ptt-crm-api -f --since "30 min ago"
journalctl -u ptt-worker -n 100 --no-pager
journalctl -u ptt-fb-autosync -n 50 --no-pager
```

---

## Tài liệu liên quan

| Tài liệu | Nội dung |
|----------|----------|
| [`handover-production-flask-to-nest.md`](./handover-production-flask-to-nest.md) | Bàn giao 1 trang · pilot · sign-off |
| [`phase5-flask-retirement-checklist.md`](./phase5-flask-retirement-checklist.md) | Cutover Phase 5 chi tiết |
| [`crm-flask-retirement-master-checklist.md`](./crm-flask-retirement-master-checklist.md) | Wave 0–8 migration |
| [`vps-production-operations.md`](./vps-production-operations.md) | Vận hành phase-by-phase (một số mục Flask đã lỗi thời) |
| `deploy/env.phase5-flask-retire.example` | Env mẫu production |
| `deploy/nginx-ops.conf` | Nginx staff console |
