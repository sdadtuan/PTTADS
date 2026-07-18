#!/usr/bin/env bash
# Start Temporal server + UI (Phase 3 T1)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
echo "==> Temporal stack (server :7233, UI http://127.0.0.1:8088)"
docker compose -f docker-compose.temporal.yml up -d
echo "OK  Wait ~30s for temporal ready, then: ./scripts/local_temporal_worker.sh"
