# VPS Checklist — Phase 2 Production Cutover

> **Host production:** `https://pttads.vn` (Flask Agency) · `https://api.pttads.vn` (Nest CRM API)  
> **Repo root trên VPS:** `/var/www/ptt`  
> **Nest service:** `/var/www/ptt/services/ptt-crm-api` · systemd `ptt-crm-api.service`  
> **Change window:** ~15 phút · rollback SLA ≤ 5 phút  
> **W5 defer:** Prod `POST /api/v1/leads` → Phase 2.1. Phase 2 chỉ **PATCH assign/status**.

**Runbook chi tiết:** [cutover-leads-write-phase2.md](./cutover-leads-write-phase2.md) §4–§8  
**Staging gate pack:** [cutover-leads-write-phase2.md](./cutover-leads-write-phase2.md) §3.8  
**UAT sign-off:** [phase2-uat-signoff.md](./phase2-uat-signoff.md)

---

## 0. Thông tin host (điền trước cutover)

| Mục | Giá trị |
|-----|---------|
| VPS hostname | `________________` |
| SSH user | `deploy` (hoặc `ptt`) |
| Flask unit | `ptt.service` |
| Worker unit | `ptt-worker.service` |
| Nest unit | `ptt-crm-api.service` |
| PG `DATABASE_URL` | `postgresql://ptt:***@127.0.0.1:5432/ptt_agency` |
| SQLite | `/var/www/ptt/ptt.db` |
| Nginx config | `deploy/nginx-leads-v1-cutover.conf` → `/etc/nginx/sites-enabled/` |
| Pilot client codes (≥3) | `________________, ________________, ________________` |
| Change window (ICT) | `YYYY-MM-DD HH:MM – HH:MM` |
| Operator on-call | `________________` |

---

## 1. Pre-flight (T-7 → T-1 ngày)

### 1.1 DDL & schema

```bash
cd /var/www/ptt
export DATABASE_URL=postgresql://ptt:***@127.0.0.1:5432/ptt_agency

./scripts/apply_pg_ddl_v3.sh
./scripts/apply_pg_ddl_v3_events_idempotency.sh   # LeadAssigned idempotency (P1)

.venv/bin/python -c "
from ptt_crm.pg_schema import pg_v3_ready, pg_domain_events_idempotency_ready
assert pg_v3_ready(), 'v3 missing'
assert pg_domain_events_idempotency_ready(), 'idempotency missing'
print('OK schema')
"
```

- [ ] `pg_v3_ready` = true  
- [ ] `pg_domain_events_idempotency_ready` = true  
- [ ] `crm_leads_sync_state.sync_mode` = `sqlite_to_pg` (pre-cutover)

### 1.2 Systemd Phase 2 timers

```bash
cd /var/www/ptt
sudo ./scripts/install_phase2_systemd_timers.sh
systemctl list-timers --no-pager 'ptt-*'
```

- [ ] `ptt-lead-shadow-sync.timer` active  
- [ ] `ptt-meta-insights.timer` active (02:00 ICT)  
- [ ] `ptt-meta-token-refresh.timer` active  
- [ ] `ptt-write-soak.timer` active (hourly)

**Flask `/var/www/ptt/.env` (staging trước, prod sau):**

```bash
PTT_LEAD_SHADOW_SYNC=1
PTT_META_INSIGHTS_SYNC=1
PTT_META_TOKEN_REFRESH=1
PTT_WRITE_SOAK_LOG=/var/www/ptt/.local-dev/write-soak-evidence.jsonl
PTT_TOKEN_VAULT_KEY=<base64-32-bytes>    # bắt buộc prod Meta token
SENTRY_DSN=https://...@sentry.io/...
SENTRY_ENVIRONMENT=production
```

- [ ] `PTT_TOKEN_VAULT_KEY` set (Meta token refresh)  
- [ ] `SENTRY_DSN` + `SENTRY_ENVIRONMENT=production` trên Flask, Nest, worker

### 1.3 Closed-loop ≥3 clients (Track M)

Per client code (`CLIENT_A`, `CLIENT_B`, `CLIENT_C`):

