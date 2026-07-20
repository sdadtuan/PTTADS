#!/usr/bin/env bash
# Phase 4 kickoff gate — ops-web /seo/hub batch B1 + Nest seo-admin API
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="${PYTHON:-python3}"
export DATABASE_URL="${DATABASE_URL:-postgresql://ptt:ptt_dev@127.0.0.1:5432/ptt_agency}"
export PTT_ARTIFACTS_DIR="${PTT_ARTIFACTS_DIR:-$ROOT/.local-dev}"
export OPS_E2E_API_URL="${OPS_E2E_API_URL:-http://127.0.0.1:3000}"
export PTT_CRM_API_AUTH_DISABLED="${PTT_CRM_API_AUTH_DISABLED:-1}"
export PTT_STAFF_STUB_USERS="${PTT_STAFF_STUB_USERS:-staff@demo.local:demo123:staff-demo-1:1:Demo Staff}"

mkdir -p "$PTT_ARTIFACTS_DIR"
REPORT="$PTT_ARTIFACTS_DIR/phase4-seo-hub-kickoff-report.json"

echo "==> Nest seo-admin API smoke"
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

HUB_JSON=$(curl -sf "${OPS_E2E_API_URL}/api/v1/seo/hub?days=28" \
  -H "Authorization: Bearer $STAFF_TOKEN")
echo "$HUB_JSON" | "$PYTHON" -c '
import json,sys
d=json.load(sys.stdin)
assert d.get("ok") is True, d
assert "summary" in d and "clients" in d
print("OK  GET /api/v1/seo/hub")
'

CLIENTS_JSON=$(curl -sf "${OPS_E2E_API_URL}/api/v1/seo/clients" \
  -H "Authorization: Bearer $STAFF_TOKEN")
echo "$CLIENTS_JSON" | "$PYTHON" -c '
import json,sys
d=json.load(sys.stdin)
assert d.get("ok") is True, d
print("OK  GET /api/v1/seo/clients")
'

fi

echo ""
echo "==> ops-web build (seo routes)"
cd "$ROOT/services/ops-web"
if [[ ! -d node_modules ]]; then npm install; fi
npm run build

"$PYTHON" - <<PY
import json
from datetime import datetime, timezone
from pathlib import Path
report = {
    "phase": "4-kickoff",
    "component": "seo_hub_b1",
    "ok": True,
    "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "routes": ["/seo/hub", "/seo/clients"],
    "nest_api": ["/api/v1/seo/hub", "/api/v1/seo/clients"],
    "notes": "Batch B1 hub + clients — research screen next",
}
path = Path("$REPORT")
path.parent.mkdir(parents=True, exist_ok=True)
path.write_text(json.dumps(report, indent=2) + "\\n", encoding="utf-8")
print(json.dumps(report, indent=2))
PY

echo ""
echo "OK  Phase 4 SEO hub kickoff gate — $REPORT"
