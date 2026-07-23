#!/usr/bin/env bash
# Wave B7 gate — client offboard (B7.1-S1)
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

export WAVE_B7_SKIP_JEST="${WAVE_B7_SKIP_JEST:-0}"
export WAVE_B7_SKIP_B6_GATE="${WAVE_B7_SKIP_B6_GATE:-0}"

echo "== Wave B7 gate =="
"$PYTHON" -m ptt_crm.wave_b7_gates
