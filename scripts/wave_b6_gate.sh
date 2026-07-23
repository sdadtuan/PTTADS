#!/usr/bin/env bash
# Wave B6 gate — Launch QA + Creative brief on service lifecycle
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

export WAVE_B6_SKIP_JEST="${WAVE_B6_SKIP_JEST:-0}"
export WAVE_B6_SKIP_B5_GATE="${WAVE_B6_SKIP_B5_GATE:-0}"
export WAVE_B6_EXPECT_LAUNCH_QA_AUTO_START="${WAVE_B6_EXPECT_LAUNCH_QA_AUTO_START:-0}"

echo "== Wave B6 gate =="
"$PYTHON" -m ptt_crm.wave_b6_gates
