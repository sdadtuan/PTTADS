#!/usr/bin/env bash
# Seed unique creative for Playwright approve E2E (Temporal WF when configured)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CLIENT_ID="${1:-${PORTAL_E2E_CLIENT_ID:-550e8400-e29b-41d4-a716-446655440000}}"
API="${PTT_API_URL:-${PORTAL_E2E_API_URL:-http://127.0.0.1:3000}}"
TITLE="E2E Banner $(date +%s)"
export PORTAL_E2E_CREATIVE_TITLE="$TITLE"

HEADERS=(-H 'Content-Type: application/json')
if [[ -n "${PTT_CRM_INTERNAL_KEY:-}" ]]; then
  HEADERS+=(-H "X-PTT-Internal-Key: $PTT_CRM_INTERNAL_KEY")
fi

echo "==> Submit creative '$TITLE' for client $CLIENT_ID"
curl -sf -X POST "$API/api/v1/creatives" \
  "${HEADERS[@]}" \
  -d "{
    \"client_id\": \"$CLIENT_ID\",
    \"title\": \"$TITLE\",
    \"description\": \"Playwright approve flow — Temporal live\",
    \"external_campaign_id\": \"camp_e2e_1\",
    \"version\": 1,
    \"submitted_by\": \"e2e@pttads.vn\"
  }" | python3 -m json.tool
echo "OK  PORTAL_E2E_CREATIVE_TITLE=$TITLE"
