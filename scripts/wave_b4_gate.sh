#!/usr/bin/env bash
# Wave B4 full gate — env, workflow export, pytest parity, Nest unit tests.
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

export WAVE_B4_EXPECT_FUNNEL_NEST="${WAVE_B4_EXPECT_FUNNEL_NEST:-1}"
export WAVE_B4_EXPECT_PRESALES_ON_LEAD="${WAVE_B4_EXPECT_PRESALES_ON_LEAD:-1}"
export WAVE_B4_SKIP_PYTEST="${WAVE_B4_SKIP_PYTEST:-0}"
export WAVE_B4_SKIP_JEST="${WAVE_B4_SKIP_JEST:-0}"

"$PYTHON" -m ptt_crm.wave_b4_funnel_gates
