#!/usr/bin/env bash
# Phase 3 Temporal gate — docker stack + worker + live workflow execution
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="${PYTHON:-python3}"
if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PYTHON="$ROOT/.venv/bin/python"
fi
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
export PTT_ARTIFACTS_DIR="${PTT_ARTIFACTS_DIR:-$ROOT/.local-dev}"
export DATABASE_URL="${DATABASE_URL:-postgresql://ptt:ptt_dev@127.0.0.1:5432/ptt_agency}"
export PTT_TEMPORAL_ADDRESS="${PTT_TEMPORAL_ADDRESS:-127.0.0.1:7233}"
export PTT_TEMPORAL_NAMESPACE="${PTT_TEMPORAL_NAMESPACE:-default}"
export PTT_TEMPORAL_TASK_QUEUE="${PTT_TEMPORAL_TASK_QUEUE:-ptt-agency}"
export TEMPORAL_GATE_CLIENT_ID="${TEMPORAL_GATE_CLIENT_ID:-550e8400-e29b-41d4-a716-446655440000}"
export PTT_API_URL="${PTT_API_URL:-http://127.0.0.1:3000}"
export PTT_CRM_API_AUTH_DISABLED="${PTT_CRM_API_AUTH_DISABLED:-1}"
cd "$ROOT"

WORKER_PID=""
cleanup() {
  if [[ -n "${WORKER_PID}" ]] && kill -0 "${WORKER_PID}" 2>/dev/null; then
    kill "${WORKER_PID}" 2>/dev/null || true
    wait "${WORKER_PID}" 2>/dev/null || true
  fi
}
trap cleanup EXIT

echo "==> Temporal deps"
if ! "$PYTHON" -c "import temporalio" 2>/dev/null; then
  "$PYTHON" -m pip install -r requirements-temporal.txt
fi

echo "==> Temporal server (docker)"
if command -v docker >/dev/null 2>&1; then
  docker compose -f docker-compose.temporal.yml up -d
  echo "    Waiting for Temporal :7233..."
  for _ in $(seq 1 45); do
    if "$PYTHON" -c "
import asyncio
from temporalio.client import Client
async def main():
    await Client.connect('127.0.0.1:7233', namespace='default')
asyncio.run(main())
print('ok')
" 2>/dev/null | grep -q ok; then
      break
    fi
    sleep 2
  done
else
  echo "WARN docker not found — assume Temporal already running on $PTT_TEMPORAL_ADDRESS"
fi

echo "==> PG DDL (launch QA + creatives)"
./scripts/apply_pg_ddl_v3_launch_qa.sh 2>/dev/null || true
./scripts/apply_pg_ddl_v3_creatives.sh 2>/dev/null || true

echo "==> Seed gate client onboarding checklist"
"$PYTHON" scripts/seed_temporal_gate_data.py

echo "==> Start Temporal worker (background)"
"$ROOT/scripts/local_temporal_worker.sh" &
WORKER_PID=$!
for _ in $(seq 1 20); do
  if kill -0 "${WORKER_PID}" 2>/dev/null; then
    sleep 1
  else
    echo "FAIL Temporal worker exited early — check docker logs ptt-temporal" >&2
    exit 1
  fi
done

SKIP_LIVE=""
if [[ "${1:-}" == "--unit-only" ]]; then
  SKIP_LIVE="--no-live"
fi

echo "==> Temporal gate pack"
"$PYTHON" -m ptt_crm.phase3_temporal_gates $SKIP_LIVE
