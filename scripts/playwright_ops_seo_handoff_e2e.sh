#!/usr/bin/env bash
# Playwright E2E — ops-web SEO/AEO §12 handoff (Nest + ops-web, no Flask)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="${PYTHON:-python3}"
if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PYTHON="$ROOT/.venv/bin/python"
fi
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
export DATABASE_URL="${DATABASE_URL:-postgresql://ptt:ptt_dev@127.0.0.1:5432/ptt_agency}"
export SEO_AEO_DB="${SEO_AEO_DB:-pg}"
export OPS_E2E_URL="${OPS_E2E_URL:-http://127.0.0.1:3200}"
export OPS_E2E_API_URL="${OPS_E2E_API_URL:-http://127.0.0.1:3000}"
export OPS_E2E_SKIP_SERVER="${OPS_E2E_SKIP_SERVER:-1}"
export OPS_E2E_STAFF_EMAIL="${OPS_E2E_STAFF_EMAIL:-staff@demo.local}"
export OPS_E2E_STAFF_PASSWORD="${OPS_E2E_STAFF_PASSWORD:-demo123}"
export PTT_CRM_API_AUTH_DISABLED="${PTT_CRM_API_AUTH_DISABLED:-1}"
export PTT_STAFF_STUB_USERS="${PTT_STAFF_STUB_USERS:-staff@demo.local:demo123:staff-demo-1:1:Demo Staff}"
export OPS_SEO_HANDOFF_CUSTOMER_ID="${OPS_SEO_HANDOFF_CUSTOMER_ID:-1}"
export OPS_SEO_HANDOFF_DOMAIN="${OPS_SEO_HANDOFF_DOMAIN:-handoff-e2e.example.com}"
export NEXT_PUBLIC_PTT_SEO_HUB_ENABLED="${NEXT_PUBLIC_PTT_SEO_HUB_ENABLED:-1}"
export NEXT_PUBLIC_PTT_SEO_GATE_A_ENABLED="${NEXT_PUBLIC_PTT_SEO_GATE_A_ENABLED:-1}"
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

if [[ "${OPS_SEO_HANDOFF_SKIP_PREFLIGHT:-0}" != "1" ]]; then
  echo "==> Preflight HTTP"
  _wait_http "${OPS_E2E_API_URL}/health" "Nest API"
  _wait_http "${OPS_E2E_URL}/login" "ops-web login"

  if command -v docker >/dev/null 2>&1; then
    docker compose up -d postgres 2>/dev/null || true
  fi
  echo "==> Seed handoff pilot client settings"
  "$PYTHON" "$ROOT/scripts/seed_ops_seo_handoff_e2e.py" --apply \
    --customer-id "$OPS_SEO_HANDOFF_CUSTOMER_ID" \
    --domain "$OPS_SEO_HANDOFF_DOMAIN"
fi

echo "==> Playwright ops-web SEO handoff §12"
cd "$ROOT/services/ops-web"
if [[ ! -d node_modules/@playwright/test ]]; then
  npm install
fi
if [[ ! -d ~/.cache/ms-playwright ]] && [[ ! -d node_modules/playwright/.local-browsers ]]; then
  npx playwright install chromium
fi
npm run test:e2e -- e2e/seo-handoff.spec.ts

REPORT="$PTT_ARTIFACTS_DIR/seo-handoff-e2e-report.json"
mkdir -p "$(dirname "$REPORT")"
"$PYTHON" - <<PY
import json
from datetime import datetime, timezone
from pathlib import Path
report = {
    "ok": True,
    "component": "ops_web_seo_handoff_s12",
    "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
    "playwright_spec": "services/ops-web/e2e/seo-handoff.spec.ts",
    "customer_id": int("${OPS_SEO_HANDOFF_CUSTOMER_ID}"),
    "domain": "${OPS_SEO_HANDOFF_DOMAIN}",
    "notes": "SPEC_UI_UX_SEO_AEO.md §12 — ops-web Playwright (no Flask)",
}
Path("${REPORT}").write_text(json.dumps(report, indent=2) + "\\n", encoding="utf-8")
print(json.dumps(report, indent=2))
PY

echo "OK  SEO handoff Playwright E2E — $REPORT"
