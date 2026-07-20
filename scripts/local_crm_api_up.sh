#!/usr/bin/env bash
# Start NestJS CRM read API (Phase 1b Bước 7 — PG read replica default)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
API_DIR="$ROOT/services/ptt-crm-api"

export DATABASE_URL="${DATABASE_URL:-postgresql://ptt:ptt_dev@127.0.0.1:5432/ptt_agency}"
export PTT_LEADS_WRITE_SOURCE="${PTT_LEADS_WRITE_SOURCE:-pg}"
export PTT_LEADS_READ_SOURCE="${PTT_LEADS_READ_SOURCE:-pg}"
export PTT_LEAD_REPLICA_SYNC="${PTT_LEAD_REPLICA_SYNC:-0}"
export PTT_LEADS_WRITE_ENABLED="${PTT_LEADS_WRITE_ENABLED:-1}"
export PTT_LEADS_READ_UPSTREAM="${PTT_LEADS_READ_UPSTREAM:-nest}"
export PTT_SQLITE_PATH="${PTT_SQLITE_PATH:-$ROOT/ptt.db}"
export PTT_CRM_API_AUTH_DISABLED="${PTT_CRM_API_AUTH_DISABLED:-1}"
export PTT_PORTAL_JWT_SECRET="${PTT_PORTAL_JWT_SECRET:-dev-portal-jwt-change-me-min-32-chars}"
export PTT_PORTAL_STUB_USERS="${PTT_PORTAL_STUB_USERS:-viewer@demo.local:demo123:550e8400-e29b-41d4-a716-446655440000:viewer,approver@demo.local:demo123:550e8400-e29b-41d4-a716-446655440000:approver}"
export PTT_PORTAL_CORS_ORIGINS="${PTT_PORTAL_CORS_ORIGINS:-http://127.0.0.1:3100,http://localhost:3100}"
export PTT_STAFF_JWT_SECRET="${PTT_STAFF_JWT_SECRET:-dev-staff-jwt-change-me-min-32-chars}"
export PTT_STAFF_STUB_USERS="${PTT_STAFF_STUB_USERS:-staff@demo.local:demo123:staff-demo-1:1:Demo Staff}"
export PTT_OPS_CORS_ORIGINS="${PTT_OPS_CORS_ORIGINS:-http://127.0.0.1:3200,http://localhost:3200}"
export PTT_WEBHOOKS_NEST_ENABLED="${PTT_WEBHOOKS_NEST_ENABLED:-1}"
export PTT_WEBHOOKS_NEST_META="${PTT_WEBHOOKS_NEST_META:-1}"
export PTT_JOBS_ENABLED="${PTT_JOBS_ENABLED:-1}"
export PTT_WEBHOOK_V1_ENQUEUE="${PTT_WEBHOOK_V1_ENQUEUE:-1}"
export CRM_FACEBOOK_VERIFY_TOKEN="${CRM_FACEBOOK_VERIFY_TOKEN:-dev-meta-verify-token}"
export PTT_PORTAL_SEO_ENABLED="${PTT_PORTAL_SEO_ENABLED:-1}"
export PTT_SEO_EXPERIMENTS_ENABLED="${PTT_SEO_EXPERIMENTS_ENABLED:-1}"
export PTT_SEO_GOVERNANCE_ENABLED="${PTT_SEO_GOVERNANCE_ENABLED:-1}"
# Portal SEO reads seo_aeo.* via Nest PG — Flask monolith optional for other routes only.
export PTT_PORTAL_SEO_SERVICE_TOKEN="${PTT_PORTAL_SEO_SERVICE_TOKEN:-dev-portal-seo-internal}"
export PTT_FLASK_MONOLITH_URL="${PTT_FLASK_MONOLITH_URL:-http://127.0.0.1:5050}"
export PTT_CRM_INTERNAL_KEY="${PTT_CRM_INTERNAL_KEY:-$PTT_PORTAL_SEO_SERVICE_TOKEN}"
export PTT_TEMPORAL_ADDRESS="${PTT_TEMPORAL_ADDRESS:-127.0.0.1:7233}"
export PTT_TEMPORAL_NAMESPACE="${PTT_TEMPORAL_NAMESPACE:-default}"
export PTT_TEMPORAL_TASK_QUEUE="${PTT_TEMPORAL_TASK_QUEUE:-ptt-agency}"
export CRM_API_PORT="${CRM_API_PORT:-3000}"
export PORT="$CRM_API_PORT"

cd "$API_DIR"
if [[ ! -d node_modules ]]; then
  echo "==> npm install (ptt-crm-api)"
  npm install
fi

echo "==> ptt-crm-api on http://127.0.0.1:$PORT (write: $PTT_LEADS_WRITE_ENABLED, read: $PTT_LEADS_READ_SOURCE, PG: $DATABASE_URL)"
exec npm run start:dev
