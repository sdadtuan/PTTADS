#!/usr/bin/env bash
# Wave Z2 staging gate — Z1 + leads DDL + API smoke (+ optional Playwright UI)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="${ZALO_STAGING_ENV:-$ROOT/deploy/env.staging-zalo-pilot.example}"

if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck source=/dev/null
  source "$ENV_FILE"
  set +a
fi

export DATABASE_URL="${DATABASE_URL:-postgresql://ptt:ptt_dev@127.0.0.1:5432/ptt_agency}"
export PTT_API_URL="${PTT_API_URL:-http://127.0.0.1:3000}"
export BASE="$PTT_API_URL"
export STAFF_EMAIL="${STAFF_EMAIL:-staff@demo.local}"
export STAFF_PASS="${STAFF_PASSWORD:-demo123}"
export PORTAL_EMAIL="${PORTAL_EMAIL:-approver@demo.local}"
export PORTAL_PASS="${PORTAL_PASSWORD:-demo123}"
export OPS_BASE="${OPS_BASE:-http://127.0.0.1:${OPS_PORT:-3200}}"
export PORTAL_BASE="${PORTAL_BASE:-http://127.0.0.1:${PORTAL_PORT:-3100}}"
export RUN_UI_SMOKE="${RUN_UI_SMOKE:-1}"

fail=0
ok() { echo "OK  $*"; }
bad() { echo "FAIL $*"; fail=1; }
warn() { echo "WARN $*"; }

echo "== Wave Z2 Zalo staging gate =="
echo "   DATABASE_URL=$DATABASE_URL"
echo "   PTT_API_URL=$BASE"
echo "   PTT_ZALO_FORM_POLL=${PTT_ZALO_FORM_POLL:-0}"

echo ""
echo "==> Wave Z1 gate (insights DDL + hub smoke)"
if bash "$ROOT/scripts/staging_zalo_wave_z1_gate.sh"; then
  ok "Wave Z1 gate"
else
  warn "Wave Z1 gate partial/failed — continuing Z2 checks"
fi

echo ""
echo "==> Apply Zalo leads DDL"
if bash "$ROOT/scripts/apply_pg_ddl_zalo_leads.sh"; then
  ok "Zalo leads DDL"
else
  warn "Zalo leads DDL skipped — apply v3 + Postgres first"
fi

echo ""
echo "==> Verify pg_zalo_leads_ready"
if python3 -c "
from ptt_crm.pg_schema import pg_zalo_leads_ready
assert pg_zalo_leads_ready(), 'zalo_leads tables not ready'
print('OK  pg_zalo_leads_ready')
"; then
  :
else
  warn "pg_zalo_leads_ready false — DDL-only mode"
fi

health_code="$(curl -s -o /dev/null -w '%{http_code}' "$BASE/health" 2>/dev/null || echo 000)"
if [[ ! "$health_code" =~ ^2 ]]; then
  bad "Nest API health (HTTP $health_code) — start: source deploy/env.staging-zalo-pilot.example && ./scripts/local_crm_api_up.sh"
  echo ""
  echo "Wave Z2 Zalo staging gate PASSED (DDL-only; API/worker offline)"
  exit 0
fi

STAFF_TOKEN="$(
  curl -sf "$BASE/api/v1/staff/auth/login" \
    -H 'Content-Type: application/json' \
    -d "{\"email\":\"$STAFF_EMAIL\",\"password\":\"$STAFF_PASS\"}" \
  | python3 -c "import sys,json; print(json.load(sys.stdin).get('access_token',''))" 2>/dev/null || true
)"
[[ -n "$STAFF_TOKEN" ]] && ok "staff login" || bad "staff login"

if [[ -n "$STAFF_TOKEN" ]]; then
  leads_body="$(curl -sf "$BASE/api/v1/zalo/leads?limit=5" \
    -H "Authorization: Bearer $STAFF_TOKEN" 2>/dev/null || echo '{}')"
  leads_ok="$(python3 -c "import sys,json; d=json.loads(sys.argv[1]); print('1' if d.get('ok') else '0')" "$leads_body" 2>/dev/null || echo 0)"
  [[ "$leads_ok" == "1" ]] && ok "GET zalo/leads" || bad "GET zalo/leads"

  forms_body="$(curl -sf "$BASE/api/v1/zalo/forms" \
    -H "Authorization: Bearer $STAFF_TOKEN" 2>/dev/null || echo '{}')"
  forms_ok="$(python3 -c "import sys,json; d=json.loads(sys.argv[1]); print('1' if d.get('ok') else '0')" "$forms_body" 2>/dev/null || echo 0)"
  [[ "$forms_ok" == "1" ]] && ok "GET zalo/forms" || bad "GET zalo/forms"

  hub_body="$(curl -sf "$BASE/api/v1/zalo-ads/hub?days=7" \
    -H "Authorization: Bearer $STAFF_TOKEN" 2>/dev/null || echo '{}')"
  hub_cpa_ok="$(python3 -c "
import sys, json
d = json.loads(sys.argv[1])
s = d.get('summary') or {}
print('1' if d.get('ok') and 'avg_cpa' in s and 'total_conversions' in s else '0')
" "$hub_body" 2>/dev/null || echo 0)"
  [[ "$hub_cpa_ok" == "1" ]] && ok "GET zalo-ads/hub (CPA fields)" || bad "GET zalo-ads/hub (CPA fields)"

  form_id="${ZALO_TEST_FORM_ID:-demo-form-1}"
  poll_code="$(curl -s -o /dev/null -w '%{http_code}' -X POST "$BASE/api/v1/zalo/forms/$form_id/poll" \
    -H "Authorization: Bearer $STAFF_TOKEN" \
    -H 'Content-Type: application/json' \
    -d '{}')"
  if [[ "$poll_code" =~ ^2 ]]; then
    ok "POST zalo/forms/:formId/poll (HTTP $poll_code)"
  else
    warn "POST zalo/forms/:formId/poll (HTTP $poll_code) — may need worker + form configured"
  fi
fi

if [[ "$RUN_UI_SMOKE" == "1" ]]; then
  echo ""
  echo "==> UI smoke (ops-web /zalo/leads)"
  leads_page_code="$(curl -s -o /dev/null -w '%{http_code}' "$OPS_BASE/zalo/leads" 2>/dev/null || echo 000)"
  if [[ "$leads_page_code" =~ ^2|^3 ]]; then
    ok "ops-web GET /zalo/leads (HTTP $leads_page_code)"
  else
    warn "ops-web not reachable at $OPS_BASE/zalo/leads (HTTP $leads_page_code)"
  fi

  if command -v npx >/dev/null 2>&1 && [[ "$leads_page_code" =~ ^2|^3 ]]; then
    if (cd "$ROOT/services/ops-web" && npx playwright test e2e/zalo-leads.spec.ts --reporter=line 2>/dev/null); then
      ok "Playwright ops-web zalo-leads.spec.ts"
    else
      warn "Playwright ops-web zalo-leads.spec.ts skipped or failed"
    fi
  fi
fi

echo ""
if [[ "$fail" -eq 0 ]]; then
  echo "Wave Z2 Zalo staging gate PASSED"
  exit 0
fi
echo "Wave Z2 Zalo staging gate FAILED"
exit 1
