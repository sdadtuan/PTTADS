#!/usr/bin/env bash
# Meta campaign write pilot smoke — 1 real campaign (Phase 4)
# Requires: Nest API, Temporal worker, PG, Meta token on pilot client channel account
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

: "${DATABASE_URL:?Set DATABASE_URL}"
: "${PTT_META_CAMPAIGN_WRITE_PILOT_CLIENTS:?Set pilot client UUID}"
: "${PTT_META_CAMPAIGN_WRITE_PILOT_CAMPAIGNS:?Set Meta campaign ID}"

export PTT_META_CAMPAIGN_WRITE_STUB=0
export PTT_META_CAMPAIGN_WRITE_PILOT=1
NEST_URL="${PTT_NEST_LEADS_URL:-http://127.0.0.1:3000}"
CLIENT_ID="${PTT_META_CAMPAIGN_WRITE_PILOT_CLIENTS%%,*}"
CAMPAIGN_ID="${PTT_META_CAMPAIGN_WRITE_PILOT_CAMPAIGNS%%,*}"
BUDGET_VND="${PILOT_BUDGET_VND:-500000}"
INTERNAL_KEY="${PTT_CRM_INTERNAL_KEY:-}"

echo "==> Meta campaign write pilot"
echo "    client=$CLIENT_ID campaign=$CAMPAIGN_ID budget=$BUDGET_VND"

HDR=(-H "Content-Type: application/json" -H "Accept: application/json")
if [[ -n "$INTERNAL_KEY" ]]; then
  HDR+=(-H "X-PTT-Internal-Key: $INTERNAL_KEY")
fi

SUBMIT=$(curl -sf "${HDR[@]}" -X POST "$NEST_URL/api/v1/campaign-writes" -d "{
  \"client_id\": \"$CLIENT_ID\",
  \"external_campaign_id\": \"$CAMPAIGN_ID\",
  \"change_type\": \"daily_budget\",
  \"new_value\": {\"daily_budget_vnd\": $BUDGET_VND},
  \"submitted_by\": \"pilot-smoke@pttads.vn\"
}")
REQ_ID=$(echo "$SUBMIT" | python3 -c "import sys,json; print(json.load(sys.stdin)['request']['id'])")
echo "    submitted request=$REQ_ID"

curl -sf "${HDR[@]}" -X POST "$NEST_URL/api/v1/campaign-writes/$REQ_ID/approve" \
  -d '{"approved_by":"admin@pttads.vn","note":"pilot-smoke"}' >/dev/null
echo "    approved — check Temporal UI + PG status executed"

echo "OK  Pilot smoke submitted. Verify:"
echo "    SELECT id, status, executed_at, execution_error FROM campaign_write_requests WHERE id='$REQ_ID';"
