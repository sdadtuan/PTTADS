#!/usr/bin/env bash
# Wave B10 smoke — anomalies, roas, budget-recommendations
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BASE="${BASE:-http://127.0.0.1:3000}"
STAFF_EMAIL="${STAFF_EMAIL:-staff@demo.local}"
STAFF_PASS="${STAFF_PASSWORD:-demo123}"
CLIENT_ID="${B10_SMOKE_CLIENT_ID:-}"

fail=0
ok() { echo "OK  $*"; }
bad() { echo "FAIL $*"; fail=1; }

echo "== Wave B10 smoke BASE=$BASE =="

STAFF_TOKEN="$(
  curl -sf "$BASE/api/v1/staff/auth/login" \
    -H 'Content-Type: application/json' \
    -d "{\"email\":\"$STAFF_EMAIL\",\"password\":\"$STAFF_PASS\"}" \
  | python3 -c "import sys,json; print(json.load(sys.stdin).get('access_token',''))" 2>/dev/null || true
)"
[[ -n "$STAFF_TOKEN" ]] && ok "staff login" || bad "staff login"

if [[ -n "$STAFF_TOKEN" ]]; then
  qs=""
  if [[ -n "$CLIENT_ID" ]]; then
    qs="?client_id=${CLIENT_ID}"
  fi

  for path in meta/anomalies meta/roas meta/budget-recommendations; do
    body="$(curl -sf "$BASE/api/v1/${path}${qs}" -H "Authorization: Bearer $STAFF_TOKEN" 2>/dev/null || echo '{}')"
    parsed="$(python3 -c "
import sys,json
d=json.loads(sys.argv[1])
if not d.get('ok'):
    print('0'); raise SystemExit
if d.get('disabled'):
    print('disabled'); raise SystemExit
print('1')
" "$body" 2>/dev/null || echo 0)"
    if [[ "$parsed" == "1" ]]; then
      ok "GET /${path}"
    elif [[ "$parsed" == "disabled" ]]; then
      bad "GET /${path} (PTT_META_ANOMALY_ENABLED/PTT_META_ROAS_ENABLED=0 on API)"
    else
      bad "GET /${path}"
    fi
  done
fi

if [[ "$fail" -ne 0 ]]; then
  exit 1
fi
echo "Wave B10 smoke PASS"
