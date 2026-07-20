# SEO/AEO — PostgreSQL cutover + GSC/GA4 OAuth UAT

> **Mục tiêu:** Production `SEO_AEO_DB=pg`, backfill verified, GSC/GA4 OAuth live, daily sync timers chạy ổn.  
> **Pilot:** 1 client SEO (`PILOT_CUSTOMER_ID`) · soak ≥ 7 ngày trước mở rộng.  
> **Rollback:** `SEO_AEO_DB=sqlite` + restart `ptt` (PG data giữ làm backup).

---

## Prerequisites

- [ ] Phase 3 SEO modules stable trên SQLite ≥ 7 ngày
- [ ] `DATABASE_URL` trỏ PostgreSQL production (`ptt_agency`)
- [ ] Google Cloud OAuth client với redirect URIs:
  - `https://pttads.vn/api/v1/seo/gsc/oauth/callback`
  - `https://pttads.vn/api/v1/seo/ga4/oauth/callback`
- [ ] APIs enabled: Search Console, Analytics Data, Analytics Admin
- [ ] `PTT_TOKEN_VAULT_KEY` set (production — encrypt refresh tokens)
- [ ] Backup: `pg_dump` + copy `ptt.db` trước change window

---

## 1. Staging rehearsal (bắt buộc)

```bash
cd /var/www/ptt
export DATABASE_URL=postgresql://...
export SEO_AEO_DB=dual   # optional 24h soak

# Dry-run
APPLY=0 ./scripts/seo_aeo_prod_cutover.sh

# Verify
python3 scripts/verify_seo_aeo_oauth_uat.py --customer-id <PILOT_ID>
python3 -m pytest tests/test_seo_aeo_pg_cutover.py tests/test_seo_aeo_phase4_*.py -q
```

Dual-write soak (optional 24h):

```bash
# .env
SEO_AEO_DB=dual
# So sánh counts mỗi 6h:
python3 scripts/migrate_sqlite_seo_aeo_to_pg.py --verify-only
```

---

## 2. Production change window

### 2.1 Backup

```bash
sudo -u postgres pg_dump "$DATABASE_URL" -Fc -f /var/backups/ptt_seo_aeo_pre_cutover.dump
cp /var/www/ptt/ptt.db /var/backups/ptt_$(date +%Y%m%d).db
```

### 2.2 Cutover script

```bash
cd /var/www/ptt
export PILOT_CUSTOMER_ID=<id>
sudo -E APPLY=1 ./scripts/seo_aeo_prod_cutover.sh
```

Script thực hiện:
1. Verify PG schema + env
2. Backfill `migrate_sqlite_seo_aeo_to_pg.py`
3. Backfill `migrate_crm_aeo_to_pg.py` (mentions)
4. Set `SEO_AEO_DB=pg`, sync flags trong `.env`
5. Restart `ptt`, worker, enable GSC/GA4/freshness timers

### 2.3 Manual .env checklist

```bash
# /var/www/ptt/.env — bổ sung/verify
SEO_AEO_DB=pg
DATABASE_URL=postgresql://...

# GSC OAuth
PTT_GSC_OAUTH_CLIENT_ID=...
PTT_GSC_OAUTH_CLIENT_SECRET=...
PTT_GSC_OAUTH_REDIRECT_URI=https://pttads.vn/api/v1/seo/gsc/oauth/callback
PTT_GSC_SYNC_ENABLED=1

# GA4 OAuth (có thể dùng chung client ID với GSC)
PTT_GA4_OAUTH_CLIENT_ID=...          # hoặc bỏ trống → fallback GSC
PTT_GA4_OAUTH_CLIENT_SECRET=...
PTT_GA4_OAUTH_REDIRECT_URI=https://pttads.vn/api/v1/seo/ga4/oauth/callback
PTT_GA4_SYNC_ENABLED=1

PTT_TOKEN_VAULT_KEY=...
PTT_JOBS_ENABLED=1
PTT_JOBS_SYNC_FALLBACK=1             # fallback inline nếu queue down

# Tắt stub trên prod
# PTT_GSC_SYNC_STUB=0
# PTT_GA4_SYNC_STUB=0
```

```bash
sudo systemctl restart ptt ptt-temporal-worker
sudo systemctl enable --now ptt-seo-gsc-sync.timer ptt-seo-ga4-sync.timer
```

---

## 3. UAT — GSC OAuth (pilot client)

