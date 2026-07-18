# Runbook — Cutover write traffic Leads CRM (Phase 2 W8)

> **Mục tiêu:** Assign / update lead production ghi **PostgreSQL `crm_leads` (OLTP primary)** qua NestJS. SQLite `ptt.db` giữ **shadow** cho rollback Hub/SOP/legacy. Rollback write ≤ 5 phút.

**Phụ thuộc:** Phase 1b B8 read cutover ổn định · B9 staging write POC · W2 shadow sync · W7 write dual-run soak.

**PRD:** [`2026-07-17-prd-phase-2.md`](../specs/2026-07-17-prd-phase-2.md) · **Kiến trúc:** [`2026-07-17-architecture-phase-2.md`](../specs/2026-07-17-architecture-phase-2.md)

---

## 1. Kiến trúc sau cutover write

| Path | Write upstream | DB ghi | Ghi chú |
|------|----------------|--------|---------|
| `PATCH /api/v1/leads/:id` (Nest) | Nest :3000 | **PostgreSQL** | Source of truth sau cutover |
| `POST /api/v1/leads` (Nest) | Nest :3000 | **PostgreSQL** | Prod id allocator (không dùng range 900M staging) |
| `POST /api/crm/leads/:id/assign` (Flask UI) | Flask **hoặc** proxy Nest | SQLite **hoặc** PG | Theo `PTT_LEADS_WRITE_UPSTREAM` (W6) |
| Ingest webhook / queue | Flask worker | SQLite → PG replica | `sync_lead_replica` vẫn chạy trong transition |
| Shadow job | `sync_lead_shadow` | PG → SQLite | Rollback read legacy modules |

```mermaid
flowchart LR
    UI[Agency UI assign]
    NGX[Nginx optional]
    FL[Flask /api/crm]
    NE[Nest PATCH /api/v1/leads]
    PG[(PG crm_leads OLTP)]
    SQL[(SQLite shadow)]
    SH[sync_lead_shadow]

    UI --> FL
    FL -->|WRITE_UPSTREAM=nest| NE
    FL -->|WRITE_UPSTREAM=flask| SQL
    NE --> PG
    PG --> SH --> SQL
```

**Hai lớp điều khiển:**

1. **Nest** — `PTT_LEADS_WRITE_ENABLED=1` bật route `POST/PATCH /api/v1/leads` (mặc định prod = `0` đến cutover window).
2. **Flask strangler** — `PTT_LEADS_WRITE_UPSTREAM=nest|flask` định tuyến assign UI/legacy API (W6).

**Sync mode (PG `crm_leads_sync_state.sync_mode`):**

| Mode | Replica SQLite→PG | Shadow PG→SQLite | Primary write |
|------|-------------------|------------------|---------------|
| `sqlite_to_pg` | ✅ | optional | SQLite (pre-cutover) |
| `pg_primary` | pause / ingest only | ✅ | PostgreSQL |
| `paused` | ❌ | ❌ | Manual ops |

---

## 2. Feature flags

| Flag | Pre-cutover | Cutover window | Rollback |
|------|-------------|----------------|----------|
| `PTT_LEADS_READ_UPSTREAM` | `nest` | `nest` | `nest` (read giữ Nest) |
| `PTT_LEADS_WRITE_ENABLED` | `0` | **`1`** | **`0`** |
| `PTT_LEADS_WRITE_UPSTREAM` | `flask` | **`nest`** | **`flask`** |
| `PTT_LEAD_SHADOW_SYNC` | `0` | **`1`** | `1` (giữ shadow) hoặc `0` |
| `PTT_LEAD_REPLICA_SYNC` | `1` | `0` hoặc `1`* | **`1`** |
| `PTT_LEADS_READ_SOURCE` (Nest) | `pg` | `pg` | `pg` |
| `PTT_EVENT_PUBLISH_RMQ` | `1` | `1` | `1` |

\* Transition: replica sync ingest-only; sau soak 48h tắt replica nếu ingest đã queue→PG.

**Nest `.env` production:**

```bash
DATABASE_URL=postgresql://ptt:***@127.0.0.1:5432/ptt_agency
PTT_LEADS_READ_SOURCE=pg
PTT_LEADS_WRITE_ENABLED=1          # bật tại cutover
PTT_CRM_INTERNAL_KEY=<shared-secret>
PTT_CRM_API_AUTH_DISABLED=0
```

