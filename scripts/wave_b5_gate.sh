#!/usr/bin/env bash
# Wave B5 full gate — S0–S5 DoD (env, modules, pytest parity, Nest jest)
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

export WAVE_B5_EXPECT_SERVICE_DELIVERY_NEST="${WAVE_B5_EXPECT_SERVICE_DELIVERY_NEST:-1}"
export WAVE_B5_SKIP_PYTEST="${WAVE_B5_SKIP_PYTEST:-0}"
export WAVE_B5_SKIP_JEST="${WAVE_B5_SKIP_JEST:-0}"

echo "== Wave B5 gate =="
bash "$ROOT/scripts/wave_b5_s0_gate.sh"
"$PYTHON" -m ptt_crm.wave_b5_gates
