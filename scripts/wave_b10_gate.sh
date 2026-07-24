#!/usr/bin/env bash
# Wave B10 gate — Meta Enterprise Intelligence
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

export WAVE_B10_SKIP_BUILD="${WAVE_B10_SKIP_BUILD:-0}"
export WAVE_B10_SKIP_JEST="${WAVE_B10_SKIP_JEST:-0}"
export WAVE_B10_SKIP_B9_GATE="${WAVE_B10_SKIP_B9_GATE:-0}"
export WAVE_B10_SKIP_PG="${WAVE_B10_SKIP_PG:-1}"
export WAVE_B10_SKIP_E2E="${WAVE_B10_SKIP_E2E:-1}"

echo "== Wave B10 gate =="
"$PYTHON" -m ptt_crm.wave_b10_gates
