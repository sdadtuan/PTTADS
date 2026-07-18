#!/usr/bin/env bash
# Smoke test Phase 1 local stack
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PORT="${PORT:-5050}"
BASE="http://127.0.0.1:$PORT"

echo "==> Smoke test $BASE"

curl -sf "$BASE/healthz" >/dev/null && echo "OK  GET /healthz" || { echo "FAIL /healthz"; exit 1; }

channels="$(curl -sf "$BASE/api/v1/channels")"
echo "OK  GET /api/v1/channels"
echo "$channels" | head -c 200
echo "..."

# Meta verify challenge (mock token via env not required for route reachability)
# Full test needs CRM_FACEBOOK_VERIFY_TOKEN in .env

PYTHON="${PYTHON:-python3}"
if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PYTHON="$ROOT/.venv/bin/python"
fi

cd "$ROOT"
"$PYTHON" -m unittest tests.test_ptt_jobs tests.test_ptt_channel tests.test_agency_blueprint tests.test_observability tests.test_crm_leads_v1 tests.test_agency_client_leads tests.test_leads_v1_contract -q
echo "OK  unit tests ptt_jobs + ptt_channel + agency + observability + crm_leads_v1 + leads_v1_contract"

if command -v node >/dev/null 2>&1 && [[ -d "$ROOT/services/ptt-crm-api/node_modules" ]]; then
  echo "==> NestJS ptt-crm-api contract tests"
  (cd "$ROOT/services/ptt-crm-api" && npm test --silent && npm run test:e2e --silent)
  echo "OK  ptt-crm-api jest + e2e golden"
elif command -v node >/dev/null 2>&1 && [[ -f "$ROOT/services/ptt-crm-api/package.json" ]]; then
  echo "SKIP ptt-crm-api (run: cd services/ptt-crm-api && npm install && npm run test:e2e)"
fi

if [[ -x "$ROOT/scripts/local_dual_run_check.sh" ]] && curl -sf "${PTT_NEST_LEADS_URL:-http://127.0.0.1:3000}/health" >/dev/null 2>&1; then
  echo "==> Dual-run Flask vs Nest (sample=5)"
  "$ROOT/scripts/local_dual_run_check.sh" 5 || echo "WARN dual-run check failed (Nest/Flask drift?)"
else
  echo "SKIP dual-run (start Nest: ./scripts/local_crm_api_up.sh)"
fi

echo ""
echo "==> Smoke passed. Manual webhook test (with valid Meta sig in .env):"
echo "    curl -X POST $BASE/api/v1/webhooks/meta -H 'Content-Type: application/json' -d @tests/fixtures/channels/meta/webhook_leadgen.json"
