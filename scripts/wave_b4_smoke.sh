#!/usr/bin/env bash
# Wave B4 smoke — funnel routes + care gate API presence.
set -euo pipefail

BASE="${BASE:-http://127.0.0.1:3000}"
EMAIL="${ADMIN_EMAIL:-admin@pttads.vn}"
PASS="${ADMIN_PASSWORD:-}"
LEAD_ID="${LEAD_ID:-}"

if [[ -z "$PASS" ]]; then
  echo "Set ADMIN_PASSWORD" >&2
  exit 1
fi

fail=0
ok() { echo "OK  $*"; }
bad() { echo "FAIL $*"; fail=1; }

echo "== Wave B4 smoke BASE=$BASE =="

TOKEN="$(
  curl -sf "$BASE/api/v1/staff/auth/login" \
    -H 'Content-Type: application/json' \
    -d "{\"email\":\"$EMAIL\",\"password\":\"$PASS\"}" \
  | python3 -c "import sys,json; print(json.load(sys.stdin).get('access_token',''))"
)"
[[ -n "$TOKEN" ]] && ok "staff login" || { bad "login"; exit 1; }

AUTH=(-H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json")

if [[ -z "$LEAD_ID" ]]; then
  LEAD_ID="$(
    curl -sf "$BASE/api/v1/leads?limit=1" "${AUTH[@]}" \
    | python3 -c "import sys,json; ls=json.load(sys.stdin).get('leads') or []; print(ls[0]['id'] if ls else '')"
  )"
fi
[[ -n "$LEAD_ID" ]] && ok "lead id=$LEAD_ID" || { bad "no LEAD_ID"; exit 1; }

funnel_code="$(curl -s -o /dev/null -w "%{http_code}" "$BASE/api/v1/leads/$LEAD_ID/funnel" "${AUTH[@]}")"
[[ "$funnel_code" =~ ^2 ]] && ok "GET /leads/:id/funnel (HTTP $funnel_code)" || bad "GET funnel (HTTP $funnel_code)"

rq_code="$(curl -s -o /dev/null -w "%{http_code}" "$BASE/api/v1/leads/review-queue/count" "${AUTH[@]}")"
if [[ "$rq_code" =~ ^2 ]]; then
  ok "GET review-queue/count (HTTP $rq_code)"
elif [[ "$rq_code" == "403" ]]; then
  ok "GET review-queue/count (HTTP 403 — user thiếu cap assign, route OK)"
else
  bad "GET review-queue/count (HTTP $rq_code)"
fi

care_code="$(curl -s -o /dev/null -w "%{http_code}" "$BASE/api/v1/leads/$LEAD_ID/care-pipeline" "${AUTH[@]}")"
[[ "$care_code" =~ ^2 ]] && ok "GET care-pipeline (HTTP $care_code)" || bad "GET care-pipeline (HTTP $care_code)"

list_code="$(curl -s -o /dev/null -w "%{http_code}" "$BASE/api/v1/leads?limit=1&hide_review_queue=0" "${AUTH[@]}")"
[[ "$list_code" =~ ^2 ]] && ok "GET leads hide_review_queue=0 (HTTP $list_code)" || bad "GET leads filter (HTTP $list_code)"

echo ""
if [[ "$fail" -eq 0 ]]; then
  echo "Wave B4 smoke PASSED"
  exit 0
fi
echo "Wave B4 smoke FAILED"
exit 1
