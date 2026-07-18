# Runbook — Sprint 0 (Phase 2.1 bridge)

> **Mục tiêu:** W5 prod create · Portal JWT auth spike · ROAS fix · CAPI LeadCreated pilot

## 1. DDL

```bash
cd /var/www/ptt
./scripts/apply_pg_ddl_v3_events_idempotency.sh   # idempotency_key (version ≤32 chars)
./scripts/apply_pg_ddl_v3_sprint0.sh              # crm_leads_prod_id_seq + portal_client_users
```

## 2. Env (staging / prod pilot)

```bash
set -a && source deploy/env.sprint0.example && set +a
# Edit secrets: PTT_CRM_INTERNAL_KEY, PTT_PORTAL_JWT_SECRET
sudo systemctl restart ptt-crm-api
```

| Var | Staging | Prod pilot |
|-----|---------|------------|
| `PTT_LEADS_CREATE_ID_MODE` | `staging` (≥900M) | `prod` (<900M seq) |
| `PTT_LEADS_WRITE_ENABLED` | `1` | `1` when cutover |
| `PTT_PORTAL_STUB_USERS` | dev users OK | remove — use PG users |

## 3. Smoke

```bash
# Staging create (id ≥ 900M)
./scripts/local_leads_write_staging.sh

# Prod create (id < 900M) — requires CREATE_ID_MODE=prod + sprint0 DDL
./scripts/local_leads_write_prod_create.sh

# Portal login
curl -s -X POST http://127.0.0.1:3000/api/v1/portal/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"viewer@demo.local","password":"demo123"}' | jq .

# Portal UI (Next.js spike)
./scripts/local_portal_up.sh
# → http://127.0.0.1:3100/login

# CAPI enqueue from LeadCreated outbox
./scripts/process_lead_created_capi.sh
```

## 4. Systemd (VPS)

```bash
sudo cp ptt-lead-created-capi.service ptt-lead-created-capi.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now ptt-lead-created-capi.timer
```

## 5. Rollback W5 prod create

```bash
PTT_LEADS_CREATE_ID_MODE=staging
sudo systemctl restart ptt-crm-api
```

PATCH assign unaffected.

---

| Version | Date | Change |
|---------|------|--------|
| 1.0 | 2026-07-17 | Sprint 0 runbook |