**Flask `/var/www/ptt/.env`:**

```bash
PTT_LEADS_READ_UPSTREAM=nest
PTT_LEADS_WRITE_UPSTREAM=nest      # cutover; flask = rollback
PTT_NEST_LEADS_URL=http://127.0.0.1:3000
PTT_CRM_INTERNAL_KEY=<shared-secret>
PTT_LEAD_SHADOW_SYNC=1
PTT_LEAD_REPLICA_SYNC=0            # sau cutover pg_primary
DATABASE_URL=postgresql://ptt:***@127.0.0.1:5432/ptt_agency
```

---

## 3. Pre-flight (staging) — gate trước prod

### 3.1 Schema & data

```bash
docker compose up -d postgres
./scripts/apply_pg_ddl_v2_leads.sh    # nếu chưa có v2
./scripts/apply_pg_ddl_v3.sh
./scripts/sync_leads_backfill.sh
./scripts/reconcile_lead_replica.sh 50

# Validate FK (sau orphan cleanup)
# ALTER TABLE crm_leads VALIDATE CONSTRAINT crm_leads_agency_client_fk;
```

Checklist:

- [ ] DDL v3 applied (`crm_leads` OLTP columns, `crm_leads_shadow_state`, `hub_campaign_map`)
- [ ] SQLite ↔ PG count reconcile pass (non-duplicate leads)
- [ ] Orphan `agency_client_id` = 0 trước FK validate

### 3.2 Nest write + events

```bash
cd services/ptt-crm-api && npm ci && npm test && npm run test:e2e

export PTT_LEADS_WRITE_ENABLED=1
export PTT_LEADS_READ_SOURCE=pg
./scripts/local_crm_api_up.sh &
./scripts/local_leads_write_staging.sh
```

Checklist:

- [ ] `POST/PATCH /api/v1/leads` e2e pass (12 tests)
- [ ] `/health` → `leads_write_enabled: true` (staging)
- [ ] `LeadAssigned` row trong `domain_events` + RMQ publish ≤ 30s
- [ ] OpenAPI write frozen CI (`./scripts/ci_openapi_write_freeze.sh` + GitHub `phase2-write-gates.yml`)

### 3.3 Shadow + write dual-run soak

```bash
export PTT_LEAD_SHADOW_SYNC=1
export PTT_LEADS_WRITE_ENABLED=1

# Sau mỗi Nest PATCH staging — shadow sync
./scripts/sync_lead_shadow.sh

# Soak ≥ 48h staging: assign qua Nest, shadow lag ≤ 1 phút
./scripts/dual_run_write_check.py --sample 50
./scripts/sync_lead_shadow.sh reconcile
```

Checklist:

- [ ] Write dual-run mismatch = **0%** staging ≥ 48h (`dual_run_write_check.py`)
- [ ] Shadow lag ≤ 1 phút (`crm_leads_shadow_state.last_shadow_at`)
- [ ] B8 read cutover prod stable ≥ 7 ngày (prerequisite)

### 3.5 Staging pilot (automated gate)

```bash
# Env template
set -a && source deploy/env.staging-write-pilot.example && set +a

# Nest + PG up, then:
./scripts/staging_write_cutover_pilot.sh --apply-sync-mode --drill

# Report JSON: .local-dev/staging-write-pilot-report.json
```

Checklist pilot script:

- [ ] `preflight` — Nest `/health` + `leads_write_enabled`, PG v3, env flags
- [ ] `nest_write_smoke` — POST/PATCH staging lead
- [ ] `shadow_sync` — incremental PG → SQLite
- [ ] `post_write` — dual-run 0 mismatch, shadow lag, `LeadAssigned` event
- [ ] `rollback_drill` (optional `--drill`) — flags rollback ≤ 5 phút

### 3.6 Prod cutover gates (trước §4 change window)

**OpenAPI freeze (CI):**

```bash
./scripts/ci_openapi_write_freeze.sh
# PR: thay đổi schemas/crm/leads-v1-write.openapi.yaml → version bump bắt buộc
```

**48h soak evidence (staging VPS):**

