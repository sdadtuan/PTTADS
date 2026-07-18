#!/usr/bin/env bash
# LeadAssigned outbox → RMQ E2E (Phase 2 P1)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
PYTHON="${PYTHON:-python3}"
if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PYTHON="$ROOT/.venv/bin/python"
fi

exec "$PYTHON" "$ROOT/scripts/lead_assigned_rmq_e2e.py" "$@"
