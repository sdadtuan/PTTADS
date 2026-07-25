#!/usr/bin/env bash
# Wave Z1 staging gate — DDL + API smoke (+ optional Playwright UI)
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

echo "== Wave Z1 Zalo staging gate =="
echo "   DATABASE_URL=$DATABASE_URL"
echo "   PTT_API_URL=$BASE"
echo "   PTT_ZALO_ADS_STUB=${PTT_ZALO_ADS_STUB:-0} PTT_ZALO_INSIGHTS_SYNC=${PTT_ZALO_INSIGHTS_SYNC:-0}"

echo ""
echo "==> Apply Zalo DDL"
bash "$ROOT/scripts/apply_pg_ddl_zalo_insights_sync.sh"

echo ""
echo "==> Verify zalo_insights_sync_state"
python3 -c "
from ptt_crm.pg_schema import pg_zalo_sync_ready
assert pg_zalo_sync_ready(), 'zalo_insights_sync_state not ready'
print('OK  pg_zalo_sync_ready')
"

health_code="$(curl -s -o /dev/null -w '%{http_code}' "$BASE/health" 2>/dev/null || echo 000)"
if [[ ! "$health_code" =~ ^2 ]]; then
  bad "Nest API health (HTTP $health_code) — start: source deploy/env.staging-zalo-pilot.example && ./scripts/local_crm_api_up.sh"
  echo ""
  [[ "$fail" -eq 0 ]] && echo "Wave Z1 Zalo staging gate PASSED (DDL only)" && exit 0
  echo "Wave Z1 Zalo staging gate FAILED"
  exit 1
fi
ok "Nest API health (HTTP $health_code)"

STAFF_TOKEN="$(
  curl -sf "$BASE/api/v1/staff/auth/login" \
    -H 'Content-Type: application/json' \
    -d "{\"email\":\"$STAFF_EMAIL\",\"password\":\"$STAFF_PASS\"}" \
  | python3 -c "import sys,json; print(json.load(sys.stdin).get('access_token',''))" 2>/dev/null || true
)"
[[ -n "$STAFF_TOKEN" ]] && ok "staff login" || bad "staff login"

PORTAL_TOKEN="$(
  curl -sf "$BASE/api/v1/portal/auth/login" \
    -H 'Content-Type: application/json' \
    -d "{\"email\":\"$PORTAL_EMAIL\",\"password\":\"$PORTAL_PASS\"}" \
  | python3 -c "import sys,json; print(json.load(sys.stdin).get('access_token',''))" 2>/dev/null || true
)"
[[ -n "$PORTAL_TOKEN" ]] && ok "portal login" || bad "portal login"

if [[ -n "$STAFF_TOKEN" ]]; then
  hub_body="$(curl -sf "$BASE/api/v1/zalo-ads/hub?days=7" \
    -H "Authorization: Bearer $STAFF_TOKEN" 2>/dev/null || echo '{}')"
  hub_ok="$(python3 -c "import sys,json; d=json.loads(sys.argv[1]); print('1' if d.get('ok') else '0')" "$hub_body" 2>/dev/null || echo 0)"
  [[ "$hub_ok" == "1" ]] && ok "GET zalo-ads/hub" || bad "GET zalo-ads/hub"

  pilot_code="$(curl -s -o /dev/null -w '%{http_code}' "$BASE/api/v1/zalo-ads/pilot-status" \
    -H "Authorization: Bearer $STAFF_TOKEN")"
  [[ "$pilot_code" =~ ^2 ]] && ok "GET zalo-ads/pilot-status (HTTP $pilot_code)" || bad "GET zalo-ads/pilot-status (HTTP $pilot_code)"

  export_code="$(curl -s -o /dev/null -w '%{http_code}' "$BASE/api/v1/zalo-ads/hub/export?days=7&scope=clients" \
    -H "Authorization: Bearer $STAFF_TOKEN")"
  [[ "$export_code" =~ ^2 ]] && ok "GET zalo-ads/hub/export (HTTP $export_code)" || bad "GET zalo-ads/hub/export (HTTP $export_code)"

  client_id="${ZALO_PILOT_CLIENT_ID:-550e8400-e29b-41d4-a716-446655440000}"
  sync_code="$(curl -s -o /dev/null -w '%{http_code}' -X POST "$BASE/api/v1/clients/$client_id/sync/zalo-insights" \
    -H "Authorization: Bearer $STAFF_TOKEN" \
    -H 'Content-Type: application/json' \
    -d '{}')"
  [[ "$sync_code" =~ ^2 ]] && ok "POST clients/:id/sync/zalo-insights (HTTP $sync_code)" || warn "POST sync/zalo-insights (HTTP $sync_code) — may need agency write cap"

  sync_status_code="$(curl -s -o /dev/null -w '%{http_code}' "$BASE/api/v1/clients/$client_id/zalo/sync-status" \
    -H "Authorization: Bearer $STAFF_TOKEN")"
  [[ "$sync_status_code" =~ ^2 ]] && ok "GET clients/:id/zalo/sync-status (HTTP $sync_status_code)" || bad "GET zalo/sync-status (HTTP $sync_status_code)"
