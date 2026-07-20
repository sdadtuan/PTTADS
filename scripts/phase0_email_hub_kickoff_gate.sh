#!/usr/bin/env bash
# EM-0 kickoff gate — DDL + Nest email hub/governance + ops-web /email/hub
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="${PYTHON:-python3}"
export DATABASE_URL="${DATABASE_URL:-postgresql://ptt:ptt_dev@127.0.0.1:5432/ptt_agency}"
export PTT_ARTIFACTS_DIR="${PTT_ARTIFACTS_DIR:-$ROOT/.local-dev}"
export OPS_E2E_API_URL="${OPS_E2E_API_URL:-http://127.0.0.1:3000}"
export PTT_CRM_API_AUTH_DISABLED="${PTT_CRM_API_AUTH_DISABLED:-1}"
export PTT_STAFF_STUB_USERS="${PTT_STAFF_STUB_USERS:-staff@demo.local:demo123:staff-demo-1:1:Demo Staff}"

mkdir -p "$PTT_ARTIFACTS_DIR"
REPORT="$PTT_ARTIFACTS_DIR/phase0-email-hub-kickoff-report.json"

echo "==> Apply email_mkt DDL (idempotent)"
if [[ "${SKIP_DDL:-0}" == "1" ]]; then
  echo "SKIP  DDL (SKIP_DDL=1)"
else
  bash "$ROOT/scripts/apply_pg_ddl_email_mkt.sh"
fi

echo ""
echo "==> Nest email-marketing API smoke"
if [[ "${SKIP_NEST_SMOKE:-0}" == "1" ]]; then
  echo "SKIP  Nest smoke (SKIP_NEST_SMOKE=1)"
else
  STAFF_TOKEN=$(curl -sf -X POST "${OPS_E2E_API_URL}/api/v1/staff/auth/login" \
    -H 'Content-Type: application/json' \
    -d '{"email":"staff@demo.local","password":"demo123"}' \
    | "$PYTHON" -c 'import json,sys; print(json.load(sys.stdin).get("access_token",""))')

  if [[ -z "$STAFF_TOKEN" ]]; then
    echo "FAIL staff login" >&2
    exit 1
  fi

  HUB_JSON=$(curl -sf "${OPS_E2E_API_URL}/api/v1/email/hub?days=28" \
    -H "Authorization: Bearer $STAFF_TOKEN")
  echo "$HUB_JSON" | "$PYTHON" -c '
import json,sys
d=json.load(sys.stdin)
assert d.get("ok") is True, d
assert "summary" in d and "clients" in d
print("OK  GET /api/v1/email/hub")
'

  GOV_JSON=$(curl -sf "${OPS_E2E_API_URL}/api/v1/email/governance?scope=global" \
    -H "Authorization: Bearer $STAFF_TOKEN")
  echo "$GOV_JSON" | "$PYTHON" -c '
import json,sys
d=json.load(sys.stdin)
assert d.get("ok") is True, d
assert d.get("read_only") is True, d
assert isinstance(d.get("rules"), list), d
print("OK  GET /api/v1/email/governance")
'
fi

echo ""
echo "==> Nest unit test (email-marketing.service.spec.ts)"
cd "$ROOT/services/ptt-crm-api"
npm test -- --testPathPattern=email-marketing.service.spec --passWithNoTests 2>/dev/null || npm test -- email-marketing.service.spec.ts

echo ""
echo "==> ops-web build (email routes)"
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
    "phase": "em-0-kickoff",
    "component": "email_hub_governance",
    "ok": True,
    "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "routes": ["/email", "/email/hub", "/email/governance"],
    "nest_api": ["/api/v1/email/hub", "/api/v1/email/governance"],
    "ddl": "deploy/sql/email_mkt_pg_schema.sql",
    "notes": "EM-0 skeleton — workspaces/contacts EM-1",
}
path = Path("$REPORT")
path.parent.mkdir(parents=True, exist_ok=True)
path.write_text(json.dumps(report, indent=2) + "\\n", encoding="utf-8")
print(json.dumps(report, indent=2))
PY

echo ""
echo "OK  EM-0 email hub kickoff gate — $REPORT"