```bash
# Bật timer ghi mẫu dual-run mỗi giờ
sudo cp ptt-write-soak.service ptt-write-soak.timer /etc/systemd/system/
sudo systemctl enable --now ptt-write-soak.timer

# Hoặc thủ công sau mỗi assign test:
./scripts/write_soak_record.sh

# Xem gate 48h
./scripts/dual_run_write_check.py --soak-report --quiet

# Prod gate tổng hợp (chạy trước cutover prod)
./scripts/write_cutover_prod_gates.sh
# Report: .local-dev/write-cutover-prod-gates.json
```

Checklist prod gates:

- [ ] `ci_openapi_write_freeze.sh` green trên CI
- [ ] Soak log ≥ 48h span, ≥ 24 OK samples, 0 mismatch (`PTT_WRITE_SOAK_LOG`)
- [ ] Live `dual_run_write_check.py` pass ngay trước cutover
- [ ] Staging pilot report pass (`staging_write_cutover_pilot.sh`)

### 3.7 P1 — LeadAssigned + rollback drill evidence

**Idempotency migration (catalog key):**

```bash
./scripts/apply_pg_ddl_v3_events_idempotency.sh
# Adds domain_events.idempotency_key — lead:{lead_id}:assigned:{owner_id}
```

**LeadAssigned outbox → RMQ E2E (≤ 30s publish lag):**

```bash
export PTT_LEADS_WRITE_ENABLED=1
export PTT_EVENT_PUBLISH_RMQ=1   # optional — outbox publish still verified via published_at

./scripts/lead_assigned_rmq_e2e.sh
# Report: .local-dev/lead-assigned-rmq-e2e.json
```

Checklist:

- [ ] Nest PATCH assign → `domain_events` row with `idempotency_key`
- [ ] Re-assign same owner after round-trip → **1** row per catalog key
- [ ] `run_event_publisher` / worker → `published_at` within 30s
- [ ] Staging pilot: `./scripts/staging_write_cutover_pilot.sh --lead-assigned-e2e`

**Rollback drill evidence (≤ 5 min):**

```bash
./scripts/local_leads_write_cutover_drill.sh
# or flags-only record:
./scripts/rollback_drill_record.py

# Report: .local-dev/rollback-drill-evidence.json
```

Checklist:

- [ ] `rollback_elapsed_sec` ≤ 300
- [ ] `PTT_LEADS_WRITE_UPSTREAM=flask` after drill
- [ ] Evidence attached to runbook §7 incident log when prod cutover

### 3.8 Phase 2 completion gate pack (staging)

**One-command staging validation:**

```bash
set -a && source deploy/env.staging-phase2-gates.example && set +a

# Prerequisites per client: seed_meta_channel_account + sync_hub_campaign_map
# Local dev (no PG clients): ./scripts/bootstrap_local_phase2_gate_clients.py
# Nest write: ./scripts/local_crm_api_up.sh

# Optional — seed 48h soak for gate validation (staging; prod uses timer):
./scripts/seed_write_soak_staging.sh

./scripts/staging_phase2_gate_pack.sh
# Report: .local-dev/phase2-ops-gate-report.json
```

Includes:

- Closed-loop **≥3 clients** (`PTT_CLOSED_LOOP_CLIENT_CODES`)
- Write pilot + `--lead-assigned-e2e` + rollback drill
- `write_cutover_prod_gates.sh` (OpenAPI + 48h soak)
- UAT automated subset

**Prod cutover assistant (dry-run default):**

```bash
./scripts/prod_write_cutover.sh              # preflight + W5 defer note
./scripts/prod_write_cutover.sh --apply      # sync_mode pg_primary only
# Report: .local-dev/prod-write-cutover-report.json
```

**UAT + sign-off:**

- Checklist: [phase2-uat-signoff.md](./phase2-uat-signoff.md)
- **VPS prod cutover checklist:** [vps-phase2-production-cutover-checklist.md](./vps-phase2-production-cutover-checklist.md)
- `./scripts/phase2_uat_gate.py`
- Meta runbooks: [meta-token-refresh.md](./meta-token-refresh.md), [meta-insights-replay.md](./meta-insights-replay.md)
- Sentry: [sentry-phase2-dashboards.md](./sentry-phase2-dashboards.md)

