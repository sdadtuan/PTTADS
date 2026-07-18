# VPS Phase 3 — Portal + Temporal + TLS cutover

> **Domain:** `portal.pttads.vn` · **API:** `api.pttads.vn` (existing Nest)

## Pre-flight (Phase 2 gates)

- [ ] G1–G7 pass ([vps-phase2-production-cutover-checklist.md](./vps-phase2-production-cutover-checklist.md))
- [ ] DDL v3 creatives + launch-qa applied on prod PG
- [ ] `PTT_PORTAL_JWT_SECRET` ≥ 32 chars (not dev default)
- [ ] Portal users in `portal_client_users` (bcrypt) — no `plain:` prod passwords

## 1. DNS

- [ ] `portal.pttads.vn` A/AAAA → VPS IP
- [ ] `api.pttads.vn` CORS includes `https://portal.pttads.vn`

## 2. TLS (certbot)

```bash
sudo CERTBOT_EMAIL=ops@pttads.vn ./scripts/certbot_portal_vps.sh
curl -sfI https://portal.pttads.vn/login
```

## 3. Build & env

```bash
cd /var/www/ptt/services/portal-web
npm ci && npm run build
cp -r .next/static .next/standalone/.next/static
cp -r public .next/standalone/public 2>/dev/null || true
```

`/var/www/ptt/.env` additions:

```bash
NEXT_PUBLIC_PTT_API_URL=https://api.pttads.vn
PORTAL_PORT=3100
PTT_TEMPORAL_ADDRESS=127.0.0.1:7233
PTT_TEMPORAL_NAMESPACE=default
PTT_TEMPORAL_TASK_QUEUE=ptt-agency
PTT_PORTAL_CORS_ORIGINS=https://portal.pttads.vn
PTT_CRM_INTERNAL_KEY=<s2s>
```

## 4. Temporal + worker

```bash
docker compose -f docker-compose.temporal.yml up -d
sudo ./scripts/install_phase3_systemd.sh
sudo systemctl start ptt-temporal-worker
journalctl -u ptt-temporal-worker -n 20 --no-pager
```

## 5. Portal systemd

```bash
sudo systemctl start ptt-portal-web
journalctl -u ptt-portal-web -n 20 --no-pager
```

## 6. Smoke

```bash
curl -sf https://api.pttads.vn/health
curl -sfI https://portal.pttads.vn/login
./scripts/seed_portal_demo_creative.sh
```

Playwright against staging/prod:

```bash
PORTAL_E2E_URL=https://portal.pttads.vn \
PORTAL_E2E_API_URL=https://api.pttads.vn \
PORTAL_E2E_SKIP_SERVER=1 \
./scripts/playwright_portal_e2e_temporal.sh
```

## 7. Optional — Keycloak (Phase 3.1)

See [keycloak-portal-auth.md](./keycloak-portal-auth.md). Set `PTT_PORTAL_AUTH_MODE=keycloak` on Nest after realm import.

## Rollback

1. `systemctl stop ptt-portal-web ptt-temporal-worker`
2. Remove nginx site symlink for portal
3. Flask Agency Ops unchanged — internal users unaffected
