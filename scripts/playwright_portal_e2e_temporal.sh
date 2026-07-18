#!/usr/bin/env bash
# Playwright E2E with Temporal stack — seed creative + approve flow
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export PORTAL_E2E_URL="${PORTAL_E2E_URL:-http://127.0.0.1:3100}"
export PORTAL_E2E_API_URL="${PORTAL_E2E_API_URL:-http://127.0.0.1:3000}"
export PORTAL_E2E_SKIP_SERVER="${PORTAL_E2E_SKIP_SERVER:-1}"
export PORTAL_E2E_CLIENT_ID="${PORTAL_E2E_CLIENT_ID:-550e8400-e29b-41d4-a716-446655440000}"
export PTT_TEMPORAL_ADDRESS="${PTT_TEMPORAL_ADDRESS:-127.0.0.1:7233}"

echo "==> Temporal stack (optional — skip if already up)"
if command -v docker >/dev/null 2>&1; then
  docker compose -f "$ROOT/docker-compose.temporal.yml" up -d 2>/dev/null || true
fi

WORKER_PID=""
cleanup() {
  if [[ -n "$WORKER_PID" ]] && kill -0 "$WORKER_PID" 2>/dev/null; then
    kill "$WORKER_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT

if [[ "${PORTAL_E2E_START_WORKER:-1}" == "1" ]]; then
  echo "==> Start Temporal Python worker (background)"
  "$ROOT/scripts/local_temporal_worker.sh" &
  WORKER_PID=$!
  sleep 3
fi

echo "==> Seed pending creative (starts WF when Nest has PTT_TEMPORAL_ADDRESS)"
export PTT_API_URL="$PORTAL_E2E_API_URL"
"$ROOT/scripts/seed_portal_e2e_creative.sh" || true

echo "==> Playwright E2E"
"$ROOT/scripts/playwright_portal_e2e.sh"
