#!/usr/bin/env bash
# Run automated Phase 3 + Phase 4 closure gates (local or CI)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="${PYTHON:-python3}"
if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PYTHON="$ROOT/.venv/bin/python"
fi
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
export PTT_ARTIFACTS_DIR="${PTT_ARTIFACTS_DIR:-$ROOT/.local-dev}"
export DATABASE_URL="${DATABASE_URL:-postgresql://ptt:ptt_dev@127.0.0.1:5432/ptt_agency}"
export PTT_API_URL="${PTT_API_URL:-http://127.0.0.1:3000}"
export PORTAL_E2E_URL="${PORTAL_E2E_URL:-http://127.0.0.1:3100}"
export PORTAL_E2E_API_URL="${PORTAL_E2E_API_URL:-http://127.0.0.1:3000}"
export PTT_PORTAL_JWT_SECRET="${PTT_PORTAL_JWT_SECRET:-dev-portal-jwt-change-me-min-32-chars}"
export PTT_CRM_API_AUTH_DISABLED="${PTT_CRM_API_AUTH_DISABLED:-1}"
export PTT_META_CAMPAIGN_WRITE_STUB="${PTT_META_CAMPAIGN_WRITE_STUB:-1}"
# Local gate default — override in prod/staging env files
export PTT_TOKEN_VAULT_KEY="${PTT_TOKEN_VAULT_KEY:-test-vault-key-for-unit-tests-only}"
cd "$ROOT"

SKIP_PLAYWRIGHT="${SKIP_PLAYWRIGHT:-0}"
SKIP_CUTOVER="${SKIP_CUTOVER:-0}"

PORTAL_PID=""
NEST_PID=""
cleanup() {
  if [[ -n "${PORTAL_PID}" ]] && kill -0 "${PORTAL_PID}" 2>/dev/null; then
    kill "${PORTAL_PID}" 2>/dev/null || true
  fi
  if [[ -n "${NEST_PID}" ]] && kill -0 "${NEST_PID}" 2>/dev/null; then
    kill "${NEST_PID}" 2>/dev/null || true
  fi
}
trap cleanup EXIT

_wait_http() {
  local url="$1" tries="${2:-30}"
  for _ in $(seq 1 "$tries"); do
    if curl -sf "$url" >/dev/null 2>&1; then return 0; fi
    sleep 2
  done
  return 1
}

_ensure_stack() {
  if command -v docker >/dev/null 2>&1; then
    docker compose up -d postgres 2>/dev/null || true
  fi
  if ! _wait_http "${PTT_API_URL}/health" 3; then
    echo "==> Start Nest CRM API (background)"
    "$ROOT/scripts/local_crm_api_up.sh" &
    NEST_PID=$!
    _wait_http "${PTT_API_URL}/health" 45 || echo "WARN Nest not ready" >&2
  fi
  if [[ "$SKIP_PLAYWRIGHT" != "1" ]] && ! _wait_http "${PORTAL_E2E_URL}/login" 3; then
    echo "==> Start portal-web (background)"
    PORTAL_PORT="${PORTAL_PORT:-3100}" "$ROOT/scripts/local_portal_up.sh" &
    PORTAL_PID=$!
    _wait_http "${PORTAL_E2E_URL}/login" 60 || echo "WARN Portal not ready — Playwright may fail" >&2
  fi
}

_ensure_stack

echo "========================================"
echo " PTT Phase 3 + 4 automated closure"
echo " Artifacts: $PTT_ARTIFACTS_DIR"
echo "========================================"

echo ""
echo "==> [1/5] Phase 3 track + QA gates"
./scripts/phase3_qa_gate.sh

if [[ "$SKIP_PLAYWRIGHT" != "1" ]]; then
  echo ""
  echo "==> [2/5] Phase 3 Playwright E2E (portal + Meta tab)"
  ./scripts/phase3_playwright_e2e_gate.sh
else
  echo ""
  echo "==> [2/5] Skip Playwright (SKIP_PLAYWRIGHT=1)"
fi

echo ""
echo "==> [3/5] Phase 4 gate pack"
./scripts/phase4_gate.sh

if [[ "$SKIP_CUTOVER" != "1" ]]; then
  echo ""
  echo "==> [4/5] Phase 3 prod cutover dry-run"
  export APPLY=0
  export PTT_CUTOVER_SKIP_URL_CHECK=1
  export PTT_CUTOVER_ENV="${PTT_CUTOVER_ENV:-local}"
  export PORTAL_PILOT_PASSWORD="${PORTAL_PILOT_PASSWORD:-local-cutover-pilot-demo123!}"
  export PTT_PORTAL_JWT_SECRET="${PTT_PORTAL_JWT_SECRET:-local-cutover-dry-run-jwt-secret-32chars-min!!}"
  export PTT_SQLITE_PATH="${PTT_SQLITE_PATH:-$ROOT/ptt.db}"
  ./scripts/close_phase3_prod_cutover.sh || {
    echo "WARN Phase 3 cutover dry-run failed — see preflight JSON" >&2
  }

  echo ""
  echo "==> [5/5] Phase 4 prod cutover dry-run"
  export PTT_CUTOVER_SKIP_PILOT=1
  ./scripts/close_phase4_prod_cutover.sh || {
    echo "WARN Phase 4 cutover dry-run failed — see preflight JSON" >&2
  }
else
  echo ""
  echo "==> [4-5/5] Skip cutover dry-runs (SKIP_CUTOVER=1)"
fi

echo ""
echo "==> Closure summary"
"$PYTHON" - <<'PY'
import json
from pathlib import Path

root = Path(".local-dev")
files = [
    ("Phase 3 QA", "phase3-qa-gate-report.json"),
    ("Phase 3 UAT", "phase3-uat-signoff.json"),
    ("Phase 4", "phase4-gate-report.json"),
    ("Phase 3 cutover", "phase3-prod-cutover-preflight.json"),
    ("Phase 4 cutover", "phase4-prod-cutover-preflight.json"),
]
for label, name in files:
    p = root / name
    if not p.is_file():
        print(f"  {label}: MISSING {name}")
        continue
    data = json.loads(p.read_text())
    ok = data.get("ok")
    if ok is None and name == "phase3-uat-signoff.json":
        ok = data.get("automated_qa_ok")
    summary = data.get("summary") or {}
    extra = ""
    if summary:
        extra = f" ({summary.get('passed', '?')}/{summary.get('total', '?')})"
    print(f"  {label}: {'PASS' if ok else 'FAIL'}{extra}")
PY

echo ""
echo "Manual prod checklist (not automated):"
echo "  - docs/runbooks/phase3-uat-signoff.md"
echo "  - docs/runbooks/vps-phase3-portal-cutover-checklist.md"
echo "  - docs/runbooks/phase4-prod-cutover-checklist.md"
echo "  - docs/runbooks/vps-production-operations.md"
