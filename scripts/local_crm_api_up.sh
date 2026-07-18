#!/usr/bin/env bash
# Start NestJS CRM read API (Phase 1b Bước 7 — PG read replica default)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
API_DIR="$ROOT/services/ptt-crm-api"

export DATABASE_URL="${DATABASE_URL:-postgresql://ptt:ptt_dev@127.0.0.1:5432/ptt_agency}"
export PTT_LEADS_READ_SOURCE="${PTT_LEADS_READ_SOURCE:-pg}"
export PTT_SQLITE_PATH="${PTT_SQLITE_PATH:-$ROOT/ptt.db}"
export PTT_CRM_API_AUTH_DISABLED="${PTT_CRM_API_AUTH_DISABLED:-1}"
export PTT_PORTAL_JWT_SECRET="${PTT_PORTAL_JWT_SECRET:-dev-portal-jwt-change-me-min-32-chars}"
export PTT_PORTAL_STUB_USERS="${PTT_PORTAL_STUB_USERS:-viewer@demo.local:demo123:550e8400-e29b-41d4-a716-446655440000:viewer,approver@demo.local:demo123:550e8400-e29b-41d4-a716-446655440000:approver}"
export PTT_PORTAL_CORS_ORIGINS="${PTT_PORTAL_CORS_ORIGINS:-http://127.0.0.1:3100,http://localhost:3100}"
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

echo "==> ptt-crm-api on http://127.0.0.1:$PORT (read: $PTT_LEADS_READ_SOURCE, PG: $DATABASE_URL)"
exec npm run start:dev
