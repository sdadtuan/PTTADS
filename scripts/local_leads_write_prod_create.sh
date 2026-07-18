#!/usr/bin/env bash
# Smoke POST /api/v1/leads prod create (W5 Sprint 0)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BASE="${PTT_NEST_LEADS_URL:-http://127.0.0.1:3000}"
KEY="${PTT_CRM_INTERNAL_KEY:-}"
CLIENT_ID="${CLIENT_ID:-550e8400-e29b-41d4-a716-446655440000}"
HDR=(-H 'Content-Type: application/json')
if [[ -n "$KEY" ]]; then
  HDR+=(-H "X-PTT-Internal-Key: $KEY")
fi
echo "==> W5 prod create smoke → $BASE (PTT_LEADS_CREATE_ID_MODE=${PTT_LEADS_CREATE_ID_MODE:-staging})"
body="$(curl -sf "${HDR[@]}" -X POST "$BASE/api/v1/leads" -d "{
  \"full_name\": \"W5 Prod Smoke\",
  \"phone\": \"0901111222\",
  \"channel\": \"meta\",
  \"client_id\": \"$CLIENT_ID\",
  \"source\": \"api\"
}")"
echo "$body" | python3 -m json.tool
id="$(echo "$body" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")"
if [[ "$id" -ge 900000000 ]]; then
  echo "FAIL id=$id still in staging range — set PTT_LEADS_CREATE_ID_MODE=prod and apply sprint0 DDL" >&2
  exit 1
fi
echo "OK  created lead id=$id (< 900M prod allocator)"
