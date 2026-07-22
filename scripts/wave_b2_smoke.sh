#!/usr/bin/env bash
# Wave B2 API smoke — workflows, leads, token vault routes, KPI CRUD.
# Usage:
#   ADMIN_PASSWORD='...' ./scripts/wave_b2_smoke.sh
#   BASE=http://127.0.0.1:3000 CLIENT_ID=660e8400-... ADMIN_PASSWORD='...' ./scripts/wave_b2_smoke.sh
set -euo pipefail

BASE="${BASE:-http://127.0.0.1:3000}"
EMAIL="${ADMIN_EMAIL:-admin@pttads.vn}"
PASS="${ADMIN_PASSWORD:-}"
CLIENT_ID="${CLIENT_ID:-}"

if [[ -z "$PASS" ]]; then
  echo "Set ADMIN_PASSWORD (from /var/www/ptt/.env)" >&2
  exit 1
fi

fail=0
ok() { echo "OK  $*"; }
bad() { echo "FAIL $*"; fail=1; }

http_get() {
  local path="$1"
  local label="$2"
  local code body
  body="$(mktemp)"
  code="$(curl -s -o "$body" -w "%{http_code}" "$BASE$path" "${AUTH[@]}")"
  if [[ "$code" =~ ^2 ]]; then
    ok "$label (HTTP $code)"
  else
    bad "$label (HTTP $code) $(head -c 200 "$body" | tr '\n' ' ')"
  fi
  rm -f "$body"
}

echo "== Wave B2 smoke BASE=$BASE =="

TOKEN="$(
  curl -sf "$BASE/api/v1/staff/auth/login" \
    -H 'Content-Type: application/json' \
    -d "{\"email\":\"$EMAIL\",\"password\":\"$PASS\"}" \
  | python3 -c "import sys,json; print(json.load(sys.stdin).get('access_token',''))"
)"
if [[ -z "$TOKEN" ]]; then
  echo "FAIL login" >&2
  exit 1
fi
ok "staff login"

AUTH=(-H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json")

if [[ -z "$CLIENT_ID" ]]; then
  CLIENT_ID="$(
    curl -sf "$BASE/api/v1/clients?limit=1" "${AUTH[@]}" \
    | python3 -c "import sys,json; cs=json.load(sys.stdin).get('clients') or []; print(cs[0]['id'] if cs else '')"
  )"
fi

if [[ -n "$CLIENT_ID" ]]; then
  ok "client id=$CLIENT_ID"
  http_get "/api/v1/clients/$CLIENT_ID/leads" "GET client leads"
  http_get "/api/v1/clients/$CLIENT_ID/onboarding/workflow-status" "GET onboarding workflow-status"
  sync_code="$(curl -s -o /dev/null -w "%{http_code}" -X POST "$BASE/api/v1/clients/$CLIENT_ID/sync/insights" "${AUTH[@]}" -d '{}')"
  if [[ "$sync_code" =~ ^2 ]]; then
    ok "POST sync/insights (HTTP $sync_code)"
  else
    bad "POST sync/insights (HTTP $sync_code)"
  fi
else
  echo "SKIP client routes — no CLIENT_ID"
fi

# KPI CRUD round-trip (test code)
TEST_CODE="wave_b2_smoke_test"
curl -sf -X DELETE "$BASE/api/v1/kpi-definitions/$TEST_CODE" "${AUTH[@]}" -d '{}' >/dev/null 2>&1 || true
create_code="$(curl -s -o /dev/null -w "%{http_code}" -X POST "$BASE/api/v1/kpi-definitions" "${AUTH[@]}" \
  -d "{\"code\":\"$TEST_CODE\",\"name\":\"Smoke\",\"formula\":\"1+1\",\"granularity\":\"daily\"}")"
if [[ "$create_code" =~ ^2 ]]; then
  ok "POST kpi-definitions (HTTP $create_code)"
  patch_code="$(curl -s -o /dev/null -w "%{http_code}" -X PATCH "$BASE/api/v1/kpi-definitions/$TEST_CODE" "${AUTH[@]}" \
    -d '{"name":"Smoke updated"}')"
  [[ "$patch_code" =~ ^2 ]] && ok "PATCH kpi-definitions (HTTP $patch_code)" || bad "PATCH kpi-definitions (HTTP $patch_code)"
  del_code="$(curl -s -o /dev/null -w "%{http_code}" -X DELETE "$BASE/api/v1/kpi-definitions/$TEST_CODE" "${AUTH[@]}" -d '{}')"
  [[ "$del_code" =~ ^2 ]] && ok "DELETE kpi-definitions (HTTP $del_code)" || bad "DELETE kpi-definitions (HTTP $del_code)"
else
  bad "POST kpi-definitions (HTTP $create_code)"
fi

http_get "/api/v1/notifications?limit=5" "GET notifications (link_url field)"

echo ""
if [[ "$fail" -eq 0 ]]; then
  echo "Wave B2 smoke PASSED"
  exit 0
fi
echo "Wave B2 smoke FAILED — check Nest logs: journalctl -u ptt-crm-api -n 80 --no-pager"
exit 1
