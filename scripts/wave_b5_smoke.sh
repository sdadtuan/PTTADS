#!/usr/bin/env bash
# Wave B5 smoke — S0 contract routes + S5 lifecycle SOP + SOP hub
set -euo pipefail

BASE="${BASE:-http://127.0.0.1:3000}"
EMAIL="${ADMIN_EMAIL:-admin@pttads.vn}"
PASS="${ADMIN_PASSWORD:-}"
LEAD_ID="${LEAD_ID:-}"
LIFECYCLE_ID="${LIFECYCLE_ID:-}"

if [[ -z "$PASS" ]]; then
  echo "Set ADMIN_PASSWORD" >&2
  exit 1
fi

fail=0
ok() { echo "OK  $*"; }
bad() { echo "FAIL $*"; fail=1; }

echo "== Wave B5 smoke BASE=$BASE =="

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

contract_code="$(curl -s -o /dev/null -w "%{http_code}" "$BASE/api/v1/leads/$LEAD_ID/contract" "${AUTH[@]}")"
if [[ "$contract_code" =~ ^2 ]]; then
  ok "GET /leads/:id/contract (HTTP $contract_code)"
elif [[ "$contract_code" == "404" ]]; then
  body="$(curl -s "$BASE/api/v1/leads/$LEAD_ID/contract" "${AUTH[@]}")"
  if [[ "$body" == *"PTT_CRM_SERVICE_DELIVERY_NEST"* ]]; then
    bad "Wave B5 disabled — set PTT_CRM_SERVICE_DELIVERY_NEST=1"
  else
    bad "GET contract (HTTP $contract_code)"
  fi
else
  bad "GET contract (HTTP $contract_code)"
fi

pending_code="$(curl -s -o /dev/null -w "%{http_code}" "$BASE/api/v1/contracts/approvals/pending" "${AUTH[@]}")"
if [[ "$pending_code" =~ ^2 ]]; then
  ok "GET contracts/approvals/pending (HTTP $pending_code)"
elif [[ "$pending_code" == "403" ]]; then
  ok "GET approvals/pending (HTTP 403 — thiếu cap, route OK)"
else
  bad "GET approvals/pending (HTTP $pending_code)"
fi

if [[ -z "$LIFECYCLE_ID" ]]; then
  LIFECYCLE_ID="$(
    curl -sf "$BASE/api/crm/service-lifecycle?include_draft=1" "${AUTH[@]}" \
    | python3 -c "import sys,json; ls=json.load(sys.stdin).get('lifecycles') or []; print(ls[0]['id'] if ls else '')"
  )"
fi

if [[ -n "$LIFECYCLE_ID" ]]; then
  ok "lifecycle id=$LIFECYCLE_ID"
  sop_code="$(curl -s -o /dev/null -w "%{http_code}" "$BASE/api/crm/service-lifecycle/$LIFECYCLE_ID/sop" "${AUTH[@]}")"
  [[ "$sop_code" =~ ^2 ]] && ok "GET service-lifecycle/:id/sop (HTTP $sop_code)" || bad "GET lifecycle sop (HTTP $sop_code)"
else
  bad "no LIFECYCLE_ID — skip S5 sop route"
fi

sop_tpl_code="$(curl -s -o /dev/null -w "%{http_code}" "$BASE/api/crm/sop/templates" "${AUTH[@]}")"
[[ "$sop_tpl_code" =~ ^2 ]] && ok "GET /crm/sop/templates (HTTP $sop_tpl_code)" || bad "GET sop/templates (HTTP $sop_tpl_code)"

sop_runs_code="$(curl -s -o /dev/null -w "%{http_code}" "$BASE/api/crm/sop/runs?status=all" "${AUTH[@]}")"
[[ "$sop_runs_code" =~ ^2 ]] && ok "GET /crm/sop/runs (HTTP $sop_runs_code)" || bad "GET sop/runs (HTTP $sop_runs_code)"

echo ""
if [[ "$fail" -eq 0 ]]; then
  echo "Wave B5 smoke PASSED"
  exit 0
fi
echo "Wave B5 smoke FAILED"
exit 1