```bash
export CLIENT_CODE=CLIENT_A
export META_AD_ACCOUNT_ID=act_XXXXX
export META_ACCESS_TOKEN=EAAx...
export META_PIXEL_ID=123456789012345
export TOKEN_EXPIRES=2026-12-31
./scripts/seed_meta_channel_account.py
./scripts/sync_hub_campaign_map.sh
./scripts/staging_closed_loop_pilot.sh --sync
```

- [ ] ≥3 client active trong PG `clients`  
- [ ] Meta channel account + pixel mỗi client  
- [ ] `hub_campaign_map` ≥1 active / client  
- [ ] `daily_performance` T-1 rows sau insights sync  
- [ ] CPL tab Agency UI có data

**Env gate pack:**

```bash
cp deploy/env.staging-phase2-gates.example /var/www/ptt/.env.phase2-gates
# Sửa PTT_CLOSED_LOOP_CLIENT_CODES=<3 mã thật>
# Sửa PTT_SQLITE_PATH=/var/www/ptt/ptt.db
nano /var/www/ptt/.env.phase2-gates
```

### 1.4 Nest write + Flask flags (staging mirror)

**Nest** (`/etc/systemd/system/ptt-crm-api.service` hoặc drop-in):

```bash
PTT_LEADS_READ_SOURCE=pg
PTT_LEADS_WRITE_ENABLED=1          # staging; prod = 0 đến change window
PTT_CRM_INTERNAL_KEY=<shared-secret>
PTT_CRM_API_AUTH_DISABLED=0        # prod bắt buộc auth
```

**Flask** (staging pilot):

```bash
PTT_LEADS_READ_UPSTREAM=nest
PTT_LEADS_WRITE_UPSTREAM=nest
PTT_LEADS_WRITE_ENABLED=1
PTT_LEAD_SHADOW_SYNC=1
PTT_LEAD_REPLICA_SYNC=0
PTT_NEST_LEADS_URL=http://127.0.0.1:3000
```

```bash
sudo systemctl restart ptt-crm-api ptt ptt-worker
curl -s http://127.0.0.1:3000/health | jq '.leads_write_enabled'   # → true (staging)
```

- [ ] Nest `/health` trả `leads_write_enabled: true` (staging)  
- [ ] `./scripts/local_leads_write_staging.sh` pass (hoặc tương đương trên VPS)

---

## 2. Staging gate pack (bắt buộc trước prod)

```bash
cd /var/www/ptt
set -a && source .env.phase2-gates && set +a

# KHÔNG dùng seed soak cho prod sign-off — chỉ validate script:
# ./scripts/seed_write_soak_staging.sh   # optional staging demo

./scripts/staging_phase2_gate_pack.sh
# Report: .local-dev/phase2-ops-gate-report.json
```

**Pass criteria:**

| Step | Pass |
|------|------|
| `closed_loop_3client` | 3/3 clients OK |
| `write_pilot` | preflight + nest smoke + shadow + dual-run + `--lead-assigned-e2e` |
| `prod_gates` | OpenAPI freeze + **48h soak thật** + live dual-run + RMQ E2E + rollback drill |
| `uat_automated` | pg_v3 + idempotency + nest health + meta tables + OpenAPI CI |

- [ ] `phase2-ops-gate-report.json` → `"ok": true`  
- [ ] Sign-off template trong report đã review

**Prod gates dry-run (không apply cutover):**

```bash
./scripts/write_cutover_prod_gates.sh
# → .local-dev/write-cutover-prod-gates.json

./scripts/prod_write_cutover.sh
# → .local-dev/prod-write-cutover-report.json
```

- [ ] OpenAPI freeze CI pass  
- [ ] 48h soak: span ≥ 48h, ok_samples ≥ 24, failures = 0  
- [ ] Rollback drill ≤ 300s

---

## 3. 48h soak evidence (prod gate — timer thật)

```bash
# Bật timer (nếu chưa)
sudo systemctl enable --now ptt-write-soak.timer

# Verify hourly samples
tail -5 /var/www/ptt/.local-dev/write-soak-evidence.jsonl
./scripts/write_cutover_prod_gates.sh --skip-live-dual-run   # chỉ check soak, nếu cần
```

- [ ] Timer chạy ≥ 48h liên tục trước prod window  
- [ ] `evaluate_soak_gate`: `span_hours ≥ 48`, `ok_sample_count ≥ 24`  
- [ ] **Không** dùng `seed_write_soak_staging.sh` làm bằng chứng prod duy nhất

