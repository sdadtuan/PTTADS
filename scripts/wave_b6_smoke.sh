#!/usr/bin/env bash
# Wave B6 smoke — Launch QA + Creative brief lifecycle routes
set -euo pipefail

BASE="${BASE:-http://127.0.0.1:3000}"
EMAIL="${ADMIN_EMAIL:-admin@pttads.vn}"
PASS="${ADMIN_PASSWORD:-}"
LIFECYCLE_ID="${LIFECYCLE_ID:-}"

if [[ -z "$PASS" ]]; then
  echo "Set ADMIN_PASSWORD" >&2
  exit 1
fi

fail=0
ok() { echo "OK  $*"; }
bad() { echo "FAIL $*"; fail=1; }

echo "== Wave B6 smoke BASE=$BASE =="

TOKEN="$(
  curl -sf "$BASE/api/v1/staff/auth/login" \
    -H 'Content-Type: application/json' \
    -d "{\"email\":\"$EMAIL\",\"password\":\"$PASS\"}" \
  | python3 -c "import sys,json; print(json.load(sys.stdin).get('access_token',''))"
)"
[[ -n "$TOKEN" ]] && ok "staff login" || { bad "login"; exit 1; }

AUTH=(-H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json")

if [[ -z "$LIFECYCLE_ID" ]]; then
  LIFECYCLE_ID="$(
    curl -sf "$BASE/api/crm/service-lifecycle?include_draft=1" "${AUTH[@]}" \
    | python3 -c "import sys,json; ls=json.load(sys.stdin).get('lifecycles') or []; print(ls[0]['id'] if ls else '')"
  )"
fi

if [[ -n "$LIFECYCLE_ID" ]]; then
  ok "lifecycle id=$LIFECYCLE_ID"
  for path in launch-qa creative-brief; do
    code="$(curl -s -o /dev/null -w "%{http_code}" "$BASE/api/crm/service-lifecycle/$LIFECYCLE_ID/$path" "${AUTH[@]}")"
    [[ "$code" =~ ^2 ]] && ok "GET service-lifecycle/:id/$path (HTTP $code)" || bad "GET lifecycle $path (HTTP $code)"
  done
  adv_code="$(curl -s -o /dev/null -w "%{http_code}" "$BASE/api/crm/service-lifecycle/$LIFECYCLE_ID/advance-info" "${AUTH[@]}")"
  [[ "$adv_code" =~ ^2 ]] && ok "GET advance-info (HTTP $adv_code)" || bad "GET advance-info (HTTP $adv_code)"
  lqa_stats="$(curl -s -o /dev/null -w "%{http_code}" "$BASE/api/crm/launch-qa/stats" "${AUTH[@]}")"
  [[ "$lqa_stats" =~ ^2 ]] && ok "GET /crm/launch-qa/stats (HTTP $lqa_stats)" || bad "GET launch-qa/stats (HTTP $lqa_stats)"
  lqa_runs="$(curl -s -o /dev/null -w "%{http_code}" "$BASE/api/crm/launch-qa/runs?status=all" "${AUTH[@]}")"
  [[ "$lqa_runs" =~ ^2 ]] && ok "GET /crm/launch-qa/runs (HTTP $lqa_runs)" || bad "GET launch-qa/runs (HTTP $lqa_runs)"
  cr_stats="$(curl -s -o /dev/null -w "%{http_code}" "$BASE/api/crm/creatives/stats" "${AUTH[@]}")"
  [[ "$cr_stats" =~ ^2 ]] && ok "GET /crm/creatives/stats (HTTP $cr_stats)" || bad "GET creatives/stats (HTTP $cr_stats)"
  cr_list="$(curl -s -o /dev/null -w "%{http_code}" "$BASE/api/crm/creatives?status=all" "${AUTH[@]}")"
  [[ "$cr_list" =~ ^2 ]] && ok "GET /crm/creatives (HTTP $cr_list)" || bad "GET creatives (HTTP $cr_list)"
else
  bad "no LIFECYCLE_ID — skip B6 lifecycle routes"
fi

echo ""
if [[ "$fail" -eq 0 ]]; then
  echo "Wave B6 smoke PASSED"
  exit 0
fi
echo "Wave B6 smoke FAILED"
exit 1
