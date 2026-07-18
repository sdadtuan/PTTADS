#!/usr/bin/env bash
# Phase 3 Client Portal MVP gate — seed demo data + API smoke + build
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="${PYTHON:-python3}"
if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PYTHON="$ROOT/.venv/bin/python"
fi
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
export PTT_ARTIFACTS_DIR="${PTT_ARTIFACTS_DIR:-$ROOT/.local-dev}"
export DATABASE_URL="${DATABASE_URL:-postgresql://ptt:ptt_dev@127.0.0.1:5432/ptt_agency}"
export PTT_API_URL="${PTT_API_URL:-http://127.0.0.1:3000}"
export PORTAL_DEMO_CLIENT_ID="${PORTAL_DEMO_CLIENT_ID:-550e8400-e29b-41d4-a716-446655440000}"
export PTT_PORTAL_JWT_SECRET="${PTT_PORTAL_JWT_SECRET:-dev-portal-jwt-change-me-min-32-chars}"
export PTT_PORTAL_STUB_USERS="${PTT_PORTAL_STUB_USERS:-viewer@demo.local:demo123:${PORTAL_DEMO_CLIENT_ID}:viewer,approver@demo.local:demo123:${PORTAL_DEMO_CLIENT_ID}:approver}"
export PORTAL_E2E_APPROVER_EMAIL="${PORTAL_E2E_APPROVER_EMAIL:-approver@demo.local}"
export PORTAL_E2E_APPROVER_PASSWORD="${PORTAL_E2E_APPROVER_PASSWORD:-demo123}"
export PORTAL_E2E_CLIENT_ID="${PORTAL_E2E_CLIENT_ID:-$PORTAL_DEMO_CLIENT_ID}"
export PTT_CRM_API_AUTH_DISABLED="${PTT_CRM_API_AUTH_DISABLED:-1}"
cd "$ROOT"

echo "==> Apply PG DDL (performance + creatives + portal users)"
./scripts/apply_pg_ddl_v3.sh 2>/dev/null || true
./scripts/apply_pg_ddl_v3_creatives.sh 2>/dev/null || true
./scripts/apply_pg_ddl_v3_sprint0.sh 2>/dev/null || true

echo "==> Seed portal gate users (PG auth — works without Nest stub env)"
"$PYTHON" scripts/seed_portal_gate_users.py

echo "==> Seed portal demo performance (T-30 Meta + Google)"
"$PYTHON" scripts/seed_portal_demo_performance.py --days 30

echo "==> Phase 3 portal MVP gate pack"
SKIP_BUILD=""
if [[ "${1:-}" == "--skip-build" ]]; then
  SKIP_BUILD="--skip-build"
fi
"$PYTHON" -m ptt_crm.phase3_portal_gates $SKIP_BUILD
RC=$?

if [[ "$RC" -eq 0 ]] && [[ "${RUN_PORTAL_E2E:-0}" == "1" ]]; then
  echo "==> Playwright E2E (portal must be running on :3100)"
  ./scripts/playwright_portal_e2e.sh
fi

exit "$RC"