| # | Step | Expected |
|---|------|----------|
| 1 | Login admin → `/crm/seo/technical?customer_id=<PILOT>` | Page loads |
| 2 | Click **Kết nối Google** (GSC) → chọn site | Redirect Google consent |
| 3 | Approve → callback | Redirect về technical page `gsc_connected=1` |
| 4 | `GET /api/v1/seo/clients/<PILOT>/gsc/integration` | `connected: true`, `site_url` set |
| 5 | Click **Sync OAuth** | Job queued or inline sync OK |
| 6 | `GET /api/v1/seo/clients/<PILOT>/gsc/summary` | clicks/impressions > 0 sau sync |
| 7 | SQL: `SELECT COUNT(*) FROM seo_aeo.seo_gsc_daily_stats WHERE customer_id=<PILOT>` | > 0 rows |
| 8 | SQL: `SELECT integrations_json->'gsc' FROM seo_aeo.seo_client_settings WHERE customer_id=<PILOT>` | refresh_token_encrypted present |

Manual sync test:

```bash
sudo systemctl start ptt-seo-gsc-sync.service
journalctl -u ptt-seo-gsc-sync.service -n 50 --no-pager
```

---

## 4. UAT — GA4 OAuth (pilot client)

| # | Step | Expected |
|---|------|----------|
| 1 | Technical Console → GA4 section | Integration status visible |
| 2 | **Kết nối Google** → nhập Property ID (optional) | OAuth flow |
| 3 | Callback `/api/v1/seo/ga4/oauth/callback` | Redirect `ga4_connected=1` |
| 4 | `GET /api/v1/seo/clients/<PILOT>/ga4/integration` | `connected: true`, `property_id` |
| 5 | **Sync OAuth** | Rows in `seo_ga4_daily_stats` |
| 6 | GA4 summary KPIs update on page | sessions/users/pageviews |

```bash
sudo systemctl start ptt-seo-ga4-sync.service
journalctl -u ptt-seo-ga4-sync.service -n 50 --no-pager
```

---

## 5. UAT — SEO modules on PG (pilot client)

| Module | Route | Check |
|--------|-------|-------|
| Hub | `/crm/seo` | Client list, AEO coverage |
| Client settings | `/crm/seo/clients/<PILOT>` | Save domains → PG |
| Research | `/crm/seo/research` | Add keyword → persists after refresh |
| Content | `/crm/seo/content` | Create card, transition status |
| Technical | `/crm/seo/technical` | Issues CRUD |
| AEO Console | `/crm/seo/aeo` | Scan stub off → real scan |
| Authority | `/crm/seo/authority` | CSV import |
| Reports | `/crm/seo/reports` | Dashboard loads |
| Automations | `/crm/seo/automations` | Alerts panel |

Regression:

```bash
python3 scripts/migrate_sqlite_seo_aeo_to_pg.py --verify-only
python3 scripts/verify_seo_aeo_oauth_uat.py --customer-id <PILOT>
```

---

## 6. Monitor (7 ngày soak)

| Signal | Command | Action |
|--------|---------|--------|
| GSC sync fail | `journalctl -u ptt-seo-gsc-sync` | Check token, site_url |
| GA4 sync fail | `journalctl -u ptt-seo-ga4-sync` | Check property_id, API quota |
| PG errors | `journalctl -u ptt \| grep -i seo_aeo` | Rollback if P1 |
| Job queue | `SELECT status, COUNT(*) FROM job_queue WHERE job_type LIKE 'seo_%' GROUP BY 1` | DLQ replay |
| integrations | `SELECT customer_id, integrations_json FROM seo_aeo.seo_client_settings WHERE integrations_json != '{}'` | Token refresh |

Daily timer status:

```bash
systemctl list-timers --no-pager 'ptt-seo-*'
```

---

## 7. Rollback

1. `.env`: `SEO_AEO_DB=sqlite`
2. `sudo systemctl restart ptt ptt-temporal-worker`
3. SQLite `seo_*` data frozen tại thời điểm cutover vẫn intact
4. PG data **không drop** — retry cutover sau post-mortem

OAuth-only rollback (giữ PG):

- Revoke tokens trong Google Cloud / client settings UI
- Set `PTT_GSC_SYNC_ENABLED=0` / `PTT_GA4_SYNC_ENABLED=0`

---

## 8. Sign-off

