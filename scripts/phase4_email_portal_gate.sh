#!/usr/bin/env bash
# EM-4 gate — portal email (approvals, dashboard, campaign stats)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="${PYTHON:-python3}"
export DATABASE_URL="${DATABASE_URL:-postgresql://ptt:ptt_dev@127.0.0.1:5432/ptt_agency}"
export PTT_ARTIFACTS_DIR="${PTT_ARTIFACTS_DIR:-$ROOT/.local-dev}"
export OPS_E2E_API_URL="${OPS_E2E_API_URL:-http://127.0.0.1:3000}"
export PTT_CRM_API_AUTH_DISABLED="${PTT_CRM_API_AUTH_DISABLED:-1}"
export PTT_EMAIL_PORTAL_ENABLED="${PTT_EMAIL_PORTAL_ENABLED:-1}"
export PTT_PORTAL_JWT_SECRET="${PTT_PORTAL_JWT_SECRET:-dev-portal-jwt-change-me-min-32-chars}"

mkdir -p "$PTT_ARTIFACTS_DIR"
REPORT="$PTT_ARTIFACTS_DIR/phase4-email-portal-report.json"

echo "==> Ensure EM-0..EM-3 DDL"
bash "$ROOT/scripts/apply_pg_ddl_email_mkt.sh"
bash "$ROOT/scripts/apply_pg_ddl_email_mkt_em1.sh"
bash "$ROOT/scripts/apply_pg_ddl_email_mkt_em3.sh"

CLIENT_ID=$("$PYTHON" - <<'PY'
import os, psycopg2
conn = psycopg2.connect(os.environ["DATABASE_URL"])
cur = conn.cursor()
cur.execute("SELECT id::text FROM clients ORDER BY created_at ASC LIMIT 1")
row = cur.fetchone()
cur.close()
conn.close()
print(row[0] if row else "")
PY
)
export PORTAL_DEMO_CLIENT_ID="${PORTAL_DEMO_CLIENT_ID:-$CLIENT_ID}"
export PTT_PORTAL_STUB_USERS="${PTT_PORTAL_STUB_USERS:-viewer@demo.local:demo123:${PORTAL_DEMO_CLIENT_ID}:viewer,approver@demo.local:demo123:${PORTAL_DEMO_CLIENT_ID}:approver}"

echo ""
echo "==> Nest EM-4 portal email smoke"
if [[ "${SKIP_NEST_SMOKE:-0}" == "1" ]]; then
  echo "SKIP  Nest smoke"