**W5 defer:** Prod `POST /api/v1/leads` → Phase 2.1. Phase 2 prod cutover = PATCH assign/status only.

### 3.4 W6 Flask proxy (UI assign qua Nest)

Module: `ptt_crm/leads_write_upstream.py` — proxy khi `PTT_LEADS_WRITE_UPSTREAM=nest`.

Trước prod cutover UI, xác nhận:

- [ ] `POST /api/crm/leads/:id/assign` proxy Nest khi `PTT_LEADS_WRITE_UPSTREAM=nest`
- [ ] UX Agency Ops assign modal không đổi (reason, owner picker)
- [ ] Assignment log SQLite mirror (`crm_lead_assignment_logs`)
- [ ] Staging smoke: `./scripts/local_leads_write_staging.sh` + assign UI

> API-only cutover (Nest trực tiếp) không cần flag nest trên Flask; UI assign cần `WRITE_UPSTREAM=nest`.

---

## 4. Cutover production (change window)

**Thứ tự khuyến nghị** — tổng thời gian ~15 phút, rollback ≤ 5 phút.

### Bước 0 — Freeze & backup

```bash
# Thông báo CSKH + AM — freeze assign bulk trong window
cp /var/www/ptt/ptt.db /var/backups/ptt-$(date +%Y%m%d-%H%M)-pre-write-cutover.db
pg_dump "$DATABASE_URL" -Fc -f /var/backups/ptt_agency-$(date +%Y%m%d-%H%M).dump
```

### Bước 1 — Bật shadow sync (PG → SQLite)

```bash
# Flask .env
PTT_LEAD_SHADOW_SYNC=1

# Cron / worker job (mỗi phút)
# enqueue: sync_lead_shadow incremental
./scripts/sync_lead_shadow.sh
```

Verify:

```bash
./scripts/sync_lead_shadow.sh reconcile
# shadow_state.last_shadow_at gần NOW()
```

### Bước 2 — Set sync_mode pg_primary

```bash
psql "$DATABASE_URL" -c "
  UPDATE crm_leads_sync_state
  SET sync_mode = 'pg_primary', updated_at = NOW()
  WHERE id = 1;
"
```

Tắt replica sync ghi ngược (tránh loop):

```bash
PTT_LEAD_REPLICA_SYNC=0   # Flask .env + worker
sudo systemctl restart ptt-worker
```

### Bước 3 — Bật Nest write

```bash
# /etc/ptt-crm-api.env hoặc service drop-in
PTT_LEADS_WRITE_ENABLED=1

sudo systemctl restart ptt-crm-api
curl -s http://127.0.0.1:3000/health | jq '.leads_write_enabled'
# → true
```

Smoke S2S:

```bash
export KEY="$PTT_CRM_INTERNAL_KEY"
curl -sf -H "X-PTT-Internal-Key: $KEY" -X PATCH \
  "https://api.pttads.vn/api/v1/leads/<TEST_LEAD_ID>" \
  -H 'Content-Type: application/json' \
  -d '{"owner_id":1,"assigned_by":"cutover-smoke"}' | jq .
```

### Bước 4 — Chuyển write upstream (Flask UI / legacy)

```bash
# Flask .env
PTT_LEADS_WRITE_UPSTREAM=nest

sudo systemctl restart ptt
```

### Bước 5 — Verify end-to-end

```bash
# PG authoritative
psql "$DATABASE_URL" -c "
  SELECT sqlite_lead_id, owner_id, status, write_source, updated_at
  FROM crm_leads WHERE sqlite_lead_id = <TEST_LEAD_ID>;
"

# Shadow caught up
./scripts/sync_lead_shadow.sh
./scripts/dual_run_write_check.py --sample 20 --quiet

# Event outbox
psql "$DATABASE_URL" -c "
  SELECT event_type, aggregate_id, created_at, published_at
  FROM domain_events
  WHERE event_type = 'LeadAssigned'
  ORDER BY created_at DESC LIMIT 5;
"
```

Manual smoke (Agency Ops):

- [ ] Assign 1 lead từ UI → owner_id đúng trên PG + shadow ≤ 1 phút
- [ ] Lead detail / list read vẫn OK (B8)
- [ ] Assignment log hiển thị

---

## 5. macOS local / dev

Không có `systemctl` — dùng script local:

