#!/usr/bin/env bash
# Start Temporal docker + Python worker (dev convenience)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
"$ROOT/scripts/local_temporal_up.sh"
echo "==> Starting worker in foreground (Ctrl+C to stop)"
exec "$ROOT/scripts/local_temporal_worker.sh"
