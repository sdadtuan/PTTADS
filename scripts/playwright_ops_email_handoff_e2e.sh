#!/usr/bin/env bash
# Playwright E2E — ops-web Email Marketing §13 handoff (Nest + ops-web, no Flask)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="${PYTHON:-python3}"
if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PYTHON="$ROOT/.venv/bin/python"
fi
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
export DATABASE_URL="${DATABASE_URL:-postgresql://ptt:ptt_dev@127.0.0.1:5432/ptt_agency}"
export OPS_E2E_URL="${OPS_E2E_URL:-http://127.0.0.1:3200}"
export OPS_E2E_API_URL="${OPS_E2E_API_URL:-http://127.0.0.1:3000}"
export OPS_E2E_SKIP_SERVER="${OPS_E2E_SKIP_SERVER:-1}"
export OPS_E2E_STAFF_EMAIL="${OPS_E2E_STAFF_EMAIL:-staff@demo.local}"
export OPS_E2E_STAFF_PASSWORD="${OPS_E2E_STAFF_PASSWORD:-demo123}"
export PTT_CRM_API_AUTH_DISABLED="${PTT_CRM_API_AUTH_DISABLED:-1}"
export PTT_STAFF_STUB_USERS="${PTT_STAFF_STUB_USERS:-staff@demo.local:demo123:staff-demo-1:1:Demo Staff}"
export OPS_EMAIL_HANDOFF_DOMAIN="${OPS_EMAIL_HANDOFF_DOMAIN:-handoff-email.example.com}"
export NEXT_PUBLIC_PTT_EMAIL_ENABLED="${NEXT_PUBLIC_PTT_EMAIL_ENABLED:-1}"
export NEXT_PUBLIC_PTT_EMAIL_GATE_A_ENABLED="${NEXT_PUBLIC_PTT_EMAIL_GATE_A_ENABLED:-1}"
export NEXT_PUBLIC_PTT_API_URL="${NEXT_PUBLIC_PTT_API_URL:-$OPS_E2E_API_URL}"
export PTT_ARTIFACTS_DIR="${PTT_ARTIFACTS_DIR:-$ROOT/.local-dev}"

_wait_http() {
  local url="$1" label="$2" tries="${3:-30}"
  for _ in $(seq 1 "$tries"); do
    if curl -sf "$url" >/dev/null 2>&1; then
      echo "OK  $label → $url"
      return 0
    fi
    sleep 2
  done
  echo "FAIL $label not reachable: $url" >&2
  return 1
}

if [[ "${OPS_EMAIL_HANDOFF_SKIP_PREFLIGHT:-0}" != "1" ]]; then
  echo "==> Preflight HTTP"
  _wait_http "${OPS_E2E_API_URL}/health" "Nest API"
  _wait_http "${OPS_E2E_URL}/login" "ops-web login"

  if command -v docker >/dev/null 2>&1; then
    docker compose up -d postgres 2>/dev/null || true
  fi
  echo "==> Apply email DDL (idempotent)"
  bash "$ROOT/scripts/apply_pg_ddl_email_mkt.sh" 2>/dev/null || true
  bash "$ROOT/scripts/apply_pg_ddl_email_mkt_em1.sh" 2>/dev/null || true

  echo "==> Seed handoff pilot workspace"
  SEED_OUT=$("$PYTHON" "$ROOT/scripts/seed_ops_email_handoff_e2e.py" --apply \
    --domain "$OPS_EMAIL_HANDOFF_DOMAIN" 2>&1)
  echo "$SEED_OUT"
  if [[ -z "${OPS_EMAIL_HANDOFF_CLIENT_ID:-}" ]]; then
    export OPS_EMAIL_HANDOFF_CLIENT_ID=$(echo "$SEED_OUT" | "$PYTHON" -c 'import json,sys
for line in sys.stdin:
    line=line.strip()
    if not line: continue
    try:
        d=json.loads(line)
        if d.get("client_id"):
            print(d["client_id"])
            break
    except json.JSONDecodeError:
        pass')
  fi
  echo "Pilot client: ${OPS_EMAIL_HANDOFF_CLIENT_ID:-unset}"
fi

echo "==> Playwright ops-web Email handoff §13"
cd "$ROOT/services/ops-web"
if [[ ! -d node_modules/@playwright/test ]]; then
  npm install
fi
if [[ ! -d ~/.cache/ms-playwright ]] && [[ ! -d node_modules/playwright/.local-browsers ]]; then
  npx playwright install chromium
fi
npm run test:e2e -- e2e/email-handoff.spec.ts

REPORT="$PTT_ARTIFACTS_DIR/email-handoff-e2e-report.json"
mkdir -p "$(dirname "$REPORT")"
"$PYTHON" - <<PY
import json
import os
from datetime import datetime, timezone
from pathlib import Path
report = {
    "ok": True,
    "component": "ops_web_email_handoff_s13",
    "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
    "playwright_spec": "services/ops-web/e2e/email-handoff.spec.ts",
    "client_id": os.environ.get("OPS_EMAIL_HANDOFF_CLIENT_ID", ""),
    "domain": os.environ.get("OPS_EMAIL_HANDOFF_DOMAIN", ""),
    "notes": "SPEC_UI_UX_EMAIL_MARKETING.md §13 — ops-web Playwright (no Flask)",
}
Path("${REPORT}").write_text(json.dumps(report, indent=2) + "\\n", encoding="utf-8")
print(json.dumps(report, indent=2))
PY

echo "OK  Email handoff Playwright E2E — $REPORT"
