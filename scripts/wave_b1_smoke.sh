#!/usr/bin/env bash
# Wave B1 API smoke — run on VPS after deploy.
# Usage:
#   ADMIN_PASSWORD='...' ./scripts/wave_b1_smoke.sh
#   BASE=http://127.0.0.1:3000 ADMIN_EMAIL=admin@pttads.vn ADMIN_PASSWORD='...' ./scripts/wave_b1_smoke.sh
set -euo pipefail

BASE="${BASE:-http://127.0.0.1:3000}"
EMAIL="${ADMIN_EMAIL:-admin@pttads.vn}"
PASS="${ADMIN_PASSWORD:-}"

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
    if [[ "$code" == "404" ]]; then
      echo "      hint: Nest chưa rebuild Wave B1 — git pull && cd services/ptt-crm-api && npm run build && sudo systemctl restart ptt-crm-api"
    fi
  fi
  rm -f "$body"
}

echo "== Wave B1 smoke BASE=$BASE =="

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

AUTH=(-H "Authorization: Bearer $TOKEN")

health="$(curl -sf "$BASE/health" || true)"
echo "$health" | grep -q '"ok"' && ok "health" || bad "health"

curl -sf "$BASE/api/v1/agency/stats" "${AUTH[@]}" >/dev/null && ok "GET agency/stats" || bad "GET agency/stats"
http_get "/api/v1/kpi-definitions" "GET kpi-definitions"
http_get "/api/v1/notifications?limit=5" "GET notifications"
http_get "/api/v1/jobs?limit=5" "GET jobs"
http_get "/api/v1/crm/hub-campaign-maps?limit=5" "GET hub-campaign-maps"

CLIENT_ID="$(
  curl -sf "$BASE/api/v1/clients?limit=1" "${AUTH[@]}" \
  | python3 -c "import sys,json; cs=json.load(sys.stdin).get('clients') or []; print(cs[0]['id'] if cs else '')"
)"
if [[ -n "$CLIENT_ID" ]]; then
  ok "clients list (id=$CLIENT_ID)"
  http_get "/api/v1/clients/$CLIENT_ID/onboarding" "GET onboarding"
else
  echo "SKIP client onboarding — no clients in PG"
fi

echo ""
if [[ "$fail" -eq 0 ]]; then
  echo "Wave B1 smoke PASSED"
  exit 0
fi
echo "Wave B1 smoke FAILED — check Nest logs: journalctl -u ptt-crm-api -n 80 --no-pager"
exit 1