```bash
docker compose up -d postgres
./scripts/apply_pg_ddl_v3.sh

export PTT_LEADS_WRITE_ENABLED=1
export PTT_LEAD_SHADOW_SYNC=1
export PTT_LEADS_WRITE_UPSTREAM=nest
export PTT_NEST_LEADS_URL=http://127.0.0.1:3000

./scripts/local_crm_api_up.sh &          # terminal 1
./scripts/local_phase1_up.sh             # terminal 2

./scripts/local_leads_write_staging.sh
./scripts/sync_lead_shadow.sh
./scripts/dual_run_write_check.py --sample 10
./scripts/local_leads_write_cutover_drill.sh
```

---

## 6. Monitor sau cutover (7 ngày)

| Metric | Target | Nguồn |
|--------|--------|-------|
| Write dual-run mismatch | 0% staging; prod reconcile daily | `dual_run_write_check.py` |
| Shadow lag | ≤ 5 phút | `crm_leads_shadow_state` |
| Nest PATCH p95 | < 500ms | Sentry / APM |
| LeadAssigned publish lag | ≤ 30s | `domain_events.published_at` |
| Nest write 5xx | < 0.1% | Sentry |

Cron / systemd đề xuất:

```bash
# Khuyến nghị — shadow mỗi phút (systemd, repo root)
sudo cp ptt-lead-shadow-sync.service ptt-lead-shadow-sync.timer /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now ptt-lead-shadow-sync.timer

# Meta closed-loop (Phase 2)
sudo cp ptt-meta-insights.service ptt-meta-insights.timer /etc/systemd/system/
sudo cp ptt-meta-token-refresh.service ptt-meta-token-refresh.timer /etc/systemd/system/
sudo systemctl enable --now ptt-meta-insights.timer ptt-meta-token-refresh.timer

# Legacy cron shadow
# * * * * * deploy cd /var/www/ptt && PTT_LEAD_SHADOW_SYNC=1 ./scripts/sync_lead_shadow.sh incremental

# Reconcile hàng ngày 06:00
0 6 * * * ptt cd /var/www/ptt && ./scripts/dual_run_write_check.py --sample 100 --quiet
```

---

## 7. Rollback write (≤ 5 phút)

**Kích hoạt khi:** Nest write lỗi hàng loạt · PG unavailable · owner_id sai hàng loạt · CSKH blocked.

### 7.1 Khẩn cấp — về SQLite OLTP

```bash
# 1. Flask assign lại SQLite
PTT_LEADS_WRITE_UPSTREAM=flask
sudo systemctl restart ptt

# 2. Tắt Nest write (404 routes)
PTT_LEADS_WRITE_ENABLED=0
sudo systemctl restart ptt-crm-api

# 3. Sync mode
psql "$DATABASE_URL" -c "
  UPDATE crm_leads_sync_state SET sync_mode = 'sqlite_to_pg', updated_at = NOW() WHERE id = 1;
"

# 4. Bật lại replica sync (SQLite truth)
PTT_LEAD_REPLICA_SYNC=1
PTT_LEAD_SHADOW_SYNC=0          # tùy chọn — pause shadow
sudo systemctl restart ptt-worker
```

Verify rollback:

```bash
# Assign qua Flask UI — ghi SQLite
curl -sf -X POST -b cookies.txt \
  "https://pttads.vn/api/crm/leads/<ID>/assign" \
  -H 'Content-Type: application/json' \
  -d '{"to_user_id":2,"reason":"rollback drill"}' | jq .

sqlite3 /var/www/ptt/ptt.db "SELECT id, owner_id, status FROM crm_leads WHERE id=<ID>;"
```

**Read traffic:** Giữ `PTT_LEADS_READ_UPSTREAM=nest` nếu B8 ổn — chỉ write rollback. Nếu PG data nghi ngờ: rollback read theo [cutover-leads-read-b8.md](./cutover-leads-read-b8.md) §5.

### 7.2 Nest down, PG OK

```bash
PTT_LEADS_WRITE_UPSTREAM=flask
PTT_LEADS_WRITE_ENABLED=0
sudo systemctl restart ptt ptt-crm-api
```

SQLite shadow + replica sync đảm bảo Flask modules hoạt động.