else
  if [[ -z "$CLIENT_ID" ]]; then
    echo "WARN  no clients row"
  else
    STAFF_TOKEN=$(curl -sf -X POST "${OPS_E2E_API_URL}/api/v1/staff/auth/login" \
      -H 'Content-Type: application/json' \
      -d '{"email":"staff@demo.local","password":"demo123"}' \
      | "$PYTHON" -c 'import json,sys; print(json.load(sys.stdin).get("access_token",""))')
    [[ -n "$STAFF_TOKEN" ]] || { echo "FAIL staff login" >&2; exit 1; }

    curl -sf -X POST "${OPS_E2E_API_URL}/api/v1/email/workspaces" \
      -H "Authorization: Bearer $STAFF_TOKEN" \
      -H 'Content-Type: application/json' \
      -d "{\"client_id\":\"$CLIENT_ID\",\"name\":\"EM-4 Portal Workspace\"}" 2>/dev/null || true

    SEG_JSON=$(curl -sf -X POST "${OPS_E2E_API_URL}/api/v1/email/segments" \
      -H "Authorization: Bearer $STAFF_TOKEN" \
      -H 'Content-Type: application/json' \
      -d "{\"client_id\":\"$CLIENT_ID\",\"name\":\"EM-4 Portal Segment\",\"definition_json\":{\"lifecycle_stage\":\"subscriber\"}}")
    SEG_ID=$(echo "$SEG_JSON" | "$PYTHON" -c 'import json,sys; print(json.load(sys.stdin).get("id",""))')

    TMPL_JSON=$(curl -sf -X POST "${OPS_E2E_API_URL}/api/v1/email/templates" \
      -H "Authorization: Bearer $STAFF_TOKEN" \
      -H 'Content-Type: application/json' \
      -d "{\"client_id\":\"$CLIENT_ID\",\"name\":\"EM-4 Portal Template\",\"subject_template\":\"Hello\",\"html_body\":\"<p>Hi</p><a href=\\\"{{unsubscribe_url}}\\\">Unsubscribe</a>\"}")
    TMPL_ID=$(echo "$TMPL_JSON" | "$PYTHON" -c 'import json,sys; print(json.load(sys.stdin).get("id",""))')

    CAMP_JSON=$(curl -sf -X POST "${OPS_E2E_API_URL}/api/v1/email/campaigns" \
      -H "Authorization: Bearer $STAFF_TOKEN" \
      -H 'Content-Type: application/json' \
      -d "{\"client_id\":\"$CLIENT_ID\",\"name\":\"EM-4 Portal Campaign\",\"template_id\":\"$TMPL_ID\",\"segment_id\":\"$SEG_ID\"}")
    CAMP_ID=$(echo "$CAMP_JSON" | "$PYTHON" -c 'import json,sys; print(json.load(sys.stdin).get("id",""))')

    curl -sf -X POST "${OPS_E2E_API_URL}/api/v1/email/contacts/import" \
      -H "Authorization: Bearer $STAFF_TOKEN" \
      -H 'Content-Type: application/json' \
      -d "{\"client_id\":\"$CLIENT_ID\",\"rows\":[{\"email\":\"em4-portal@example.com\",\"lifecycle_stage\":\"subscriber\"}]}" >/dev/null 2>&1 || true

    curl -sf -X POST "${OPS_E2E_API_URL}/api/v1/email/consent" \
      -H "Authorization: Bearer $STAFF_TOKEN" \
      -H 'Content-Type: application/json' \
      -d "{\"client_id\":\"$CLIENT_ID\",\"email\":\"em4-portal@example.com\",\"status\":\"opted_in\",\"source\":\"em4-gate\"}" >/dev/null 2>&1 || true

    curl -sf -X POST "${OPS_E2E_API_URL}/api/v1/email/segments/${SEG_ID}/compute" \
      -H "Authorization: Bearer $STAFF_TOKEN" -d '{}' >/dev/null 2>&1 || true

    curl -sf -X POST "${OPS_E2E_API_URL}/api/v1/email/campaigns/${CAMP_ID}/submit" \
      -H "Authorization: Bearer $STAFF_TOKEN" \
      -H 'Content-Type: application/json' \
      -d '{}' \
      | "$PYTHON" -c 'import json,sys; d=json.load(sys.stdin); assert d.get("status")=="pending_approval"; print("OK  staff submit campaign")'

    VIEWER_TOKEN=$(curl -sf -X POST "${OPS_E2E_API_URL}/api/v1/portal/auth/login" \
      -H 'Content-Type: application/json' \
      -d '{"email":"viewer@demo.local","password":"demo123"}' \
      | "$PYTHON" -c 'import json,sys; print(json.load(sys.stdin).get("access_token",""))')
    [[ -n "$VIEWER_TOKEN" ]] || { echo "FAIL portal viewer login" >&2; exit 1; }

    curl -sf "${OPS_E2E_API_URL}/api/v1/portal/email/dashboard" \
      -H "Authorization: Bearer $VIEWER_TOKEN" \
      | "$PYTHON" -c 'import json,sys; d=json.load(sys.stdin); assert d.get("ok") is True; print("OK  GET portal/email/dashboard")'

    curl -sf "${OPS_E2E_API_URL}/api/v1/portal/email/approvals/pending" \
      -H "Authorization: Bearer $VIEWER_TOKEN" \
      | "$PYTHON" -c 'import json,sys; d=json.load(sys.stdin); assert d.get("ok") is True; print("OK  GET portal/email/approvals/pending")'

    curl -sf "${OPS_E2E_API_URL}/api/v1/portal/email/approvals/${CAMP_ID}/preview" \
      -H "Authorization: Bearer $VIEWER_TOKEN" \
      | "$PYTHON" -c 'import json,sys; d=json.load(sys.stdin); assert d.get("ok") is True and d.get("html_body"); print("OK  GET portal approval preview")'

    APPROVER_TOKEN=$(curl -sf -X POST "${OPS_E2E_API_URL}/api/v1/portal/auth/login" \
      -H 'Content-Type: application/json' \
      -d '{"email":"approver@demo.local","password":"demo123"}' \
      | "$PYTHON" -c 'import json,sys; print(json.load(sys.stdin).get("access_token",""))')

    curl -sf -X POST "${OPS_E2E_API_URL}/api/v1/portal/email/approvals/${CAMP_ID}/approve" \
      -H "Authorization: Bearer $APPROVER_TOKEN" \
      | "$PYTHON" -c 'import json,sys; d=json.load(sys.stdin); assert d.get("campaign",{}).get("status")=="approved"; print("OK  POST portal approve")'

    curl -sf "${OPS_E2E_API_URL}/api/v1/portal/email/campaigns/${CAMP_ID}/stats" \
      -H "Authorization: Bearer $VIEWER_TOKEN" \
      | "$PYTHON" -c 'import json,sys; d=json.load(sys.stdin); assert d.get("ok") is True; print("OK  GET portal campaign stats")'

    curl -sf "${OPS_E2E_API_URL}/api/v1/portal/email/reports/summary?days=28" \
      -H "Authorization: Bearer $VIEWER_TOKEN" \
      | "$PYTHON" -c 'import json,sys; d=json.load(sys.stdin); assert d.get("ok") is True; print("OK  GET portal reports/summary")'
  fi
fi

echo ""
echo "==> Unit tests"
cd "$ROOT/services/ptt-crm-api"
npm test -- portal-email

echo ""
echo "==> portal-web build"
cd "$ROOT/services/portal-web"
if [[ ! -d node_modules ]]; then npm install; fi
npm run build

mkdir -p "$(dirname "$REPORT")"
cd "$ROOT"
"$PYTHON" - <<PY
import json
from datetime import datetime, timezone
from pathlib import Path
report = {
    "phase": "em-4",
    "component": "email_portal",
    "ok": True,
    "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "portal_routes": [
        "/email",
        "/email/approvals",
        "/email/campaigns/[id]",
    ],
    "nest_api": [
        "GET /api/v1/portal/email/dashboard",
        "GET /api/v1/portal/email/campaigns",
        "GET /api/v1/portal/email/campaigns/:id/stats",
        "GET /api/v1/portal/email/approvals/pending",
        "GET /api/v1/portal/email/approvals/:id/preview",
        "POST /api/v1/portal/email/approvals/:id/approve",
        "POST /api/v1/portal/email/approvals/:id/reject",
        "GET /api/v1/portal/email/reports/summary",
    ],
}
path = Path("$REPORT")
path.write_text(json.dumps(report, indent=2) + "\\n", encoding="utf-8")
print(json.dumps(report, indent=2))
PY

echo ""
echo "OK  EM-4 gate — $REPORT"
