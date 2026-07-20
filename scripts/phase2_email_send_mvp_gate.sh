#!/usr/bin/env bash
# EM-2 gate — segments, templates, campaigns, preflight, submit
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="${PYTHON:-python3}"
export DATABASE_URL="${DATABASE_URL:-postgresql://ptt:ptt_dev@127.0.0.1:5432/ptt_agency}"
export PTT_ARTIFACTS_DIR="${PTT_ARTIFACTS_DIR:-$ROOT/.local-dev}"
export OPS_E2E_API_URL="${OPS_E2E_API_URL:-http://127.0.0.1:3000}"
export PTT_CRM_API_AUTH_DISABLED="${PTT_CRM_API_AUTH_DISABLED:-1}"
export PTT_STAFF_STUB_USERS="${PTT_STAFF_STUB_USERS:-staff@demo.local:demo123:staff-demo-1:1:Demo Staff}"

mkdir -p "$PTT_ARTIFACTS_DIR"
REPORT="$PTT_ARTIFACTS_DIR/phase2-email-send-mvp-report.json"

echo "==> Ensure EM-0 + EM-1 DDL"
bash "$ROOT/scripts/apply_pg_ddl_email_mkt.sh"
bash "$ROOT/scripts/apply_pg_ddl_email_mkt_em1.sh"

echo ""
echo "==> Nest EM-2 API smoke"
if [[ "${SKIP_NEST_SMOKE:-0}" == "1" ]]; then
  echo "SKIP  Nest smoke"
