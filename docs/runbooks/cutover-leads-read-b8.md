# Runbook — Cutover read traffic Leads API (Phase 1b Bước 8)

> **Mục tiêu:** `GET /api/v1/leads` production đọc từ NestJS (PG replica). Flask giữ CRM UI + write APIs. Rollback ≤ 5 phút.

---

## 1. Kiến trúc sau cutover

| Path | Upstream | DB | Auth |
|------|----------|-----|------|
| `api.pttads.vn/api/v1/leads` | Nest :3000 | PostgreSQL `crm_leads` | `X-PTT-Internal-Key` (Nginx inject) |
| `pttads.vn/api/v1/leads` (browser) | Flask proxy → Nest *hoặc* Flask local | Tùy flag | Flask session `crm_agency` view |
| `pttads.vn/api/crm/*` | Flask :8002 | SQLite | Session |
| Agency Ops UI | Flask | SQLite | Session |

**Hai lớp routing:**

1. **Nginx** (`PTT_LEADS_READ_UPSTREAM` → snippet) — cho `api.pttads.vn` và host API.
2. **Flask app** (`PTT_LEADS_READ_UPSTREAM=nest`) — proxy sau auth cho client có session cookie trên `pttads.vn`.

---

## 2. Pre-flight (staging)

```bash
# Stack
docker compose up -d postgres
./scripts/apply_pg_ddl_v2_leads.sh
./scripts/sync_leads_backfill.sh
./scripts/reconcile_lead_replica.sh 50

# Nest + tests
cd services/ptt-crm-api && npm install && npm test && npm run test:e2e
./scripts/local_crm_api_up.sh &

# Dual-run 0% mismatch ≥ 3 ngày
export PTT_LEADS_API_DUAL_RUN=1
./scripts/local_dual_run_check.sh 50
```

Checklist:

- [ ] `reconcile_lead_replica` → `ok: true`
- [ ] Dual-run mismatch = 0 trên staging ≥ 72h
- [ ] Nest `/health` → `leads_read_source: pg`
- [ ] Sentry project + alert error rate Nest

---

## 3. Deploy production

