# Deploy Client Portal + Temporal (Phase 3)

## Prerequisites

- Phase 2 gates pass (PG OLTP, performance DDL)
- Nest `ptt-crm-api` on `:3000`
- DDL applied:
  ```bash
  ./scripts/apply_pg_ddl_v3_creatives.sh
  ./scripts/apply_pg_ddl_v3_launch_qa.sh
  ```

## 1. Temporal (VPS)

```bash
docker compose -f docker-compose.temporal.yml up -d
sudo cp deploy/ptt-temporal-worker.service /etc/systemd/system/
# EnvironmentFile: PTT_TEMPORAL_ADDRESS=127.0.0.1:7233, DATABASE_URL, PTT_TEMPORAL_TASK_QUEUE=ptt-agency
sudo systemctl enable --now ptt-temporal-worker
```

UI (restrict via firewall/VPN): `http://127.0.0.1:8088`

## 2. Nest CRM API env

```bash
PTT_TEMPORAL_ADDRESS=127.0.0.1:7233
PTT_TEMPORAL_NAMESPACE=default
PTT_TEMPORAL_TASK_QUEUE=ptt-agency
PTT_PORTAL_CORS_ORIGINS=https://portal.pttads.vn
PTT_PORTAL_JWT_SECRET=<32+ chars>
PTT_CRM_INTERNAL_KEY=<s2s key for Flask → Nest>
```

## 3. Portal web build

```bash
cd services/portal-web
npm ci && npm run build
# standalone output: .next/standalone — copy static + public per Next docs
cp -r .next/static .next/standalone/.next/static
cp -r public .next/standalone/public 2>/dev/null || true
```

Env `/var/www/ptt/.env`:

```bash
NEXT_PUBLIC_PTT_API_URL=https://api.pttads.vn
PORTAL_PORT=3100
```

```bash
sudo cp deploy/ptt-portal-web.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now ptt-portal-web
```

## 4. TLS nginx

```bash
sudo certbot certonly --nginx -d portal.pttads.vn
sudo cp deploy/nginx-portal.conf /etc/nginx/sites-available/portal.pttads.vn
sudo ln -sf /etc/nginx/sites-available/portal.pttads.vn /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

Ensure `api.pttads.vn` CORS allows `https://portal.pttads.vn`.

## 5. Smoke

```bash
curl -sf https://api.pttads.vn/health
curl -sfI https://portal.pttads.vn/login
./scripts/seed_portal_demo_creative.sh  # requires Nest up + internal key if auth on
```

Playwright (staging / Temporal live):

```bash
./scripts/playwright_portal_e2e_temporal.sh
# or against prod:
PORTAL_E2E_URL=https://portal.pttads.vn PORTAL_E2E_API_URL=https://api.pttads.vn ./scripts/playwright_portal_e2e_temporal.sh
```

Prod TLS:

```bash
sudo CERTBOT_EMAIL=ops@pttads.vn ./scripts/certbot_portal_vps.sh
sudo ./scripts/install_phase3_systemd.sh
```

Track G Google sync:

```bash
./scripts/apply_pg_ddl_v3_google_sync.sh
PTT_GOOGLE_INSIGHTS_STUB=1 ./scripts/sync_google_insights.sh
```

Track D Hub/SOP:

```bash
./scripts/apply_pg_ddl_v4_hub_sop.sh
python3 scripts/migrate_sqlite_hub_sop_to_pg.py
# see docs/runbooks/hub-pg-migration.md
```

## Rollback

- `systemctl stop ptt-portal-web ptt-temporal-worker`
- Remove nginx site; Flask Agency Ops unchanged