fi

if [[ -n "$PORTAL_TOKEN" ]]; then
  perf_body="$(curl -sf "$BASE/api/v1/performance?channel=zalo&group_by=campaign" \
    -H "Authorization: Bearer $PORTAL_TOKEN" 2>/dev/null || echo '{}')"
  perf_ok="$(python3 -c "import sys,json; d=json.loads(sys.argv[1]); print('1' if d.get('ok') and d.get('channel')=='zalo' else '0')" "$perf_body" 2>/dev/null || echo 0)"
  [[ "$perf_ok" == "1" ]] && ok "GET performance?channel=zalo" || bad "GET performance?channel=zalo"
fi

if [[ "$RUN_UI_SMOKE" == "1" ]]; then
  echo ""
  echo "==> UI smoke (ops-web + portal)"
  ops_code="$(curl -s -o /dev/null -w '%{http_code}' "$OPS_BASE/zalo/zalo-ads" 2>/dev/null || echo 000)"
  if [[ "$ops_code" =~ ^2|^3 ]]; then
    ok "ops-web GET /zalo/zalo-ads (HTTP $ops_code)"
  else
    warn "ops-web not reachable at $OPS_BASE (HTTP $ops_code) — start ./scripts/local_ops_up.sh"
  fi

  portal_code="$(curl -s -o /dev/null -w '%{http_code}' "$PORTAL_BASE/zalo" 2>/dev/null || echo 000)"
  if [[ "$portal_code" =~ ^2|^3 ]]; then
    ok "portal-web GET /zalo (HTTP $portal_code)"
  else
    warn "portal-web not reachable at $PORTAL_BASE (HTTP $portal_code) — start ./scripts/local_portal_up.sh"
  fi

  if command -v npx >/dev/null 2>&1 && [[ "$ops_code" =~ ^2|^3 ]]; then
    if (cd "$ROOT/services/ops-web" && npx playwright test e2e/zalo-ads.spec.ts --reporter=line 2>/dev/null); then
      ok "Playwright ops-web zalo-ads.spec.ts"
    else
      warn "Playwright ops-web zalo-ads.spec.ts skipped or failed"
    fi
  fi

  if command -v npx >/dev/null 2>&1 && [[ "$portal_code" =~ ^2|^3 ]]; then
    if (cd "$ROOT/services/portal-web" && npx playwright test e2e/portal.spec.ts -g "Zalo performance" --reporter=line 2>/dev/null); then
      ok "Playwright portal Zalo tab"
    else
      warn "Playwright portal Zalo tab skipped or failed"
    fi
  fi
fi

echo ""
if [[ "$fail" -eq 0 ]]; then
  echo "Wave Z1 Zalo staging gate PASSED"
  exit 0
fi
echo "Wave Z1 Zalo staging gate FAILED"
exit 1
