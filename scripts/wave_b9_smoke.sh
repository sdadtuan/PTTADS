#!/usr/bin/env bash
# Wave B9 smoke — tracking health, conversion rules, test-pixel stub
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BASE="${BASE:-http://127.0.0.1:3000}"
STAFF_EMAIL="${STAFF_EMAIL:-staff@demo.local}"
STAFF_PASS="${STAFF_PASSWORD:-demo123}"
CLIENT_ID="${B9_SMOKE_CLIENT_ID:-}"

fail=0
ok() { echo "OK  $*"; }
bad() { echo "FAIL $*"; fail=1; }

echo "== Wave B9 smoke BASE=$BASE =="

STAFF_TOKEN="$(
  curl -sf "$BASE/api/v1/staff/auth/login" \
    -H 'Content-Type: application/json' \
    -d "{\"email\":\"$STAFF_EMAIL\",\"password\":\"$STAFF_PASS\"}" \
  | python3 -c "import sys,json; print(json.load(sys.stdin).get('access_token',''))" 2>/dev/null || true
)"
[[ -n "$STAFF_TOKEN" ]] && ok "staff login" || bad "staff login"

if [[ -n "$STAFF_TOKEN" ]]; then
  health_qs=""
  if [[ -n "$CLIENT_ID" ]]; then
    health_qs="?client_id=${CLIENT_ID}"
  fi
  health_body="$(curl -sf "$BASE/api/v1/meta/tracking/health${health_qs}" \
    -H "Authorization: Bearer $STAFF_TOKEN" 2>/dev/null || echo '{}')"
  health_ok="$(python3 -c "
import sys,json
d=json.loads(sys.argv[1])
if not d.get('ok'):
    print('0'); raise SystemExit
if d.get('disabled'):
    print('disabled'); raise SystemExit
g=d.get('global') or {}
print('1' if isinstance(g, dict) and 'sent' in g else '0')
" "$health_body" 2>/dev/null || echo 0)"
  if [[ "$health_ok" == "1" ]]; then
    ok "GET meta/tracking/health"
  elif [[ "$health_ok" == "disabled" ]]; then
    bad "GET meta/tracking/health (PTT_META_TRACKING_ENABLED=0 on API)"
  else
    bad "GET meta/tracking/health"
  fi

  rules_code="$(curl -s -o /dev/null -w "%{http_code}" "$BASE/api/v1/meta/conversion-rules" \
    -H "Authorization: Bearer $STAFF_TOKEN")"
  [[ "$rules_code" =~ ^2 ]] && ok "GET meta/conversion-rules (HTTP $rules_code)" || bad "GET conversion-rules (HTTP $rules_code)"

  events_code="$(curl -s -o /dev/null -w "%{http_code}" "$BASE/api/v1/meta/capi/events?limit=5" \
    -H "Authorization: Bearer $STAFF_TOKEN")"
  [[ "$events_code" =~ ^2 ]] && ok "GET meta/capi/events (HTTP $events_code)" || bad "GET capi/events (HTTP $events_code)"

  if [[ -n "$CLIENT_ID" ]]; then
    acct_body="$(curl -sf "$BASE/api/v1/meta/tracking/health?client_id=${CLIENT_ID}" \
      -H "Authorization: Bearer $STAFF_TOKEN" 2>/dev/null || echo '{}')"
    acct_id="$(python3 -c "
import sys,json
d=json.loads(sys.argv[1])
rows=d.get('accounts') or []
print(rows[0].get('channel_account_id','') if rows else '')
" "$acct_body" 2>/dev/null || true)"
    if [[ -n "$acct_id" ]]; then
      test_body="$(curl -sf -X POST \
        "$BASE/api/v1/clients/${CLIENT_ID}/channel-accounts/${acct_id}/test-pixel" \
        -H "Authorization: Bearer $STAFF_TOKEN" \
        -H 'Content-Type: application/json' \
        -d '{}' 2>/dev/null || echo '{}')"
      test_ok="$(python3 -c "import sys,json; d=json.loads(sys.argv[1]); print('1' if d.get('ok') else '0')" "$test_body" 2>/dev/null || echo 0)"
      [[ "$test_ok" == "1" ]] && ok "POST test-pixel stub" || bad "POST test-pixel (set PTT_CAPI_STUB=1 + pixel on account)"
    else
      ok "POST test-pixel skipped (no meta channel account for client)"
    fi
  else
    ok "POST test-pixel skipped (set B9_SMOKE_CLIENT_ID for full path)"
  fi
fi

echo ""
if [[ "$fail" -eq 0 ]]; then
  echo "Wave B9 smoke PASSED"
  exit 0
fi
echo "Wave B9 smoke FAILED"
exit 1
