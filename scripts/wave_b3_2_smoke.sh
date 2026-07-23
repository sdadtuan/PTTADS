#!/usr/bin/env bash
# Wave B3.2 smoke — Meta hub filters + CSV export.
# Usage:
#   ADMIN_PASSWORD='...' ./scripts/wave_b3_2_smoke.sh
#   CLIENT_ID=<uuid> ADMIN_PASSWORD='...' ./scripts/wave_b3_2_smoke.sh
set -euo pipefail

BASE="${BASE:-http://127.0.0.1:3000}"
EMAIL="${ADMIN_EMAIL:-admin@pttads.vn}"
PASS="${ADMIN_PASSWORD:-}"
CLIENT_ID="${CLIENT_ID:-}"

if [[ -z "$PASS" ]]; then
  echo "Set ADMIN_PASSWORD" >&2
  exit 1
fi

fail=0
ok() { echo "OK  $*"; }
bad() { echo "FAIL $*"; fail=1; }

echo "== Wave B3.2 smoke BASE=$BASE =="

TOKEN="$(
  curl -sf "$BASE/api/v1/staff/auth/login" \
    -H 'Content-Type: application/json' \
    -d "{\"email\":\"$EMAIL\",\"password\":\"$PASS\"}" \
  | python3 -c "import sys,json; print(json.load(sys.stdin).get('access_token',''))"
)"
[[ -n "$TOKEN" ]] && ok "staff login" || { echo "FAIL login"; exit 1; }

AUTH=(-H "Authorization: Bearer $TOKEN")

hub_resp="$(mktemp)"
hub_code="$(curl -s -o "$hub_resp" -w "%{http_code}" \
  "$BASE/api/v1/facebook-ads/hub?days=28&date_to=$(date -u -v-1d +%Y-%m-%d 2>/dev/null || date -u -d 'yesterday' +%Y-%m-%d)" \
  "${AUTH[@]}")"
if [[ "$hub_code" == "200" ]]; then
  ok "GET hub days=28 (HTTP 200)"
  python3 -c "
import json
b = json.load(open('$hub_resp'))
assert b.get('ok') is True, b
assert 'date_from' in b and 'date_to' in b, b
print('range', b['date_from'], '->', b['date_to'], 'clients', len(b.get('clients') or []))
"
else
  bad "GET hub (HTTP $hub_code) $(head -c 200 "$hub_resp" | tr '\n' ' ')"
fi
rm -f "$hub_resp"

if [[ -n "$CLIENT_ID" ]]; then
  filt_code="$(curl -s -o /dev/null -w "%{http_code}" \
    "$BASE/api/v1/facebook-ads/hub?days=7&client_id=$CLIENT_ID" "${AUTH[@]}")"
  [[ "$filt_code" == "200" ]] && ok "GET hub client_id filter" || bad "client filter HTTP $filt_code"
fi

exp_file="$(mktemp)"
exp_code="$(curl -s -o "$exp_file" -w "%{http_code}" \
  "$BASE/api/v1/facebook-ads/hub/export?days=7&scope=clients" "${AUTH[@]}")"
if [[ "$exp_code" == "200" ]]; then
  head_line="$(head -1 "$exp_file")"
  if [[ "$head_line" == *"client_id"* ]]; then
    ok "GET hub/export clients CSV"
  else
    bad "export CSV missing header"
  fi
else
  bad "GET export (HTTP $exp_code)"
fi
rm -f "$exp_file"

exp2_file="$(mktemp)"
exp2_code="$(curl -s -o "$exp2_file" -w "%{http_code}" \
  "$BASE/api/v1/facebook-ads/hub/export?days=7&scope=campaigns" "${AUTH[@]}")"
if [[ "$exp2_code" == "200" ]]; then
  head_line="$(head -1 "$exp2_file")"
  if [[ "$head_line" == *"campaign_id"* ]]; then
    ok "GET hub/export campaigns CSV"
  else
    bad "campaign export CSV missing header"
  fi
else
  bad "GET campaign export (HTTP $exp2_code)"
fi
rm -f "$exp2_file"

echo ""
if [[ "$fail" -eq 0 ]]; then
  echo "Wave B3.2 smoke PASSED"
  exit 0
fi
echo "Wave B3.2 smoke FAILED"
exit 1
