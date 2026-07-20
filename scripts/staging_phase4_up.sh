#!/usr/bin/env bash
# Start Staging Phase 4 stack — Phase 3 base + Temporal worker + Flask readonly
#
# Usage:
#   set -a && source deploy/env.staging-phase4.example && set +a
#   ./scripts/staging_phase4_up.sh
#
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

export PTT_FLASK_MONOLITH_MODE="${PTT_FLASK_MONOLITH_MODE:-readonly}"
export PTT_META_CAMPAIGN_WRITE_STUB="${PTT_META_CAMPAIGN_WRITE_STUB:-1}"

echo "==> Phase 4 staging stack (Nest + Temporal worker + Flask readonly hint)"
echo "    Flask: PTT_FLASK_MONOLITH_MODE=$PTT_FLASK_MONOLITH_MODE"
echo "    Run Flask in another terminal: flask run --port 5050"
echo ""

if command -v docker >/dev/null 2>&1; then
  docker compose -f docker-compose.temporal.yml up -d 2>/dev/null || true
fi

"$ROOT/scripts/local_temporal_worker.sh" &
WORKER_PID=$!
trap 'kill $WORKER_PID 2>/dev/null || true' EXIT

exec "$ROOT/scripts/staging_phase3_up.sh" --nest-only
