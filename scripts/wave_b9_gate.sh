#!/usr/bin/env bash
# Wave B9 gate — Meta Enterprise Conversion OS / tracking
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
PYTHON="${PYTHON:-python3}"
if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PYTHON="$ROOT/.venv/bin/python"
fi
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
export PTT_ARTIFACTS_DIR="${PTT_ARTIFACTS_DIR:-$ROOT/.local-dev}"

if [[ -f "$ROOT/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT/.env"
  set +a
fi

export WAVE_B9_SKIP_PG="${WAVE_B9_SKIP_PG:-0}"
export WAVE_B9_SKIP_BUILD="${WAVE_B9_SKIP_BUILD:-0}"
export WAVE_B9_SKIP_JEST="${WAVE_B9_SKIP_JEST:-0}"
export WAVE_B9_SKIP_B8_GATE="${WAVE_B9_SKIP_B8_GATE:-0}"
export WAVE_B9_SKIP_HORIZON1="${WAVE_B9_SKIP_HORIZON1:-1}"
export WAVE_B9_SKIP_E2E="${WAVE_B9_SKIP_E2E:-1}"
export WAVE_B9_SKIP_SOAK="${WAVE_B9_SKIP_SOAK:-1}"
export WAVE_B9_EXPECT_TRACKING_ENABLED="${WAVE_B9_EXPECT_TRACKING_ENABLED:-0}"

echo "== Wave B9 gate =="
"$PYTHON" -m ptt_crm.wave_b9_gates