- [ ] `SEO_AEO_DB=pg` production ≥ 7 ngày
- [ ] Backfill counts match (hoặc documented exceptions)
- [ ] Pilot GSC OAuth connected + daily sync OK
- [ ] Pilot GA4 OAuth connected + daily sync OK
- [ ] Hub, research, content, technical UAT pass
- [ ] No P1 incidents related to SEO/AEO PG
- [ ] Runbook rollback tested on staging

**Signed:** _______________ **Date:** _______________

---

## 9. Phase 5C — Portal SEO pilot UAT

> **Mục tiêu:** Client portal `/seo/*` read-only + approver duyệt `client_review`. Nest → Flask internal API.

### 9.1 Prerequisites

- [ ] `SEO_AEO_DB=pg` (Flask + PG schema có `seo_portal_client_map`)
- [ ] Nest `ptt-crm-api` + Next `portal-web` + Flask monolith chạy
- [ ] Env:

```bash
export PTT_PORTAL_SEO_ENABLED=1
export PTT_PORTAL_SEO_SERVICE_TOKEN=<shared-secret>   # Flask + Nest
export PTT_FLASK_MONOLITH_URL=http://127.0.0.1:5050    # hoặc production URL
export SEO_AEO_DB=pg
export DATABASE_URL=postgresql://...
```

### 9.2 Seed pilot map + E2E content

```bash
cd /var/www/ptt   # hoặc repo local
export PYTHONPATH=$PWD

# Map portal client UUID → CRM customer_id
python3 scripts/seed_portal_seo_pilot_map.py --apply

# Optional: seed governance-compliant client_review item
python3 scripts/seed_portal_seo_e2e_content.py --apply --title "Pilot UAT review"
```

Pilot UUID mặc định: `550e8400-e29b-41d4-a716-446655440000` → `customer_id=1`.

### 9.3 Smoke (API)

```bash
# Login portal (approver)
TOKEN=$(curl -sf -X POST http://127.0.0.1:3000/api/v1/portal/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"approver@demo.local","password":"demo123"}' | jq -r .token)

# Summary KPIs
curl -sf -H "Authorization: Bearer $TOKEN" \
  http://127.0.0.1:3000/api/v1/portal/seo/summary | jq .

# Executive report (read-only)
curl -sf -H "Authorization: Bearer $TOKEN" \
  "http://127.0.0.1:3000/api/v1/portal/seo/reports/executive?type=executive" | jq .

# Pending client_review
curl -sf -H "Authorization: Bearer $TOKEN" \
  http://127.0.0.1:3000/api/v1/portal/seo/content/pending | jq .
```

### 9.4 Playwright E2E (local / CI)

```bash
# Terminal 1: Nest
./scripts/local_crm_api_up.sh

# Terminal 2: Flask (PORT=5050, token khớp Nest)
export PTT_PORTAL_SEO_SERVICE_TOKEN=dev-portal-seo-internal
export SEO_AEO_DB=pg
python3 app.py

# Terminal 3: Portal
./scripts/local_portal_up.sh

# Terminal 4: Gate
export PTT_PORTAL_SEO_SERVICE_TOKEN=dev-portal-seo-internal
export PORTAL_E2E_FLASK_URL=http://127.0.0.1:5050
chmod +x scripts/phase5_portal_seo_e2e_gate.sh
./scripts/phase5_portal_seo_e2e_gate.sh
```

Kỳ vọng: 3 tests pass trong `e2e/portal-seo.spec.ts`; sign-off tại `.local-dev/phase5-portal-seo-uat-signoff.json`.

### 9.5 Manual UAT checklist (pilot client)

| # | Role | Action | Expected |
|---|------|--------|----------|
| 1 | viewer | Login → `/seo` | KPIs hiển thị, không nút approve |
| 2 | viewer | `/seo/reports` | Báo cáo read-only, không internal notes |
| 3 | viewer | `/seo/content` | Thấy pending list, không approve |
| 4 | approver | Mở item → Approve | Status → `approved`, biến mất khỏi pending |
| 5 | CRM staff | Content detail timeline | Approval ghi nhận với actor portal |
| 6 | approver | Approve item thiếu QA | Governance block message |

### 9.6 Production deploy

```bash
python3 scripts/seed_portal_seo_pilot_map.py --apply --client-id <UUID> --customer-id <CRM_ID>
sudo systemctl restart ptt-crm-api
cd services/portal-web && npm run build && pm2 restart portal-web
# Bật flag sau smoke:
# PTT_PORTAL_SEO_ENABLED=1
```