**Evidence file lưu kèm sign-off:**

- `.local-dev/write-soak-evidence.jsonl`  
- `.local-dev/write-cutover-prod-gates.json`

---

## 4. Meta runbooks (T-3)

| Runbook | Action | Done |
|---------|--------|------|
| [meta-token-refresh.md](./meta-token-refresh.md) | `ptt-meta-token-refresh.timer` + test refresh 1 account | [ ] |
| [meta-insights-replay.md](./meta-insights-replay.md) | Replay T-1 sau outage; verify `daily_performance` | [ ] |

```bash
# Token refresh status
systemctl status ptt-meta-token-refresh.timer
journalctl -u ptt-meta-token-refresh.service -n 20

# Insights replay (manual)
cd /var/www/ptt
export PTT_META_INSIGHTS_SYNC=1
.venv/bin/python -m ptt_meta.insights_sync --date $(date -v-1d +%Y-%m-%d)  # macOS
# Linux: date -d 'yesterday' +%Y-%m-%d
```

---

## 5. Sentry dashboards (T-3)

Theo [sentry-phase2-dashboards.md](./sentry-phase2-dashboards.md):

- [ ] Project `ptt-crm-api` — Nest write 5xx, PATCH p95  
- [ ] Project `ptt-flask` — Flask proxy errors  
- [ ] Project `ptt-worker` — meta_insights, shadow, capi  
- [ ] Alert: write 5xx > 0.1% / 15 phút → `#ptt-ops`  
- [ ] Alert: Meta insights sync warning ≥ 1/ngày  

---

## 6. Prod change window (§4–§8 runbook)

**Thông báo:** AM + CSKH freeze bulk assign trong window.

### Bước 0 — Backup

```bash
cp /var/www/ptt/ptt.db /var/backups/ptt-$(date +%Y%m%d-%H%M)-pre-write-cutover.db
pg_dump "$DATABASE_URL" -Fc -f /var/backups/ptt_agency-$(date +%Y%m%d-%H%M).dump
```

- [ ] SQLite backup OK  
- [ ] PG dump OK  

### Bước 1 — Shadow sync ON

```bash
# Flask .env
PTT_LEAD_SHADOW_SYNC=1
sudo systemctl restart ptt-worker
./scripts/sync_lead_shadow.sh reconcile
```

- [ ] `last_shadow_at` gần NOW()

### Bước 2 — sync_mode = pg_primary

```bash
psql "$DATABASE_URL" -c "
  UPDATE crm_leads_sync_state
  SET sync_mode = 'pg_primary', updated_at = NOW() WHERE id = 1;
"
# Flask .env
PTT_LEAD_REPLICA_SYNC=0
sudo systemctl restart ptt-worker
```

Hoặc assistant:

```bash
./scripts/prod_write_cutover.sh --apply   # chỉ sync_mode + verify
```

- [ ] `sync_mode = pg_primary`  
- [ ] `PTT_LEAD_REPLICA_SYNC=0`

### Bước 3 — Nest write ON

```bash
# ptt-crm-api env
PTT_LEADS_WRITE_ENABLED=1
sudo systemctl restart ptt-crm-api
curl -s http://127.0.0.1:3000/health | jq '.leads_write_enabled'
```

**Smoke PATCH (W5 defer — không POST create prod):**

```bash
export KEY="$PTT_CRM_INTERNAL_KEY"
curl -sf -H "X-PTT-Internal-Key: $KEY" -X PATCH \
  "https://api.pttads.vn/api/v1/leads/<TEST_LEAD_ID>" \
  -H 'Content-Type: application/json' \
  -d '{"owner_id":1,"assigned_by":"cutover-smoke"}' | jq .
```

- [ ] PATCH smoke OK  
- [ ] **Không** bật prod POST create (W5 → Phase 2.1)

### Bước 4 — Flask write upstream = nest

```bash
PTT_LEADS_WRITE_UPSTREAM=nest
sudo systemctl restart ptt
```

- [ ] UI assign 1 lead → PG `owner_id` đúng  
- [ ] Shadow catch-up ≤ 1 phút

### Bước 5 — Verify E2E

