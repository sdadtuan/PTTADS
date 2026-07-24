#!/usr/bin/env bash
# Wave B8 smoke — attribution on performance + facebook hub (read-only)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BASE="${BASE:-http://127.0.0.1:3000}"
STAFF_EMAIL="${STAFF_EMAIL:-staff@demo.local}"
STAFF_PASS="${STAFF_PASSWORD:-demo123}"
PORTAL_EMAIL="${PORTAL_EMAIL:-approver@demo.local}"
PORTAL_PASS="${PORTAL_PASSWORD:-demo123}"

fail=0
ok() { echo "OK  $*"; }
bad() { echo "FAIL $*"; fail=1; }

echo "== Wave B8 smoke BASE=$BASE =="

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
  hub_body="$(curl -sf "$BASE/api/v1/facebook-ads/hub?days=7" \
    -H "Authorization: Bearer $STAFF_TOKEN" 2>/dev/null || echo '{}')"
  hub_ok="$(python3 -c "import sys,json; d=json.loads(sys.argv[1]); print('1' if d.get('ok') and d.get('attribution',{}).get('attribution_model')=='last_touch_crm' else '0')" "$hub_body" 2>/dev/null || echo 0)"
  [[ "$hub_ok" == "1" ]] && ok "GET facebook-ads/hub attribution" || bad "GET facebook-ads/hub attribution"

  camp_code="$(curl -s -o /dev/null -w "%{http_code}" "$BASE/api/v1/facebook-ads/hub/campaigns?days=7" \
    -H "Authorization: Bearer $STAFF_TOKEN")"
  [[ "$camp_code" =~ ^2 ]] && ok "GET facebook-ads/hub/campaigns (HTTP $camp_code)" || bad "GET hub/campaigns (HTTP $camp_code)"

  sync_code="$(curl -s -o /dev/null -w "%{http_code}" "$BASE/api/v1/meta/sync/status" \
    -H "Authorization: Bearer $STAFF_TOKEN")"
  [[ "$sync_code" =~ ^2 ]] && ok "GET meta/sync/status (HTTP $sync_code)" || bad "GET meta/sync/status (HTTP $sync_code)"
fi

if [[ -n "$PORTAL_TOKEN" ]]; then
  perf_body="$(curl -sf "$BASE/api/v1/performance?channel=meta&group_by=campaign" \
    -H "Authorization: Bearer $PORTAL_TOKEN" 2>/dev/null || echo '{}')"
  perf_ok="$(python3 -c "
import sys,json
d=json.loads(sys.argv[1])
if d.get('attribution_model')!='last_touch_crm':
    print('0'); raise SystemExit
rows=d.get('rows') or []
row=next((r for r in rows if r.get('external_campaign_id')=='camp_e2e'), None)
print('1' if row and row.get('hub_mapped') and row.get('cpl_delta_vnd') is not None else '0')
" "$perf_body" 2>/dev/null || echo 0)"
  if [[ "$perf_ok" == "1" ]]; then
    ok "GET performance CPL delta (camp_e2e mapped)"
  else
    model_ok="$(python3 -c "import sys,json; d=json.loads(sys.argv[1]); print('1' if d.get('attribution_model')=='last_touch_crm' else '0')" "$perf_body" 2>/dev/null || echo 0)"
    [[ "$model_ok" == "1" ]] && ok "GET performance attribution_model (no camp_e2e seed)" || bad "GET performance attribution"
  fi
fi

echo ""
if [[ "$fail" -eq 0 ]]; then
  echo "Wave B8 smoke PASSED"
  exit 0
fi
echo "Wave B8 smoke FAILED"
exit 1