**Rollback:** `PTT_PORTAL_SEO_ENABLED=0` — ẩn nav SEO; CRM approve vẫn hoạt động.

---

## 10. Phase 5 — Prod flags + 7-day soak

> **Mục tiêu:** Bật có kiểm soát Governance → Portal SEO → Experiments; soak ≥ 7 ngày trước mở rộng.

### 10.1 Feature flags

| Variable | Prod default | Purpose |
|----------|--------------|---------|
| `PTT_SEO_GOVERNANCE_ENABLED` | `1` | Policy engine + publish gates |
| `PTT_PORTAL_SEO_ENABLED` | `0` | Portal `/seo/*` nav + Nest bridge |
| `PTT_SEO_EXPERIMENTS_ENABLED` | `0` | CRM Experiments console |

Template: `deploy/env.phase5-prod.example`

### 10.2 Staged cutover (VPS)

```bash
cd /var/www/ptt
export DATABASE_URL=postgresql://...
export SEO_AEO_DB=pg

# Pre-flight gate (pytest Phase 5)
chmod +x scripts/phase5_prod_cutover_gate.sh
./scripts/phase5_prod_cutover_gate.sh

# Step 1 — governance only
APPLY=1 PHASE5_ENABLE_GOVERNANCE=1 sudo -E ./scripts/close_phase5_prod_cutover.sh

# Step 2 — portal (sau UAT §9)
python3 scripts/seed_portal_seo_pilot_map.py --apply --client-id <UUID> --customer-id <CRM_ID>
APPLY=1 PHASE5_ENABLE_PORTAL=1 \
  PTT_PORTAL_SEO_SERVICE_TOKEN=<secret> \
  PHASE5_SKIP_PORTAL_SIGNOFF=0 \
  sudo -E ./scripts/close_phase5_prod_cutover.sh

# Step 3 — experiments (internal team)
APPLY=1 PHASE5_ENABLE_EXPERIMENTS=1 sudo -E ./scripts/close_phase5_prod_cutover.sh
```

### 10.3 Daily soak (≥ 7 ngày)

```bash
# Cron hoặc systemd timer — 1 lần/ngày
./scripts/phase5_soak_record.sh

# Sau ≥7 ngày — evaluate gate
export PHASE5_SKIP_SOAK=0
export PTT_PHASE5_SOAK_DAYS=7
./scripts/phase5_prod_cutover_gate.sh
```

Artifact: `.local-dev/phase5-soak-evidence.jsonl`, `.local-dev/phase5-gate-report.json`

### 10.4 Monitor

| Signal | Action |
|--------|--------|
| Publish blocked spike | Review `seo_governance_evaluations` + overrides |
| Portal 503 | Check `PTT_FLASK_MONOLITH_URL`, service token |
| Experiments GSC pull fail | Verify `target_url` + GSC stats rows |
| Governance false positive | Policy override via content detail modal |

### 10.5 Rollback

| Component | Action |
|-----------|--------|
| Governance | `PTT_SEO_GOVERNANCE_ENABLED=0` + restart `ptt` |
| Portal SEO | `PTT_PORTAL_SEO_ENABLED=0` + restart `ptt-crm-api` |
| Experiments | `PTT_SEO_EXPERIMENTS_ENABLED=0` — UI ẩn, data giữ |

### 10.6 Sign-off

Checklist đầy đủ VPS: [`phase5-prod-signoff-checklist.md`](./phase5-prod-signoff-checklist.md)  
Evidence template: [`docs/evidence/phase5-prod-signoff.template.json`](../evidence/phase5-prod-signoff.template.json)

- [ ] `phase5-gate-report.json` — all checks pass
- [ ] Governance modal UAT (content detail)
- [ ] Portal pilot UAT (§9) nếu bật portal
- [ ] Soak ≥ 7 ngày, 0 failure samples
- [ ] Rollback drill trên staging

**Signed:** _______________ **Date:** _______________

---

## Quick reference

```bash
# Verify anytime
python3 scripts/verify_seo_aeo_oauth_uat.py --customer-id <PILOT>

# Full cutover
APPLY=1 PILOT_CUSTOMER_ID=<id> sudo -E ./scripts/seo_aeo_prod_cutover.sh

# Count verify
python3 scripts/migrate_sqlite_seo_aeo_to_pg.py --verify-only
```