```bash
./scripts/dual_run_write_check.py --sample 50 --quiet
psql "$DATABASE_URL" -c "
  SELECT event_type, aggregate_id, created_at, published_at
  FROM domain_events WHERE event_type = 'LeadAssigned'
  ORDER BY created_at DESC LIMIT 5;
"
./scripts/lead_assigned_rmq_e2e.sh   # nếu RMQ enabled
```

- [ ] Dual-run 0 mismatch (hoặc chỉ timestamp format — ghi nhận)  
- [ ] LeadAssigned outbox published ≤ 30s  
- [ ] Assignment log UI OK

### Bước 6 — Post-cutover monitor (7 ngày)

| Metric | Target |
|--------|--------|
| Write dual-run mismatch | 0% |
| Shadow lag | ≤ 5 phút |
| Nest PATCH p95 | < 500ms |
| Nest write 5xx | < 0.1% |

- [ ] Daily reconcile cron 06:00 ICT  
- [ ] Sentry dashboard review ngày D+1, D+3, D+7

---

## 7. Rollback (≤ 5 phút) — drill trước prod

```bash
./scripts/local_leads_write_cutover_drill.sh
# Evidence: .local-dev/rollback-drill-evidence.json
```

**Prod rollback khẩn cấp:**

```bash
PTT_LEADS_WRITE_UPSTREAM=flask && sudo systemctl restart ptt
PTT_LEADS_WRITE_ENABLED=0 && sudo systemctl restart ptt-crm-api
psql "$DATABASE_URL" -c "UPDATE crm_leads_sync_state SET sync_mode='sqlite_to_pg', updated_at=NOW() WHERE id=1;"
PTT_LEAD_REPLICA_SYNC=1 && sudo systemctl restart ptt-worker
```

- [ ] Rollback drill evidence `rollback_within_target: true`  
- [ ] Runbook §7 reviewed với on-call

---

## 8. UAT + sign-off AM/Admin

```bash
./scripts/phase2_uat_gate.py --am-name "..." --admin-name "..."
# → .local-dev/phase2-uat-signoff.json
```

Manual checklist: [phase2-uat-signoff.md](./phase2-uat-signoff.md) (W-UAT-01 → X-UAT-05)

- [ ] AM signed — CPL + assign + closed-loop ≥3 clients  
- [ ] Admin signed — soak + rollback + timers + Sentry + runbooks  

**Artifacts đính kèm Phase 2 Done:**

| File | Mô tả |
|------|-------|
| `.local-dev/phase2-ops-gate-report.json` | Staging gate pack |
| `.local-dev/write-cutover-prod-gates.json` | Prod gates |
| `.local-dev/write-soak-evidence.jsonl` | 48h soak (timer) |
| `.local-dev/rollback-drill-evidence.json` | Rollback drill |
| `.local-dev/prod-write-cutover-report.json` | Cutover assistant |
| `.local-dev/phase2-uat-signoff.json` | UAT + signatures |

---

## 9. Local dev vs VPS — khác biệt thường gặp

| Issue | Local macOS | VPS fix |
|-------|-------------|---------|
| `nest_leads_write_disabled` | Docker Nest `WRITE_ENABLED=0` | Restart `ptt-crm-api` với `PTT_LEADS_WRITE_ENABLED=1` |
| `domain_events_idempotency` fail | DDL chưa apply | `./scripts/apply_pg_ddl_v3_events_idempotency.sh` |
| `lead_assigned_rmq_e2e` 404 POST | Nest write off / W5 defer | Staging: bật write; Prod: dùng PATCH-only path |
| Dual-run timestamp mismatch | Format Z vs space | Known — reconcile policy; prod dùng sample lớn hơn |
| 0 clients PG | Chưa seed | Agency UI tạo client + seed meta + hub map |

---

## 10. Go / No-Go

**GO prod cutover khi:**

- [ ] Staging gate pack `ok: true`  
- [ ] 48h soak timer evidence pass  
- [ ] Rollback drill ≤ 5 min  
- [ ] AM + Admin sign-off  
- [ ] Sentry dashboards live  
- [ ] W5 defer acknowledged (PATCH only)

**NO-GO / defer → Phase 2.1:**

- Soak chưa đủ 48h  
- Dual-run mismatch không giải thích được  
- RMQ E2E fail trên staging  
- Meta closed-loop < 3 clients

---

| Version | Date | Change |
|---------|------|--------|
| 1.0 | 2026-07-17 | VPS Phase 2 production cutover checklist |
