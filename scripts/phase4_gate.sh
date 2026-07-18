#!/usr/bin/env bash
# Phase 4 gate pack — F1 campaign writes, F2 workflow, F3 Flask guard, F4 ClickHouse
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
export PTT_META_CAMPAIGN_WRITE_STUB="${PTT_META_CAMPAIGN_WRITE_STUB:-1}"
export PTT_CRM_API_AUTH_DISABLED="${PTT_CRM_API_AUTH_DISABLED:-1}"
export PHASE4_PILOT_CLIENT_ID="${PHASE4_PILOT_CLIENT_ID:-550e8400-e29b-41d4-a716-446655440000}"
export PHASE4_PILOT_CAMPAIGN_ID="${PHASE4_PILOT_CAMPAIGN_ID:-120210123456789}"
cd "$ROOT"

NEST_PID=""
cleanup() {
  if [[ -n "${NEST_PID}" ]] && kill -0 "${NEST_PID}" 2>/dev/null; then
    kill "${NEST_PID}" 2>/dev/null || true
    wait "${NEST_PID}" 2>/dev/null || true
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

echo "==> Postgres + DDL v5"
if command -v docker >/dev/null 2>&1; then
  docker compose up -d postgres 2>/dev/null || true
fi
./scripts/apply_pg_ddl_v3.sh 2>/dev/null || true
./scripts/apply_pg_ddl_v3_events_idempotency.sh 2>/dev/null || true
./scripts/apply_pg_ddl_v5_campaign_writes.sh

if ! _wait_http "${PTT_API_URL}/health" 3; then
  echo "==> Start Nest CRM API (background)"
  "$ROOT/scripts/local_crm_api_up.sh" &
  NEST_PID=$!
  _wait_http "${PTT_API_URL}/health" 45 || echo "WARN Nest not ready — nest API gate may fail"
fi

echo "==> Phase 4 gate pack"
"$PYTHON" -m ptt_crm.phase4_gates