else
  STAFF_TOKEN=$(curl -sf -X POST "${OPS_E2E_API_URL}/api/v1/staff/auth/login" \
    -H 'Content-Type: application/json' \
    -d '{"email":"staff@demo.local","password":"demo123"}' \
    | "$PYTHON" -c 'import json,sys; print(json.load(sys.stdin).get("access_token",""))')
  [[ -n "$STAFF_TOKEN" ]] || { echo "FAIL staff login" >&2; exit 1; }

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
  if [[ -z "$CLIENT_ID" ]]; then
    echo "WARN  no clients row — seed agency client first"
  else
    curl -sf -X POST "${OPS_E2E_API_URL}/api/v1/email/workspaces" \
      -H "Authorization: Bearer $STAFF_TOKEN" \
      -H 'Content-Type: application/json' \
      -d "{\"client_id\":\"$CLIENT_ID\",\"name\":\"EM-2 Gate Workspace\"}" 2>/dev/null || true

    curl -sf -X POST "${OPS_E2E_API_URL}/api/v1/email/contacts/import" \
      -H "Authorization: Bearer $STAFF_TOKEN" \
      -H 'Content-Type: application/json' \
      -d "{\"client_id\":\"$CLIENT_ID\",\"rows\":[{\"email\":\"em2-gate@example.com\",\"first_name\":\"Gate\",\"lifecycle_stage\":\"subscriber\"}]}" \
      | "$PYTHON" -c 'import json,sys; d=json.load(sys.stdin); assert d.get("ok") is True; print("OK  import contact")'

    curl -sf -X POST "${OPS_E2E_API_URL}/api/v1/email/consent" \
      -H "Authorization: Bearer $STAFF_TOKEN" \
      -H 'Content-Type: application/json' \
      -d "{\"client_id\":\"$CLIENT_ID\",\"email\":\"em2-gate@example.com\",\"status\":\"opted_in\",\"source\":\"em2-gate\"}" \
      | "$PYTHON" -c 'import json,sys; d=json.load(sys.stdin); assert d.get("ok") is True; print("OK  consent opted_in")'

    SEG_JSON=$(curl -sf -X POST "${OPS_E2E_API_URL}/api/v1/email/segments" \
      -H "Authorization: Bearer $STAFF_TOKEN" \
      -H 'Content-Type: application/json' \
      -d "{\"client_id\":\"$CLIENT_ID\",\"name\":\"EM-2 Gate Segment\",\"definition_json\":{\"lifecycle_stage\":\"subscriber\"}}")
    SEG_ID=$(echo "$SEG_JSON" | "$PYTHON" -c 'import json,sys; d=json.load(sys.stdin); print(d.get("id",""))')
    echo "$SEG_JSON" | "$PYTHON" -c 'import json,sys; d=json.load(sys.stdin); assert d.get("id"); print("OK  POST /email/segments")'

    COMPUTE_JSON=$(curl -sf -X POST "${OPS_E2E_API_URL}/api/v1/email/segments/${SEG_ID}/compute" \
      -H "Authorization: Bearer $STAFF_TOKEN" \
      -H 'Content-Type: application/json' \
      -d '{}')
    echo "$COMPUTE_JSON" | "$PYTHON" -c 'import json,sys; d=json.load(sys.stdin); assert d.get("ok") is True; assert d.get("member_count",0) >= 1; print("OK  POST /email/segments/:id/compute")'

    TMPL_JSON=$(curl -sf -X POST "${OPS_E2E_API_URL}/api/v1/email/templates" \
      -H "Authorization: Bearer $STAFF_TOKEN" \
      -H 'Content-Type: application/json' \
      -d "{\"client_id\":\"$CLIENT_ID\",\"name\":\"EM-2 Gate Template\",\"subject_template\":\"Hello\",\"html_body\":\"<p>Hi</p><a href=\\\"{{unsubscribe_url}}\\\">Unsubscribe</a>\"}")
    TMPL_ID=$(echo "$TMPL_JSON" | "$PYTHON" -c 'import json,sys; d=json.load(sys.stdin); print(d.get("id",""))')
    echo "$TMPL_JSON" | "$PYTHON" -c 'import json,sys; d=json.load(sys.stdin); assert d.get("id"); print("OK  POST /email/templates")'

    curl -sf -X POST "${OPS_E2E_API_URL}/api/v1/email/templates/${TMPL_ID}/preflight" \
      -H "Authorization: Bearer $STAFF_TOKEN" \
      -H 'Content-Type: application/json' \
      -d '{}' \
      | "$PYTHON" -c 'import json,sys; d=json.load(sys.stdin); assert d.get("passed") is True; print("OK  template preflight")'

    CAMP_JSON=$(curl -sf -X POST "${OPS_E2E_API_URL}/api/v1/email/campaigns" \
      -H "Authorization: Bearer $STAFF_TOKEN" \
      -H 'Content-Type: application/json' \
      -d "{\"client_id\":\"$CLIENT_ID\",\"name\":\"EM-2 Gate Campaign\",\"template_id\":\"$TMPL_ID\",\"segment_id\":\"$SEG_ID\"}")
    CAMP_ID=$(echo "$CAMP_JSON" | "$PYTHON" -c 'import json,sys; d=json.load(sys.stdin); print(d.get("id",""))')
    echo "$CAMP_JSON" | "$PYTHON" -c 'import json,sys; d=json.load(sys.stdin); assert d.get("id"); print("OK  POST /email/campaigns")'

    curl -sf -X POST "${OPS_E2E_API_URL}/api/v1/email/campaigns/${CAMP_ID}/preflight" \
      -H "Authorization: Bearer $STAFF_TOKEN" \
      -H 'Content-Type: application/json' \
      -d '{}' \
      | "$PYTHON" -c 'import json,sys; d=json.load(sys.stdin); assert d.get("passed") is True; print("OK  campaign preflight")'

    SUBMIT_JSON=$(curl -sf -X POST "${OPS_E2E_API_URL}/api/v1/email/campaigns/${CAMP_ID}/submit" \
      -H "Authorization: Bearer $STAFF_TOKEN" \
      -H 'Content-Type: application/json' \
      -d '{}')
    echo "$SUBMIT_JSON" | "$PYTHON" -c 'import json,sys; d=json.load(sys.stdin); assert d.get("status")=="pending_approval"; print("OK  POST /email/campaigns/:id/submit")'
  fi
fi

echo ""
echo "==> Unit tests"
cd "$ROOT/services/ptt-crm-api"
npm test -- email-marketing

echo ""
echo "==> ops-web build"
cd "$ROOT/services/ops-web"
if [[ ! -d node_modules ]]; then npm install; fi
npm run build

cd "$ROOT"
mkdir -p "$(dirname "$REPORT")"
"$PYTHON" - <<PY
import json
from datetime import datetime, timezone
from pathlib import Path
report = {
    "phase": "em-2",
    "component": "email_send_mvp",
    "ok": True,
    "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "routes": [
        "/email/segments",
        "/email/templates", "/email/templates/[id]",
        "/email/campaigns", "/email/campaigns/[id]", "/email/campaigns/[id]/review",
    ],
    "nest_api": [
        "GET/POST /api/v1/email/segments",
        "POST /api/v1/email/segments/:id/compute",
        "GET/POST/PATCH /api/v1/email/templates",
        "POST /api/v1/email/templates/:id/preflight",
        "GET/POST /api/v1/email/campaigns",
        "POST /api/v1/email/campaigns/:id/preflight",
        "POST /api/v1/email/campaigns/:id/submit",
    ],
}
path = Path("$REPORT")
path.write_text(json.dumps(report, indent=2) + "\\n", encoding="utf-8")
print(json.dumps(report, indent=2))
PY

echo ""
echo "OK  EM-2 gate — $REPORT"
