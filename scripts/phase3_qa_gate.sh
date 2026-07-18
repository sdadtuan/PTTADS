#!/usr/bin/env bash
# Phase 3 QA gate — refresh track gates + regression + UAT sign-off template
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
export PTT_PORTAL_JWT_SECRET="${PTT_PORTAL_JWT_SECRET:-dev-portal-jwt-change-me-min-32-chars}"
export PTT_CRM_API_AUTH_DISABLED="${PTT_CRM_API_AUTH_DISABLED:-1}"
export PTT_TOKEN_VAULT_KEY="${PTT_TOKEN_VAULT_KEY:-test-vault-key-for-unit-tests-only}"
cd "$ROOT"

REFRESH=1
if [[ "${1:-}" == "--no-refresh" ]]; then
  REFRESH=0
fi

NEST_PID=""
cleanup() {
  if [[ -n "${NEST_PID}" ]] && kill -0 "${NEST_PID}" 2>/dev/null; then
    kill "${NEST_PID}" 2>/dev/null || true
    wait "${NEST_PID}" 2>/dev/null || true
  fi
}
trap cleanup EXIT

_wait_http() {
  local url="$1" tries="${2:-45}"
  for _ in $(seq 1 "$tries"); do
    if curl -sf "$url" >/dev/null 2>&1; then
      return 0
    fi
    sleep 2
  done
  return 1
}

_ensure_nest() {
  if _wait_http "${PTT_API_URL}/health" 3; then
    echo "OK  Nest already up at ${PTT_API_URL}"
    return 0
  fi
  echo "==> Start Nest CRM API (background)"
  "$ROOT/scripts/local_crm_api_up.sh" &
  NEST_PID=$!
  if _wait_http "${PTT_API_URL}/health" 45; then
    echo "OK  Nest ready"
    return 0
  fi
  echo "WARN Nest not ready — portal/temporal gates may fail" >&2
  return 1
}

if [[ "$REFRESH" -eq 1 ]]; then
  echo "==> Refresh Phase 3 track gates"
  if command -v docker >/dev/null 2>&1; then
    docker compose up -d postgres 2>/dev/null || true
  fi
  _ensure_nest || true

  ./scripts/phase3_portal_mvp_gate.sh --skip-build
  ./scripts/phase3_google_gate.sh
  ./scripts/phase3_hub_migration_gate.sh
  ./scripts/phase3_temporal_gate.sh
else
  echo "==> Skip track refresh (--no-refresh) — aggregate existing reports"
fi

echo "==> Phase 3 QA gate pack (regression + sign-off)"
"$PYTHON" -m ptt_crm.phase3_qa_gates
