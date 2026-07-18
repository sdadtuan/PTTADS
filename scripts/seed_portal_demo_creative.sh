#!/usr/bin/env bash
# Seed pending creative via Nest internal API (starts Temporal WF when configured)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CLIENT_ID="${1:-550e8400-e29b-41d4-a716-446655440000}"
API="${PTT_API_URL:-http://127.0.0.1:3000}"

echo "==> Submit creative for client $CLIENT_ID via POST /api/v1/creatives"
curl -sf -X POST "$API/api/v1/creatives" \
  -H 'Content-Type: application/json' \
  -d "{
    \"client_id\": \"$CLIENT_ID\",
    \"title\": \"Banner Meta T7/2026\",
    \"description\": \"Creative chờ client duyệt trước khi publish.\",
    \"external_campaign_id\": \"camp_demo_1\",
    \"external_campaign_name\": \"Demo Summer Campaign\",
    \"version\": 2,
    \"asset_url\": \"https://example.com/demo-banner.jpg\",
    \"submitted_by\": \"am@pttads.vn\"
  }" | python3 -m json.tool
echo "OK  Login portal as approver@demo.local to approve"
