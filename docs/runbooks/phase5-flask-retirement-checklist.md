# Phase 5 — Flask monolith retirement checklist

> **Mục tiêu:** `PTT_FLASK_MONOLITH_MODE=retired`, `systemctl stop ptt.service`, nginx không proxy Flask :8002.

## Prerequisites (must pass before cutover)

> **Horizon 0 (partial):** SEO + Email admin only — [`close_flask_retirement_delivery_admin.sh`](../scripts/close_flask_retirement_delivery_admin.sh)  
> **Full retirement:** checklist below + [`close_flask_retirement.sh`](../scripts/close_flask_retirement.sh)

- [ ] Phase 2 prod: `./scripts/phase2_prod_cutover.sh --apply`
- [ ] Phase 3 UAT: `./scripts/phase3_prod_uat_gate.sh` + human sign-off
- [ ] Phase 4 readonly soak ≥14 ngày (`docs/runbooks/phase4-prod-cutover-checklist.md`)
- [ ] Staging gate: `./scripts/staging_phase5_gate_pack.sh` → `ok: true`
- [ ] `PTT_WEBHOOKS_FLASK_FALLBACK=0` trên prod
- [ ] Portal SEO Nest PG native (không `PTT_FLASK_MONOLITH_URL` trên portal path)
- [ ] ops-web có `/seo/hub` minimum

## Cutover window

```bash
set -a && source deploy/env.phase5-flask-retire.example && set +a
# Chỉnh DATABASE_URL, JWT secrets trên VPS

# 1. Dry-run
sudo -E ./scripts/close_flask_retirement.sh

# 2. Execute
sudo -E APPLY=1 ./scripts/close_flask_retirement.sh
```

Script sẽ:

1. Chạy `ptt_crm.phase5_flask_retirement_gates`
2. Ghi `.env`: `PTT_FLASK_MONOLITH_MODE=retired`, `PTT_WEBHOOKS_FLASK_FALLBACK=0`
3. Deploy `deploy/nginx-rs-flask-retired.conf` → rs.pttads.vn
4. `systemctl stop ptt.service && systemctl disable ptt.service`
5. Restart: `ptt-crm-api`, `ptt-worker`, `ptt-fb-autosync`, `ptt-temporal-worker`, `ptt-ops-web`, `ptt-portal-web`

## Post-cutover verification

| Check | Command / URL |
|-------|----------------|
| Nest health | `curl -sf http://127.0.0.1:3000/health` |
| ops-web leads | https://ops.pttads.vn/crm/leads |
| ops-web SEO hub | https://ops.pttads.vn/seo/hub |
| Portal SEO | https://portal.pttads.vn/seo |
| rs redirect | `curl -I https://rs.pttads.vn/crm/leads` → 302 ops |
| Flask down | `systemctl is-active ptt.service` → inactive |
| Webhook queue | Meta test event → job_queue, không 502 |
| Worker alive | `systemctl status ptt-worker ptt-fb-autosync` |

## Soak (≥14 ngày)

```bash
./scripts/phase5_soak_record.sh   # cron daily
# Evaluate: PHASE5_SKIP_SOAK=0 ./scripts/staging_phase5_gate_pack.sh
```

## Rollback (emergency)

```bash
sudo cp /etc/nginx/sites-available/rs.pttads.vn.pre-phase5.bak /etc/nginx/sites-available/rs.pttads.vn
sudo nginx -t && sudo systemctl reload nginx
# .env
PTT_FLASK_MONOLITH_MODE=readonly
PTT_WEBHOOKS_FLASK_FALLBACK=1   # tạm nếu Nest webhook chưa cover hết channel
sudo systemctl enable --now ptt.service
sudo systemctl restart ptt ptt-crm-api
```

## Units giữ chạy (Python workers ≠ Flask HTTP)

| Unit | Vai trò |
|------|---------|
| `ptt-crm-api` | Nest API |
| `ptt-worker` | Job queue ingest |
| `ptt-fb-autosync` | FB background sync |
| `ptt-temporal-worker` | Workflows |
| `ptt-ops-web` | Staff console |
| `ptt-portal-web` | Client portal |
| ~~`ptt.service`~~ | **Retired** |

## Sign-off

| Role | Name | Date | OK |
|------|------|------|-----|
| Tech Lead | | | [ ] |
| DevOps | | | [ ] |
| QA | | | [ ] |

Artifact: `.local-dev/phase5-flask-retirement-gate-report.json`
