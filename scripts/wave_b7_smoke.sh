#!/usr/bin/env bash
# Wave B7 smoke — client offboard routes (read-only unless OFFBOARD_SMOKE=1)
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

echo "== Wave B7 smoke BASE=$BASE =="

TOKEN="$(
  curl -sf "$BASE/api/v1/staff/auth/login" \
    -H 'Content-Type: application/json' \
    -d "{\"email\":\"$EMAIL\",\"password\":\"$PASS\"}" \
  | python3 -c "import sys,json; print(json.load(sys.stdin).get('access_token',''))"
)"
[[ -n "$TOKEN" ]] && ok "staff login" || { bad "login"; exit 1; }

AUTH=(-H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json")

if [[ -z "$CLIENT_ID" ]]; then
  CLIENT_ID="$(
    curl -sf "$BASE/api/v1/clients?limit=5" "${AUTH[@]}" \
    | python3 -c "import sys,json; cs=json.load(sys.stdin).get('clients') or []; print(cs[0]['id'] if cs else '')"
  )"
fi

if [[ -n "$CLIENT_ID" ]]; then
  ok "client id=$CLIENT_ID"
  audit_code="$(curl -s -o /dev/null -w "%{http_code}" "$BASE/api/v1/clients/$CLIENT_ID/offboard/audit" "${AUTH[@]}")"
  [[ "$audit_code" =~ ^2 ]] && ok "GET clients/:id/offboard/audit (HTTP $audit_code)" || bad "GET offboard/audit (HTTP $audit_code)"

  detail="$(curl -sf "$BASE/api/v1/clients/$CLIENT_ID" "${AUTH[@]}" 2>/dev/null || echo '{}')"
  locked="$(python3 -c "import sys,json; d=json.loads(sys.argv[1]); print('1' if d.get('tenant_locked') else '0')" "$detail" 2>/dev/null || echo 0)"

  if [[ "${OFFBOARD_SMOKE:-0}" == "1" && "$locked" != "1" ]]; then
    off_body="$(curl -sf -X POST "$BASE/api/v1/clients/$CLIENT_ID/offboard" "${AUTH[@]}" \
      -d '{"reason":"other","note":"wave-b7-smoke"}' || echo '{}')"
    ok_val="$(python3 -c "import sys,json; d=json.loads(sys.argv[1]); print('1' if d.get('ok') else '0')" "$off_body" 2>/dev/null || echo 0)"
    [[ "$ok_val" == "1" ]] && ok "POST offboard (idempotent ok)" || bad "POST offboard failed"

    off2="$(curl -sf -X POST "$BASE/api/v1/clients/$CLIENT_ID/offboard" "${AUTH[@]}" \
      -d '{"reason":"other"}' || echo '{}')"
    idem="$(python3 -c "import sys,json; d=json.loads(sys.argv[1]); print('1' if d.get('idempotent') else '0')" "$off2" 2>/dev/null || echo 0)"
    [[ "$idem" == "1" ]] && ok "POST offboard idempotent replay" || bad "offboard idempotent replay"

    patch_code="$(curl -s -o /dev/null -w "%{http_code}" -X PATCH "$BASE/api/v1/clients/$CLIENT_ID" "${AUTH[@]}" \
      -d '{"notes":"blocked-after-offboard"}')"
    [[ "$patch_code" == "403" ]] && ok "PATCH client blocked (HTTP 403)" || bad "PATCH after offboard (HTTP $patch_code, want 403)"
  else
    echo "SKIP POST offboard — set OFFBOARD_SMOKE=1 and use disposable CLIENT_ID to mutate"
  fi
else
  bad "no CLIENT_ID — skip B7 offboard routes"
fi

echo ""
if [[ "$fail" -eq 0 ]]; then
  echo "Wave B7 smoke PASSED"
  exit 0
fi
echo "Wave B7 smoke FAILED"
exit 1
