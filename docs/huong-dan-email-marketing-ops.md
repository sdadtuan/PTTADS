# Hướng dẫn sử dụng & triển khai phân hệ Email Marketing Ops

> **Phiên bản:** 2.0 · **Ngày:** 2026-07-25  
> **Đối tượng:** Admin VPS, Head CRM/Email, Email Strategist, Deliverability Specialist, Compliance, AM, vận hành agency  
> **Phạm vi:** Setup đầy đủ trên **VPS/staging/local** + hướng dẫn sử dụng từng màn hình ops-web, portal & trang public  
> **URL staff:** `https://ops.pttads.vn/email/*` · `https://rs.pttads.vn/email/*`  
> **URL client:** `https://portal.pttads.vn/email/*`  
> **Spec tham chiếu:**  
> - [`SPEC_EMAIL_MARKETING_OPERATING_SYSTEM.md`](SPEC_EMAIL_MARKETING_OPERATING_SYSTEM.md) — master spec kỹ thuật & nghiệp vụ (EM-OS v1.3)  
> - [`SPEC_UI_UX_EMAIL_MARKETING.md`](SPEC_UI_UX_EMAIL_MARKETING.md) — UI/UX screens E-01…E-13, P-EMAIL-*  
> - [`EMAIL_MARKETING_COMPLETION_ROADMAP.md`](EMAIL_MARKETING_COMPLETION_ROADMAP.md) — lộ trình EM-0→EM-5, P1/P2  
> - [`specs/2026-07-19-email-marketing-architecture.md`](specs/2026-07-19-email-marketing-architecture.md) — kiến trúc C4, DDL, API, deployment  

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
9. [Client Portal Email](#9-client-portal-email)
10. [Trang public & capture API](#10-trang-public--capture-api)
11. [Gates, QA & nghiệm thu](#11-gates-qa--nghiệm-thu)
12. [Xử lý sự cố thường gặp](#12-xử-lý-sự-cố-thường-gặp)
13. [Checklist go-live](#13-checklist-go-live)
14. [Phụ lục — env, API, runbook](#14-phụ-lục--env-api-runbook)

---

## 1. Tổng quan phân hệ

**Email Marketing Enterprise Operating System (EM-OS)** là phân hệ vận hành email marketing quy mô agency trên PTTADS — phục vụ **nhiều client trong một agency PTT** (multi-client), không phải SaaS multi-agency:

```
Acquisition → Capture & Consent → Unified Profile → Segmentation
           → Template → Campaign → Preflight → Approve → Send
           → Engagement → Deliverability → Reports → Governance
```

### 1.1. Stack canonical (2026-07-25)

| Lớp | Thành phần | Ghi chú |
|-----|------------|---------|
| **Staff UI** | ops-web `/email/*` | ~21 routes — E-01…E-13 + public pages |
| **Staff API** | Nest `ptt-crm-api` `/api/v1/email/*` | Module `email-marketing/` — **không proxy Flask** |
| **Domain/workers** | Python `ptt_email/` + `ptt_worker` | Send, journey, deliverability, BI export |
| **Data** | PostgreSQL `email_mkt.*` | PostgreSQL-only (ADR-EM-01) |
| **CRM master** | SQLite `crm_customers` | Liên kết `client_id` ↔ `customer_id` |
| **ESP** | SendGrid / Mailgun | ChannelAdapter `ptt_channel/adapters/email.py` |
| **Flask `/crm/email/*`** | **Không tồn tại** | nginx redirect → ops-web `/email/*` |

### 1.2. Module & route ops-web

| Screen ID | Module | Route | Phase | Trạng thái |
|-----------|--------|-------|-------|------------|
| E-01 | Email Ops Hub | `/email/hub` | EM-0 | ✅ |
| E-02 | Danh sách client Email | `/email/clients` | EM-1 | ✅ |
| E-03 | Client workspace + settings | `/email/clients/:id` | EM-1 | ✅ |
| E-04 | Danh bạ contacts | `/email/contacts` | EM-1 | ✅ |
| E-05 | Consent registry | `/email/consent` | EM-1 | ✅ |
| E-06 | Suppression master | `/email/suppression` | EM-1 | ✅ |
| E-07 | Segment builder | `/email/segments` | EM-2 | ✅ P1 (RFM/Behavior) |
| E-08 | Template studio | `/email/templates` | EM-2 | 🟡 |
| E-08b | Template editor | `/email/templates/:id` | EM-2 | 🟡 |
| E-09 | Campaign console | `/email/campaigns` | EM-2 | ✅ |
| E-09b | Campaign detail | `/email/campaigns/:id` | EM-2/10 | ✅ |
| E-09c | Preflight QA | `/email/campaigns/:id/review` | EM-10 | ✅ |
| E-10 | Journey builder | `/email/journeys` | EM-3 | ✅ |
| E-10b | Journey canvas | `/email/journeys/:id` | EM-12 | ✅ |
| E-11 | Deliverability console | `/email/deliverability` | EM-3 | ✅ P1 wizard |
| E-12 | Analytics center | `/email/reports` | EM-3 | ✅ P1 Grafana |
| E-13 | Governance hub | `/email/governance` | EM-0→P1 | ✅ write + audit |
| — | Gate A go-live | `/email/gate-a` | EM-5 | ✅ |
| P-EMAIL-PUB-01 | Preference center | `/email/public/preferences/:token` | EM-1 | ✅ |
| P-EMAIL-PUB-02 | Unsubscribe | `/email/public/unsubscribe/:token` | EM-1 | ✅ |
| P-EMAIL-PUB-03 | Double opt-in confirm | `/email/public/confirm/:token` | EM-1 | ✅ |

### 1.3. Nguyên tắc vận hành (spec §1.3)

1. **Staff 100% ops-web** — không dùng Flask admin email.
2. **Consent-first** — không gửi nếu thiếu consent hoặc trong suppression master.
3. **`client_id` filter** — mọi màn hình và API scoped theo client.
4. **Governance-heavy** — approval workflow, audit mọi thao tác rủi ro cao.
5. **Deliverability-by-design** — domain verify, warm-up, auto-pause khi complaint spike.
6. **Pilot → soak → prod** — staged cutover B1→B4 trước khi mở rộng client.

### 1.4. Personas & entry points (UI/UX spec §2)

| Persona | Scenario | Entry point |
|---------|----------|-------------|
| Email CoE Lead | Review standards, global rules | E-01 → E-13 |
| Email Strategist | Segment, campaign, schedule send | E-07, E-08, E-09 |
| Content Designer | Template, blocks, render test | E-08, E-08b |
| Deliverability Specialist | Domain, warm-up, pause send | E-11 |
| Compliance Reviewer | Audit consent, approve high-risk send | E-05, E-09c |
| Account Manager | Client health, calendar, reports | E-02, E-12 |
| Admin | ESP credentials, DNS setup | E-03 Settings |
| Client Approver | Duyệt campaign trước send | Portal P-EMAIL-02 |
| End subscriber | Preferences, unsubscribe | Public P-EMAIL-PUB-* |

---

## 2. Kiến trúc trên VPS

```
┌─────────────────────────────────────────────────────────────────────┐
│  VPS (vd. /var/www/ptt)                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐  │
│  │ ops-web :3200│  │ portal-web   │  │ nginx                    │  │
│  │ staff /email/*│ │ :3100 /email │  │ /crm/email → /email 302  │  │
│  └──────┬───────┘  └──────┬───────┘  └──────────────────────────┘  │
│         │                 │                                         │
│  ┌──────┴─────────────────┴───────┐                                │
│  │ ptt-crm-api (Nest) :3000       │  ← /api/v1/email/*             │
│  └──────┬─────────────────────────┘                                │
│         │                                                           │
│  ┌──────┴───────┐  ┌────────────────┐  ┌─────────────────────────┐ │
│  │ ptt_worker   │  │ Temporal       │  │ ESP (SendGrid/Mailgun)  │ │
│  │ job_queue    │  │ approval WF    │  │ webhooks → Nest         │ │
│  └──────┬───────┘  └────────────────┘  └─────────────────────────┘ │
│         ▼                                                           │
│  PostgreSQL (email_mkt.*)  ──export──▶  ClickHouse (BI)            │
│         │                                                           │
│  systemd timers: send due · journey scan · domain verify · CH exp │
└─────────────────────────────────────────────────────────────────────┘
```

| Thành phần | Path / URL |
|------------|------------|
| Repo | `/var/www/ptt` (hoặc clone local) |
| Env | `/var/www/ptt/.env` |
| Staff console | `rs.pttads.vn` hoặc `ops.pttads.vn` |
| PG schema | `deploy/sql/email_mkt_pg_schema.sql` + wave migrations |
| Grafana dashboard | `deploy/grafana/email-ops-dashboard.json` |
| Gate reports | `.local-dev/wave-gates/` |

**Luồng request staff:**

```
Browser → nginx /email/* → ops-web :3200
Browser → nginx /api/v1/email/* → Nest :3000 (Staff JWT + RBAC)
Worker  → PG email_mkt.* → ESP API → webhook → engagement ingest
```

---

## 3. Triển khai & setup đầy đủ

> **Thứ tự khuyến nghị:** local dev → staging mirror → soak ≥7 ngày → production staged cutover (B1→B4).  
> Runbook pilot: [`runbooks/email-marketing-prod-pilot-checklist.md`](runbooks/email-marketing-prod-pilot-checklist.md)

### 3.1. Điều kiện tiên quyết

- [ ] PostgreSQL production (`DATABASE_URL`) — schema `email_mkt`
- [ ] `ptt-crm-api`, ops-web, `ptt_worker` deploy healthy
- [ ] Staff auth: Keycloak hoặc staff JWT prod (`PTT_CRM_API_AUTH_DISABLED=0`)
- [ ] ESP account pilot (SendGrid/Mailgun) + webhook URL public
- [ ] Backup: `pg_dump` trước mọi change window
- [ ] (Tuỳ chọn BI) ClickHouse + Grafana cho E-12

### 3.2. Bước 1 — Apply schema PostgreSQL

```bash
cd /var/www/ptt   # hoặc repo root local
export DATABASE_URL=postgresql://ptt:PASSWORD@127.0.0.1:5432/ptt_agency

# Schema base EM-0
./scripts/apply_pg_ddl_email_mkt.sh

# Wave migrations (chạy theo phase đã deploy)
./scripts/apply_pg_ddl_email_mkt_em1.sh   # EM-1 capture/profile
./scripts/apply_pg_ddl_email_mkt_em3.sh   # EM-3 enterprise
./scripts/apply_pg_ddl_email_mkt_em7.sh   # EM-7 wave2
./scripts/apply_pg_ddl_email_mkt_em11.sh  # EM-11 prod ops
./scripts/apply_pg_ddl_email_mkt_em12.sh  # EM-12 automation
```

**Verify:**

```bash
psql "$DATABASE_URL" -c "\dt email_mkt.*"
psql "$DATABASE_URL" -c "SELECT COUNT(*) FROM email_mkt.clients;"
```

Hub ops-web sẽ hiện banner vàng nếu schema chưa apply — kiểm tra tại `/email/hub`.

### 3.3. Bước 2 — Env cốt lõi (staging / prod)

Copy template và chỉnh secret:

```bash
cp deploy/env.em5-prod.example .env.email-pilot
# Real ESP send (sau domain verify):
cp deploy/env.em5-prod-send.example .env.email-send
```

**Biến môi trường cốt lõi** (merge vào `/var/www/ptt/.env`):

```bash
# Core module
PTT_EMAIL_ENABLED=1
PTT_EMAIL_DB=pg
DATABASE_URL=postgresql://...

# Staged cutover — B1 admin only (khuyến nghị bắt đầu)
PTT_EMAIL_SEND_ENABLED=0
PTT_EMAIL_JOURNEYS_ENABLED=0
PTT_EMAIL_PORTAL_ENABLED=0

# Auth prod
PTT_CRM_API_AUTH_DISABLED=0
PTT_STAFF_STUB_USERS=
PTT_PORTAL_STUB_USERS=
PTT_PORTAL_JWT_SECRET=<min-32-chars>

# Sending defaults (workspace override trong PG)
PTT_EMAIL_DEFAULT_DAILY_CAP=50000
PTT_EMAIL_FREQUENCY_CAP_7D=5
PTT_EMAIL_SEND_BATCH_SIZE=100

# Deliverability alerts (P1.3)
PTT_EMAIL_DELIVERABILITY_ALERTS=1
PTT_EMAIL_SLACK_WEBHOOK=https://hooks.slack.com/...
PTT_EMAIL_TEAMS_WEBHOOK=https://outlook.office.com/webhook/...

# BI (EM-3+, optional pilot)
PTT_EMAIL_CLICKHOUSE_EXPORT=1
CLICKHOUSE_URL=http://127.0.0.1:8123
PTT_EMAIL_GRAFANA_URL=https://grafana.example/d/email-ops

# ops-web URL (CORS Nest)
PTT_OPS_WEB_URL=https://rs.pttads.vn
PTT_OPS_CORS_ORIGINS=https://rs.pttads.vn,https://ops.pttads.vn
```

**Real ESP send** (B2 — sau soak B1):

```bash
PTT_EMAIL_SEND_ENABLED=1
PTT_EMAIL_ESP_DRY_RUN=0
EMAIL_ESP_PROVIDER=sendgrid
SENDGRID_API_KEY=SG.xxx
PTT_EMAIL_WEBHOOK_VERIFY=1
SENDGRID_WEBHOOK_VERIFICATION_KEY=...
```

Template đầy đủ: `deploy/env.em5-prod.example`, `deploy/env.em5-prod-send.example`, `deploy/env.em9-wave4.example`.

### 3.4. Bước 3 — RBAC & seed pilot

```bash
# Seed 7 caps crm_email_mkt_* trên PG staff permissions
python3 scripts/seed_staff_email_mkt_permissions.py

# E2E handoff seed (staging/dev)
python3 scripts/seed_ops_email_handoff_e2e.py
```

Gán quyền staff qua Admin → Phân quyền trang → section `crm_email_mkt` (xem §5).

**Pilot client checklist:**

| Biến | Giá trị |
|------|---------|
| `PILOT_CLIENT_UUID` | UUID trong `email_mkt.clients` |
| Sending domain | vd. `mail.clientdomain.com` |
| ESP provider | sendgrid / mailgun |
| Portal approver | email client approver |

### 3.5. Bước 4 — Build & deploy services

```bash
# Nest API
cd services/ptt-crm-api
npm ci && npm run build
sudo systemctl restart ptt-crm-api

# ops-web (set NEXT_PUBLIC_* trước build)
cd services/ops-web
export NEXT_PUBLIC_PTT_EMAIL_ENABLED=1
export NEXT_PUBLIC_PTT_EMAIL_SEND_ENABLED=0   # B1
npm ci && npm run build
sudo systemctl restart ops-web

# Worker
export PTT_JOBS_ENABLED=1
sudo systemctl restart ptt-worker
```

**ops-web env build-time** (`services/ops-web/.env.production` hoặc CI):

```bash
NEXT_PUBLIC_PTT_EMAIL_ENABLED=1
NEXT_PUBLIC_PTT_EMAIL_SEND_ENABLED=1
NEXT_PUBLIC_PTT_EMAIL_JOURNEYS_ENABLED=0
NEXT_PUBLIC_PTT_EMAIL_GATE_A_ENABLED=1
NEXT_PUBLIC_API_URL=https://api.pttads.vn
```

### 3.6. Bước 5 — Systemd timers & cron

Enable sau khi module healthy:

```bash
# Campaign schedule due (EM-10)
sudo systemctl enable --now ptt-email-campaign-schedule.timer

# Journey scan (B4)
sudo systemctl enable --now ptt-email-journey.timer

# Soak evidence (Gate A)
sudo systemctl enable --now ptt-email-soak.timer

# ClickHouse export (BI)
./scripts/export_email_facts_clickhouse.sh   # manual test
```

Script cron tham chiếu: `scripts/email_campaign_schedule_due_cron.sh`, `scripts/email_journey_cron.sh`, `scripts/phase5_email_soak_record.sh`.

### 3.7. Bước 6 — Nginx routes

```nginx
# Staff ops-web
location /email {
    proxy_pass http://127.0.0.1:3200;
}
location /api/v1/email {
    proxy_pass http://127.0.0.1:3000;
}
location /api/v1/webhooks/email {
    proxy_pass http://127.0.0.1:3000;
}

# Public preference/unsub (ops-web public routes)
location /email/public {
    proxy_pass http://127.0.0.1:3200;
}

# Portal client
location /email {
    # portal host only
    proxy_pass http://127.0.0.1:3100;
}
```

**Không proxy Flask** cho EM-OS. Legacy `/crm/email/*` → 302 `/email/*`.

```bash
sudo nginx -t && sudo systemctl reload nginx
```

### 3.8. Bước 7 — Grafana & ClickHouse (E-12, tuỳ chọn)

1. Import dashboard: `deploy/grafana/email-ops-dashboard.json`
2. Import alert rules: `deploy/grafana/email-ops-alert-rules.json`
3. Set `PTT_EMAIL_GRAFANA_URL` → iframe trên `/email/reports`
4. Verify API: `GET /api/v1/email/reports/bi-status`

### 3.9. Setup local dev (developer)

```bash
cd PTTADS
export DATABASE_URL=postgresql://localhost/ptt_crm
export PTT_EMAIL_DB=pg
export PTT_EMAIL_ENABLED=1
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

Hub local: `http://localhost:3200/email/hub`  
Login dev: `staff@demo.local` / `demo123` (khi stub auth bật).

**QA gates local:**

```bash
./scripts/phase0_email_hub_kickoff_gate.sh
./scripts/email_handoff_gate.sh
./scripts/email_p1_gate.sh
./scripts/phase5_email_prod_pilot_gate.sh
```

### 3.10. Rollback nhanh

| Tình huống | Hành động |
|------------|-----------|
| Module UI lỗi | `PTT_EMAIL_ENABLED=0` + `NEXT_PUBLIC_PTT_EMAIL_ENABLED=0` → rebuild ops-web |
| Send incident | `PTT_EMAIL_SEND_ENABLED=0` → pause campaigns + domain E-11 |
| Portal lỗi | `PTT_EMAIL_PORTAL_ENABLED=0` |
| Journey lỗi | `PTT_EMAIL_JOURNEYS_ENABLED=0` |
| Emergency full stop | `PTT_EMAIL_ENABLED=0` + worker stop |

---

## 4. Bật tính năng theo phase & flag

### 4.1. Backend flags

| Biến | Default dev | Ý nghĩa |
|------|-------------|---------|
| `PTT_EMAIL_ENABLED` | `0` | Nest module + hub API |
| `PTT_EMAIL_SEND_ENABLED` | `0` | Enqueue ESP send |
| `PTT_EMAIL_ESP_DRY_RUN` | `1` dev | Log only, không gọi ESP |
| `PTT_EMAIL_JOURNEYS_ENABLED` | `0` | Journey scan timer |
| `PTT_EMAIL_PORTAL_ENABLED` | `0` | Portal client email |
| `PTT_EMAIL_DELIVERABILITY_ALERTS` | `1` | Slack/Teams on hub load |
| `PTT_EMAIL_CLICKHOUSE_EXPORT` | `0` pilot | BI export job |
| `PTT_EMAIL_WEBHOOK_VERIFY` | `1` prod | Verify ESP webhook signature |

### 4.2. ops-web flags (`NEXT_PUBLIC_PTT_EMAIL_*`)

File: `services/ops-web/src/lib/email-flags.ts`

| Flag | Route / behavior nếu `0` |
|------|--------------------------|
| `NEXT_PUBLIC_PTT_EMAIL_ENABLED` | Ẩn toàn bộ menu Email |
| `NEXT_PUBLIC_PTT_EMAIL_SEND_ENABLED` | Banner "Send platform tắt" trên campaigns |
| `NEXT_PUBLIC_PTT_EMAIL_JOURNEYS_ENABLED` | Ẩn/hide journey actions |
| `NEXT_PUBLIC_PTT_EMAIL_GATE_A_ENABLED` | Ẩn `/email/gate-a` |

Rebuild ops-web sau mỗi thay đổi `NEXT_PUBLIC_*`.

### 4.3. Staged prod cutover (Gate A §B)

```bash
# B1 — Ops admin only (soak ≥3 ngày)
PTT_EMAIL_ENABLED=1
PTT_EMAIL_SEND_ENABLED=0
PTT_EMAIL_JOURNEYS_ENABLED=0
PTT_EMAIL_PORTAL_ENABLED=0

# B2 — Send MVP (sau domain verify + consent OK)
PTT_EMAIL_SEND_ENABLED=1
PTT_EMAIL_ESP_DRY_RUN=0

# B3 — Portal (sau 1 campaign send OK)
PTT_EMAIL_PORTAL_ENABLED=1

# B4 — Journeys widen (sau portal E2E)
PTT_EMAIL_JOURNEYS_ENABLED=1
```

Soak hàng ngày: `./scripts/phase5_email_soak_record.sh`  
Gate: `./scripts/phase5_email_prod_pilot_gate.sh`

---

## 5. Truy cập & phân quyền

### 5.1. Đăng nhập staff

1. `https://rs.pttads.vn/login` hoặc `ops.pttads.vn/login`
2. Sidebar → **Agency & Hub** → link Email (khi `NEXT_PUBLIC_PTT_EMAIL_ENABLED=1`)
3. Hub: `/email/hub`

### 5.2. Section keys RBAC

7 actions trên section `crm_email_mkt`:

| Action | Quyền UI/API |
|--------|--------------|
| `view` | Xem hub, clients, contacts, segments, campaigns |
| `write` | Tạo/sửa segment, template, campaign draft |
| `settings` | Workspace, governance CRUD, ESP config |
| `deliverability` | Domain register/verify/pause |
| `reports` | Export ClickHouse, scheduled PDF |
| `compliance` | Consent/suppression write |
| `approve` | Staff approve campaign, schedule send |

Seed: `scripts/seed_staff_email_mkt_permissions.py`

**Gợi ý theo vai trò:**

| Vai trò | Actions |
|---------|---------|
| Head Email / CoE | view + settings + approve + reports |
| Email Strategist | view + write + approve |
| Content Designer | view + write (templates) |
| Deliverability | view + deliverability + reports |
| Compliance | view + compliance + approve |
| AM | view + settings + reports |
| Agency admin (`crm_agency:create`) | Full bypass tương đương settings |

Nest guards: `StaffEmailViewGuard`, `StaffEmailWriteGuard`, `StaffEmailSettingsGuard`, `StaffEmailDeliverabilityGuard`, `StaffEmailReportsGuard`, `StaffEmailComplianceGuard`, `StaffEmailApproveGuard`.

### 5.3. Navigation rules (UI/UX spec §3.4)

| Điều kiện | UI |
|-----------|-----|
| Schema chưa apply | Banner vàng hub → Governance |
| Client chưa ESP/domain | Banner vàng workspace + disable Schedule send |
| SPF/DKIM/DMARC fail | Badge đỏ E-11 + hub alert |
| Complaint rate > threshold | Banner đỏ hub → `/email/deliverability` |
| Campaign pending approval | Badge hub KPI `pending_approvals` |
| Send queue lag > 5 min | KPI hub `send_queue_lag_minutes` |
| Segment thiếu consent | Warning preflight / compute excluded count |

---

## 6. Hướng dẫn từng màn hình (UI/UX)

> Screen ID theo [`SPEC_UI_UX_EMAIL_MARKETING.md`](SPEC_UI_UX_EMAIL_MARKETING.md) §5.  
> Layout: card pattern, dense tables, tiếng Việt; EN cho thuật ngữ kỹ thuật (SPF, DKIM, DMARC).

### 6.1. E-01 — Email Ops Hub (`/email/hub`)

**Mục đích:** Dashboard executive — KPI tổng, client health, alerts, send calendar, pending approvals.

**Layout (spec wireframe §6):**

```
┌─────────────────────────────────────────────────────────────┐
│ Filter: [Days ▼] [Client UUID] [Domain]        [Làm mới]   │
├──────────┬──────────┬──────────┬──────────┬───────────────┤
│ Emails   │ Open rate│ Complaint│ Revenue  │ Pending / Queue│
│ sent     │          │ rate     │ attrib.  │ approval / lag │
├──────────┴──────────┴──────────┴──────────┴───────────────┤
│ Quick links: Clients · Contacts · Segments · Campaigns …    │
│ Alerts banner (deliverability → E-11)                       │
│ Send calendar (7d) │ Client email health table → E-03      │
└─────────────────────────────────────────────────────────────┘
```

**Thao tác hàng ngày (AM / Head Email):**

1. Mở `/email/hub`
2. Chọn **Days** (7 / 28 / 90) và lọc client nếu cần
3. Kiểm tra **Complaint rate** và **Alerts** — click link → E-11
4. Review **Send calendar** — campaign scheduled 7 ngày tới
5. Drill-down client health → `/email/clients/:id` (≤3 click tới contacts — spec §13)
6. Xử lý **Pending approval** → `/email/campaigns`

**API:** `GET /api/v1/email/hub?days=28&client_id=&domain=`  
Hub gọi `hubWithAlerts()` — post Slack/Teams nếu webhook configured (P1.3).

---

### 6.2. E-02 / E-03 — Clients & Workspace (`/email/clients`, `/email/clients/:id`)

**E-02 — Danh sách client:**

- Cột: client code, name, workspace, ESP, contact count
- Tạo workspace mới cho client chưa có
- Search theo tên/code

**E-03 — Client workspace tabs:**

```
[Tổng quan] [Danh bạ] [Consent] [Phân khúc] [Chiến dịch] [Deliverability] [Báo cáo] [Cài đặt]
```

**Context bar (luôn hiển thị):** Client name · Sending domain · ESP · Daily cap · Owner AM · Consent mode

**Tab Cài đặt (Settings)** — cap `settings`:

| Field | Mô tả |
|-------|-------|
| Workspace name | Tên hiển thị nội bộ |
| From name / From email | Default sender |
| Reply-to | Reply address |
| ESP provider | sendgrid / mailgun |
| Daily send cap | Max emails/ngày |
| Frequency cap 7d | Max emails/contact/7 ngày |
| Timezone | Quiet hours reference |

**Onboard client mới (AM):**

1. CRM: tạo/chọn customer → có `client_id` UUID trong `email_mkt.clients`
2. `/email/clients` → tạo workspace nếu chưa có
3. `/email/clients/:id?tab=settings` — điền from/reply, ESP, caps
4. `/email/deliverability` — domain wizard (§6.11)
5. `/email/contacts` — import CSV hoặc capture API
6. `/email/consent` — verify opted-in marketing

**API:** `GET/POST /api/v1/email/workspaces`, `GET /api/v1/email/clients`

---

### 6.3. E-04 — Contacts (`/email/contacts`)

**Mục đích:** Danh bạ unified profile per client.

**Cột chính:** email, tên, lifecycle stage, consent status, suppressed flag

**Thao tác:**

1. Lọc **Client UUID** (bắt buộc cho import)
2. **Import CSV** — format: `email,first_name,last_name` (một email/dòng)
3. Click contact → xem consent history (link E-05)
4. Kiểm tra badge **suppressed** trước khi add vào segment

**API:** `GET /api/v1/email/contacts`, `POST /api/v1/email/contacts/import`

**Business rule:** Contact mới từ import cần consent record `opted_in` trước khi eligible send.

---

### 6.4. E-05 — Consent registry (`/email/consent`)

**Mục đích:** Audit trail consent — append-only, không UPDATE (ADR-EM-08).

**Thao tác Compliance:**

1. Lọc client + topic (`marketing`, `newsletter`, …)
2. Tra cứu contact theo email
3. Verify `status=opted_in` + `recorded_at` + `source`
4. Double opt-in: chờ confirm qua P-EMAIL-PUB-03

**API:** `GET /api/v1/email/consent`, `POST /api/v1/email/consent` (compliance cap)

**SLA:** Unsubscribe xử lý < 24h (spec KPI §9).

---

### 6.5. E-06 — Suppression master (`/email/suppression`)

**Mục đích:** Hard suppression — bounce hard, complaint, global unsub, legal hold.

**Nguồn suppression tự động:**

- Webhook ESP: bounce hard, complaint, unsub
- Public one-click unsub (P-EMAIL-PUB-02)
- Manual add (compliance)

**Thao tác:**

1. Search email / client scope
2. Review reason + expires_at
3. **Không xóa** complaint suppression — chỉ compliance override có audit

**API:** `GET/POST /api/v1/email/suppression`

Send pipeline loại suppression trước enqueue (eligibility v1/v2).

---

### 6.6. E-07 — Segment builder (`/email/segments`)

**Mục đích:** Định nghĩa audience — Rules, Static, Lifecycle, RFM, Behavior (P1.2).

**UI — 5 tabs SegmentBuilder:**

| Tab | segment_type | Mô tả |
|-----|--------------|-------|
| Rules | `dynamic` | Filter JSON rules cơ bản |
| Static | `static` | Upload list `contact_ids` |
| Lifecycle | `lifecycle` | Filter `lifecycle_stage` (lead, MQL, customer…) |
| RFM | `rfm` | Recency days + min opens |
| Behavior | `dynamic` | `last_open_within_days`, `last_click_within_days` |

**Thao tác Strategist:**

1. Chọn **Client** từ dropdown (hoặc `?client_id=UUID`)
2. Chọn tab → đặt tên segment → định nghĩa
3. **Save** — PATCH definition
4. **Compute** — `POST /segments/:id/compute` → `member_count` + excluded suppression/consent
5. **Duplicate** — copy segment cho A/B test audience

**Kết quả compute hiển thị:**

- `member_count` — contacts eligible
- Excluded suppression / consent counts

**API:** `GET/POST/PATCH /api/v1/email/segments`, `POST /segments/:id/compute`

---

### 6.7. E-08 / E-08b — Template studio (`/email/templates`, `/email/templates/:id`)

**Mục đích:** Master templates + blocks + personalization tokens.

**Thao tác Designer:**

1. Tạo template mới — chọn client
2. Editor HTML + blocks JSON
3. **Bắt buộc:** link unsubscribe `{{unsubscribe_url}}` hoặc `List-Unsubscribe`
4. Render test desktop/mobile (preview card)
5. Preflight template: `POST /templates/:id/preflight`

**Preflight checks (EM-10 v2):**

- Unsubscribe link present
- Link validation
- Personalization tokens resolved
- Spam score stub (Phase 3+)

**Trạng thái:** Blocks/HTML shipped; drag-drop WYSIWYG = backlog P2.

---

### 6.8. E-09 / E-09b / E-09c — Campaigns (`/email/campaigns`)

**Pipeline status:** `draft` → `pending_approval` → `approved` → `scheduled` → `sending` → `sent` | `cancelled`

**E-09 — Campaign console:**

- List campaigns filter client/status
- **New campaign** — chọn segment + template
- Banner nếu `PTT_EMAIL_SEND_ENABLED=0`

**E-09b — Campaign detail (`/email/campaigns/:id`):**

- Audience summary, schedule, send stats live
- Actions: Submit approval, Schedule, Cancel (cap approve)

**E-09c — Preflight review (`/email/campaigns/:id/review`):**

Checklist QA trước send:

| Check | Pass criteria |
|-------|---------------|
| Unsubscribe | Template có unsub link |
| Consent gap | 0 contacts thiếu opted_in trong audience |
| Suppression overlap | Excluded count = 0 conflict |
| Domain health | Domain verified, not paused |
| Frequency cap | Under 7d cap per governance |
| Approval | Staff + client (nếu policy) approved |

**Thao tác broadcast (Flow F1):**

1. Tạo campaign draft
2. Chọn segment đã compute + template preflight pass
3. **Run preflight** trên review page
4. **Submit approval** → Temporal workflow
5. Staff **Approve** (cap `approve`)
6. **Schedule send** hoặc send immediately
7. Monitor trên hub + E-12

**API:** `GET/POST /api/v1/email/campaigns`, `POST /campaigns/:id/submit`, `POST /campaigns/:id/schedule`, `GET /campaigns/:id/preflight`

---

### 6.9. E-10 / E-10b — Journeys (`/email/journeys`, `/email/journeys/:id`)

**Mục đích:** Automation multi-step — trigger → wait → send → branch.

**Yêu cầu:** `PTT_EMAIL_JOURNEYS_ENABLED=1` (B4 cutover)

**Thao tác:**

1. Tạo journey — trigger type (segment entry, event, date)
2. Canvas editor — nodes: send email, wait, condition, exit
3. **Activate** journey — status `active`
4. Worker `email_journey_scan` enroll contacts theo trigger

**API:** `GET/POST /api/v1/email/journeys`, `PATCH /journeys/:id`, `POST /journeys/:id/activate`

Cron: `scripts/email_journey_cron.sh`

---

### 6.10. E-11 — Deliverability (`/email/deliverability`)

**Mục đích:** DNS auth, warm-up, pause domain, complaint response.

**Domain onboarding wizard (P1.5) — 3 bước:**

| Bước | Hành động |
|------|-----------|
| 1. Domain | Nhập sending domain → Register |
| 2. DNS records | Copy SPF, DKIM CNAME, DMARC TXT vào DNS provider client |
| 3. Verify & warm-up | Verify DNS → xem warm-up stage meter |

**Bảng domains:**

| Cột | Ý nghĩa |
|-----|---------|
| SPF / DKIM / DMARC | pass / fail / pending |
| Warm-up stage | 0–5 volume ramp |
| Status | active / paused / pending |

**Thao tác Deliverability Specialist:**

1. Chọn client dropdown
2. Wizard onboard domain mới HOẶC manual **+ Thêm domain**
3. **Verify** sau khi client cấu hình DNS
4. **Pause** domain khi complaint spike
5. Follow runbook recovery → gradual warm-up restore

**API:** `GET/POST /api/v1/email/deliverability/domains`, `POST /domains/:id/verify`, `POST /domains/:id/pause`

Runbook: [`runbooks/email-deliverability-incident.md`](runbooks/email-deliverability-incident.md)

---

### 6.11. E-12 — Reports (`/email/reports`)

**Mục đích:** Analytics center — engagement, deliverability scorecard, BI export.

**Panels:**

1. **KPI summary** — sent, delivered, open rate, click rate, unsubs, revenue attrib.
2. **Engagement chart** — series theo ngày (7/28/90d filter)
3. **Deliverability scorecard** — bounce rate, complaint rate, paused domains
4. **BI & Grafana (P1.4)** — ClickHouse status + iframe Grafana nếu URL set
5. **Scheduled PDF** — weekly executive report per client (cap reports)

**Thao tác AM:**

1. Chọn client UUID + days
2. Review KPI → export ClickHouse nếu BI enabled
3. Tạo weekly schedule PDF → recipient email
4. Mở Grafana embed để drill-down ops metrics

**API:** `GET /reports/summary`, `/reports/deliverability`, `/reports/engagement-series`, `/reports/bi-status`, `POST /reports/export-clickhouse`

---

### 6.12. E-13 — Governance (`/email/governance`)

**Mục đích:** Global/brand/market rules + audit tail (P1.1 write).

**Global rules — rule types:**

| rule_type | Config ví dụ |
|-----------|--------------|
| `frequency_cap_7d` | `{ "max": 5 }` |
| `quiet_hours` | `{ "start": "22:00", "end": "07:00", "tz": "Asia/Ho_Chi_Minh" }` |
| `complaint_rate_threshold` | `{ "max_pct": 0.1 }` |
| `approval_threshold_audience` | `{ "min_members": 10000 }` |
| `custom` | JSON tùy chỉnh |

**Thao tác CoE / Compliance (cap settings):**

1. Filter scope: global / brand / market / client
2. **+ Thêm rule** — type, priority, config_json
3. Toggle ON/OFF — không xóa history
4. **Sửa** config → audit ghi before/after
5. Review **Audit log (50 gần nhất)** — actor, action, entity, diff

**Read-only** nếu thiếu cap settings — badge "Read-only" hiển thị.

**API:** `GET /governance`, `POST/PATCH/DELETE /governance/rules`

---

### 6.13. Gate A console (`/email/gate-a`)

**Mục đích:** EM-5 readiness — automated checks + staged cutover checklist + sign-off template.

**Thao tác DevOps / Head Email:**

1. Review gate status cards (automated + soak)
2. Download sign-off template JSON
3. Follow checklist §B1→B4 trước prod cutover

Flag: `NEXT_PUBLIC_PTT_EMAIL_GATE_A_ENABLED=1`  
API: `/api/v1/email/gate-a/status`, `/readiness`, `/signoff-template`

---

## 7. Luồng nghiệp vụ end-to-end

### 7.1. Flow F1 — Template → Campaign → Send (spec §4.1)

```
Segment (E-07) → Template (E-08) → Campaign draft (E-09)
→ Preflight (E-09c) → Approval (staff + portal) → Schedule
→ Worker → ESP → Webhooks → Stats (E-12)
```

**Business rules (spec §6.1):**

1. Không enqueue nếu `consent_status != opted_in`
2. Hard suppression always excluded
3. Frequency cap 7d per workspace/governance
4. Quiet hours respect timezone
5. Approval bắt buộc nếu audience > threshold

### 7.2. Flow F2 — Capture → Consent (spec §4.2)

```
Form submit → POST /api/v1/email/capture
→ contact upsert → consent_records append
→ (optional) double opt-in email → confirm token → opted_in
→ eligible for segments
```

Embed form landing page:

```html
<form action="https://api.pttads.vn/api/v1/email/capture" method="POST">
  <input type="hidden" name="client_id" value="UUID" />
  <input type="email" name="email" required />
  <input type="text" name="first_name" />
  <button type="submit">Đăng ký</button>
</form>
```

### 7.3. Flow F3 — Deliverability incident (spec §4.3)

```
Webhook complaint spike → auto-pause domain
→ Slack/Teams alert (P1.3) → E-11 console
→ diagnose → warm-up recovery → resume campaigns
```

### 7.4. Flow F4 — Client approval portal (spec §4.4)

```
Strategist submit → Portal notification → P-EMAIL-02 review preview
→ Approve/Reject → campaign status update → schedule per policy
```

### 7.5. Flow F5 — Suppression & unsubscribe (spec §4.5)

```
One-click unsub / complaint / hard bounce → webhook ingest
→ suppression_entries → remove from segments → skip send queue → audit
```

---

## 8. Cron, jobs & tự động hóa

### 8.1. Job types (`ptt_jobs` handlers)

| Job type | Handler | Trigger |
|----------|---------|---------|
| `email_send_batch` | `ptt_email/sender.py` | Campaign approved / schedule due |
| `email_segment_compute` | segment refresh | Manual compute / timer |
| `email_domain_verify` | deliverability | Daily / manual verify |
| `email_engagement_ingest` | webhook worker | ESP webhook POST |
| `email_clickhouse_export` | `ptt_email/bi_clickhouse.py` | Hourly timer |
| `email_journey_scan` | journey engine | Every 1 min (B4) |
| `email_report_schedule` | PDF generator | Weekly cron |

### 8.2. Systemd units (architecture §13.2)

| Unit | Schedule |
|------|----------|
| `ptt-email-send-worker.service` | Always on |
| `ptt-email-campaign-schedule.timer` | Every 1 min |
| `ptt-email-journey.timer` | Every 1 min |
| `ptt-email-domain-verify.timer` | Daily 06:00 |
| `ptt-email-clickhouse-export.timer` | Hourly |
| `ptt-email-deliverability-scan.timer` | Every 15 min |
| `ptt-email-soak.timer` | Daily (Gate A evidence) |

### 8.3. Temporal workflows

- `EmailCampaignApprovalWorkflow` — staff + optional client approver
- Journey enrollment (EM-12) — long-running automation state

---

## 9. Client Portal Email

Flag: `PTT_EMAIL_PORTAL_ENABLED=1` (B3)

| Screen | Route | Chức năng |
|--------|-------|-----------|
| P-EMAIL-01 | `/email` | Dashboard KPI client |
| P-EMAIL-02 | `/email/approvals` | Approval inbox + preview |
| P-EMAIL-03 | `/email/campaigns/:id` | Campaign performance |

**Setup portal pilot:**

1. Map client UUID ↔ portal user (`client_channel_accounts` / portal bridge)
2. Bật `PTT_EMAIL_PORTAL_ENABLED=1`
3. Client approver login → test approve E2E
4. Verify Temporal workflow completes → campaign `approved`

API: Nest `portal-email/` module — scoped JWT `client_id`.

---

## 10. Trang public & capture API

Standalone minimal layout — không admin shell.

| ID | Route | Mô tả |
|----|-------|-------|
| P-EMAIL-PUB-01 | `/email/public/preferences/:token` | Preference center — update topics |
| P-EMAIL-PUB-02 | `/email/public/unsubscribe/:token` | One-click unsubscribe |
| P-EMAIL-PUB-03 | `/email/public/confirm/:token` | Double opt-in confirmation |

**Token generation:** Backend tạo signed token khi gửi email capture/confirmation — không expose PII trong URL path.

**Public API (no auth):**

| Method | Path | Mô tả |
|--------|------|-------|
| POST | `/api/v1/email/capture` | Form submission |
| GET/POST | preference/unsub routes | Token-scoped updates |

---

## 11. Gates, QA & nghiệm thu

### 11.1. Gate scripts theo phase

| Phase | Script | Mô tả |
|-------|--------|-------|
| EM-0 | `./scripts/phase0_email_hub_kickoff_gate.sh` | Hub + schema |
| EM-1 | `./scripts/phase1_email_ops_gate.sh` | Capture/profile |
| EM-2 | `./scripts/phase2_email_send_mvp_gate.sh` | Send MVP |
| EM-3 | `./scripts/phase3_email_enterprise_gate.sh` | Deliverability/BI |
| EM-4 | `./scripts/phase4_email_portal_gate.sh` | Portal |
| EM-5 | `./scripts/phase5_email_prod_pilot_gate.sh` | Gate A prod |
| §13 | `./scripts/email_handoff_gate.sh` | Playwright handoff |
| P1 | `./scripts/email_p1_gate.sh` | UX parity QA |
| Full | `./scripts/email_mkt_full_regression_gate.sh` | Regression all waves |

### 11.2. Playwright E2E

```bash
export OPS_E2E_API_URL=http://127.0.0.1:3000
export OPS_EMAIL_HANDOFF_CLIENT_ID=<pilot-uuid>
EMAIL_HANDOFF_SKIP_E2E=0 ./scripts/playwright_ops_email_handoff_e2e.sh
```

Spec: `services/ops-web/e2e/email-handoff.spec.ts` — hub, drill-down, governance, segments RFM, deliverability wizard, reports BI, mobile smoke.

### 11.3. Human sign-off Gate A

Template: `docs/evidence/em5-email-pilot-signoff.template.json`  
Completed: `docs/evidence/em5-email-pilot-signoff.json` (prod pilot)

---

## 12. Xử lý sự cố thường gặp

| Triệu chứng | Nguyên nhân | Hành động |
|-------------|-------------|-----------|
| Hub banner "Schema chưa apply" | DDL chưa chạy | `./scripts/apply_pg_ddl_email_mkt.sh` |
| Menu Email không hiện | Flag off | `NEXT_PUBLIC_PTT_EMAIL_ENABLED=1` + rebuild |
| 403 trên API | Thiếu RBAC cap | `seed_staff_email_mkt_permissions.py` + gán quyền |
| Preflight fail unsub | Template thiếu link | Thêm `{{unsubscribe_url}}` |
| Compute member_count = 0 | Consent/suppression | E-05/E-06 review |
| Send queue lag cao | Worker down | Restart `ptt-worker`, check job_queue |
| ESP dry-run only | Flag dev | `PTT_EMAIL_ESP_DRY_RUN=0` + API key |
| Webhook không ingest | URL/signature | Verify nginx `/api/v1/webhooks/email` |
| Grafana trống trên E-12 | URL chưa set | `PTT_EMAIL_GRAFANA_URL` |
| Complaint spike | List hygiene / content | Pause domain E-11 → runbook incident |
| Portal approve stuck | Temporal | Check workflow status + logs |

Runbook chi tiết: [`runbooks/email-deliverability-incident.md`](runbooks/email-deliverability-incident.md)

---

## 13. Checklist go-live

In A4: [`forms/email-marketing-ops-checklist-a4.html`](forms/email-marketing-ops-checklist-a4.html)

### 13.1. Infrastructure

- [ ] PG `email_mkt.*` applied + verified
- [ ] RBAC caps seeded + staff assigned
- [ ] Nest + ops-web + worker healthy
- [ ] Nginx routes `/email/*` + `/api/v1/email/*`
- [ ] Backup procedure documented

### 13.2. Pilot client

- [ ] Workspace configured (from/reply, ESP, caps)
- [ ] Domain verified SPF/DKIM/DMARC
- [ ] ≥100 contacts với consent opted_in
- [ ] Test segment compute > 0 eligible

### 13.3. Send path

- [ ] Template preflight pass
- [ ] 1 test campaign dry-run OK
- [ ] 1 real ESP send pilot OK (B2)
- [ ] Webhook engagement received
- [ ] Bounce test → auto suppression

### 13.4. Ops & monitoring

- [ ] Hub alerts + Slack/Teams tested
- [ ] Soak ≥7 days (`phase5_email_soak_record.sh`)
- [ ] Gate A PASS (`phase5_email_prod_pilot_gate.sh`)
- [ ] P1 gate PASS (`email_p1_gate.sh`)
- [ ] Human sign-off JSON completed

### 13.5. Documentation & training

- [ ] Team trained on E-01…E-13 flows
- [ ] Checklist A4 printed/shared
- [ ] PPT: `docs/Email_Marketing_Ops_Training.pptx`

---

## 14. Phụ lục — env, API, runbook

### 14.1. Env template index

| File | Use case |
|------|----------|
| `deploy/env.em5-prod.example` | Gate A pilot base |
| `deploy/env.em5-prod-send.example` | Real ESP send |
| `deploy/env.em6-send.example` | Send platform hardening |
| `deploy/env.em7-wave2.example` | Wave 2 enterprise |
| `deploy/env.em8-wave3.example` | Wave 3 depth |
| `deploy/env.em9-wave4.example` | Portal wave 4 |

### 14.2. API map (Nest `/api/v1/email/`)

| Method | Path | RBAC |
|--------|------|------|
| GET | `/hub` | view |
| GET | `/governance` | view |
| POST/PATCH/DELETE | `/governance/rules` | settings |
| GET | `/clients` | view |
| GET/POST | `/workspaces` | view / settings |
| GET/POST | `/contacts/import` | view / write |
| GET/POST | `/consent` | view / compliance |
| GET/POST | `/suppression` | view / compliance |
| GET/POST/PATCH | `/segments` | view / write |
| POST | `/segments/:id/compute` | write |
| GET/POST/PATCH | `/templates` | view / write |
| GET/POST/PATCH | `/campaigns` | view / write |
| POST | `/campaigns/:id/submit` | write |
| POST | `/campaigns/:id/schedule` | approve |
| GET | `/campaigns/:id/preflight` | view |
| GET/POST | `/deliverability/domains` | view / deliverability |
| POST | `/deliverability/domains/:id/verify` | deliverability |
| GET | `/reports/summary` | view |
| GET | `/reports/bi-status` | reports |
| POST | `/reports/export-clickhouse` | reports |
| GET/POST | `/journeys` | view / write |
| GET | `/gate-a/status` | view |

Chi tiết OpenAPI: `schemas/email/` (architecture doc §7).

### 14.3. PostgreSQL schema chính

| Table | Mô tả |
|-------|-------|
| `email_mkt.clients` | Client master |
| `email_mkt.workspaces` | Per-client email workspace |
| `email_mkt.contacts` | Unified profile |
| `email_mkt.consent_records` | Append-only consent |
| `email_mkt.suppression_entries` | Suppression master |
| `email_mkt.segments` | Segment definitions |
| `email_mkt.templates` | Email templates |
| `email_mkt.campaigns` | Broadcast campaigns |
| `email_mkt.journeys` | Automation graphs |
| `email_mkt.domains` | Sending domains + DNS status |
| `email_mkt.engagement_events` | Open/click/bounce |
| `email_mkt.rules` | Governance rules |
| `email_mkt.audit_log` | Governance audit |

DDL: `deploy/sql/email_mkt_pg_schema.sql`

### 14.4. KPI targets (spec §9)

| KPI | Target |
|-----|--------|
| Delivery rate | ≥ 98% |
| Hard bounce rate | < 0.5% |
| Complaint rate | < 0.1% |
| Domain auth pass | 100% SPF/DKIM/DMARC |
| Approval SLA | < 24h business hours |
| Send queue lag P95 | < 5 min |

### 14.5. Tài liệu & runbook liên quan

| Tài liệu | Mô tả |
|----------|-------|
| [`EMAIL_MARKETING_COMPLETION_ROADMAP.md`](EMAIL_MARKETING_COMPLETION_ROADMAP.md) | Lộ trình EM-0→EM-5, P1/P2 |
| [`runbooks/email-marketing-prod-pilot-checklist.md`](runbooks/email-marketing-prod-pilot-checklist.md) | Gate A human checklist |
| [`runbooks/email-deliverability-incident.md`](runbooks/email-deliverability-incident.md) | Incident response |
| [`forms/email-marketing-ops-checklist-a4.html`](forms/email-marketing-ops-checklist-a4.html) | Checklist in A4 |
| [`Email_Marketing_Ops_Training.pptx`](Email_Marketing_Ops_Training.pptx) | Slide đào tạo |
| `scripts/generate_email_marketing_training_pptx.py` | Regenerate PPT |

### 14.6. Regenerate training PPT

```bash
python3 scripts/generate_email_marketing_training_pptx.py
# Output: docs/Email_Marketing_Ops_Training.pptx
```

---

**Lịch sử tài liệu**

| Version | Date | Change |
|---------|------|--------|
| 1.0 | 2026-07-25 | P1 brief ops guide |
| 2.0 | 2026-07-25 | Full setup + screen-by-screen theo EM-OS spec v1.3 & UI/UX v1.3 |
