# PTT CRM API — NestJS read-only (Phase 1b)

Lead read API mirroring Flask `/api/v1/leads`. Contract frozen in `schemas/crm/leads-v1.openapi.yaml`.

**Requires Node.js ≥ 22** (SQLite fallback uses built-in `node:sqlite`).

## Endpoints

| Method | Path | Auth |
|--------|------|------|
| GET | `/health` | Public |
| GET | `/api/v1/leads` | `X-PTT-Internal-Key` (optional dev) |
| GET | `/api/v1/leads/:id` | same |

## Local dev (Bước 7 — PG read replica)

```bash
docker compose up -d postgres
./scripts/apply_pg_ddl_v2_leads.sh   # if DB existed before v2 DDL
./scripts/sync_leads_backfill.sh     # SQLite → PG

cd services/ptt-crm-api
npm install
export DATABASE_URL=postgresql://ptt:ptt_dev@127.0.0.1:5432/ptt_agency
export PTT_LEADS_READ_SOURCE=pg
export PTT_CRM_API_AUTH_DISABLED=1
npm run start:dev
```

Or from repo root: `./scripts/local_crm_api_up.sh`

Health: `curl http://127.0.0.1:3000/health`  
Leads: `curl http://127.0.0.1:3000/api/v1/leads?limit=5`

**SQLite fallback** (contract tests / legacy):

```bash
export PTT_LEADS_READ_SOURCE=sqlite
export PTT_SQLITE_PATH=../../ptt.db
```

## Tests (golden contract)

```bash
npm test              # mapper unit tests (sqlite + pg row)
npm run test:e2e      # sqlite mode (temp DB)
# PG e2e runs when local postgres has crm_leads (skipped otherwise)
npm run test:e2e -- leads-pg.e2e-spec.ts
```

## Docker

From repo root:

```bash
docker compose up -d postgres
./scripts/sync_leads_backfill.sh
docker compose up -d crm-api
curl http://127.0.0.1:3000/health
```

## Env

| Variable | Default | Mô tả |
|----------|---------|-------|
| `PORT` / `CRM_API_PORT` | `3000` | HTTP port |
| `DATABASE_URL` | `postgresql://ptt:ptt_dev@127.0.0.1:5432/ptt_agency` | PG read replica |
| `PTT_LEADS_READ_SOURCE` | `pg` | `pg` \| `sqlite` |
| `PTT_SQLITE_PATH` | `../../ptt.db` | SQLite fallback (read-only) |
| `PTT_CRM_INTERNAL_KEY` | — | Require header when set |
| `PTT_CRM_API_AUTH_DISABLED` | `0` | `1` = skip auth (local dev) |

## Nginx (staging/prod cutover — Bước 8)

```nginx
location /api/v1/leads {
    proxy_pass http://127.0.0.1:3000;
    proxy_set_header Host $host;
    proxy_set_header X-PTT-Internal-Key $ptt_internal_key;
}
```

Flask CRM UI và write APIs giữ nguyên trên upstream Flask.

## Dual-run (Bước 4–7)

Staging bật trên Flask — so sánh Flask (SQLite) vs Nest (PG replica):

```bash
export PTT_LEADS_API_DUAL_RUN=1
export PTT_NEST_LEADS_URL=http://127.0.0.1:3000
export PTT_LEADS_READ_SOURCE=pg   # on Nest process
./scripts/sync_leads_backfill.sh
./scripts/local_crm_api_up.sh &
./scripts/local_dual_run_check.sh 50
```

Batch check (cron / CI):

```bash
./scripts/local_dual_run_check.sh 50
# hoặc: python scripts/dual_run_leads_check.py --sample 50
```

Mismatch → JSON log + Sentry tag `dual_run_mismatch`.

## Write staging (Bước 9 — staging only)

**Default off** (`PTT_LEADS_WRITE_ENABLED=0`) — write routes return 404.

```bash
export PTT_LEADS_WRITE_ENABLED=1
./scripts/local_crm_api_up.sh
./scripts/local_leads_write_staging.sh
npm run test:e2e -- leads-write.e2e-spec.ts
```

OpenAPI draft: `schemas/crm/leads-v1-write.openapi.yaml`  
Phase 2 prod cutover: `docs/specs/2026-07-17-phase-2-write-cutover-ticket.md`

| Variable | Default | Mô tả |
|----------|---------|-------|
| `PTT_LEADS_WRITE_ENABLED` | `0` | `1` = enable POST/PATCH (staging only) |

