#!/usr/bin/env bash
# Smoke POST/PATCH /api/v1/leads write (Phase 1b B9 — staging only)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BASE="${PTT_NEST_LEADS_URL:-http://127.0.0.1:3000}"

export PTT_LEADS_WRITE_ENABLED=1
export PTT_LEADS_READ_SOURCE=pg
export DATABASE_URL="${DATABASE_URL:-postgresql://ptt:ptt_dev@127.0.0.1:5432/ptt_agency}"
export PTT_CRM_API_AUTH_DISABLED="${PTT_CRM_API_AUTH_DISABLED:-1}"

if ! curl -sf "$BASE/health" >/dev/null 2>&1; then
  echo "FAIL Nest not running — ./scripts/local_crm_api_up.sh (with PTT_LEADS_WRITE_ENABLED=1)"
  exit 1
fi

echo "==> POST /api/v1/leads (staging stub)"
CREATE=$(curl -sf -X POST "$BASE/api/v1/leads" \
  -H 'Content-Type: application/json' \
  -d '{"full_name":"CLI Staging Lead","phone":"0905555555","channel":"meta","source":"staging"}')
echo "$CREATE" | head -c 300
echo ""
LEAD_ID=$(echo "$CREATE" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
echo "lead_id=$LEAD_ID"

echo "==> PATCH assign lead_id=$LEAD_ID"
curl -sf -X PATCH "$BASE/api/v1/leads/$LEAD_ID" \
  -H 'Content-Type: application/json' \
  -d '{"owner_id":1,"assigned_by":"cli-smoke"}' | head -c 200
echo "..."

echo "OK  write staging smoke passed"
