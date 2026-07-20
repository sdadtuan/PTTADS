#!/usr/bin/env bash
# Phase 5C — Portal SEO E2E gate (local or staging URLs)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="${PYTHON:-python3}"
if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PYTHON="$ROOT/.venv/bin/python"
fi
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
export DATABASE_URL="${DATABASE_URL:-postgresql://ptt:ptt_dev@127.0.0.1:5432/ptt_agency}"
export SEO_AEO_DB="${SEO_AEO_DB:-pg}"
export PTT_SQLITE_PATH="${PTT_SQLITE_PATH:-$ROOT/ptt.db}"
export PORTAL_E2E_URL="${PORTAL_E2E_URL:-http://127.0.0.1:3100}"
export PORTAL_E2E_API_URL="${PORTAL_E2E_API_URL:-http://127.0.0.1:3000}"
export PORTAL_E2E_FLASK_URL="${PORTAL_E2E_FLASK_URL:-http://127.0.0.1:5050}"
export PORTAL_E2E_SKIP_FLASK="${PORTAL_E2E_SKIP_FLASK:-1}"
export PORTAL_E2E_SKIP_SERVER="${PORTAL_E2E_SKIP_SERVER:-1}"
export PORTAL_E2E_CLIENT_ID="${PORTAL_E2E_CLIENT_ID:-550e8400-e29b-41d4-a716-446655440000}"
export PORTAL_E2E_APPROVER_EMAIL="${PORTAL_E2E_APPROVER_EMAIL:-approver@demo.local}"
export PORTAL_E2E_APPROVER_PASSWORD="${PORTAL_E2E_APPROVER_PASSWORD:-demo123}"
export PORTAL_E2E_VIEWER_EMAIL="${PORTAL_E2E_VIEWER_EMAIL:-viewer@demo.local}"
export PORTAL_E2E_VIEWER_PASSWORD="${PORTAL_E2E_VIEWER_PASSWORD:-demo123}"
export PTT_PORTAL_JWT_SECRET="${PTT_PORTAL_JWT_SECRET:-dev-portal-jwt-change-me-min-32-chars}"
export PTT_CRM_API_AUTH_DISABLED="${PTT_CRM_API_AUTH_DISABLED:-1}"
export PTT_PORTAL_STUB_USERS="${PTT_PORTAL_STUB_USERS:-viewer@demo.local:demo123:${PORTAL_E2E_CLIENT_ID}:viewer,approver@demo.local:demo123:${PORTAL_E2E_CLIENT_ID}:approver}"
export PTT_PORTAL_SEO_ENABLED="${PTT_PORTAL_SEO_ENABLED:-1}"
export PTT_PORTAL_SEO_SERVICE_TOKEN="${PTT_PORTAL_SEO_SERVICE_TOKEN:-dev-portal-seo-internal}"
export PTT_FLASK_MONOLITH_URL="${PTT_FLASK_MONOLITH_URL:-$PORTAL_E2E_FLASK_URL}"
export PORTAL_E2E_INTERNAL_KEY="${PORTAL_E2E_INTERNAL_KEY:-$PTT_PORTAL_SEO_SERVICE_TOKEN}"
export RUN_PORTAL_SEO_E2E=1
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
  if [[ "${PORTAL_E2E_SKIP_FLASK:-1}" != "1" ]]; then
    _wait_http "${PORTAL_E2E_FLASK_URL}/healthz" "Flask monolith"
  fi
  _wait_http "${PORTAL_E2E_URL}/login" "Portal login page"

  if [[ "$PORTAL_E2E_API_URL" == http://127.0.0.1:* ]] || [[ "$PORTAL_E2E_API_URL" == http://localhost:* ]]; then
    echo "==> Local seed (portal map + gate users)"
    if command -v docker >/dev/null 2>&1; then
      docker compose up -d postgres 2>/dev/null || true
    fi
    "$PYTHON" scripts/seed_portal_gate_users.py
    "$PYTHON" scripts/seed_portal_seo_pilot_map.py --apply
    echo "NOTE: Nest portal SEO reads seo_aeo PG directly (PTT_PORTAL_SEO_ENABLED=1); Flask monolith not required."
  fi
fi

echo "==> Seed portal SEO E2E content (Python — không cần Flask restart)"
VIEWER_TITLE="E2E Viewer SEO $(date +%s)"
APPROVE_TITLE="E2E SEO Approve $(date +%s)"
SEED_JSON=$("$PYTHON" scripts/seed_portal_seo_e2e_content.py --apply --title "$APPROVE_TITLE")
echo "$SEED_JSON"
"$PYTHON" scripts/seed_portal_seo_e2e_content.py --apply --title "$VIEWER_TITLE" >/dev/null
export PORTAL_E2E_SEO_TITLE="$APPROVE_TITLE"
export PORTAL_E2E_VIEWER_SEO_TITLE="$VIEWER_TITLE"
export PORTAL_E2E_SKIP_HTTP_SEED=1
export PORTAL_E2E_SEO_CONTENT_ID="$(echo "$SEED_JSON" | "$PYTHON" -c 'import json,sys; print(json.load(sys.stdin).get("id",""))')"

echo "==> Playwright Portal SEO E2E"
cd "$ROOT/services/portal-web"
if [[ ! -d node_modules ]]; then
  npm install
fi
npx playwright test e2e/portal-seo.spec.ts

echo "==> Update Phase 5C UAT sign-off"
cd "$ROOT"
"$PYTHON" -m ptt_crm.phase5_portal_seo_gates
echo "OK  Portal SEO E2E gate complete — see .local-dev/phase5-portal-seo-uat-signoff.json"
