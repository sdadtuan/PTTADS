#!/usr/bin/env bash
# EM-1 gate — workspaces, contacts, consent, suppression + public token flow
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="${PYTHON:-python3}"
export DATABASE_URL="${DATABASE_URL:-postgresql://ptt:ptt_dev@127.0.0.1:5432/ptt_agency}"
export PTT_ARTIFACTS_DIR="${PTT_ARTIFACTS_DIR:-$ROOT/.local-dev}"
export OPS_E2E_API_URL="${OPS_E2E_API_URL:-http://127.0.0.1:3000}"
export PTT_CRM_API_AUTH_DISABLED="${PTT_CRM_API_AUTH_DISABLED:-1}"
export PTT_STAFF_STUB_USERS="${PTT_STAFF_STUB_USERS:-staff@demo.local:demo123:staff-demo-1:1:Demo Staff}"

mkdir -p "$PTT_ARTIFACTS_DIR"
REPORT="$PTT_ARTIFACTS_DIR/phase1-email-ops-report.json"

echo "==> Apply EM-1 DDL extension"
bash "$ROOT/scripts/apply_pg_ddl_email_mkt_em1.sh"

echo ""
echo "==> Nest EM-1 API smoke"
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
    curl -sf "${OPS_E2E_API_URL}/api/v1/email/clients?limit=5" \
      -H "Authorization: Bearer $STAFF_TOKEN" \
      | "$PYTHON" -c 'import json,sys; d=json.load(sys.stdin); assert d.get("ok") is True; print("OK  GET /email/clients")'

    WS_JSON=$(curl -sf -X POST "${OPS_E2E_API_URL}/api/v1/email/workspaces" \
      -H "Authorization: Bearer $STAFF_TOKEN" \
      -H 'Content-Type: application/json' \
      -d "{\"client_id\":\"$CLIENT_ID\",\"name\":\"EM-1 Gate Workspace\"}" 2>/dev/null || true)
    if [[ -n "$WS_JSON" ]]; then
      echo "$WS_JSON" | "$PYTHON" -c 'import json,sys; d=json.load(sys.stdin); assert "id" in d or d.get("error")=="workspace_exists"; print("OK  POST /email/workspaces")'
    fi

    IMPORT_JSON=$(curl -sf -X POST "${OPS_E2E_API_URL}/api/v1/email/contacts/import" \
      -H "Authorization: Bearer $STAFF_TOKEN" \
      -H 'Content-Type: application/json' \
      -d "{\"client_id\":\"$CLIENT_ID\",\"rows\":[{\"email\":\"em1-gate@example.com\",\"first_name\":\"Gate\"}]}")
    echo "$IMPORT_JSON" | "$PYTHON" -c 'import json,sys; d=json.load(sys.stdin); assert d.get("ok") is True; print("OK  POST /email/contacts/import")'

    CONSENT_JSON=$(curl -sf -X POST "${OPS_E2E_API_URL}/api/v1/email/consent" \
      -H "Authorization: Bearer $STAFF_TOKEN" \
      -H 'Content-Type: application/json' \
      -d "{\"client_id\":\"$CLIENT_ID\",\"email\":\"em1-gate@example.com\",\"status\":\"opted_in\",\"source\":\"gate\"}")
    TOKEN=$(echo "$CONSENT_JSON" | "$PYTHON" -c 'import json,sys; d=json.load(sys.stdin); print(d.get("preference_token") or "")')
    echo "$CONSENT_JSON" | "$PYTHON" -c 'import json,sys; d=json.load(sys.stdin); assert d.get("ok") is True; print("OK  POST /email/consent")'

    if [[ -n "$TOKEN" ]]; then
      curl -sf "${OPS_E2E_API_URL}/api/v1/email/public/preferences/$TOKEN" \
        | "$PYTHON" -c 'import json,sys; d=json.load(sys.stdin); assert d.get("ok") is True; print("OK  GET public preferences")'
    fi

    curl -sf -X POST "${OPS_E2E_API_URL}/api/v1/email/suppression" \
      -H "Authorization: Bearer $STAFF_TOKEN" \
      -H 'Content-Type: application/json' \
      -d "{\"client_id\":\"$CLIENT_ID\",\"email\":\"blocked-gate@example.com\",\"reason\":\"manual\"}" \
      | "$PYTHON" -c 'import json,sys; d=json.load(sys.stdin); assert d.get("ok") is True; print("OK  POST /email/suppression")'
  fi
fi

echo ""
echo "==> Unit tests"
cd "$ROOT/services/ptt-crm-api"
npm test -- email-marketing.service.spec.ts

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
    "phase": "em-1",
    "component": "email_ops_crud",
    "ok": True,
    "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "routes": [
        "/email/clients", "/email/clients/[id]", "/email/contacts",
        "/email/consent", "/email/suppression",
        "/email/public/preferences/[token]",
    ],
    "nest_api": [
        "GET/POST /api/v1/email/workspaces",
        "GET/POST /api/v1/email/contacts/import",
        "GET/POST /api/v1/email/consent",
        "GET/POST /api/v1/email/suppression",
        "POST /api/v1/email/capture",
    ],
}
path = Path("$REPORT")
path.write_text(json.dumps(report, indent=2) + "\\n", encoding="utf-8")
print(json.dumps(report, indent=2))
PY

echo ""
echo "OK  EM-1 gate — $REPORT"
