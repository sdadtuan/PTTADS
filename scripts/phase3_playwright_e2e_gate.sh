#!/usr/bin/env bash
# Phase 3 Playwright E2E gate — local or prod URLs (portal + Nest must be up)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="${PYTHON:-python3}"
if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PYTHON="$ROOT/.venv/bin/python"
fi
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
export PTT_ARTIFACTS_DIR="${PTT_ARTIFACTS_DIR:-$ROOT/.local-dev}"
export DATABASE_URL="${DATABASE_URL:-postgresql://ptt:ptt_dev@127.0.0.1:5432/ptt_agency}"
export PORTAL_E2E_URL="${PORTAL_E2E_URL:-http://127.0.0.1:3100}"
export PORTAL_E2E_API_URL="${PORTAL_E2E_API_URL:-http://127.0.0.1:3000}"
export PORTAL_E2E_SKIP_SERVER="${PORTAL_E2E_SKIP_SERVER:-1}"
export PORTAL_E2E_CLIENT_ID="${PORTAL_E2E_CLIENT_ID:-550e8400-e29b-41d4-a716-446655440000}"
export PORTAL_E2E_APPROVER_EMAIL="${PORTAL_E2E_APPROVER_EMAIL:-approver@demo.local}"
export PORTAL_E2E_APPROVER_PASSWORD="${PORTAL_E2E_APPROVER_PASSWORD:-demo123}"
export PTT_PORTAL_JWT_SECRET="${PTT_PORTAL_JWT_SECRET:-dev-portal-jwt-change-me-min-32-chars}"
export PTT_CRM_API_AUTH_DISABLED="${PTT_CRM_API_AUTH_DISABLED:-1}"
export RUN_PORTAL_E2E=1
cd "$ROOT"

_wait_http() {
  local url="$1" label="$2" tries="${3:-30}"
  for _ in $(seq 1 "$tries"); do
    if curl -sf "$url" >/dev/null 2>&1; then
      echo "OK  $label → $url"
      return 0
    fi
    sleep 2
  done
  echo "FAIL $label not reachable: $url" >&2
  return 1
}

if [[ "${PORTAL_E2E_SKIP_PREFLIGHT:-0}" != "1" ]]; then
  echo "==> Preflight HTTP"
  _wait_http "${PORTAL_E2E_API_URL}/health" "Nest API"
  _wait_http "${PORTAL_E2E_URL}/login" "Portal login page"

  if [[ "$PORTAL_E2E_API_URL" == http://127.0.0.1:* ]] || [[ "$PORTAL_E2E_API_URL" == http://localhost:* ]]; then
    echo "==> Local seed (PG users + performance)"
    if command -v docker >/dev/null 2>&1; then
      docker compose up -d postgres 2>/dev/null || true
    fi
    ./scripts/apply_pg_ddl_v3_creatives.sh 2>/dev/null || true
    "$PYTHON" scripts/seed_portal_gate_users.py
    "$PYTHON" scripts/seed_portal_demo_performance.py --days 30
  fi
fi

echo "==> Playwright E2E (Temporal stack + creative approve)"
./scripts/playwright_portal_e2e_temporal.sh

echo "==> Update QA sign-off (playwright flag)"
export RUN_PORTAL_E2E=1
"$PYTHON" -m ptt_crm.phase3_qa_gates
RC=$?
echo "OK  Playwright gate complete — see .local-dev/phase3-uat-signoff.json"
exit "$RC"
