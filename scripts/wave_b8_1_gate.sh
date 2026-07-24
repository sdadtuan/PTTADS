#!/usr/bin/env bash
# Wave B8.1 — Meta Enterprise breakdown + RBAC gates
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="${ROOT}${PYTHONPATH:+:$PYTHONPATH}"
export WAVE_B8_SKIP_PG="${WAVE_B8_SKIP_PG:-1}"
export WAVE_B8_SKIP_BUILD="${WAVE_B8_SKIP_BUILD:-1}"
export WAVE_B8_SKIP_JEST="${WAVE_B8_SKIP_JEST:-1}"
export WAVE_B8_SKIP_E2E="${WAVE_B8_SKIP_E2E:-1}"
export WAVE_B8_SKIP_B7_GATE="${WAVE_B8_SKIP_B7_GATE:-1}"
export WAVE_B8_SKIP_HORIZON1="${WAVE_B8_SKIP_HORIZON1:-1}"
python3 -m ptt_crm.wave_b81_gates