> **macOS (local dev):** Không có `systemctl`. Dùng [§3.0 Mac local](#30-mac-local--dev) bên dưới.  
> **Linux VPS:** Dùng systemd [§3.1](#31-nestjs-service-vps).

### 3.0 Mac local / dev

```bash
# PostgreSQL (Docker)
docker compose up -d postgres
./scripts/apply_pg_ddl_v2_leads.sh    # nếu DB đã tồn tại trước v2
./scripts/sync_leads_backfill.sh

# Nest CRM API — terminal riêng (không systemd)
./scripts/local_crm_api_up.sh
# → http://127.0.0.1:3000/health

# Flask (terminal khác)
./scripts/local_phase1_up.sh

# Verify
curl http://127.0.0.1:3000/health
./scripts/local_dual_run_check.sh 50
./scripts/local_leads_cutover_drill.sh
```

Nginx cutover trên Mac: chỉ dry-run snippet (không reload nginx thật):

```bash
./scripts/apply_leads_read_upstream.sh --dry-run
```

App-level cutover trên Mac (Flask proxy → Nest):

```bash
export PTT_LEADS_READ_UPSTREAM=nest
export PTT_NEST_LEADS_URL=http://127.0.0.1:3000
# restart Flask local
```

### 3.1 NestJS service (VPS)

```bash
cd /var/www/ptt/services/ptt-crm-api
npm ci && npm run build
sudo cp deploy/ptt-crm-api.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now ptt-crm-api
curl -s http://127.0.0.1:3000/health | jq .
```

`.env` production (Nest):

```bash
DATABASE_URL=postgresql://ptt:***@127.0.0.1:5432/ptt_agency
PTT_LEADS_READ_SOURCE=pg
PTT_CRM_INTERNAL_KEY=<shared-secret>
PTT_CRM_API_AUTH_DISABLED=0
```

### 3.2 Nginx cutover (`api.pttads.vn`)

1. Thêm upstream blocks từ `deploy/nginx-leads-v1-cutover.conf` vào server block.
2. Map secret:

```nginx
map "" $ptt_crm_internal_key {
    default "<same as PTT_CRM_INTERNAL_KEY>";
}
```

3. Apply routing:

```bash
# .env: PTT_LEADS_READ_UPSTREAM=nest
sudo ./scripts/apply_leads_read_upstream.sh --reload
```

4. Include snippet trong server block **trước** `location /` catch-all:

```nginx
include /etc/nginx/snippets/ptt-leads-v1-routing.conf;
```

### 3.3 Flask app proxy (optional — pttads.vn session clients)

```bash
# /var/www/ptt/.env
PTT_LEADS_READ_UPSTREAM=nest
PTT_NEST_LEADS_URL=http://127.0.0.1:3000
PTT_CRM_INTERNAL_KEY=<shared-secret>
sudo systemctl restart ptt
```

Giữ `PTT_LEADS_API_DUAL_RUN=0` sau cutover (tránh so sánh thừa).

---

## 4. Verify sau cutover

```bash
# Nest trực tiếp
curl -s -H "X-PTT-Internal-Key: $KEY" \
  https://api.pttads.vn/api/v1/leads?limit=1 | jq .

# Flask proxy (session cookie hoặc test client)
curl -s -b cookies.txt https://pttads.vn/api/v1/leads?limit=1 | jq .

# Agency Ops UI smoke — không regression
# Manual: A-01 list clients, A-03 lead detail, ingest monitor
```

Monitor 7 ngày:

- Nest error rate < 0.1%
- p95 latency `/api/v1/leads` baseline
- Sentry: không tag `dual_run_mismatch` (dual-run tắt)
- PG replica lag ≤ 1 phút (`/health/worker` → `crm_leads_replica`)

---

## 5. Rollback (≤ 5 phút)

### Nginx → Flask (khẩn cấp)

```bash
# .env
PTT_LEADS_READ_UPSTREAM=flask

sudo ./scripts/apply_leads_read_upstream.sh --reload
sudo systemctl restart ptt   # nếu Flask app proxy đang nest
```

Verify:

```bash
curl -s https://api.pttads.vn/api/v1/leads?limit=1
# Response từ Flask SQLite — same contract LeadV1
```

### Nest down nhưng PG OK

```bash
PTT_LEADS_READ_UPSTREAM=flask
# apply nginx + restart ptt
```

### PG replica lệch

```bash
PTT_LEADS_READ_UPSTREAM=flask          # rollback read
PTT_LEAD_REPLICA_SYNC=0                # stop sync
# Nest: PTT_LEADS_READ_SOURCE=sqlite   # emergency Nest fallback
```

SQLite **không** bị ảnh hưởng — OLTP primary vẫn an toàn.

---

## 6. Rollback drill (staging / local)

```bash
chmod +x scripts/local_leads_cutover_drill.sh
./scripts/local_leads_cutover_drill.sh

# Toggle nginx snippet dry-run
PTT_LEADS_READ_UPSTREAM=flask ./scripts/apply_leads_read_upstream.sh --dry-run
PTT_LEADS_READ_UPSTREAM=nest  ./scripts/apply_leads_read_upstream.sh --dry-run
```

Ghi nhận drill trong change log (ngày, người, kết quả).

---

## 7. Out of scope B8

- Write APIs (`POST/PATCH /api/v1/leads`) → Bước 9 staging
- JWT / Keycloak → Phase 2
- Deprecate Flask read routes → sau soak ổn định

---

## 8. Artifacts

| File | Mô tả |
|------|-------|
| `deploy/nginx-leads-v1-cutover.conf` | Upstream + hướng dẫn include |
| `deploy/nginx-leads-v1-upstream-nest.conf` | Snippet nest |
| `deploy/nginx-leads-v1-upstream-flask.conf` | Snippet rollback |
| `scripts/apply_leads_read_upstream.sh` | Ghi snippet + reload nginx |
| `scripts/local_leads_cutover_drill.sh` | Drill local/staging |
| `deploy/ptt-crm-api.service` | systemd Nest |
| `ptt_crm/leads_upstream.py` | Flask proxy sau auth |
| `PTT_LEADS_READ_UPSTREAM` | `flask` \| `nest` |

---

| Version | Date | Change |
|---------|------|--------|
| 1.0 | 2026-07-17 | B8 cutover runbook |
