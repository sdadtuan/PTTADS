#!/usr/bin/env bash
# Run PTT Temporal Python worker (Phase 3 T4)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
export DATABASE_URL="${DATABASE_URL:-postgresql://ptt:ptt_dev@127.0.0.1:5432/ptt_agency}"
export PTT_TEMPORAL_ADDRESS="${PTT_TEMPORAL_ADDRESS:-127.0.0.1:7233}"
export PTT_TEMPORAL_NAMESPACE="${PTT_TEMPORAL_NAMESPACE:-default}"
export PTT_TEMPORAL_TASK_QUEUE="${PTT_TEMPORAL_TASK_QUEUE:-ptt-agency}"

PYTHON="${PYTHON:-python3}"
if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PYTHON="$ROOT/.venv/bin/python"
fi

if ! "$PYTHON" -c "import temporalio" 2>/dev/null; then
  echo "==> Installing temporalio (requirements-temporal.txt)"
  "$PYTHON" -m pip install -r "$ROOT/requirements-temporal.txt"
fi

echo "==> Temporal worker queue=$PTT_TEMPORAL_TASK_QUEUE addr=$PTT_TEMPORAL_ADDRESS"
exec "$PYTHON" "$ROOT/ptt_temporal/worker.py"