### 7.3 PG/SQLite drift sau rollback

```bash
./scripts/sync_leads_backfill.sh          # SQLite → PG catch-up
./scripts/reconcile_lead_replica.sh 100
```

Ghi incident: thời điểm cutover, thời điểm rollback, lead ids bị ảnh hưởng.

---

## 8. Rollback drill (staging / local)

**Mục tiêu:** Toàn bộ rollback ≤ 5 phút, có log.

```bash
chmod +x scripts/local_leads_write_cutover_drill.sh
./scripts/local_leads_write_cutover_drill.sh
```

Drill checklist:

| Bước | Hành động | SLA |
|------|-----------|-----|
| T0 | Ghi timestamp, bật `WRITE_UPSTREAM=nest` + Nest write | — |
| T+1 | PATCH test lead qua Nest | < 30s |
| T+2 | Shadow sync + dual_run verify | < 2 phút |
| T+3 | Rollback flags (`flask`, `WRITE_ENABLED=0`) | < 1 phút |
| T+4 | Assign qua Flask SQLite verify | < 1 phút |
| T+5 | Ghi kết quả drill | — |

Template change log:

```
Date: YYYY-MM-DD
Operator: ...
Environment: staging | prod-drill
Cutover flags applied: OK / FAIL
Rollback flags applied: OK / FAIL
Elapsed rollback: __ min __ sec
dual_run_write_check: OK / FAIL
Notes: ...
```

---

## 9. Out of scope W8

- Deprecate Flask CRM monolith → Phase 3–4
- Hub / SOP / cases PG migration
- `POST /api/v1/leads` prod create (W5) — có thể defer Phase 2.1
- JWT / Keycloak auth
- Meta closed-loop (Track M) — runbook riêng insights sync

---

## 10. Artifacts

| File | Mô tả |
|------|-------|
| `docs/runbooks/cutover-leads-write-phase2.md` | Runbook này (W8) |
| `docs/runbooks/cutover-leads-read-b8.md` | Read cutover (prerequisite) |
| `scripts/staging_write_cutover_pilot.sh` | Staging pilot gates + JSON report (P0 #3) |
| `deploy/env.staging-write-pilot.example` | Staging env template |
| `ptt_crm/staging_write_pilot.py` | Pilot gate engine |
| `scripts/ci_openapi_write_freeze.sh` | OpenAPI write v1.0.0 freeze CI |
| `scripts/write_cutover_prod_gates.sh` | Prod gates — OpenAPI + 48h soak + live dual-run |
| `scripts/write_soak_record.sh` | Hourly soak sample |
| `ptt-write-soak.timer` | Systemd hourly soak evidence |
| `ptt_crm/write_soak_evidence.py` | 48h soak gate evaluator |
| `.github/workflows/phase2-write-gates.yml` | GitHub CI write gates |
| `scripts/local_leads_write_cutover_drill.sh` | Drill local/staging |
| `scripts/dual_run_write_check.py` | PG ↔ SQLite ↔ Nest write compare (W7) |
| `scripts/sync_lead_shadow.sh` | Shadow sync + reconcile (W2) |
| `scripts/local_leads_write_staging.sh` | Nest write smoke (B9) |
| `ptt_crm/lead_shadow_sync.py` | PG → SQLite shadow |
| `ptt_crm/leads_write_upstream.py` | Flask assign → Nest PATCH (W6) |
| `ptt_crm/dual_run_write.py` | Write dual-run engine |
| `services/ptt-crm-api/` | Nest read + write |
| `schemas/crm/leads-v1-write.openapi.yaml` | Write contract v1.0.0 frozen |

| Env var | Giá trị cutover | Giá trị rollback |
|---------|-----------------|------------------|
| `PTT_LEADS_WRITE_ENABLED` | `1` | `0` |
| `PTT_LEADS_WRITE_UPSTREAM` | `nest` | `flask` |
| `PTT_LEAD_SHADOW_SYNC` | `1` | `0` hoặc `1` |
| `PTT_LEAD_REPLICA_SYNC` | `0` | `1` |
| `sync_mode` (PG) | `pg_primary` | `sqlite_to_pg` |

---

| Version | Date | Change |
|---------|------|--------|
| 1.0 | 2026-07-17 | W8 write cutover + rollback runbook |
