#!/usr/bin/env bash
# EM-3 gate — journeys, deliverability, reports
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="${PYTHON:-python3}"
export DATABASE_URL="${DATABASE_URL:-postgresql://ptt:ptt_dev@127.0.0.1:5432/ptt_agency}"
export PTT_ARTIFACTS_DIR="${PTT_ARTIFACTS_DIR:-$ROOT/.local-dev}"
export OPS_E2E_API_URL="${OPS_E2E_API_URL:-http://127.0.0.1:3000}"
export PTT_CRM_API_AUTH_DISABLED="${PTT_CRM_API_AUTH_DISABLED:-1}"
export PTT_STAFF_STUB_USERS="${PTT_STAFF_STUB_USERS:-staff@demo.local:demo123:staff-demo-1:1:Demo Staff}"

mkdir -p "$PTT_ARTIFACTS_DIR"
REPORT="$PTT_ARTIFACTS_DIR/phase3-email-enterprise-report.json"

echo "==> Ensure EM-0..EM-2 DDL"
bash "$ROOT/scripts/apply_pg_ddl_email_mkt.sh"
bash "$ROOT/scripts/apply_pg_ddl_email_mkt_em1.sh"
bash "$ROOT/scripts/apply_pg_ddl_email_mkt_em3.sh"

echo ""
echo "==> Nest EM-3 API smoke"
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
    JOURNEY_JSON=$(curl -sf -X POST "${OPS_E2E_API_URL}/api/v1/email/journeys" \
      -H "Authorization: Bearer $STAFF_TOKEN" \
      -H 'Content-Type: application/json' \
      -d "{\"client_id\":\"$CLIENT_ID\",\"name\":\"EM-3 Gate Journey\"}")
    JOURNEY_ID=$(echo "$JOURNEY_JSON" | "$PYTHON" -c 'import json,sys; d=json.load(sys.stdin); print(d.get("id",""))')
    echo "$JOURNEY_JSON" | "$PYTHON" -c 'import json,sys; d=json.load(sys.stdin); assert d.get("id"); print("OK  POST /email/journeys")'

    curl -sf -X POST "${OPS_E2E_API_URL}/api/v1/email/journeys/${JOURNEY_ID}/activate" \
      -H "Authorization: Bearer $STAFF_TOKEN" \
      -H 'Content-Type: application/json' \
      -d '{}' \
      | "$PYTHON" -c 'import json,sys; d=json.load(sys.stdin); assert d.get("status")=="active"; print("OK  POST /email/journeys/:id/activate")'

    DOM_JSON=$(curl -sf -X POST "${OPS_E2E_API_URL}/api/v1/email/deliverability/domains" \
      -H "Authorization: Bearer $STAFF_TOKEN" \
      -H 'Content-Type: application/json' \
      -d "{\"client_id\":\"$CLIENT_ID\",\"domain\":\"mail.em3-gate.example.com\"}")
    DOM_ID=$(echo "$DOM_JSON" | "$PYTHON" -c 'import json,sys; d=json.load(sys.stdin); print(d.get("id",""))')
    echo "$DOM_JSON" | "$PYTHON" -c 'import json,sys; d=json.load(sys.stdin); assert d.get("id"); print("OK  POST /email/deliverability/domains")'

    curl -sf -X POST "${OPS_E2E_API_URL}/api/v1/email/deliverability/domains/${DOM_ID}/verify" \
      -H "Authorization: Bearer $STAFF_TOKEN" \
      -H 'Content-Type: application/json' \
      -d '{}' \
      | "$PYTHON" -c 'import json,sys; d=json.load(sys.stdin); assert d.get("spf_status")=="pass"; print("OK  POST verify domain")'

    curl -sf "${OPS_E2E_API_URL}/api/v1/email/reports/summary?days=28" \
      -H "Authorization: Bearer $STAFF_TOKEN" \
      | "$PYTHON" -c 'import json,sys; d=json.load(sys.stdin); assert d.get("ok") is True; print("OK  GET /email/reports/summary")'

    curl -sf "${OPS_E2E_API_URL}/api/v1/email/reports/deliverability?days=30" \
      -H "Authorization: Bearer $STAFF_TOKEN" \
      | "$PYTHON" -c 'import json,sys; d=json.load(sys.stdin); assert d.get("ok") is True; print("OK  GET /email/reports/deliverability")'
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
    "phase": "em-3",
    "component": "email_enterprise",
    "ok": True,
    "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "routes": [
        "/email/journeys", "/email/journeys/[id]",
        "/email/deliverability",
        "/email/reports",
    ],
    "nest_api": [
        "GET/POST /api/v1/email/journeys",
        "POST /api/v1/email/journeys/:id/activate",
        "GET/POST /api/v1/email/deliverability/domains",
        "POST /api/v1/email/deliverability/domains/:id/verify",
        "POST /api/v1/email/deliverability/domains/:id/pause",
        "GET /api/v1/email/reports/summary",
        "GET /api/v1/email/reports/deliverability",
        "GET /api/v1/email/reports/engagement",
    ],
}
path = Path("$REPORT")
path.write_text(json.dumps(report, indent=2) + "\\n", encoding="utf-8")
print(json.dumps(report, indent=2))
PY

echo ""
echo "OK  EM-3 gate — $REPORT"
